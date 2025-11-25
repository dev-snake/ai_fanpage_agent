from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


class Database:
    """Lightweight JSON storage for demo mode."""

    def __init__(self, path: str | Path = "data.json") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

    def append(self, record: Dict[str, Any]) -> None:
        data: List[Dict[str, Any]] = json.loads(self.path.read_text(encoding="utf-8"))
        data.append(record)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def all(self) -> List[Dict[str, Any]]:
        return json.loads(self.path.read_text(encoding="utf-8"))
