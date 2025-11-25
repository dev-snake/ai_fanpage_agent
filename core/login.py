from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

from .cookies import load_cookies


class LoginManager:
    def __init__(self, cookie_path: Path, logger: logging.Logger, headless: bool = False) -> None:
        self.cookie_path = cookie_path
        self.logger = logger.getChild("login")
        self.headless = headless
        self.play = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    def _start_browser(self) -> None:
        if self.play is None:
            self.play = sync_playwright().start()
        chromium = self.play.chromium
        self.browser = chromium.launch(headless=self.headless)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()

    def _load_cookies_into_context(self) -> None:
        cookies_path = load_cookies(self.cookie_path)
        if cookies_path and self.context:
            try:
                data = json.loads(Path(cookies_path).read_text(encoding="utf-8"))
                # Playwright expects list of dict
                if isinstance(data, dict) and "cookies" in data:
                    data = data["cookies"]
                self.context.add_cookies(data)
                self.logger.info("Loaded %d cookies from %s", len(data), cookies_path)
            except Exception as exc:
                self.logger.warning("Failed to load cookies: %s", exc)

    def _save_cookies(self) -> None:
        if not self.context:
            return
        cookies = self.context.cookies()
        payload = {"cookies": cookies}
        self.cookie_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.logger.info("Saved cookies to %s", self.cookie_path)

    def _is_logged_in(self) -> bool:
        if not self.page:
            return False
        url = self.page.url.lower()
        if "login" in url:
            return False
        return True

    def login(self) -> bool:
        """
        Login via Playwright:
        - Load cookies if present
        - Check if login is valid (newsfeed loaded)
        - If not, allow manual login then save new cookies
        """
        self._start_browser()
        self._load_cookies_into_context()

        assert self.page, "Page not initialized"
        self.page.goto("https://www.facebook.com/", wait_until="domcontentloaded")

        if self._is_logged_in():
            self.logger.info("Cookie valid, already logged in.")
            return True

        self.logger.warning("Cookie invalid/expired. Please log in manually in the opened browser.")
        self.page.wait_for_timeout(500)
        self.page.bring_to_front()
        input(">> Dang nhap Facebook trong cua so vua mo, sau do nhan Enter de tiep tuc...")

        # After manual login, re-check
        self.page.goto("https://www.facebook.com/", wait_until="domcontentloaded")
        if not self._is_logged_in():
            self.logger.error("Login still failed after manual attempt.")
            return False

        self._save_cookies()
        self.logger.info("Login successful after manual input.")
        return True

    def close(self) -> None:
        if self.browser:
            self.browser.close()
        if self.play:
            self.play.stop()
        self.browser = None
        self.context = None
        self.page = None
