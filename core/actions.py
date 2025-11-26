from __future__ import annotations

import logging
from typing import List, Optional

import requests
from playwright.sync_api import BrowserContext

from .ai_engine import ActionType, Decision
from .comments import Comment
from .inbox import InboxService
from .post import PostService
from .token_manager import TokenManager


class ActionExecutor:
    def __init__(
        self,
        settings: dict,
        logger: logging.Logger,
        context: Optional[BrowserContext] = None,
        token_manager: Optional[TokenManager] = None,
    ) -> None:
        self.settings = settings
        self.logger = logger.getChild("actions")
        self.inbox = InboxService(logger=self.logger)
        self.post_service = PostService(logger=self.logger)
        self.context = context
        self.graph_version = settings.get("graph_version", "v17.0")
        self.token_manager = token_manager

    def execute(self, comment: Comment, decision: Decision) -> List[str]:
        details: List[str] = []
        for action in decision.actions:
            if action == ActionType.HIDE:
                details.append(self.hide_comment(comment))
            elif action == ActionType.REPLY and decision.reply_text:
                details.append(self.reply_comment(comment, decision.reply_text))
            elif action == ActionType.OPEN_INBOX:
                msg = decision.reply_text or "Chào bạn, mình hỗ trợ nhé?"
                details.append(self.inbox_message(comment, msg))
        return details

    # ---------- Graph API helpers ----------
    def _graph_reply(self, comment: Comment, text: str) -> str:
        # Lấy token hợp lệ từ TokenManager
        if self.token_manager:
            token = self.token_manager.get_valid_token()
        else:
            token = self.settings.get("graph_access_token")

        if not token:
            return "missing graph_access_token"
        url = f"https://graph.facebook.com/{self.graph_version}/{comment.id}/comments"
        # Add is_hidden=false to ensure reply is publicly visible
        resp = requests.post(
            url,
            params={
                "access_token": token,
                "message": text,
                "is_hidden": "false",  # Force public visibility
            },
        )
        if resp.ok:
            reply_id = resp.json().get("id")
            self.logger.info("Reply posted with ID: %s", reply_id)
            return "graph reply ok"
        return f"graph reply failed: {resp.status_code} {resp.text}"

    def _graph_hide(self, comment: Comment) -> str:
        # Lấy token hợp lệ từ TokenManager
        if self.token_manager:
            token = self.token_manager.get_valid_token()
        else:
            token = self.settings.get("graph_access_token")

        if not token:
            return "missing graph_access_token"
        url = f"https://graph.facebook.com/{self.graph_version}/{comment.id}"
        resp = requests.post(url, params={"access_token": token, "is_hidden": "true"})
        if resp.ok:
            return "graph hide ok"
        return f"graph hide failed: {resp.status_code} {resp.text}"

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
        if self.settings.get("demo", True):
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
        if self.settings.get("demo", True):
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
            comment.author, text, demo=self.settings.get("demo", True)
        )

    def create_post(self, caption: str) -> str:
        return self.post_service.create(caption, demo=self.settings.get("demo", True))
