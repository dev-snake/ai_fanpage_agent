"""
Console dashboard for sellers: show numbers and quick reports.

Usage:
    python ui/dashboard.py
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from db.database import Database


DEFAULT_DB_PATH = Path("db/agent.db")


def _db_path() -> Path:
    cfg = Path("config.json")
    if cfg.exists():
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
            return Path(data.get("database_path", DEFAULT_DB_PATH))
        except Exception:
            pass
    return DEFAULT_DB_PATH


# ---------- Data loaders ----------
def load_latest_report() -> Dict:
    with Database(_db_path()) as db:
        return db.daily_report()


def load_actions(limit: int | None = None) -> List[Dict]:
    with Database(_db_path()) as db:
        return db.actions(limit=limit)


# ---------- Helpers ----------
def parse_timestamp(ts: str) -> datetime | None:
    try:
        if ts.endswith("Z"):
            ts = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def compute_kpis(report: Dict) -> Dict[str, int]:
    records = report.get("records", [])
    summary = report.get("summary", {})
    total = summary.get("total", len(records))
    interest = summary.get("intent_interest", 0)
    spam = summary.get("intent_spam", 0)
    missing_phone = summary.get("intent_missing_phone", 0)
    inbox_done = summary.get("action_open_inbox", 0)
    replied = summary.get("action_reply", 0)
    response_rate = int(round((replied / total) * 100)) if total else 0
    return {
        "total": total,
        "interest": interest,
        "spam": spam,
        "missing_phone": missing_phone,
        "inbox": inbox_done,
        "response_rate": response_rate,
        "replied": replied,
    }


def print_kpis(kpis: Dict[str, int]) -> None:
    """Print KPIs in a simple table format"""
    print("\n" + "─" * 68)
    print("  TONG QUAN HOM NAY")
    print("─" * 68)
    print(f"  Comment hom nay         {kpis['total']:>8}")
    print(f"  Khach quan tam          {kpis['interest']:>8}")
    print(f"  Spam                    {kpis['spam']:>8}")
    print(f"  De lai so               {kpis['missing_phone']:>8}")
    print(f"  Inbox thanh cong        {kpis['inbox']:>8}")
    print(
        f"  Ti le phan hoi AI       {kpis['response_rate']:>7}%  ({kpis['replied']} reply)"
    )
    print("─" * 68 + "\n")


def hourly_summary(records: List[Dict]) -> Dict[str, int]:
    """Group comments by hour"""
    buckets = defaultdict(int)
    for r in records:
        ts = r.get("timestamp")
        dt = parse_timestamp(ts) if ts else None
        if not dt:
            continue
        buckets[dt.replace(minute=0, second=0, microsecond=0)] += 1
    return dict(sorted(buckets.items(), key=lambda x: x[0]))


def keyword_insights(records: List[Dict], top_n: int = 8) -> List[Tuple[str, int]]:
    keywords: Counter[str] = Counter()
    for r in records:
        text_parts = [
            r.get("message", ""),
            r.get("detail", ""),
            " ".join(r.get("actions", [])),
            r.get("intent", ""),
        ]
        text = " ".join([t for t in text_parts if t])
        for token in text.lower().split():
            token = re.sub(r"[^a-z0-9_]+", "", token)
            if len(token) < 3:
                continue
            keywords[token] += 1
    if not keywords:
        keywords.update({"gia": 6, "mau": 4, "freeship": 3, "inbox": 3, "sale": 2})
    return keywords.most_common(top_n)


def print_hourly_and_keywords(records: List[Dict]) -> None:
    """Print hourly activity and keyword insights"""
    print("  LUU LUONG THEO THOI GIAN")
    print("  " + "─" * 64)

    hourly = hourly_summary(records)
    if not hourly:
        print("  Chua co du lieu comment hom nay.\n")
        return

    print("  Gio      | So luong")
    print("  " + "─" * 32)
    for hour, count in hourly.items():
        bar = "▪" * min(count, 20)
        print(f"  {hour.strftime('%H:%M')}    | {bar} {count}")

    print("\n  TU KHOA NOI BAT")
    print("  " + "─" * 32)
    keywords = keyword_insights(records)
    for kw, count in keywords:
        bar = "▪" * min((count // 2 + 1), 15)
        print(f"  {kw:<16s} {bar} {count}")
    print()


def timeline(records: List[Dict], limit: int = 12) -> List[Dict]:
    def sort_key(r: Dict) -> datetime:
        dt = parse_timestamp(r.get("timestamp", "")) or datetime.min
        return dt

    data = sorted(records, key=sort_key, reverse=True)
    return data[:limit]


def print_timeline(records: List[Dict]) -> None:
    """Print recent activity timeline"""
    print("  DONG THOI GIAN XU LY (12 muc gan nhat)")
    print("  " + "─" * 64)

    if not records:
        print("  Chua co luong xu ly nao.\n")
        return

    for r in timeline(records):
        ts = r.get("timestamp")
        ts_display = parse_timestamp(ts).strftime("%H:%M") if ts else "--:--"
        comment_text = r.get("message") or guess_message(r.get("intent", ""))
        intent = r.get("intent", "unknown")
        actions = ", ".join(r.get("actions", [])) or "n/a"
        detail = r.get("detail", "") or "no detail"

        print(f"\n  [{ts_display}] {comment_text[:50]}")
        print(f"    AI Phan tich: {intent}")
        print(f"    Hanh dong: {actions}")
        print(f"    Chi tiet: {detail[:60]}")
    print()


def guess_message(intent: str) -> str:
    intent = intent or ""
    if intent == "ask_price":
        return "Hoi gia san pham?"
    if intent == "interest":
        return "Khach quan tam, can tu van."
    if intent == "missing_phone":
        return "Khach de nghi inbox / de lai so."
    if intent == "spam":
        return "Link la spam, can an."
    return "Binh luan moi tu khach."


def print_summary_report(report: Dict) -> None:
    """Print report summary"""
    if not report:
        print("\n  Chua co bao cao nao.\n")
        return

    print("\n  BAO CAO / LOG")
    print("  " + "─" * 64)
    print(f"  Ngay: {report.get('date', 'N/A')} (nguon: SQLite)")

    summary = report.get("summary", {})
    if summary:
        print("\n  Tom tat:")
        for key, value in summary.items():
            print(f"    {key:<28s} {value}")
    print()


def main() -> None:
    """Main entry point for console dashboard"""
    print("\n" + "═" * 68)
    print("  AI FANPAGE AGENT - DASHBOARD")
    print("═" * 68)

    report = load_latest_report()
    actions = load_actions()
    records = report.get("records", []) if report else actions
    kpis_source = report if report else {"records": actions}
    kpis = compute_kpis(kpis_source)

    # Print all sections
    print_kpis(kpis)
    print_hourly_and_keywords(records)
    print_timeline(records or actions)
    print_summary_report(report)

    print("═" * 68)
    print("  Huong dan: Chay agent voi lenh 'python main.py --cycles 0'")
    print("═" * 68 + "\n")


if __name__ == "__main__":
    main()
