from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from .ai_engine import Decision


class Reporter:
    def __init__(self, report_dir: str | Path) -> None:
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.records: List[Dict] = []

    def record(self, comment_id: str, decision: Decision, detail: str) -> None:
        self.records.append(
            {
                "comment_id": comment_id,
                "intent": decision.intent.value,
                "author": getattr(decision, "author", None),
                "actions": [a.value for a in decision.actions],
                "detail": detail,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    def summary(self) -> Dict[str, int]:
        intents = Counter(r["intent"] for r in self.records)
        actions = Counter(a for r in self.records for a in r["actions"])
        return {
            "total": len(self.records),
            **{f"intent_{k}": v for k, v in intents.items()},
            **{f"action_{k}": v for k, v in actions.items()},
        }

    def flush_daily(self) -> Path:
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        path = self.report_dir / f"daily-{date_str}.json"
        payload = {
            "date": date_str,
            "summary": self.summary(),
            "records": self.records,
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return path
