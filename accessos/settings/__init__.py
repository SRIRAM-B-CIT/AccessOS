"""
AccessOS Settings Package
==========================
Phase 2: Accessible configuration UI, system hardware controls,
and protected power confirmation dialogs.
"""
from .settings_window import SettingsWindow
from .camera_detector import CameraDetector
from .system_control import SystemControl
from .confirm_dialog import ConfirmDialog

__all__ = [
    "SettingsWindow",
    "CameraDetector",
    "SystemControl",
    "ConfirmDialog",
]
