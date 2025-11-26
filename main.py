from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from string import Template

from dotenv import load_dotenv

from utils.logger import setup_logger
from utils.scheduler import run_loop
from core.login import LoginManager
from core.comments import CommentFetcher
from core.ai_engine import classify_comment
from core.actions import ActionExecutor
from core.report import Reporter
from core.pages import PageSelector
from core.token_manager import TokenManager
from db.database import Database


def load_config(path: str | Path) -> dict:
    load_dotenv()
    cfg_path = Path(path)
    if not cfg_path.exists():
        raise FileNotFoundError(f"Config not found at {cfg_path}")
    raw = cfg_path.read_text(encoding="utf-8")
    # allow ${VAR} substitution from env
    rendered = Template(raw).safe_substitute(**os.environ)
    data = json.loads(rendered)
    return data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI Fanpage Agent")
    parser.add_argument("--config", default="config.json", help="Path to config.json")
    parser.add_argument("--demo", action="store_true", help="Force demo mode")
    parser.add_argument("--cycles", type=int, default=1, help="Number of cycles to run")
    parser.add_argument(
        "--interval",
        type=int,
        default=0,
        help="Seconds to sleep between cycles (0 = use config interval)",
    )
    return parser.parse_args()


def build_services(cfg: dict):
    logger = setup_logger(cfg.get("log_level", "INFO"))
    login_mgr = LoginManager(
        Path(cfg.get("cookie_path", "cookies.json")),
        logger,
        headless=cfg.get("headless", False),
    )

    # Khởi tạo TokenManager
    config_path = Path(cfg.get("config_path", "config.json"))
    token_manager = TokenManager(config_path, logger, config_dict=cfg)

    db_path = cfg.get("database_path", "db/agent.db")
    db = Database(db_path)
    processed_ids = db.processed_comment_ids()

    # Truyền token_manager vào các service
    fetcher = CommentFetcher(
        cfg, logger, processed_ids=processed_ids, token_manager=token_manager
    )
    executor = ActionExecutor(cfg, logger, token_manager=token_manager)
    reporter = Reporter(db)
    page_selector = PageSelector(
        logger, config_path=config_path, token_manager=token_manager
    )

    return (
        logger,
        login_mgr,
        fetcher,
        executor,
        reporter,
        db,
        page_selector,
        token_manager,
    )


def run_cycle(cfg: dict, services) -> None:
    logger, _, fetcher, executor, reporter, _, _, token_manager = services

    try:
        comments = fetcher.fetch_new(limit=cfg.get("max_actions_per_cycle", 20))
    except Exception as exc:
        logger.error(
            "❌ Lỗi khi fetch comments:\n"
            "   Error: %s\n"
            "   → Có thể token đã hết hạn, đang thử refresh...",
            exc,
        )
        # Thử refresh token và retry
        token = token_manager.get_valid_token(force_refresh=True)
        if token:
            logger.info("✅ Token đã được refresh, thử lại...")
            try:
                comments = fetcher.fetch_new(limit=cfg.get("max_actions_per_cycle", 20))
            except Exception as retry_exc:
                logger.error("❌ Vẫn lỗi sau khi refresh token: %s", retry_exc)
                return
        else:
            logger.error("❌ Không thể refresh token. Bỏ qua cycle này.")
            return

    if not comments:
        logger.info("No new comments.")
        return

    logger.info("Found %d comment(s).", len(comments))
    actions_done = 0
    for comment in comments:
        decision = classify_comment(comment, cfg, logger)
        logger.info(
            "%s -> %s (%.2f) | actions %s",
            comment.message,
            decision.intent.value,
            decision.confidence,
            [a.value for a in decision.actions],
        )

        try:
            details = executor.execute(comment, decision)
            for detail in details:
                reporter.record(comment, decision, detail)
                fetcher.mark_processed(comment.id)
                actions_done += 1
                if actions_done >= cfg.get("max_actions_per_cycle", 20):
                    logger.warning("Reached action cap for this cycle.")
                    return
        except Exception as exc:
            logger.error(
                "❌ Lỗi khi execute action cho comment %s:\n"
                "   Error: %s\n"
                "   → Bỏ qua comment này và tiếp tục",
                comment.id,
                exc,
            )
            continue


def main() -> None:
    args = parse_args()
    cfg = load_config(args.config)
    if args.demo:
        cfg["demo"] = True
    interval = args.interval or cfg.get("interval_seconds", 90)
    cfg["config_path"] = args.config

    logger, login_mgr, fetcher, executor, reporter, db, page_selector, token_manager = (
        build_services(cfg)
    )
    services = (
        logger,
        login_mgr,
        fetcher,
        executor,
        reporter,
        db,
        page_selector,
        token_manager,
    )

    if cfg.get("demo", False):
        logger.info("Demo mode: skip real login and page selection.")
    else:
        login_ok = login_mgr.login()
        if not login_ok:
            logger.error(
                "Login failed. Please ensure cookies.json is valid or log in once to refresh cookies."
            )
            return

        try:
            # Cập nhật browser context cho token_manager
            token_manager.context = login_mgr.context
            fetcher.context = login_mgr.context
            executor.context = login_mgr.context

            # Validate token trước khi bắt đầu
            logger.info("🔐 Đang kiểm tra Facebook access token...")
            token = token_manager.get_valid_token()
            if token:
                logger.info("✅ Token hợp lệ, sẵn sàng hoạt động")
                # Hiển thị thông tin token
                token_info = token_manager.get_token_info()
                if token_info.get("expires_at"):
                    logger.info("⏰ Token expires at: %s", token_info["expires_at"])
                else:
                    logger.info(
                        "ℹ️  Token không có thời gian hết hạn (Page token hoặc long-lived)"
                    )
            else:
                logger.error(
                    "\n" + "=" * 60 + "\n"
                    "❌ KHÔNG THỂ LẤY TOKEN HỢP LỆ\n"
                    "=" * 60 + "\n"
                    "Agent không thể khởi động vì thiếu Facebook access token.\n\n"
                    "Vui lòng xem log ở trên để biết chi tiết lỗi.\n"
                    "📖 Hướng dẫn: TOKEN_REFRESH_GUIDE.md\n" + "=" * 60
                )
                return

            working_page = page_selector.select_page(cfg, context=login_mgr.context)
            logger.info("Working fanpage: %s", working_page)
        except Exception as exc:
            logger.error("Fanpage selection failed: %s", exc)
            return

    if not cfg.get("graph_access_token") or "{" in cfg.get("graph_access_token", ""):
        logger.warning(
            "graph_access_token missing or placeholder; Graph API will fail. Set it via env/.env."
        )
    if not cfg.get("page_id") or "{" in cfg.get("page_id", ""):
        logger.warning("page_id missing or placeholder; set PAGE_ID env or config.")

    def task():
        run_cycle(cfg, services)

    try:
        run_loop(task, interval_seconds=interval, cycles=args.cycles)
        report = reporter.flush_daily()
        total = report.get("summary", {}).get("total", 0) if report else 0
        logger.info("Saved daily summary to SQLite (%d records).", total)
    except KeyboardInterrupt:
        logger.warning("Interrupted by user.")
    finally:
        login_mgr.close()
        db.close()


if __name__ == "__main__":
    # Check if running with command line arguments
    if len(sys.argv) > 1:
        # If arguments provided, run agent directly (CLI mode)
        main()
    else:
        # Otherwise show modern PyQt6 UI (Postman-style)
        try:
            from ui.main_window import run as modern_ui_run

            modern_ui_run()
        except ImportError as e:
            print(f"\n❌ Lỗi: Không thể khởi động UI. Vui lòng cài đặt PyQt6:")
            print(f"   pip install PyQt6\n")
            print(f"Chi tiết lỗi: {e}\n")
        except Exception as e:
            print(f"\n❌ Lỗi không mong đợi: {e}\n")
