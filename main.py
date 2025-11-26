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

    config_path = Path(cfg.get("config_path", "config.json"))

    db_path = cfg.get("database_path", "db/agent.db")
    db = Database(db_path)
    processed_ids = db.processed_comment_ids()

    # Không dùng TokenManager nữa - đọc token trực tiếp từ config
    fetcher = CommentFetcher(cfg, logger, processed_ids=processed_ids)
    executor = ActionExecutor(cfg, logger)
    reporter = Reporter(db)
    page_selector = PageSelector(logger, config_path=config_path)

    return (
        logger,
        login_mgr,
        fetcher,
        executor,
        reporter,
        db,
        page_selector,
    )


def run_cycle(cfg: dict, services) -> None:
    logger, _, fetcher, executor, reporter, _, _ = services

    try:
        comments = fetcher.fetch_new(limit=cfg.get("max_actions_per_cycle", 20))
    except Exception as exc:
        logger.error(
            "❌ Lỗi khi fetch comments:\n"
            "   Error: %s\n"
            "   → Token có thể hết hạn. Vui lòng cập nhật token mới trong config.",
            exc,
        )
        return

    if not comments:
        logger.info("No new comments.")
        return

    logger.info("Found %d comment(s).", len(comments))
    actions_done = 0
    for comment in comments:
        # Hiển thị thông tin chi tiết về comment
        logger.info(
            "\n" + "=" * 60 + "\n"
            "👤 Người dùng: %s\n"
            "🖼️  Avatar: %s\n"
            "💬 Nội dung: %s\n"
            "🕐 Thời gian: %s\n"
            "🔗 Link: %s\n" + "=" * 60,
            comment.author,
            comment.avatar_url or "(không có avatar)",
            (
                comment.message[:100] + "..."
                if len(comment.message) > 100
                else comment.message
            ),
            comment.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            comment.permalink or "(không có link)",
        )

        decision = classify_comment(comment, cfg, logger)
        logger.info(
            "🤖 AI phân tích: %s (confidence: %.2f) | hành động: %s",
            decision.intent.value,
            decision.confidence,
            [a.value for a in decision.actions],
        )

        try:
            results = executor.execute(comment, decision)
            for status, reply_text in results:
                reporter.record(comment, decision, status, reply_text)
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

    # Clear seen cache định kỳ để tránh memory leak (sau mỗi 10 cycles)
    if not hasattr(fetcher, "_cycle_count"):
        fetcher._cycle_count = 0
    fetcher._cycle_count += 1
    if fetcher._cycle_count >= 10:
        fetcher.clear_seen_cache()
        fetcher._cycle_count = 0
        logger.debug("🧹 Cleared seen cache after 10 cycles")


def main() -> None:
    args = parse_args()
    cfg = load_config(args.config)
    if args.demo:
        cfg["demo"] = True
    interval = args.interval or cfg.get("interval_seconds", 90)
    cfg["config_path"] = args.config

    logger, login_mgr, fetcher, executor, reporter, db, page_selector = build_services(
        cfg
    )
    services = (
        logger,
        login_mgr,
        fetcher,
        executor,
        reporter,
        db,
        page_selector,
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
            # Cập nhật browser context
            fetcher.context = login_mgr.context
            executor.context = login_mgr.context

            # Kiểm tra token có trong config không
            if not cfg.get("graph_access_token") or "{" in cfg.get(
                "graph_access_token", ""
            ):
                logger.error(
                    "\n" + "=" * 60 + "\n"
                    "❌ THIẾU FACEBOOK ACCESS TOKEN\n"
                    "=" * 60 + "\n"
                    "Vui lòng cập nhật GRAPH_ACCESS_TOKEN trong file .env\n"
                    "Hoặc trong config.json\n\n"
                    "Lấy token tại: https://developers.facebook.com/tools/explorer/\n"
                    "📝 Lưu ý: Token 60 ngày không cần refresh tự động\n" + "=" * 60
                )
                return
            else:
                logger.info("✅ Token đã được cấu hình (long-lived 60 days)")

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
