"""
PyQt6 dashboard with a neutral Windows-like look.
Focuses on readability: hero header, KPI cards, summary and actions tables.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QHeaderView,
    QMainWindow,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


REPORT_DIR = Path("reports")
ACTION_LOG = Path("data/actions.json")

BASE_FONT = "Segoe UI"
WINDOW_BG = "#f5f6f8"
PANEL_BG = "#ffffff"
ACCENT = "#1a73e8"
ACCENT_DARK = "#1557b0"
BORDER = "#d9dde3"
TEXT_MAIN = "#111827"
TEXT_MUTED = "#4b5563"


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


class SummaryCard(QFrame):
    """Compact metric card with left accent."""

    def __init__(self, title: str, value: str = "--"):
        super().__init__()
        self.setObjectName("kpiCard")
        layout = QVBoxLayout()
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10.5pt;")

        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(f"color: {TEXT_MAIN}; font-size: 20pt;")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        self.setLayout(layout)

    def set_value(self, text: str) -> None:
        self.value_label.setText(text)


def pill(text: str, tone: str = "accent") -> QLabel:
    label = QLabel(text)
    label.setProperty("pill", tone)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setFont(QFont(BASE_FONT, 9, QFont.Weight.DemiBold))
    return label


class Dashboard(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AI Fanpage Agent - Dashboard")
        self.resize(1200, 760)

        self.cards: Dict[str, SummaryCard] = {}
        self.report_label = QLabel("Chua co bao cao.")

        self.summary_table = QTableWidget()
        self.actions_table = QTableWidget()

        self._init_ui()
        self.reload_data()

    def _init_ui(self) -> None:
        outer = QVBoxLayout()
        outer.setContentsMargins(26, 22, 26, 22)
        outer.setSpacing(16)

        outer.addWidget(self._build_hero())
        outer.addLayout(self._build_kpis())
        outer.addLayout(self._build_tables())

        container = QWidget()
        container.setLayout(outer)
        self.setCentralWidget(container)
        self._apply_style()

    def _build_hero(self) -> QFrame:
        hero = QFrame()
        hero.setObjectName("hero")
        layout = QHBoxLayout()
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(12)

        text_col = QVBoxLayout()
        text_col.setSpacing(6)

        title = QLabel("Tong quan AI Fanpage Agent")
        title.setFont(QFont(BASE_FONT, 19, QFont.Weight.Bold))
        title.setStyleSheet("color: #f8fafc;")
        text_col.addWidget(title)

        subtitle = QLabel("Theo doi so lieu moi nhat va nhat ky xu ly.")
        subtitle.setFont(QFont(BASE_FONT, 11))
        subtitle.setStyleSheet("color: #e5e7eb;")
        text_col.addWidget(subtitle)

        pill_row = QHBoxLayout()
        pill_row.setSpacing(8)
        self.report_label.setStyleSheet("color: #dbeafe;")
        pill_row.addWidget(pill("Dashboard PyQt6", tone="ghost"))
        pill_row.addWidget(self.report_label)
        pill_row.addStretch()
        text_col.addLayout(pill_row)

        layout.addLayout(text_col, 4)

        refresh_btn = QPushButton("Tai lai du lieu")
        refresh_btn.setMinimumHeight(40)
        refresh_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {ACCENT};
                color: white;
                border: 1px solid {ACCENT};
                border-radius: 10px;
                padding: 10px 16px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {ACCENT_DARK};
                border-color: {ACCENT_DARK};
            }}
            """
        )
        refresh_btn.clicked.connect(self.reload_data)  # type: ignore
        layout.addWidget(refresh_btn, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        hero.setLayout(layout)
        return hero

    def _build_kpis(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setSpacing(12)
        card_info = [
            ("total", "Comment hom nay"),
            ("interest", "Khach quan tam"),
            ("spam", "Spam / bo qua"),
            ("reply", "Da tra loi"),
        ]
        for idx, (key, label) in enumerate(card_info):
            card = SummaryCard(label)
            self.cards[key] = card
            grid.addWidget(card, idx // 2, idx % 2)
        return grid

    def _build_tables(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(14)

        summary_frame = self._build_table_frame("Tong ket", self.summary_table)
        self.summary_table.setColumnCount(2)
        self.summary_table.setHorizontalHeaderLabels(["Chi so", "Gia tri"])
        self.summary_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.summary_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.summary_table.verticalHeader().setVisible(False)
        self.summary_table.setAlternatingRowColors(True)

        actions_frame = self._build_table_frame("Nhat ky hanh dong", self.actions_table)
        self.actions_table.setColumnCount(5)
        self.actions_table.setHorizontalHeaderLabels(
            ["Comment ID", "Nguoi dung", "Y dinh", "Hanh dong", "Chi tiet"]
        )
        header = self.actions_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.actions_table.verticalHeader().setVisible(False)
        self.actions_table.setAlternatingRowColors(True)
        self.actions_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )

        row.addWidget(summary_frame, 2)
        row.addWidget(actions_frame, 5)
        return row

    def _build_table_frame(self, title: str, table: QTableWidget) -> QFrame:
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header = QHBoxLayout()
        label = QLabel(title)
        label.setStyleSheet(f"color: {TEXT_MAIN}; font-size: 12pt; font-weight: 600;")
        header.addWidget(label)
        header.addStretch()
        if table is self.actions_table:
            hint = QLabel("Toi da 200 dong gan nhat")
            hint.setProperty("pill", "secondary")
            header.addWidget(hint)
        layout.addLayout(header)

        layout.addWidget(table)
        frame.setLayout(layout)
        return frame

    def reload_data(self) -> None:
        report = load_latest_report()
        actions = load_actions()
        summary = report.get("summary", {}) if report else {}
        records = report.get("records", []) if report else []

        if report:
            path = report.get("_path", "")
            self.report_label.setText(f"Bao cao: {path}")
        else:
            self.report_label.setText("Chua co bao cao duoc ghi nhan.")

        self._update_cards(summary, records)
        self._populate_summary(summary)
        self._populate_actions(actions or records)

    def _update_cards(self, summary: Dict, records: List[Dict]) -> None:
        total = summary.get("total", len(records))
        interest = summary.get("intent_interest", 0)
        spam = summary.get("intent_spam", 0)
        replied = summary.get("action_reply", 0)

        for key, value in {
            "total": total,
            "interest": interest,
            "spam": spam,
            "reply": replied,
        }.items():
            card = self.cards.get(key)
            if card:
                card.set_value(str(value))

    def _populate_summary(self, summary: Dict) -> None:
        items = list(summary.items())
        self.summary_table.setRowCount(len(items))
        for row, (key, value) in enumerate(items):
            self.summary_table.setItem(row, 0, QTableWidgetItem(str(key)))
            self.summary_table.setItem(row, 1, QTableWidgetItem(str(value)))
        self.summary_table.resizeRowsToContents()

    def _populate_actions(self, actions: List[Dict]) -> None:
        display = actions[-200:] if len(actions) > 200 else actions
        self.actions_table.setRowCount(len(display))
        for row, item in enumerate(display):
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
        self.actions_table.resizeRowsToContents()

    def _apply_style(self) -> None:
        self.setStyleSheet(
            f"""
            QWidget {{
                background-color: {WINDOW_BG};
                color: {TEXT_MAIN};
                font-family: {BASE_FONT};
            }}
            QFrame#card {{
                background: {PANEL_BG};
                border: 1px solid {BORDER};
                border-radius: 12px;
            }}
            QFrame#hero {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0b1220, stop:1 #0f172a
                );
                border: 1px solid #0b1220;
                border-radius: 14px;
            }}
            QFrame#kpiCard {{
                background: {PANEL_BG};
                border: 1px solid {BORDER};
                border-left: 5px solid {ACCENT};
                border-radius: 10px;
            }}
            QTableWidget {{
                background: {PANEL_BG};
                border: 1px solid {BORDER};
                border-radius: 10px;
                gridline-color: {BORDER};
            }}
            QHeaderView::section {{
                background: #eef1f5;
                padding: 10px;
                border: none;
                border-bottom: 2px solid {BORDER};
                font-weight: 600;
                color: {TEXT_MAIN};
            }}
            QTableWidget::item {{
                padding: 8px;
            }}
            QLabel[pill="accent"] {{
                background: #e8f0fe;
                color: {ACCENT};
                border: 1px solid #d7e3fc;
                border-radius: 10px;
                padding: 4px 10px;
            }}
            QLabel[pill="secondary"] {{
                background: #e5e7eb;
                color: {TEXT_MAIN};
                border: 1px solid #d1d5db;
                border-radius: 10px;
                padding: 4px 10px;
            }}
            QLabel[pill="ghost"] {{
                background: rgba(255, 255, 255, 0.12);
                color: #f8fafc;
                border: 1px solid rgba(255, 255, 255, 0.18);
                border-radius: 10px;
                padding: 4px 10px;
            }}
            """
        )


def run() -> None:
    app = QApplication(sys.argv)
    window = Dashboard()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run()
