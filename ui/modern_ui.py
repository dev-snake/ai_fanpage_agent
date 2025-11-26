"""
Modern UI inspired by Postman - Clean, Professional Dark Theme
Fixed: Consistent colors, proper contrast, dark-only theme
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QFont, QIcon, QPalette, QColor, QAction
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
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QStackedWidget,
    QToolButton,
    QMenu,
    QScrollArea,
    QLineEdit,
    QComboBox,
    QCheckBox,
)


# ==================== DARK THEME COLORS ====================
class Colors:
    """Consistent color palette - Dark theme only"""

    # Backgrounds
    BG_DARK = "#1A1A1A"  # Darkest - main background
    BG_MEDIUM = "#252525"  # Medium - panels/cards
    BG_LIGHT = "#2D2D2D"  # Lighter - hover states

    # Sidebar
    SIDEBAR_BG = "#0F0F0F"  # Sidebar background
    SIDEBAR_HOVER = "#1A1A1A"  # Sidebar hover
    SIDEBAR_ACTIVE = "#252525"  # Sidebar active/selected

    # Text
    TEXT_PRIMARY = "#E8E8E8"  # Main text - high contrast
    TEXT_SECONDARY = "#B0B0B0"  # Secondary text
    TEXT_MUTED = "#808080"  # Muted/disabled text
    TEXT_WHITE = "#FFFFFF"  # Pure white for emphasis

    # Accent colors
    ACCENT = "#FF6C37"  # Primary accent (orange)
    ACCENT_HOVER = "#FF5722"  # Accent hover
    ACCENT_DIM = "#FF6C3750"  # Accent with transparency

    # Status colors
    SUCCESS = "#00D9A5"  # Success/positive
    WARNING = "#FFB020"  # Warning
    DANGER = "#FF4757"  # Error/danger
    INFO = "#4FC3F7"  # Info

    # UI Elements
    BORDER = "#3D3D3D"  # Border color
    BORDER_LIGHT = "#4D4D4D"  # Lighter border
    INPUT_BG = "#1F1F1F"  # Input backgrounds

    # Special
    OVERLAY = "#00000080"  # Overlay/shadow


# ==================== DATA LOADERS ====================
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


# ==================== WORKER THREAD ====================
class AgentWorker(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, cycles: int = 1):
        super().__init__()
        self.cycles = cycles
        self.is_running = True

    def run(self):
        try:
            self.log_signal.emit("🚀 Initializing agent...")

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
                self.log_signal.emit("🔐 Logging in to Facebook...")
                login_ok = login_mgr.login()
                if not login_ok:
                    self.finished_signal.emit(False, "Login failed. Check cookies.json")
                    return

                self.log_signal.emit("✅ Login successful")

                try:
                    fetcher.context = login_mgr.context
                    executor.context = login_mgr.context
                    working_page = page_selector.select_page(
                        cfg, context=login_mgr.context
                    )
                    self.log_signal.emit(f"📄 Working fanpage: {working_page}")
                except Exception as exc:
                    self.finished_signal.emit(False, f"Cannot select fanpage: {exc}")
                    return

            interval = cfg.get("interval_seconds", 90)
            count = 0

            while self.is_running:
                count += 1
                self.log_signal.emit(f"⚙️ Processing cycle {count}...")
                run_cycle(cfg, services)
                self.log_signal.emit(f"✓ Cycle {count} completed")

                if self.cycles and count >= self.cycles:
                    break
                if not self.is_running:
                    break

                self.log_signal.emit(f"⏳ Waiting {interval}s before next cycle...")
                time.sleep(interval)

            report_path = reporter.flush_daily()
            self.log_signal.emit(f"💾 Report saved: {report_path}")

            login_mgr.close()
            self.finished_signal.emit(True, "Agent completed successfully")

        except Exception as exc:
            self.log_signal.emit(f"❌ Error: {exc}")
            self.finished_signal.emit(False, str(exc))

    def stop(self):
        self.is_running = False


# ==================== SIDEBAR BUTTON ====================
class SidebarButton(QPushButton):
    def __init__(self, text: str, icon_text: str = ""):
        super().__init__()
        self.setText(f"{icon_text}  {text}" if icon_text else text)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(44)


# ==================== METRIC CARD ====================
class MetricCard(QFrame):
    def __init__(self, title: str, value: str = "0", color: str = "#FF6C37"):
        super().__init__()
        self.color = color
        self.setObjectName("metricCard")

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)

        self.value_label = QLabel(value)
        self.value_label.setObjectName("metricValue")

        self.title_label = QLabel(title)
        self.title_label.setObjectName("metricTitle")

        layout.addWidget(self.value_label)
        layout.addWidget(self.title_label)

        self.setLayout(layout)

    def set_value(self, value: str):
        self.value_label.setText(value)


# ==================== MAIN WINDOW ====================
class ModernUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker: Optional[AgentWorker] = None

        self.setWindowTitle("AI Fanpage Agent")
        self.setMinimumSize(1400, 900)

        self._init_ui()
        self._apply_dark_theme()

        # Auto-refresh timer
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.load_dashboard_data)
        self.refresh_timer.start(30000)  # Refresh every 30 seconds

        self.load_dashboard_data()

    def _init_ui(self):
        # Main container
        main_widget = QWidget()
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        sidebar = self._create_sidebar()
        main_layout.addWidget(sidebar)

        # Content area
        self.content_stack = QStackedWidget()

        # Pages
        self.dashboard_page = self._create_dashboard_page()
        self.agent_page = self._create_agent_page()
        self.settings_page = self._create_settings_page()
        self.history_page = self._create_history_page()

        self.content_stack.addWidget(self.dashboard_page)
        self.content_stack.addWidget(self.agent_page)
        self.content_stack.addWidget(self.settings_page)
        self.content_stack.addWidget(self.history_page)

        main_layout.addWidget(self.content_stack, 1)

        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

    def _create_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(240)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Logo/Brand
        brand = QLabel("AI Fanpage Agent")
        brand.setObjectName("brandLabel")
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.setMinimumHeight(70)
        layout.addWidget(brand)

        # Navigation buttons
        self.nav_buttons = []

        btn_dashboard = SidebarButton("Dashboard", "")
        btn_dashboard.setChecked(True)
        btn_dashboard.clicked.connect(lambda: self._switch_page(0))
        self.nav_buttons.append(btn_dashboard)

        btn_agent = SidebarButton("Agent Control", "")
        btn_agent.clicked.connect(lambda: self._switch_page(1))
        self.nav_buttons.append(btn_agent)

        btn_history = SidebarButton("History", "")
        btn_history.clicked.connect(lambda: self._switch_page(3))
        self.nav_buttons.append(btn_history)

        btn_settings = SidebarButton("Settings", "")
        btn_settings.clicked.connect(lambda: self._switch_page(2))
        self.nav_buttons.append(btn_settings)

        for btn in self.nav_buttons:
            layout.addWidget(btn)

        layout.addStretch()

        sidebar.setLayout(layout)
        return sidebar

    def _switch_page(self, index: int):
        self.content_stack.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)

    def _create_dashboard_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Header
        header = QHBoxLayout()
        title = QLabel("Dashboard")
        title.setObjectName("pageTitle")
        header.addWidget(title)

        header.addStretch()

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setObjectName("primaryButton")
        self.refresh_btn.clicked.connect(self.load_dashboard_data)
        header.addWidget(self.refresh_btn)

        layout.addLayout(header)

        # Metrics row
        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(20)

        self.metric_total = MetricCard("Total Comments", "0", "#42A5F5")
        self.metric_interest = MetricCard("Interested", "0", "#00BFA5")
        self.metric_spam = MetricCard("Spam Detected", "0", "#FFA500")
        self.metric_replied = MetricCard("AI Replied", "0", "#FF6C37")

        metrics_layout.addWidget(self.metric_total)
        metrics_layout.addWidget(self.metric_interest)
        metrics_layout.addWidget(self.metric_spam)
        metrics_layout.addWidget(self.metric_replied)

        layout.addLayout(metrics_layout)

        # Split view: Summary table + Recent actions
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Summary panel
        summary_panel = self._create_panel("Summary", self._create_summary_table())
        splitter.addWidget(summary_panel)

        # Recent actions panel
        actions_panel = self._create_panel(
            "Recent Activity", self._create_actions_table()
        )
        splitter.addWidget(actions_panel)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        layout.addWidget(splitter, 1)

        page.setLayout(layout)
        return page

    def _create_agent_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Header
        title = QLabel("Agent Control")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        # Control panel
        control_frame = QFrame()
        control_frame.setObjectName("contentPanel")
        control_layout = QVBoxLayout()
        control_layout.setContentsMargins(30, 30, 30, 30)
        control_layout.setSpacing(20)

        # Status
        status_layout = QHBoxLayout()
        status_label = QLabel("Status:")
        status_label.setObjectName("labelBold")
        self.agent_status = QLabel("Idle")
        self.agent_status.setObjectName("statusLabel")
        status_layout.addWidget(status_label)
        status_layout.addWidget(self.agent_status)
        status_layout.addStretch()
        control_layout.addLayout(status_layout)

        # Progress
        self.agent_progress = QProgressBar()
        self.agent_progress.setTextVisible(False)
        self.agent_progress.setMinimumHeight(6)
        control_layout.addWidget(self.agent_progress)

        # Cycle selection
        cycle_layout = QHBoxLayout()
        cycle_label = QLabel("Run Mode:")
        cycle_label.setObjectName("labelBold")
        self.cycle_combo = QComboBox()
        self.cycle_combo.addItems(["1 Cycle", "5 Cycles", "Continuous"])
        cycle_layout.addWidget(cycle_label)
        cycle_layout.addWidget(self.cycle_combo)
        cycle_layout.addStretch()
        control_layout.addLayout(cycle_layout)

        # Buttons
        btn_layout = QHBoxLayout()

        self.start_btn = QPushButton("Start Agent")
        self.start_btn.setObjectName("successButton")
        self.start_btn.setMinimumHeight(50)
        self.start_btn.clicked.connect(self.start_agent)

        self.stop_btn = QPushButton("Stop Agent")
        self.stop_btn.setObjectName("dangerButton")
        self.stop_btn.setMinimumHeight(50)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_agent)

        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)

        control_layout.addLayout(btn_layout)

        # Log viewer
        log_label = QLabel("Agent Log:")
        log_label.setObjectName("labelBold")
        control_layout.addWidget(log_label)

        self.agent_log = QTextEdit()
        self.agent_log.setObjectName("logViewer")
        self.agent_log.setReadOnly(True)
        self.agent_log.setMinimumHeight(300)
        control_layout.addWidget(self.agent_log, 1)

        control_frame.setLayout(control_layout)
        layout.addWidget(control_frame, 1)

        page.setLayout(layout)
        return page

    def _create_settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        title = QLabel("Settings")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        # Settings panel
        settings_frame = QFrame()
        settings_frame.setObjectName("contentPanel")
        settings_layout = QVBoxLayout()
        settings_layout.setContentsMargins(30, 30, 30, 30)
        settings_layout.setSpacing(20)

        # Config file status
        config_label = QLabel("Configuration Files")
        config_label.setObjectName("sectionTitle")
        settings_layout.addWidget(config_label)

        config_status = QLabel()
        config_status.setObjectName("statusInfo")
        status_text = ""

        config_exists = Path("config.json").exists()
        cookies_exists = Path("cookies.json").exists()
        reports_exists = Path("reports").exists()

        status_text += f"[{'OK' if config_exists else 'MISSING'}] config.json: "
        status_text += f"<span style='color: {Colors.SUCCESS if config_exists else Colors.DANGER}'>{'Found' if config_exists else 'Missing'}</span><br>"

        status_text += f"[{'OK' if cookies_exists else 'MISSING'}] cookies.json: "
        status_text += f"<span style='color: {Colors.SUCCESS if cookies_exists else Colors.DANGER}'>{'Found' if cookies_exists else 'Missing'}</span><br>"

        status_text += f"[{'OK' if reports_exists else 'INFO'}] reports/: "
        status_text += f"<span style='color: {Colors.INFO}'>{'Found' if reports_exists else 'Will be created'}</span>"

        config_status.setText(status_text)
        config_status.setTextFormat(Qt.TextFormat.RichText)
        settings_layout.addWidget(config_status)

        settings_layout.addSpacing(20)

        # Dashboard Settings
        refresh_label = QLabel("Dashboard Settings")
        refresh_label.setObjectName("sectionTitle")
        settings_layout.addWidget(refresh_label)

        auto_refresh = QCheckBox("Auto-refresh dashboard every 30 seconds")
        auto_refresh.setChecked(True)
        auto_refresh.toggled.connect(self._toggle_auto_refresh)
        settings_layout.addWidget(auto_refresh)

        # Info
        settings_layout.addSpacing(20)
        info_label = QLabel("About")
        info_label.setObjectName("sectionTitle")
        settings_layout.addWidget(info_label)

        about_text = QLabel(
            f"<b>AI Fanpage Agent</b><br>"
            f"Version: 2.0 - Modern Dark UI<br>"
            f"Theme: Dark Mode (Fixed)<br>"
            f"UI Framework: PyQt6"
        )
        about_text.setTextFormat(Qt.TextFormat.RichText)
        settings_layout.addWidget(about_text)

        settings_layout.addStretch()

        settings_frame.setLayout(settings_layout)
        layout.addWidget(settings_frame)

        page.setLayout(layout)
        return page

    def _create_history_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Header
        header = QHBoxLayout()
        title = QLabel("Action History")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch()

        export_btn = QPushButton("Export")
        export_btn.setObjectName("primaryButton")
        header.addWidget(export_btn)

        layout.addLayout(header)

        # History table
        self.history_table = QTableWidget()
        self.history_table.setObjectName("historyTable")
        self.history_table.setColumnCount(6)
        self.history_table.setHorizontalHeaderLabels(
            ["Timestamp", "Comment ID", "Author", "Intent", "Actions", "Detail"]
        )

        header = self.history_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)

        self.history_table.verticalHeader().setVisible(False)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )

        layout.addWidget(self.history_table, 1)

        self._load_history()

        page.setLayout(layout)
        return page

    def _create_panel(self, title: str, content: QWidget) -> QWidget:
        panel = QFrame()
        panel.setObjectName("contentPanel")

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title_label = QLabel(title)
        title_label.setObjectName("panelTitle")
        layout.addWidget(title_label)

        layout.addWidget(content, 1)

        panel.setLayout(layout)
        return panel

    def _create_summary_table(self) -> QTableWidget:
        self.summary_table = QTableWidget()
        self.summary_table.setObjectName("dataTable")
        self.summary_table.setColumnCount(2)
        self.summary_table.setHorizontalHeaderLabels(["Metric", "Value"])
        self.summary_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.summary_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.summary_table.verticalHeader().setVisible(False)
        self.summary_table.setAlternatingRowColors(True)
        return self.summary_table

    def _create_actions_table(self) -> QTableWidget:
        self.actions_table = QTableWidget()
        self.actions_table.setObjectName("dataTable")
        self.actions_table.setColumnCount(4)
        self.actions_table.setHorizontalHeaderLabels(
            ["Author", "Intent", "Actions", "Detail"]
        )

        header = self.actions_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        self.actions_table.verticalHeader().setVisible(False)
        self.actions_table.setAlternatingRowColors(True)
        self.actions_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        return self.actions_table

    def load_dashboard_data(self):
        report = load_latest_report()
        actions = load_actions()
        summary = report.get("summary", {}) if report else {}
        records = report.get("records", []) if report else []

        # Update metrics
        total = summary.get("total", len(records))
        interest = summary.get("intent_interest", 0)
        spam = summary.get("intent_spam", 0)
        replied = summary.get("action_reply", 0)

        self.metric_total.set_value(str(total))
        self.metric_interest.set_value(str(interest))
        self.metric_spam.set_value(str(spam))
        self.metric_replied.set_value(str(replied))

        # Update summary table
        items = list(summary.items())
        self.summary_table.setRowCount(len(items))
        for row, (key, value) in enumerate(items):
            self.summary_table.setItem(row, 0, QTableWidgetItem(str(key)))
            self.summary_table.setItem(row, 1, QTableWidgetItem(str(value)))

        # Update recent actions (last 50)
        display = (actions or records)[-50:]
        self.actions_table.setRowCount(len(display))
        for row, item in enumerate(display):
            self.actions_table.setItem(
                row, 0, QTableWidgetItem(str(item.get("author", "")))
            )
            self.actions_table.setItem(
                row, 1, QTableWidgetItem(str(item.get("intent", "")))
            )
            self.actions_table.setItem(
                row, 2, QTableWidgetItem(", ".join(item.get("actions", [])))
            )
            self.actions_table.setItem(
                row, 3, QTableWidgetItem(str(item.get("detail", "")))
            )

    def _load_history(self):
        actions = load_actions()
        self.history_table.setRowCount(len(actions))

        for row, item in enumerate(actions):
            timestamp = item.get("timestamp", "N/A")
            if timestamp != "N/A":
                try:
                    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    pass

            self.history_table.setItem(row, 0, QTableWidgetItem(timestamp))
            self.history_table.setItem(
                row, 1, QTableWidgetItem(str(item.get("comment_id", "")))
            )
            self.history_table.setItem(
                row, 2, QTableWidgetItem(str(item.get("author", "")))
            )
            self.history_table.setItem(
                row, 3, QTableWidgetItem(str(item.get("intent", "")))
            )
            self.history_table.setItem(
                row, 4, QTableWidgetItem(", ".join(item.get("actions", [])))
            )
            self.history_table.setItem(
                row, 5, QTableWidgetItem(str(item.get("detail", "")))
            )

    def start_agent(self):
        mode = self.cycle_combo.currentText()
        cycles = 1
        if "5" in mode:
            cycles = 5
        elif "Continuous" in mode:
            cycles = 0

        self.worker = AgentWorker(cycles)
        self.worker.log_signal.connect(self._append_log)
        self.worker.finished_signal.connect(self._on_agent_finished)

        self.agent_progress.setRange(0, 0)
        self.agent_status.setText("Running...")
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        self.worker.start()

    def stop_agent(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()
            self._append_log("⏹ Agent stopped by user")
            self.agent_status.setText("Stopped")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.agent_progress.setRange(0, 1)
            self.agent_progress.setValue(1)

    def _append_log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.agent_log.append(f"[{timestamp}] {message}")
        self.agent_status.setText(message)

    def _on_agent_finished(self, success: bool, message: str):
        self.agent_progress.setRange(0, 1)
        self.agent_progress.setValue(1)

        if success:
            self.agent_status.setText("[OK] Completed")
            self._append_log(f"✅ {message}")
        else:
            self.agent_status.setText("[ERROR] Failed")
            self._append_log(f"❌ {message}")

        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.load_dashboard_data()

    def _toggle_auto_refresh(self, checked: bool):
        if checked:
            self.refresh_timer.start(30000)
        else:
            self.refresh_timer.stop()

    def _apply_dark_theme(self):
        """Apply consistent dark theme to entire application"""
        self.setStyleSheet(
            f"""
            /* ==================== GLOBAL ==================== */
            QMainWindow, QWidget {{
                background-color: {Colors.BG_DARK};
                color: {Colors.TEXT_PRIMARY};
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
                font-size: 13px;
            }}
            
            /* ==================== SIDEBAR ==================== */
            QFrame#sidebar {{
                background-color: {Colors.SIDEBAR_BG};
                border-right: 1px solid {Colors.BORDER};
            }}
            
            QLabel#brandLabel {{
                color: {Colors.TEXT_WHITE};
                font-size: 16px;
                font-weight: 700;
                background-color: {Colors.SIDEBAR_BG};
                border-bottom: 1px solid {Colors.BORDER};
                letter-spacing: 0.5px;
            }}
            
            QPushButton {{
                background-color: transparent;
                color: {Colors.TEXT_SECONDARY};
                text-align: left;
                padding: 12px 20px;
                border: none;
                border-left: 3px solid transparent;
                font-size: 13px;
            }}
            
            QPushButton:hover {{
                background-color: {Colors.SIDEBAR_HOVER};
                color: {Colors.TEXT_PRIMARY};
            }}
            
            QPushButton:checked {{
                background-color: {Colors.SIDEBAR_ACTIVE};
                color: {Colors.TEXT_WHITE};
                border-left-color: {Colors.ACCENT};
                font-weight: 600;
            }}
            
            /* ==================== CONTENT PANELS ==================== */
            QFrame#contentPanel {{
                background-color: {Colors.BG_MEDIUM};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
            }}
            
            /* ==================== METRIC CARDS ==================== */
            QFrame#metricCard {{
                background-color: {Colors.BG_MEDIUM};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
                padding: 4px;
            }}
            
            QLabel#metricValue {{
                font-size: 32px;
                font-weight: 700;
                color: {Colors.ACCENT};
            }}
            
            QLabel#metricTitle {{
                font-size: 11px;
                color: {Colors.TEXT_SECONDARY};
                text-transform: uppercase;
                letter-spacing: 0.5px;
                font-weight: 600;
            }}
            
            /* ==================== TYPOGRAPHY ==================== */
            QLabel#pageTitle {{
                font-size: 28px;
                font-weight: 700;
                color: {Colors.TEXT_WHITE};
                margin-bottom: 8px;
            }}
            
            QLabel#panelTitle {{
                font-size: 14px;
                font-weight: 600;
                color: {Colors.TEXT_WHITE};
            }}
            
            QLabel#sectionTitle {{
                font-size: 13px;
                font-weight: 600;
                color: {Colors.TEXT_WHITE};
                margin-bottom: 10px;
            }}
            
            QLabel#labelBold {{
                font-weight: 600;
                color: {Colors.TEXT_PRIMARY};
            }}
            
            QLabel#statusLabel {{
                color: {Colors.TEXT_SECONDARY};
            }}
            
            QLabel#statusInfo {{
                color: {Colors.TEXT_PRIMARY};
                line-height: 1.8;
                font-size: 13px;
            }}
            
            QLabel {{
                color: {Colors.TEXT_PRIMARY};
            }}
            
            /* ==================== BUTTONS ==================== */
            QPushButton#primaryButton {{
                background-color: {Colors.ACCENT};
                color: {Colors.TEXT_WHITE};
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: 600;
            }}
            
            QPushButton#primaryButton:hover {{
                background-color: {Colors.ACCENT_HOVER};
            }}
            
            QPushButton#successButton {{
                background-color: {Colors.SUCCESS};
                color: {Colors.TEXT_WHITE};
                border: none;
                border-radius: 6px;
                padding: 12px 24px;
                font-weight: 600;
                font-size: 14px;
            }}
            
            QPushButton#successButton:hover {{
                background-color: #00C090;
            }}
            
            QPushButton#successButton:disabled {{
                background-color: {Colors.BG_LIGHT};
                color: {Colors.TEXT_MUTED};
            }}
            
            QPushButton#dangerButton {{
                background-color: {Colors.DANGER};
                color: {Colors.TEXT_WHITE};
                border: none;
                border-radius: 6px;
                padding: 12px 24px;
                font-weight: 600;
                font-size: 14px;
            }}
            
            QPushButton#dangerButton:hover {{
                background-color: #E63946;
            }}
            
            QPushButton#dangerButton:disabled {{
                background-color: {Colors.BG_LIGHT};
                color: {Colors.TEXT_MUTED};
            }}
            
            /* ==================== TABLES ==================== */
            QTableWidget {{
                background-color: {Colors.BG_MEDIUM};
                border: 1px solid {Colors.BORDER};
                border-radius: 6px;
                gridline-color: {Colors.BORDER};
                color: {Colors.TEXT_PRIMARY};
            }}
            
            QHeaderView::section {{
                background-color: {Colors.BG_LIGHT};
                padding: 12px;
                border: none;
                border-bottom: 2px solid {Colors.BORDER_LIGHT};
                font-weight: 600;
                color: {Colors.TEXT_WHITE};
                font-size: 12px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            
            QTableWidget::item {{
                padding: 10px;
                color: {Colors.TEXT_PRIMARY};
                border-bottom: 1px solid {Colors.BORDER};
            }}
            
            QTableWidget::item:selected {{
                background-color: {Colors.ACCENT_DIM};
                color: {Colors.TEXT_WHITE};
            }}
            
            QTableWidget::item:alternate {{
                background-color: {Colors.BG_DARK};
            }}
            
            /* ==================== LOG VIEWER ==================== */
            QTextEdit#logViewer {{
                background-color: {Colors.INPUT_BG};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 6px;
                padding: 12px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
                line-height: 1.6;
            }}
            
            /* ==================== PROGRESS BAR ==================== */
            QProgressBar {{
                border: none;
                background-color: {Colors.BG_LIGHT};
                border-radius: 3px;
                height: 6px;
            }}
            
            QProgressBar::chunk {{
                background-color: {Colors.ACCENT};
                border-radius: 3px;
            }}
            
            /* ==================== COMBOBOX ==================== */
            QComboBox {{
                background-color: {Colors.BG_MEDIUM};
                border: 1px solid {Colors.BORDER};
                border-radius: 6px;
                padding: 8px 12px;
                color: {Colors.TEXT_PRIMARY};
                min-width: 150px;
            }}
            
            QComboBox:hover {{
                border-color: {Colors.ACCENT};
            }}
            
            QComboBox::drop-down {{
                border: none;
                padding-right: 10px;
            }}
            
            QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid {Colors.TEXT_SECONDARY};
                margin-right: 5px;
            }}
            
            QComboBox QAbstractItemView {{
                background-color: {Colors.BG_MEDIUM};
                border: 1px solid {Colors.BORDER};
                selection-background-color: {Colors.ACCENT};
                selection-color: {Colors.TEXT_WHITE};
                color: {Colors.TEXT_PRIMARY};
                padding: 4px;
            }}
            
            /* ==================== CHECKBOX ==================== */
            QCheckBox {{
                color: {Colors.TEXT_PRIMARY};
                spacing: 8px;
            }}
            
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid {Colors.BORDER_LIGHT};
                border-radius: 4px;
                background-color: {Colors.BG_MEDIUM};
            }}
            
            QCheckBox::indicator:checked {{
                background-color: {Colors.ACCENT};
                border-color: {Colors.ACCENT};
            }}
            
            QCheckBox::indicator:hover {{
                border-color: {Colors.ACCENT};
            }}
            
            /* ==================== SCROLLBAR ==================== */
            QScrollBar:vertical {{
                background-color: {Colors.BG_DARK};
                width: 12px;
                border: none;
            }}
            
            QScrollBar::handle:vertical {{
                background-color: {Colors.BG_LIGHT};
                min-height: 30px;
                border-radius: 6px;
            }}
            
            QScrollBar::handle:vertical:hover {{
                background-color: {Colors.BORDER_LIGHT};
            }}
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            
            QScrollBar:horizontal {{
                background-color: {Colors.BG_DARK};
                height: 12px;
                border: none;
            }}
            
            QScrollBar::handle:horizontal {{
                background-color: {Colors.BG_LIGHT};
                min-width: 30px;
                border-radius: 6px;
            }}
            
            QScrollBar::handle:horizontal:hover {{
                background-color: {Colors.BORDER_LIGHT};
            }}
            
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
            
            /* ==================== SPLITTER ==================== */
            QSplitter::handle {{
                background-color: {Colors.BORDER};
                width: 2px;
                height: 2px;
            }}
            
            QSplitter::handle:hover {{
                background-color: {Colors.ACCENT};
            }}
        """
        )


def run():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = ModernUI()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    run()
