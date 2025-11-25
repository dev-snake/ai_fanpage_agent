from __future__ import annotations

import logging


class PostService:
    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger.getChild("post")

    def create(self, caption: str, demo: bool = True) -> str:
        if demo:
            self.logger.info("[demo] Post caption: %s", caption)
            return "demo post"
        self.logger.warning("Create post not implemented for live mode.")
        return "not implemented"
