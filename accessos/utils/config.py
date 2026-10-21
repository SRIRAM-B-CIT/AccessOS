"""
AccessOS Configuration Manager
================================
Loads configuration from a TOML file and merges it with safe built-in
defaults.  Uses stdlib ``tomllib`` (Python 3.11+); no extra dependencies.

Usage::

    from accessos.utils.config import Config
    cfg = Config()
    device = cfg.get("camera", "device", default="/dev/video2")
"""
from __future__ import annotations

import logging
import sys
import tomllib
from pathlib import Path
import copy
from typing import Any

log = logging.getLogger(__name__)

# ── Built-in defaults ─────────────────────────────────────────────────────────
_DEFAULTS: dict = {
    "theme": {
        "font_size": 18,
        "high_contrast": True,
        "focus_color": "#4f9eff",
    },
    "audio": {
        "sounds_enabled": True,
        "tts_enabled": False,   # Phase 4
        "volume": 80,
    },
    "camera": {
        "device": "/dev/video2",   # RGB camera, NOT the IR node
        "enabled": False,          # Enabled per-mode in Phase 3+
    },
    "apps": {
        "browser":  ["firefox"],
        "files":    ["thunar"],
        "terminal": ["xfce4-terminal"],
        "images":   ["ristretto"],
        "videos":   ["parole"],
    },
    "accessibility": {
        "mode": "keyboard_mouse",
        "paused": False,
        "dwell_time_ms": 1000,
        "head_sensitivity": 0.5,
    },
}


class Config:
    """
    Layered configuration: built-in defaults ← TOML file on disk.

    The file is loaded once at construction; call :meth:`reload` to re-read.
    Missing keys always fall back to defaults, so callers never get KeyError.
    """

    def __init__(self, config_path: Path | None = None) -> None:
        self._data: dict = copy.deepcopy(_DEFAULTS)

        if config_path is None:
            config_path = Path.home() / ".config" / "accessos" / "settings.toml"
        self.config_path = config_path
        self._load_from_file()

    # ── Internal helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> None:
        """Recursively merge *override* into *base* (in-place)."""
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                Config._deep_merge(base[key], value)
            else:
                base[key] = value

    def _load_from_file(self) -> None:
        if not self.config_path.exists():
            log.debug("No config file at %s — using defaults", self.config_path)
            return
        try:
            with open(self.config_path, "rb") as fh:
                file_data = tomllib.load(fh)
            self._deep_merge(self._data, file_data)
            log.info("Config loaded from %s", self.config_path)
        except Exception as exc:
            log.warning("Config load failed (%s) — using defaults", exc)

    # ── Public API ─────────────────────────────────────────────────────────────

    def get(self, *keys: str, default: Any = None) -> Any:
        """
        Retrieve a value by dotted key path.

        Example::

            cfg.get("apps", "browser")          # ["firefox"]
            cfg.get("missing", default="nope")  # "nope"
        """
        node: Any = self._data
        for key in keys:
            if isinstance(node, dict):
                node = node.get(key, default)
            else:
                return default
        return node

    def reload(self) -> None:
        """Re-read the config file from disk."""
        self._data = copy.deepcopy(_DEFAULTS)
        self._load_from_file()
