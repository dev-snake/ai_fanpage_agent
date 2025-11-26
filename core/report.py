from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from db.database import Database
from .ai_engine import Decision
from .comments import Comment


class Reporter:
    """Persist realtime actions into SQLite and provide daily summary snapshots."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def record(
        self, comment: Comment, decision: Decision, detail: str, reply_text: str = ""
    ) -> None:
        """Write a single action row into the realtime data layer."""
        self.db.record_action(
            comment_id=comment.id,
            post_id=comment.post_id,
            author=comment.author,
            avatar_url=comment.avatar_url,
            message=comment.message,
            intent=decision.intent.value,
            actions=[a.value for a in decision.actions],
            detail=detail,
            reply_text=reply_text,
            timestamp=comment.created_at or datetime.utcnow(),
        )

    def flush_daily(self) -> Dict[str, List | Dict]:
        """Aggregate today's activity and store summary in SQLite."""
        return self.db.save_daily_summary()
