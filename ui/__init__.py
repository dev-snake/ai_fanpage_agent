"""
UI package entrypoints.

- main_window.py : Primary PyQt6 UI with sidebar.
- launcher.py    : Lightweight launcher (kept for legacy/CLI).
- qt_dashboard.py: Compact PyQt dashboard view.
"""

from .main_window import ModernUI, run  # noqa: F401
