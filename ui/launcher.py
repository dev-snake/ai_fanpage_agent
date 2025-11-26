"""
Refined PyQt6 UI for AI Fanpage Agent.
Neutral, Windows-like layout with clearer hierarchy and no emojis.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QProgressBar,
)


BASE_FONT = "Segoe UI"
WINDOW_BG = "#f5f6f8"
PANEL_BG = "#ffffff"
ACCENT = "#1a73e8"
ACCENT_DARK = "#1557b0"
SECONDARY = "#1f2937"
SECONDARY_DARK = "#111827"
DANGER = "#c53030"
DANGER_DARK = "#9b2c2c"
TEXT_MAIN = "#111827"
TEXT_MUTED = "#4b5563"
BORDER = "#d9dde3"
LOG_BG = "#0f172a"
MONO_FONT = "Consolas"


def button_style(bg: str, hover: str, text: str = "#ffffff") -> str:
    """Create a consistent button stylesheet."""
    return f"""
        QPushButton {{
            background-color: {bg};
            color: {text};
            border: 1px solid {bg};
            border-radius: 8px;
            padding: 12px 16px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background-color: {hover};
            border-color: {hover};
        }}
        QPushButton:disabled {{
            background-color: #e5e7eb;
            border-color: #e5e7eb;
            color: #6b7280;
        }}
    """


def pill(text: str, tone: str = "accent") -> QLabel:
    """Create a pill-style label for quick highlights."""
    label = QLabel(text)
    label.setProperty("pill", tone)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setFont(QFont(BASE_FONT, 9, QFont.Weight.DemiBold))
    return label


class AgentWorker(QThread):
    """Background thread to run the agent without blocking the UI."""

    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, cycles: int = 1):
        super().__init__()
        self.cycles = cycles
        self.is_running = True

    def run(self) -> None:  # noqa: D401
        """Run the agent in background."""
        try:
            self.log_signal.emit("Khoi dong agent...")
            self.log_signal.emit("Dang dang nhap Facebook...")

            from main import build_services, load_config, run_cycle

            cfg = load_config("config.json")
            logger, login_mgr, fetcher, executor, reporter, db, page_selector = (
                build_services(cfg)
            )
            services = (
                logger,
                login_mgr,
                fetcher,
                executor,
                reporter,
                db,
                page_selector,
            )

            if not cfg.get("demo", False):
                self.log_signal.emit("Dang dang nhap...")
                login_ok = login_mgr.login()
                if not login_ok:
                    self.finished_signal.emit(
                        False, "Dang nhap that bai. Kiem tra cookies.json"
                    )
                    return

                self.log_signal.emit("Dang nhap thanh cong")

                try:
                    fetcher.context = login_mgr.context
                    executor.context = login_mgr.context
                    working_page = page_selector.select_page(
                        cfg, context=login_mgr.context
                    )
                    self.log_signal.emit(f"Fanpage dang lam viec: {working_page}")
                except Exception as exc:  # noqa: BLE001
                    self.finished_signal.emit(False, f"Khong the chon fanpage: {exc}")
                    return

            interval = cfg.get("interval_seconds", 90)
            count = 0
            while self.is_running:
                count += 1
                self.log_signal.emit("Dang xu ly comment...")
                run_cycle(cfg, services)
                self.log_signal.emit("Hoan thanh mot chu ky")
                if self.cycles and count >= self.cycles:
                    break
                if not self.is_running:
                    break
                time.sleep(interval)

            report_path = reporter.flush_daily()
            self.log_signal.emit(f"Da luu bao cao: {report_path}")

            login_mgr.close()
            label = "Da dung agent" if not self.is_running else "Hoan thanh"
            self.finished_signal.emit(True, f"{label}.")

        except Exception as exc:  # noqa: BLE001
            self.log_signal.emit(f"Loi: {exc}")
            self.finished_signal.emit(False, str(exc))

    def stop(self) -> None:
        """Request worker stop."""
        self.is_running = False


class AgentRunnerWindow(QWidget):
    """Window that shows agent progress and logs."""

    def __init__(self, parent=None, cycles: int = 1):
        super().__init__(parent)
        self.cycles = cycles
        self.worker: Optional[AgentWorker] = None
        self.init_ui()

    def init_ui(self) -> None:
        self.setWindowTitle("AI Fanpage Agent - Dang chay")
        self.setMinimumSize(940, 600)

        outer = QVBoxLayout()
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(14)

        outer.addWidget(self._build_runner_header())

        panel = QFrame()
        panel.setObjectName("card")
        panel_layout = QVBoxLayout()
        panel_layout.setContentsMargins(18, 16, 18, 16)
        panel_layout.setSpacing(12)

        self.status_label = QLabel("Trang thai: Dang khoi dong...")
        self.status_label.setFont(QFont(BASE_FONT, 11))
        self.status_label.setStyleSheet(f"color: {TEXT_MAIN};")
        panel_layout.addWidget(self.status_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet(
            f"""
            QProgressBar {{
                height: 8px;
                background: #e5e7eb;
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {ACCENT};
                border-radius: 4px;
            }}
            """
        )
        panel_layout.addWidget(self.progress)

        log_header = QHBoxLayout()
        title = QLabel("Nhat ky hoat dong")
        title.setFont(QFont(BASE_FONT, 11, QFont.Weight.DemiBold))
        title.setStyleSheet(f"color: {TEXT_MAIN};")
        log_header.addWidget(title)
        log_header.addStretch()

        mode_chip = pill(
            "Lien tuc" if self.cycles == 0 else f"{self.cycles} chu ky",
            tone="secondary",
        )
        log_header.addWidget(mode_chip)
        panel_layout.addLayout(log_header)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont(MONO_FONT, 10))
        self.log_text.setStyleSheet(
            f"""
            QTextEdit {{
                background: {LOG_BG};
                color: #e5e7eb;
                border: 1px solid {BORDER};
                border-radius: 8px;
                padding: 12px;
            }}
            """
        )
        panel_layout.addWidget(self.log_text)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.stop_btn = QPushButton("Dung Agent")
        self.stop_btn.setStyleSheet(button_style(DANGER, DANGER_DARK))
        self.stop_btn.clicked.connect(self.stop_agent)
        btn_row.addWidget(self.stop_btn)

        self.close_btn = QPushButton("Dong cua so")
        self.close_btn.setStyleSheet(
            button_style("#ffffff", "#e9ecef", text=TEXT_MAIN)
        )
        self.close_btn.setEnabled(False)
        self.close_btn.clicked.connect(self.close)
        btn_row.addWidget(self.close_btn)

        panel_layout.addLayout(btn_row)
        panel.setLayout(panel_layout)
        outer.addWidget(panel)

        self.setLayout(outer)
        self._apply_global_style()
        self.start_agent()

    def _build_runner_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("hero")
        layout = QVBoxLayout()
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(6)

        title = QLabel("Agent dang chay")
        title.setFont(QFont(BASE_FONT, 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #f8fafc;")
        layout.addWidget(title)

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(pill("Giu cua so mo de xem log", tone="ghost"))
        row.addWidget(pill("Tu dong luu bao cao", tone="ghost"))
        row.addStretch()
        layout.addLayout(row)

        header.setLayout(layout)
        return header

    def _apply_global_style(self) -> None:
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
                    stop:0 #0f172a, stop:1 #111827
                );
                border: 1px solid #0b1220;
                border-radius: 12px;
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

    def start_agent(self) -> None:
        """Launch the background worker."""
        self.worker = AgentWorker(cycles=self.cycles)
        self.worker.log_signal.connect(self.append_log)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()

    def append_log(self, message: str) -> None:
        """Append a log line and update status."""
        self.log_text.append(message)
        self.status_label.setText(f"Trang thai: {message}")

    def on_finished(self, success: bool, message: str) -> None:
        """Handle worker completion."""
        self.progress.setRange(0, 1)
        self.progress.setValue(1)

        if success:
            self.status_label.setText(f"Hoan thanh: {message}")
            self.log_text.append(f"\nHoan thanh: {message}")
            QMessageBox.information(self, "Hoan thanh", message)
        else:
            self.status_label.setText(f"Loi: {message}")
            self.log_text.append(f"\nLoi: {message}")
            QMessageBox.critical(self, "Loi", message)

        self.stop_btn.setEnabled(False)
        self.close_btn.setEnabled(True)

    def stop_agent(self) -> None:
        """Ask for confirmation and stop the worker."""
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self,
                "Xac nhan",
                "Ban co muon dung agent ngay bay gio?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.worker.stop()
                self.worker.wait()
                self.append_log("Da dung agent theo yeu cau")
                self.stop_btn.setEnabled(False)
                self.close_btn.setEnabled(True)


class LauncherWindow(QMainWindow):
    """Main launcher window with clear actions."""

    def __init__(self):
        super().__init__()
        self.config_exists = Path("config.json").exists()
        self.cookies_exists = Path("cookies.json").exists()
        self.reports_dir = Path("reports")
        self.init_ui()

    def init_ui(self) -> None:
        self.setWindowTitle("AI Fanpage Agent")
        self.setMinimumSize(980, 620)

        central = QWidget()
        self.setCentralWidget(central)

        outer = QVBoxLayout()
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(16)

        outer.addWidget(self._build_hero())

        content = QHBoxLayout()
        content.setSpacing(14)

        status_card = self._build_status_card()
        status_card.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        content.addWidget(status_card, 2)

        action_card = self._build_action_card()
        action_card.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        content.addWidget(action_card, 3)

        guide_card = self._build_info_card()
        guide_card.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        content.addWidget(guide_card, 3)

        outer.addLayout(content)
        central.setLayout(outer)
        self._apply_global_style()

    def _build_hero(self) -> QFrame:
        hero = QFrame()
        hero.setObjectName("hero")
        layout = QVBoxLayout()
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(6)

        title = QLabel("AI Fanpage Agent")
        title.setFont(QFont(BASE_FONT, 22, QFont.Weight.Bold))
        title.setStyleSheet("color: #f8fafc;")
        layout.addWidget(title)

        subtitle = QLabel(
            "Giao dien don gian, tap trung vao tac vu quan ly binh luan va bao cao."
        )
        subtitle.setFont(QFont(BASE_FONT, 11))
        subtitle.setStyleSheet("color: #e5e7eb;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        pill_row = QHBoxLayout()
        pill_row.setSpacing(8)
        pill_row.addWidget(pill("Launcher UI", tone="ghost"))
        pill_row.addWidget(pill("PyQt6", tone="ghost"))
        pill_row.addWidget(pill("Khong emoji", tone="ghost"))
        pill_row.addStretch()
        layout.addLayout(pill_row)

        hero.setLayout(layout)
        return hero

    def _build_status_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        title = QLabel("Tinh trang he thong")
        title.setFont(QFont(BASE_FONT, 12, QFont.Weight.DemiBold))
        layout.addWidget(title)

        layout.addLayout(self._status_row("config.json", self.config_exists))
        layout.addLayout(self._status_row("cookies.json", self.cookies_exists))
        layout.addLayout(
            self._status_row(
                "Thu muc reports/",
                self.reports_dir.exists(),
                extra="Tu dong tao khi co bao cao",
            )
        )

        note = QLabel("Neu thieu file, bo sung truoc khi chay agent.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        layout.addWidget(note)

        card.setLayout(layout)
        return card

    def _status_row(self, label: str, ok: bool, extra: str | None = None) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        row.setContentsMargins(0, 0, 0, 0)
        badge = pill("San sang" if ok else "Thieu", tone="accent" if ok else "secondary")
        name = QLabel(label)
        name.setFont(QFont(BASE_FONT, 10, QFont.Weight.DemiBold))
        name.setStyleSheet(f"color: {TEXT_MAIN};")
        row.addWidget(badge)
        row.addWidget(name)
        row.addStretch()
        if extra:
            hint = QLabel(extra)
            hint.setObjectName("muted")
            row.addWidget(hint)
        return row

    def _build_info_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("Huong dan nhanh")
        title.setFont(QFont(BASE_FONT, 12, QFont.Weight.DemiBold))
        layout.addWidget(title)

        tips = [
            "Cau hinh file config.json va cookies.json truoc khi chay.",
            "Neu chi demo, bat demo trong config de bo qua dang nhap.",
            "Bao cao se duoc luu vao thu muc reports/ sau moi lan chay.",
            "De xem log khi agent dang hoat dong, mo cua so runner.",
        ]
        for tip in tips:
            lbl = QLabel(f"• {tip}")
            lbl.setFont(QFont(BASE_FONT, 10))
            lbl.setStyleSheet(f"color: {TEXT_MUTED};")
            lbl.setWordWrap(True)
            layout.addWidget(lbl)

        layout.addStretch()
        card.setLayout(layout)
        return card

    def _build_action_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        title = QLabel("Tac vu chinh")
        title.setFont(QFont(BASE_FONT, 12, QFont.Weight.DemiBold))
        layout.addWidget(title)

        self.run_agent_btn = QPushButton("Chay 1 chu ky")
        self.run_agent_btn.setMinimumHeight(50)
        self.run_agent_btn.setStyleSheet(button_style(ACCENT, ACCENT_DARK))
        self.run_agent_btn.clicked.connect(self.run_agent)
        layout.addWidget(self.run_agent_btn)

        self.run_agent_multi_btn = QPushButton("Chay lien tuc")
        self.run_agent_multi_btn.setMinimumHeight(50)
        self.run_agent_multi_btn.setStyleSheet(button_style(SECONDARY, SECONDARY_DARK))
        self.run_agent_multi_btn.clicked.connect(self.run_agent_multi)
        layout.addWidget(self.run_agent_multi_btn)

        self.dashboard_btn = QPushButton("Mo dashboard (PyQt)")
        self.dashboard_btn.setMinimumHeight(48)
        self.dashboard_btn.setStyleSheet(button_style("#374151", "#1f2937"))
        self.dashboard_btn.clicked.connect(self.open_dashboard)
        layout.addWidget(self.dashboard_btn)

        self.console_dashboard_btn = QPushButton("Mo dashboard console")
        self.console_dashboard_btn.setMinimumHeight(48)
        self.console_dashboard_btn.setStyleSheet(button_style("#4b5563", "#374151"))
        self.console_dashboard_btn.clicked.connect(self.open_console_dashboard)
        layout.addWidget(self.console_dashboard_btn)

        layout.addStretch()

        exit_btn = QPushButton("Dong ung dung")
        exit_btn.setMinimumHeight(44)
        exit_btn.setStyleSheet(button_style("#ffffff", "#e9ecef", text=TEXT_MAIN))
        exit_btn.clicked.connect(self.close)
        layout.addWidget(exit_btn)

        card.setLayout(layout)
        return card

    def _apply_global_style(self) -> None:
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
                    stop:0 #0b1120, stop:1 #0f172a
                );
                border: 1px solid #0b1220;
                border-radius: 14px;
            }}
            QLabel#muted {{
                color: {TEXT_MUTED};
                font-size: 10pt;
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

    def run_agent(self) -> None:
        """Run agent with one cycle."""
        self.runner_window = AgentRunnerWindow(self, cycles=1)
        self.runner_window.show()

    def run_agent_multi(self) -> None:
        """Run agent continuously (0 cycles = infinite for scheduler)."""
        self.runner_window = AgentRunnerWindow(self, cycles=0)
        self.runner_window.show()

    def open_dashboard(self) -> None:
        """Open the PyQt dashboard."""
        try:
            from ui.qt_dashboard import Dashboard

            self.dashboard_window = Dashboard()
            self.dashboard_window.show()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Loi", f"Khong the mo dashboard:\n{exc}")

    def open_console_dashboard(self) -> None:
        """Open the console dashboard in a detached process."""
        try:
            subprocess.Popen([sys.executable, "-m", "ui.dashboard"])
            QMessageBox.information(
                self,
                "Console Dashboard",
                "Dashboard console da duoc mo trong cua so terminal khac.",
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Loi", f"Khong the mo console dashboard:\n{exc}")


def run() -> None:
    """Run the launcher application."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = LauncherWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    run()
