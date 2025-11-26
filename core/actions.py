from __future__ import annotations

import logging
import time
from typing import List, Optional

import requests
from playwright.sync_api import BrowserContext

from .ai_engine import ActionType, Decision
from .comments import Comment
from .inbox import InboxService
from .post import PostService


class ActionExecutor:
    def __init__(
        self,
        settings: dict,
        logger: logging.Logger,
        context: Optional[BrowserContext] = None,
    ) -> None:
        self.settings = settings
        self.logger = logger.getChild("actions")
        self.inbox = InboxService(logger=self.logger)
        self.post_service = PostService(logger=self.logger)
        self.context = context
        self.graph_version = settings.get("graph_version", "v17.0")

    def execute(self, comment: Comment, decision: Decision) -> List[tuple[str, str]]:
        """Execute actions và return list of (status, reply_text) tuples"""
        results: List[tuple[str, str]] = []
        reply_text = decision.reply_text or ""

        for action in decision.actions:
            if action == ActionType.HIDE:
                status = self.hide_comment(comment)
                results.append((status, ""))
            elif action == ActionType.REPLY and reply_text:
                status = self.reply_comment(comment, reply_text)
                results.append((status, reply_text))  # Bao gồm reply text
            elif action == ActionType.OPEN_INBOX:
                msg = reply_text or "Chào bạn, mình hỗ trợ nhé?"
                status = self.inbox_message(comment, msg)
                results.append((status, msg))
        return results

    # ---------- Graph API helpers ----------
    def _graph_reply(self, comment: Comment, text: str, retry: int = 3) -> str:
        # Đọc token từ config (long-lived 60 days)
        token = self.settings.get("graph_access_token")

        if not token:
            return "missing graph_access_token"

        url = f"https://graph.facebook.com/{self.graph_version}/{comment.id}/comments"

        for attempt in range(retry):
            try:
                # Add is_hidden=false to ensure reply is publicly visible
                resp = requests.post(
                    url,
                    params={
                        "access_token": token,
                        "message": text,
                        "is_hidden": "false",  # Force public visibility
                    },
                    timeout=10,
                )
                if resp.ok:
                    reply_id = resp.json().get("id")
                    self.logger.info("Reply posted with ID: %s", reply_id)
                    return "graph reply ok"

                # Check rate limit
                error_data = resp.json().get("error", {})
                error_code = error_data.get("code")

                if error_code in {4, 17, 32, 613} and attempt < retry - 1:
                    wait_time = min(60 * (2**attempt), 300)
                    self.logger.warning(
                        "⏱️  Rate limited on reply (code %s), waiting %ds...",
                        error_code,
                        wait_time,
                    )
                    time.sleep(wait_time)
                    # Refresh token nếu cần
                    if self.token_manager:
                        token = self.token_manager.get_valid_token()
                    continue
                elif error_code == 190 and attempt < retry - 1:
                    self.logger.warning("🔄 Token expired, refreshing...")
                    if self.token_manager:
                        token = self.token_manager.get_valid_token(force_refresh=True)
                    time.sleep(2)
                    continue

                return f"graph reply failed: {resp.status_code} {resp.text}"

            except requests.Timeout:
                if attempt < retry - 1:
                    self.logger.warning("⏱️  Timeout on reply, retrying...")
                    time.sleep(5)
                    continue
                return "graph reply failed: timeout"
            except Exception as exc:
                if attempt < retry - 1:
                    time.sleep(2)
                    continue
                return f"graph reply failed: {exc}"

        return "graph reply failed: max retries exceeded"

    def _graph_hide(self, comment: Comment, retry: int = 3) -> str:
        # Đọc token từ config (long-lived 60 days)
        token = self.settings.get("graph_access_token")

        if not token:
            return "missing graph_access_token"

        url = f"https://graph.facebook.com/{self.graph_version}/{comment.id}"

        for attempt in range(retry):
            try:
                resp = requests.post(
                    url,
                    params={"access_token": token, "is_hidden": "true"},
                    timeout=10,
                )
                if resp.ok:
                    return "graph hide ok"

                # Check rate limit
                error_data = resp.json().get("error", {})
                error_code = error_data.get("code")

                if error_code in {4, 17, 32, 613} and attempt < retry - 1:
                    wait_time = min(60 * (2**attempt), 300)
                    self.logger.warning(
                        "⏱️  Rate limited on hide (code %s), waiting %ds...",
                        error_code,
                        wait_time,
                    )
                    time.sleep(wait_time)
                    if self.token_manager:
                        token = self.token_manager.get_valid_token()
                    continue
                elif error_code == 190 and attempt < retry - 1:
                    self.logger.warning("🔄 Token expired, refreshing...")
                    if self.token_manager:
                        token = self.token_manager.get_valid_token(force_refresh=True)
                    time.sleep(2)
                    continue

                return f"graph hide failed: {resp.status_code} {resp.text}"

            except requests.Timeout:
                if attempt < retry - 1:
                    self.logger.warning("⏱️  Timeout on hide, retrying...")
                    time.sleep(5)
                    continue
                return "graph hide failed: timeout"
            except Exception as exc:
                if attempt < retry - 1:
                    time.sleep(2)
                    continue
                return f"graph hide failed: {exc}"

        return "graph hide failed: max retries exceeded"

    # ---------- Playwright helpers (fallback) ----------
    def _pw_reply(self, comment: Comment, text: str) -> str:
        if not self.context or not comment.permalink:
            return "playwright reply not available"
        try:
            page = self.context.new_page()
            page.goto(comment.permalink, wait_until="domcontentloaded")
            page.wait_for_timeout(1200)
            page.fill("textarea, div[contenteditable='true']", text)
            page.keyboard.press("Enter")
            page.wait_for_timeout(800)
            page.close()
            return "playwright reply ok"
        except Exception as exc:
            return f"playwright reply failed: {exc}"

    def _pw_hide(self, comment: Comment) -> str:
        if not self.context or not comment.permalink:
            return "playwright hide not available"
        try:
            page = self.context.new_page()
            page.goto(comment.permalink, wait_until="domcontentloaded")
            page.wait_for_timeout(1200)
            menu = page.query_selector(
                "div[aria-label='More actions'], div[aria-label='Actions for this comment']"
            )
            if menu:
                menu.click()
                hide_btn = page.query_selector("text=Hide comment")
                if hide_btn:
                    hide_btn.click()
                    page.wait_for_timeout(800)
                    page.close()
                    return "playwright hide ok"
            page.close()
            return "playwright hide not found"
        except Exception as exc:
            return f"playwright hide failed: {exc}"

    def hide_comment(self, comment: Comment) -> str:
        if self.settings.get("demo", False):  # Mặc định False
            self.logger.info("[demo] Hide comment %s", comment.id)
            return "demo hide"
        if self.settings.get("graph_access_token"):
            result = self._graph_hide(comment)
            self.logger.info(result)
            return result
        result = self._pw_hide(comment)
        self.logger.info(result)
        return result

    def reply_comment(self, comment: Comment, text: str) -> str:
        if self.settings.get("demo", False):  # Mặc định False
            self.logger.info("[demo] Reply to %s: %s", comment.id, text)
            return "demo reply"
        if self.settings.get("graph_access_token"):
            result = self._graph_reply(comment, text)
            self.logger.info(result)
            return result
        result = self._pw_reply(comment, text)
        self.logger.info(result)
        return result

    def inbox_message(self, comment: Comment, text: str) -> str:
        return self.inbox.send_message(
            comment.author, text, demo=self.settings.get("demo", False)
        )

    def create_post(self, caption: str) -> str:
        return self.post_service.create(caption, demo=self.settings.get("demo", False))
