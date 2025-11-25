"""
Simple Streamlit dashboard to view daily report and action logs.

Usage:
    streamlit run ui/dashboard.py
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import streamlit as st


REPORT_DIR = Path("reports")
ACTION_LOG = Path("data/actions.json")


def load_latest_report() -> Dict:
    reports = sorted(REPORT_DIR.glob("daily-*.json"))
    if not reports:
        return {}
    latest = reports[-1]
    data = json.loads(latest.read_text(encoding="utf-8"))
    data["_path"] = str(latest)
    return data


def load_actions() -> List[Dict]:
    if not ACTION_LOG.exists():
        return []
    try:
        return json.loads(ACTION_LOG.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def main() -> None:
    st.set_page_config(page_title="AI Fanpage Agent", layout="wide")
    st.title("AI Fanpage Agent Dashboard")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Daily Report (latest)")
        report = load_latest_report()
        if not report:
            st.info("Chưa có báo cáo. Hãy chạy agent trước.")
        else:
            st.caption(f"File: {report.get('_path')}")
            st.json(report.get("summary", {}))
            records = report.get("records", [])
            if records:
                st.dataframe(records, use_container_width=True, hide_index=True)

    with col2:
        st.subheader("Action Log (data/actions.json)")
        actions = load_actions()
        if not actions:
            st.info("Chưa có log hành động.")
        else:
            st.dataframe(actions, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown(
        "- Chạy agent: `python main.py --cycles 0` (0 hoặc bỏ tham số để chạy liên tục)\n"
        "- Mở dashboard: `streamlit run ui/dashboard.py`\n"
        "- Báo cáo lưu ở `reports/daily-YYYY-MM-DD.json`, log hành động ở `data/actions.json`."
    )


if __name__ == "__main__":
    main()
