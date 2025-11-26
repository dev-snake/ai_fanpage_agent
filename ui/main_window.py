"""
Primary PyQt6 UI for AI Fanpage Agent.
Dark, sidebar-first layout (main app window used by main.py).
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
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
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QStackedWidget,
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
        self.setMinimumHeight(100)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        self.value_label = QLabel(value)
        self.value_label.setObjectName("metricValue")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("metricTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

        layout.addWidget(self.value_label)
        layout.addWidget(self.title_label)
        layout.addStretch()

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

        btn_settings = SidebarButton("Settings", "")
        btn_settings.clicked.connect(lambda: self._switch_page(2))
        self.nav_buttons.append(btn_settings)

        btn_history = SidebarButton("History", "")
        btn_history.clicked.connect(lambda: self._switch_page(3))
        self.nav_buttons.append(btn_history)

        for btn in self.nav_buttons:
            layout.addWidget(btn)

        layout.addStretch()

        sidebar.setLayout(layout)
        return sidebar

    def _switch_page(self, page_index: int):
        self.content_stack.setCurrentIndex(page_index)
        clicked = self.sender()
        for btn in self.nav_buttons:
            btn.setChecked(btn is clicked)

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
        control_layout.setSpacing(16)

        # Status section
        status_section = QWidget()
        status_layout = QVBoxLayout()
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(8)

        status_row = QHBoxLayout()
        status_label = QLabel("Status:")
        status_label.setObjectName("labelBold")
        status_label.setFixedWidth(80)
        self.agent_status = QLabel("Idle")
        self.agent_status.setObjectName("statusLabel")
        status_row.addWidget(status_label)
        status_row.addWidget(self.agent_status)
        status_row.addStretch()
        status_layout.addLayout(status_row)

        # Progress
        self.agent_progress = QProgressBar()
        self.agent_progress.setTextVisible(False)
        self.agent_progress.setFixedHeight(6)
        status_layout.addWidget(self.agent_progress)

        status_section.setLayout(status_layout)
        control_layout.addWidget(status_section)

        control_layout.addSpacing(8)

        # Cycle selection
        cycle_row = QHBoxLayout()
        cycle_label = QLabel("Run Mode:")
        cycle_label.setObjectName("labelBold")
        cycle_label.setFixedWidth(80)
        self.cycle_combo = QComboBox()
        self.cycle_combo.addItems(["1 Cycle", "5 Cycles", "Continuous"])
        self.cycle_combo.setMinimumHeight(40)
        cycle_row.addWidget(cycle_label)
        cycle_row.addWidget(self.cycle_combo, 1)
        cycle_row.addStretch(2)
        control_layout.addLayout(cycle_row)

        control_layout.addSpacing(8)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(16)

        self.start_btn = QPushButton("Start Agent")
        self.start_btn.setObjectName("successButton")
        self.start_btn.setMinimumHeight(48)
        self.start_btn.clicked.connect(self.start_agent)

        self.stop_btn = QPushButton("Stop Agent")
        self.stop_btn.setObjectName("dangerButton")
        self.stop_btn.setMinimumHeight(48)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_agent)

        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)

        control_layout.addLayout(btn_layout)

        control_layout.addSpacing(12)

        # Log viewer
        log_label = QLabel("Agent Log:")
        log_label.setObjectName("sectionTitle")
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

        # Configuration Files Section
        config_section = self._create_settings_section(
            "Configuration Files", self._build_config_status_widget()
        )
        layout.addWidget(config_section)

        # Dashboard Settings Section
        dashboard_section = self._create_settings_section(
            "Dashboard Settings", self._build_dashboard_settings_widget()
        )
        layout.addWidget(dashboard_section)

        # About Section
        about_section = self._create_settings_section(
            "About", self._build_about_widget()
        )
        layout.addWidget(about_section)

        layout.addStretch()
        page.setLayout(layout)
        return page

    def _create_settings_section(self, title: str, content_widget: QWidget) -> QFrame:
        """Create a consistent settings section with proper spacing"""
        section = QFrame()
        section.setObjectName("contentPanel")

        section_layout = QVBoxLayout()
        section_layout.setContentsMargins(24, 20, 24, 20)
        section_layout.setSpacing(16)

        # Section title
        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")
        section_layout.addWidget(title_label)

        # Add separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setObjectName("separator")
        section_layout.addWidget(separator)

        # Content
        section_layout.addWidget(content_widget)

        section.setLayout(section_layout)
        return section

    def _build_config_status_widget(self) -> QWidget:
        """Build configuration status widget"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        config_exists = Path("config.json").exists()
        cookies_exists = Path("cookies.json").exists()
        reports_exists = Path("reports").exists()

        # Create status items
        layout.addWidget(
            self._create_status_item(
                "config.json", config_exists, "Found" if config_exists else "Missing"
            )
        )

        layout.addWidget(
            self._create_status_item(
                "cookies.json", cookies_exists, "Found" if cookies_exists else "Missing"
            )
        )

        layout.addWidget(
            self._create_status_item(
                "reports/",
                reports_exists,
                "Found" if reports_exists else "Will be created",
                use_info_color=not reports_exists,
            )
        )

        # Edit Configuration Button
        edit_config_btn = QPushButton("Edit Configuration")
        edit_config_btn.setObjectName("primaryButton")
        edit_config_btn.setMinimumHeight(44)
        edit_config_btn.clicked.connect(self._open_settings_editor)
        layout.addWidget(edit_config_btn)

        widget.setLayout(layout)
        return widget

    def _create_status_item(
        self, label: str, is_ok: bool, status: str, use_info_color: bool = False
    ) -> QWidget:
        """Create a single status item with consistent styling"""
        item = QWidget()
        item_layout = QHBoxLayout()
        item_layout.setContentsMargins(0, 0, 0, 0)
        item_layout.setSpacing(12)

        # Status badge
        badge = QLabel("OK" if is_ok else "MISSING")
        badge.setObjectName("statusBadgeOk" if is_ok else "statusBadgeMissing")
        badge.setFixedSize(70, 24)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        item_layout.addWidget(badge)

        # File name
        name_label = QLabel(label)
        name_label.setObjectName("statusItemName")
        item_layout.addWidget(name_label)

        # Status text
        status_label = QLabel(status)
        if use_info_color:
            status_label.setStyleSheet(f"color: {Colors.INFO};")
        elif is_ok:
            status_label.setStyleSheet(f"color: {Colors.SUCCESS};")
        else:
            status_label.setStyleSheet(f"color: {Colors.DANGER};")
        item_layout.addWidget(status_label)

        item_layout.addStretch()
        item.setLayout(item_layout)
        return item

    def _build_dashboard_settings_widget(self) -> QWidget:
        """Build dashboard settings widget"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        auto_refresh = QCheckBox("Auto-refresh dashboard every 30 seconds")
        auto_refresh.setChecked(True)
        auto_refresh.toggled.connect(self._toggle_auto_refresh)
        layout.addWidget(auto_refresh)

        widget.setLayout(layout)
        return widget

    def _build_about_widget(self) -> QWidget:
        """Build about info widget"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        info_items = [
            ("Application", "AI Fanpage Agent"),
            ("Version", "2.0 - Modern Dark UI"),
            ("Theme", "Dark Mode (Fixed)"),
            ("UI Framework", "PyQt6"),
        ]

        for label, value in info_items:
            item_layout = QHBoxLayout()
            item_layout.setSpacing(12)

            label_widget = QLabel(f"{label}:")
            label_widget.setObjectName("aboutLabel")
            item_layout.addWidget(label_widget)

            value_widget = QLabel(value)
            value_widget.setObjectName("aboutValue")
            item_layout.addWidget(value_widget)

            item_layout.addStretch()

            item_container = QWidget()
            item_container.setLayout(item_layout)
            layout.addWidget(item_container)

        widget.setLayout(layout)
        return widget

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

    def _open_settings_editor(self):
        """Open settings editor dialog"""
        try:
            from ui.settings_editor import show_settings_editor

            if show_settings_editor(self):
                QMessageBox.information(
                    self,
                    "Settings Saved",
                    "Settings have been saved successfully!\n\n"
                    "Please restart the application for changes to take effect.",
                )
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to open settings editor:\n{str(e)}"
            )

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
                background: transparent;
                padding: 0;
            }}
            
            QLabel#metricTitle {{
                font-size: 11px;
                color: {Colors.TEXT_SECONDARY};
                text-transform: uppercase;
                letter-spacing: 0.5px;
                font-weight: 600;
                background: transparent;
                padding: 0;
            }}
            
            /* ==================== TYPOGRAPHY ==================== */
            QLabel {{
                background: transparent;
            }}
            
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
            
            /* ==================== SETTINGS PAGE ==================== */
            QFrame#separator {{
                background-color: {Colors.BORDER};
                max-height: 1px;
                border: none;
            }}
            
            QLabel#statusBadgeOk {{
                background-color: {Colors.SUCCESS}30;
                color: {Colors.SUCCESS};
                border: 1px solid {Colors.SUCCESS};
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
                padding: 2px 8px;
            }}
            
            QLabel#statusBadgeMissing {{
                background-color: {Colors.DANGER}30;
                color: {Colors.DANGER};
                border: 1px solid {Colors.DANGER};
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
                padding: 2px 8px;
            }}
            
            QLabel#statusItemName {{
                color: {Colors.TEXT_PRIMARY};
                font-size: 13px;
                font-weight: 500;
                min-width: 120px;
            }}
            
            QLabel#aboutLabel {{
                color: {Colors.TEXT_SECONDARY};
                font-size: 13px;
                font-weight: 500;
                min-width: 120px;
            }}
            
            QLabel#aboutValue {{
                color: {Colors.TEXT_PRIMARY};
                font-size: 13px;
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
