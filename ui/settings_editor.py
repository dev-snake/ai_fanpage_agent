"""
Settings Editor - GUI để chỉnh sửa .env và config.json
Không cần mở code editor, chỉnh trực tiếp trong UI
"""

from pathlib import Path
from typing import Dict, Optional
import json

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFormLayout,
    QGroupBox,
    QMessageBox,
    QTextEdit,
    QCheckBox,
    QSpinBox,
    QComboBox,
)


class SettingsEditor(QDialog):
    """Dialog để edit settings một cách trực quan"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings Editor")
        self.setMinimumWidth(700)
        self.setMinimumHeight(600)

        self.env_file = Path(".env")
        self.config_file = Path("config.json")

        self._init_ui()
        self._load_current_settings()

    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        # Title
        title = QLabel("Settings Editor")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        subtitle = QLabel(
            "Edit your configuration here. Changes will be saved to .env and config.json files."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #808080;")
        layout.addWidget(subtitle)

        # OpenAI Settings
        openai_group = QGroupBox("OpenAI Configuration")
        openai_layout = QFormLayout()

        self.openai_key_input = QLineEdit()
        self.openai_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_key_input.setPlaceholderText("sk-...")
        openai_layout.addRow("API Key:", self.openai_key_input)

        show_key_btn = QPushButton("Show/Hide")
        show_key_btn.clicked.connect(self._toggle_key_visibility)
        openai_layout.addRow("", show_key_btn)

        self.openai_model_input = QComboBox()
        self.openai_model_input.addItems(
            ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"]
        )
        self.openai_model_input.setEditable(True)
        openai_layout.addRow("Model:", self.openai_model_input)

        openai_group.setLayout(openai_layout)
        layout.addWidget(openai_group)

        # Facebook Settings
        fb_group = QGroupBox("Facebook Configuration")
        fb_layout = QFormLayout()

        self.page_id_input = QLineEdit()
        self.page_id_input.setPlaceholderText("Your Facebook Page ID")
        fb_layout.addRow("Page ID:", self.page_id_input)

        self.graph_token_input = QLineEdit()
        self.graph_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.graph_token_input.setPlaceholderText("Optional: Graph API Access Token")
        fb_layout.addRow("Graph Token:", self.graph_token_input)

        fb_group.setLayout(fb_layout)
        layout.addWidget(fb_group)

        # Agent Settings
        agent_group = QGroupBox("Agent Settings")
        agent_layout = QFormLayout()

        self.interval_input = QSpinBox()
        self.interval_input.setRange(10, 3600)
        self.interval_input.setValue(90)
        self.interval_input.setSuffix(" seconds")
        agent_layout.addRow("Interval:", self.interval_input)

        self.max_actions_input = QSpinBox()
        self.max_actions_input.setRange(1, 100)
        self.max_actions_input.setValue(20)
        agent_layout.addRow("Max Actions/Cycle:", self.max_actions_input)

        self.headless_input = QCheckBox("Run browser in headless mode")
        agent_layout.addRow("Headless:", self.headless_input)

        self.log_level_input = QComboBox()
        self.log_level_input.addItems(["INFO", "DEBUG", "WARNING", "ERROR"])
        agent_layout.addRow("Log Level:", self.log_level_input)

        agent_group.setLayout(agent_layout)
        layout.addWidget(agent_group)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        save_btn = QPushButton("Save Settings")
        save_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #00D9A5;
                color: white;
                padding: 10px 24px;
                border: none;
                border-radius: 6px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #00C090;
            }
        """
        )
        save_btn.clicked.connect(self._save_settings)
        button_layout.addWidget(save_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #4D4D4D;
                color: white;
                padding: 10px 24px;
                border: none;
                border-radius: 6px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #3D3D3D;
            }
        """
        )
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def _toggle_key_visibility(self):
        """Toggle password visibility"""
        if self.openai_key_input.echoMode() == QLineEdit.EchoMode.Password:
            self.openai_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.graph_token_input.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.openai_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.graph_token_input.setEchoMode(QLineEdit.EchoMode.Password)

    def _load_current_settings(self):
        """Load current settings from .env and config.json"""
        # Load from .env
        if self.env_file.exists():
            env_content = self.env_file.read_text(encoding="utf-8")
            for line in env_content.split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()

                    if key == "OPENAI_API_KEY":
                        self.openai_key_input.setText(value)
                    elif key == "PAGE_ID":
                        self.page_id_input.setText(value)
                    elif key == "GRAPH_ACCESS_TOKEN":
                        self.graph_token_input.setText(value)
                    elif key == "OPENAI_MODEL":
                        self.openai_model_input.setCurrentText(value)
                    elif key == "LOG_LEVEL":
                        self.log_level_input.setCurrentText(value)
                    elif key == "INTERVAL_SECONDS":
                        try:
                            self.interval_input.setValue(int(value))
                        except ValueError:
                            pass
                    elif key == "MAX_ACTIONS_PER_CYCLE":
                        try:
                            self.max_actions_input.setValue(int(value))
                        except ValueError:
                            pass
                    elif key == "HEADLESS":
                        self.headless_input.setChecked(value.lower() == "true")

        # Load from config.json as fallback
        if self.config_file.exists():
            try:
                config = json.loads(self.config_file.read_text(encoding="utf-8"))

                # Only set if not already set from .env
                if not self.openai_model_input.currentText():
                    model = config.get("openai_model", "gpt-4o-mini")
                    self.openai_model_input.setCurrentText(model)

                if not self.log_level_input.currentText():
                    level = config.get("log_level", "INFO")
                    self.log_level_input.setCurrentText(level)

                if self.interval_input.value() == 90:  # Default value
                    interval = config.get("interval_seconds", 90)
                    self.interval_input.setValue(interval)

                if self.max_actions_input.value() == 20:  # Default value
                    max_actions = config.get("max_actions_per_cycle", 20)
                    self.max_actions_input.setValue(max_actions)

                headless = config.get("headless", False)
                if isinstance(headless, bool):
                    self.headless_input.setChecked(headless)

            except json.JSONDecodeError:
                pass

    def _save_settings(self):
        """Save settings to .env and config.json"""
        # Validate required fields
        if not self.openai_key_input.text().strip():
            QMessageBox.warning(self, "Validation Error", "OpenAI API Key is required!")
            return

        if not self.page_id_input.text().strip():
            QMessageBox.warning(
                self, "Validation Error", "Facebook Page ID is required!"
            )
            return

        try:
            # Create .env content
            env_content = f"""# AI Fanpage Agent Configuration
# Auto-generated by Settings Editor

# OpenAI Configuration
OPENAI_API_KEY={self.openai_key_input.text().strip()}
OPENAI_MODEL={self.openai_model_input.currentText()}

# Facebook Configuration
PAGE_ID={self.page_id_input.text().strip()}
"""

            if self.graph_token_input.text().strip():
                env_content += (
                    f"GRAPH_ACCESS_TOKEN={self.graph_token_input.text().strip()}\n"
                )

            env_content += f"""
# Agent Settings
LOG_LEVEL={self.log_level_input.currentText()}
INTERVAL_SECONDS={self.interval_input.value()}
MAX_ACTIONS_PER_CYCLE={self.max_actions_input.value()}
TIMEZONE=Asia/Ho_Chi_Minh
HEADLESS={str(self.headless_input.isChecked()).lower()}
"""

            # Save .env
            self.env_file.write_text(env_content, encoding="utf-8")

            # Update config.json
            if self.config_file.exists():
                config = json.loads(self.config_file.read_text(encoding="utf-8"))
            else:
                config = {}

            # Update config with new values (using ${VAR} for sensitive data)
            config["openai_api_key"] = "${OPENAI_API_KEY}"
            config["openai_model"] = self.openai_model_input.currentText()
            config["page_id"] = "${PAGE_ID}"
            config["graph_access_token"] = "${GRAPH_ACCESS_TOKEN}"
            config["log_level"] = self.log_level_input.currentText()
            config["interval_seconds"] = self.interval_input.value()
            config["max_actions_per_cycle"] = self.max_actions_input.value()
            config["headless"] = self.headless_input.isChecked()

            # Save config.json
            self.config_file.write_text(
                json.dumps(config, indent=4, ensure_ascii=False), encoding="utf-8"
            )

            QMessageBox.information(
                self,
                "Success",
                "Settings saved successfully!\n\n"
                "Restart the application for changes to take effect.",
            )

            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save settings:\n{str(e)}")


def show_settings_editor(parent=None) -> bool:
    """Show settings editor dialog"""
    dialog = SettingsEditor(parent)
    return dialog.exec() == QDialog.DialogCode.Accepted
