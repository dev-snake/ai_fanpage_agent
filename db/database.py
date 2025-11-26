from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


class Database:
    """SQLite-backed realtime data layer for actions and daily summaries."""

    def __init__(self, path: str | Path = "db/agent.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False, timeout=30)
        self.conn.row_factory = sqlite3.Row
        try:
            self._init_schema()
        except sqlite3.OperationalError as exc:
            if "syntax error" in str(exc).lower():
                self._repair_actions_table()
                self._init_schema()
            else:
                raise
        self._maybe_migrate_json()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        self.close()

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass

    def _init_schema(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                comment_id TEXT,
                post_id TEXT,
                author TEXT,
                avatar_url TEXT,
                message TEXT,
                intent TEXT,
                actions TEXT,
                detail TEXT,
                reply_text TEXT
            )
        """
        )
        self._ensure_created_at_column()
        self._ensure_reply_text_column()
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_actions_comment_id ON actions(comment_id)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_actions_created_at ON actions(created_at)"
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                date TEXT PRIMARY KEY,
                summary TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """
        )
        self.conn.commit()

    def _ensure_created_at_column(self) -> None:
        """Handle legacy DB where column was named `timestamp`."""
        try:
            cols = {
                row["name"]
                for row in self.conn.execute("PRAGMA table_info(actions)").fetchall()
            }
            if "created_at" in cols:
                return
            if "timestamp" in cols:
                self.conn.execute("ALTER TABLE actions ADD COLUMN created_at TEXT")
                self.conn.execute(
                    "UPDATE actions SET created_at = timestamp WHERE created_at IS NULL"
                )
                self.conn.commit()
                self.conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_actions_created_at ON actions(created_at)"
                )
                self.conn.commit()
        except Exception:
            # Best-effort; continue with whatever schema exists.
            pass

    def _ensure_reply_text_column(self) -> None:
        """Add reply_text column if not exists."""
        try:
            cols = {
                row["name"]
                for row in self.conn.execute("PRAGMA table_info(actions)").fetchall()
            }
            if "reply_text" not in cols:
                self.conn.execute("ALTER TABLE actions ADD COLUMN reply_text TEXT")
                self.conn.commit()
        except Exception:
            pass

    def _repair_actions_table(self) -> None:
        """Fallback: rebuild actions table if legacy schema causes syntax errors."""
        try:
            cols = {
                row["name"]
                for row in self.conn.execute("PRAGMA table_info(actions)").fetchall()
            }
        except Exception:
            cols = set()

        try:
            self.conn.execute("DROP INDEX IF EXISTS idx_actions_comment_id")
            self.conn.execute("DROP INDEX IF EXISTS idx_actions_created_at")
        except Exception:
            pass

        source_time = (
            "created_at"
            if "created_at" in cols
            else ("timestamp" if "timestamp" in cols else None)
        )
        try:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS actions_rebuild (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    comment_id TEXT,
                    post_id TEXT,
                    author TEXT,
                    avatar_url TEXT,
                    message TEXT,
                    intent TEXT,
                    actions TEXT,
                    detail TEXT,
                    reply_text TEXT
                )
            """
            )
            if cols:
                time_expr = source_time if source_time else "datetime('now')"
                select_cols = [
                    f"COALESCE({time_expr}, datetime('now')) as created_at",
                    "comment_id" if "comment_id" in cols else "NULL",
                    "post_id" if "post_id" in cols else "NULL",
                    "author" if "author" in cols else "NULL",
                    "avatar_url" if "avatar_url" in cols else "NULL",
                    "message" if "message" in cols else "NULL",
                    "intent" if "intent" in cols else "NULL",
                    "actions" if "actions" in cols else "'[]'",
                    "detail" if "detail" in cols else "NULL",
                    "reply_text" if "reply_text" in cols else "NULL",
                ]
                copy_sql = f"""
                    INSERT INTO actions_rebuild (
                        created_at, comment_id, post_id, author, avatar_url, message, intent, actions, detail, reply_text
                    )
                    SELECT {', '.join(select_cols)} FROM actions
                """
                try:
                    self.conn.execute(copy_sql)
                except Exception:
                    pass
            self.conn.execute("DROP TABLE IF EXISTS actions")
            self.conn.execute("ALTER TABLE actions_rebuild RENAME TO actions")
            self.conn.commit()
        except Exception:
            # As a last resort, drop and recreate empty table.
            self.conn.execute("DROP TABLE IF EXISTS actions")
            self.conn.commit()

    def _maybe_migrate_json(self) -> None:
        legacy_path = Path("data/actions.json")
        if not legacy_path.exists():
            return
        try:
            existing = self.conn.execute("SELECT COUNT(*) AS c FROM actions").fetchone()
            if existing and existing["c"]:
                return
            data = json.loads(legacy_path.read_text(encoding="utf-8"))
        except Exception:
            return

        if not isinstance(data, list):
            return

        for item in data:
            if not isinstance(item, dict):
                continue
            comment_id = item.get("comment_id")
            if not comment_id:
                continue
            try:
                ts = item.get("timestamp")
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else None
            except Exception:
                dt = None
            try:
                self.record_action(
                    comment_id=comment_id,
                    post_id=item.get("post_id"),
                    author=item.get("author", ""),
                    avatar_url=item.get("avatar_url"),
                    message=item.get("message", ""),
                    intent=item.get("intent", ""),
                    actions=item.get("actions", []),
                    detail=item.get("detail", ""),
                    timestamp=dt,
                )
            except Exception:
                continue

    def record_action(
        self,
        *,
        comment_id: str,
        post_id: str | None,
        author: str,
        avatar_url: str | None,
        message: str,
        intent: str,
        actions: Sequence[str],
        detail: str,
        reply_text: str = "",
        timestamp: datetime | None = None,
    ) -> None:
        ts = (timestamp or datetime.utcnow()).isoformat()
        actions_json = json.dumps(list(actions or []), ensure_ascii=False)
        self.conn.execute(
            """
            INSERT INTO actions (
                created_at, comment_id, post_id, author, avatar_url,
                message, intent, actions, detail, reply_text
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                ts,
                comment_id,
                post_id,
                author,
                avatar_url,
                message,
                intent,
                actions_json,
                detail,
                reply_text,
            ),
        )
        self.conn.commit()

    def processed_comment_ids(self) -> set[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT comment_id FROM actions WHERE comment_id IS NOT NULL"
        ).fetchall()
        return {row["comment_id"] for row in rows if row["comment_id"]}

    def _row_to_action(self, row: sqlite3.Row) -> Dict[str, Any]:
        action_list: List[str] = []
        try:
            action_list = json.loads(row["actions"] or "[]")
        except json.JSONDecodeError:
            action_list = []

        # Handle reply_text column (may not exist in old DB)
        reply_text = ""
        try:
            reply_text = row["reply_text"] or ""
        except Exception:
            pass

        return {
            "id": row["id"],
            "timestamp": row["created_at"],
            "comment_id": row["comment_id"],
            "post_id": row["post_id"],
            "author": row["author"],
            "avatar_url": row["avatar_url"],
            "message": row["message"],
            "intent": row["intent"],
            "actions": action_list,
            "detail": row["detail"],
            "reply_text": reply_text,
        }

    def _day_clause(self, day: Optional[str | date]) -> tuple[str, list[str]]:
        if not day:
            return "", []
        day_str = day.isoformat() if isinstance(day, date) else str(day)
        return " WHERE date(created_at) = ? ", [day_str]

    def actions(
        self,
        *,
        day: str | date | None = None,
        limit: int | None = None,
        newest_first: bool = False,
    ) -> List[Dict[str, Any]]:
        clause, params = self._day_clause(day)
        order = "DESC" if newest_first else "ASC"
        sql = f"SELECT * FROM actions {clause}ORDER BY created_at {order}"
        if limit:
            sql += " LIMIT ?"
            params.append(int(limit))
        try:
            rows = self.conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError as exc:
            if "syntax error" in str(exc).lower():
                self._repair_actions_table()
                rows = self.conn.execute(sql, params).fetchall()
            else:
                raise
        return [self._row_to_action(row) for row in rows]

    def summary(self, *, day: str | date | None = None) -> Dict[str, int]:
        records = self.actions(day=day)
        intents = Counter(r.get("intent") for r in records if r.get("intent"))
        action_types = Counter(
            act for r in records for act in r.get("actions", []) if act
        )
        return {
            "total": len(records),
            **{f"intent_{k}": v for k, v in intents.items()},
            **{f"action_{k}": v for k, v in action_types.items()},
        }

    def latest_day(self) -> str | None:
        row = self.conn.execute(
            "SELECT date(created_at) as day FROM actions ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        if row and row["day"]:
            return row["day"]
        return None

    def daily_report(self, *, day: str | date | None = None) -> Dict[str, Any]:
        target_day = (
            day.isoformat() if isinstance(day, date) else day
        ) or self.latest_day()
        if not target_day:
            return {}
        records = self.actions(day=target_day)
        return {
            "date": target_day,
            "summary": self.summary(day=target_day),
            "records": records,
        }

    def save_daily_summary(self, *, day: str | date | None = None) -> Dict[str, Any]:
        report = self.daily_report(day=day)
        if not report:
            return {}
        created_at = datetime.utcnow().isoformat()
        self.conn.execute(
            """
            INSERT OR REPLACE INTO reports (date, summary, created_at)
            VALUES (?, ?, ?)
        """,
            (
                report["date"],
                json.dumps(report["summary"], ensure_ascii=False),
                created_at,
            ),
        )
        self.conn.commit()
        return report

    def latest_summary(self) -> Dict[str, Any]:
        row = self.conn.execute(
            "SELECT summary FROM reports ORDER BY date DESC LIMIT 1"
        ).fetchone()
        if not row:
            return {}
        try:
            return json.loads(row["summary"])
        except json.JSONDecodeError:
            return {}
