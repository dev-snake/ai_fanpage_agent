from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

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


class Dashboard(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AI Fanpage Agent - PyQt6 Dashboard")
        self.resize(960, 640)

        self.report_label = QLabel("Report: (no data)")
        self.summary_table = QTableWidget()
        self.actions_table = QTableWidget()
        self.actions_table.setColumnCount(5)
        self.actions_table.setHorizontalHeaderLabels(
            ["comment_id", "author", "intent", "actions", "detail"]
        )
        self.actions_table.horizontalHeader().setStretchLastSection(True)

        reload_btn = QPushButton("Reload")
        reload_btn.clicked.connect(self.reload_data)  # type: ignore

        layout = QVBoxLayout()
        layout.addWidget(reload_btn)
        layout.addWidget(self.report_label)
        layout.addWidget(QLabel("Summary"))
        layout.addWidget(self.summary_table)
        layout.addWidget(QLabel("Actions"))
        layout.addWidget(self.actions_table)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.reload_data()

    def reload_data(self) -> None:
        report = load_latest_report()
        if not report:
            self.report_label.setText("Report: (no data)")
            self.summary_table.setRowCount(0)
        else:
            path = report.get("_path", "")
            self.report_label.setText(f"Report: {path}")
            summary = report.get("summary", {})
            self._populate_summary(summary)

        actions = load_actions()
        self._populate_actions(actions)

    def _populate_summary(self, summary: Dict) -> None:
        items = list(summary.items())
        self.summary_table.setColumnCount(2)
        self.summary_table.setHorizontalHeaderLabels(["key", "value"])
        self.summary_table.setRowCount(len(items))
        for row, (k, v) in enumerate(items):
            self.summary_table.setItem(row, 0, QTableWidgetItem(str(k)))
            self.summary_table.setItem(row, 1, QTableWidgetItem(str(v)))
        self.summary_table.resizeColumnsToContents()

    def _populate_actions(self, actions: List[Dict]) -> None:
        self.actions_table.setRowCount(len(actions))
        for row, item in enumerate(actions):
            self.actions_table.setItem(
                row, 0, QTableWidgetItem(str(item.get("comment_id", "")))
            )
            self.actions_table.setItem(
                row, 1, QTableWidgetItem(str(item.get("author", "")))
            )
            self.actions_table.setItem(
                row, 2, QTableWidgetItem(str(item.get("intent", "")))
            )
            self.actions_table.setItem(
                row, 3, QTableWidgetItem(", ".join(item.get("actions", [])))
            )
            self.actions_table.setItem(
                row, 4, QTableWidgetItem(str(item.get("detail", "")))
            )
        self.actions_table.resizeColumnsToContents()


def run() -> None:
    app = QApplication(sys.argv)
    window = Dashboard()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run()
