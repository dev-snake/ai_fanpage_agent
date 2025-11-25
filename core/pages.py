from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

import requests
from playwright.sync_api import BrowserContext


class PageSelector:
    def __init__(self, logger: logging.Logger, config_path: Optional[Path] = None) -> None:
        self.logger = logger.getChild("pages")
        self.config_path = config_path

    def list_pages_graph(self, token: str) -> List[Dict[str, str]]:
        url = "https://graph.facebook.com/v17.0/me/accounts"
        resp = requests.get(url, params={"access_token": token})
        if not resp.ok:
            raise RuntimeError(f"Graph API failed: {resp.status_code} {resp.text}")
        data = resp.json().get("data", [])
        return [{"id": p["id"], "name": p["name"]} for p in data]

    def list_pages_playwright(self, context: Optional[BrowserContext]) -> List[Dict[str, str]]:
        if context is None:
            return []
        page = context.new_page()
        page.goto("https://www.facebook.com/pages/?category=your_pages", wait_until="domcontentloaded")
        page.wait_for_timeout(1000)
        items = page.query_selector_all("a[href*='/pages/'] div[role='heading']")
        pages: List[Dict[str, str]] = []
        for item in items:
            name = item.inner_text().strip()
            link = item.evaluate("el => el.closest('a')?.href")  # type: ignore
            if not name or not link:
                continue
            # crude extract page id from URL
            if "/pages/" in link:
                parts = link.split("/")
                candidates = [p for p in parts if p.isdigit()]
                pid = candidates[0] if candidates else link
            else:
                pid = link
            pages.append({"id": pid, "name": name})
        page.close()
        return pages

    def _persist_page_id(self, cfg: dict, page_id: str) -> None:
        if not self.config_path:
            return
        try:
            cfg["page_id"] = page_id
            Path(self.config_path).write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
            self.logger.info("Saved selected page_id to %s", self.config_path)
        except Exception as exc:
            self.logger.warning("Could not persist page_id: %s", exc)

    def list_pages(self, cfg: dict, context: Optional[BrowserContext]) -> List[Dict[str, str]]:
        token = cfg.get("graph_access_token") or ""
        if token:
            try:
                return self.list_pages_graph(token)
            except Exception as exc:
                self.logger.warning("Graph API listing failed: %s", exc)
        demo = cfg.get("demo", False)
        if demo:
            return [
                {"id": "PAGE_1", "name": "Shop My Pham ABC"},
                {"id": "PAGE_2", "name": "Phu Kien Dien Thoai"},
                {"id": "PAGE_3", "name": "Page Ban Giay"},
            ]
        pages = self.list_pages_playwright(context)
        return pages

    def select_page(self, cfg: dict, context: Optional[BrowserContext] = None) -> str:
        """
        Resolve working page_id. Priority:
        1) Use page_id in config if valid.
        2) List pages (Graph API preferred, else Playwright, else demo) and prompt selection.
        """
        page_id = cfg.get("page_id")
        if page_id and page_id not in {"", "YOUR_PAGE_ID", "DEMO_PAGE"}:
            self.logger.info("Using configured page_id: %s", page_id)
            return page_id

        pages = self.list_pages(cfg, context)
        if not pages:
            raise RuntimeError("No fanpage found. Set page_id in config.json or provide Graph token / Playwright context.")

        if cfg.get("demo", False):
            chosen = pages[0]
            self.logger.info("Auto-selected demo page: %s (%s)", chosen["name"], chosen["id"])
        else:
            self.logger.info("Select fanpage to work on:")
            for idx, p in enumerate(pages, start=1):
                print(f"{idx}. {p['name']} ({p['id']})")
            choice = input("Nhap so thu tu (Enter=1): ").strip()
            try:
                choice_idx = int(choice) - 1 if choice else 0
            except ValueError:
                choice_idx = 0
            choice_idx = max(0, min(choice_idx, len(pages) - 1))
            chosen = pages[choice_idx]
        cfg["page_id"] = chosen["id"]
        self.logger.info("Selected page: %s (%s)", chosen["name"], chosen["id"])
        self._persist_page_id(cfg, chosen["id"])
        return chosen["id"]
