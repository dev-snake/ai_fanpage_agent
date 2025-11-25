from __future__ import annotations

import logging


class InboxService:
    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger.getChild("inbox")

    def send_message(self, user_name: str, text: str, demo: bool = True) -> str:
        if demo:
            self.logger.info("[demo] Inbox to %s: %s", user_name, text)
            return "demo inbox"
        self.logger.warning("Inbox send not implemented for live mode.")
        return "not implemented"
