"""
AccessOS entry point
=====================
Run with::

    python3 -m accessos               # fullscreen (default)
    ACCESSOS_WINDOWED=1 python3 -m accessos  # maximised window (development)

Environment variables:
  ACCESSOS_WINDOWED=1   : run maximised instead of fullscreen
  ACCESSOS_LOG_LEVEL    : logging level (DEBUG / INFO / WARNING; default INFO)
  ACCESSOS_CONFIG       : path to a custom settings.toml
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from .utils.logger import setup_logging
from .utils.config import Config
from .audio_feedback import AudioFeedback
from .app_launcher import AppLauncher


def main() -> None:
    # ── Logging ────────────────────────────────────────────────────────────────
    log_level = os.environ.get("ACCESSOS_LOG_LEVEL", "INFO")
    setup_logging(level=log_level)
    log = logging.getLogger("accessos")
    log.info("AccessOS %s starting (phase %s)", _version(), _phase())

    # ── Configuration ──────────────────────────────────────────────────────────
    cfg_path_env = os.environ.get("ACCESSOS_CONFIG")
    config = Config(
        config_path=Path(cfg_path_env) if cfg_path_env else None
    )

    # ── Services ───────────────────────────────────────────────────────────────
    audio   = AudioFeedback(enabled=config.get("audio", "sounds_enabled", default=True))
    launcher = AppLauncher(app_commands=config.get("apps", default={}))

    # ── GTK application ────────────────────────────────────────────────────────
    # Import GTK only after logging is ready, so any import warnings are captured.
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gtk

    from .home_screen import HomeScreen

    app = Gtk.Application(application_id="org.accessos.home")

    def on_activate(application: Gtk.Application) -> None:
        win = HomeScreen(
            app=application,
            config=config,
            launcher=launcher,
            audio=audio,
        )
        win.show_all()
        win.present()
        log.debug("HomeScreen presented")

    app.connect("activate", on_activate)

    log.info("Entering GTK main loop")
    exit_code = app.run(sys.argv)
    log.info("AccessOS exited with code %s", exit_code)
    sys.exit(exit_code)


def _version() -> str:
    from . import __version__
    return __version__


def _phase() -> int:
    from . import __phase__
    return __phase__


if __name__ == "__main__":
    main()
