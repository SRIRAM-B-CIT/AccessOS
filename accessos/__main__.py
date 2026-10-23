"""
AccessOS Main Entry Point
==========================
Run with:
    ./scripts/run_accessos.sh                           # Host safe profile (default, windowed)
    ./scripts/run_accessos.sh --profile camera-preview  # Camera preview only
    ./scripts/run_accessos.sh --profile vm-real         # VM real injection (VM ONLY)

Environment variables:
    ACCESSOS_PROFILE       : host-safe | camera-preview | vm-real (default: host-safe)
    ACCESSOS_WINDOWED      : 1 = windowed/maximized (default on host), 0 = fullscreen
    ACCESSOS_LOG_LEVEL     : DEBUG | INFO | WARNING | ERROR (default: INFO)
    ACCESSOS_CONFIG        : path to custom settings.toml
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from .utils.logger import setup_logging
from .utils.config import Config
from .utils.profile import LaunchProfile, resolve_profile, validate_profile_prerequisites
from .utils.build_info import format_build_banner, get_build_info
from .utils.instance_lock import SingleInstanceLock, SingleInstanceError
from .utils.environment import HostSafetyViolationError
from .audio_feedback import AudioFeedback
from .app_launcher import AppLauncher


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="accessos",
        description="AccessOS — Accessible Live Operating Environment",
    )
    parser.add_argument(
        "--profile",
        choices=["host-safe", "camera-preview", "vm-real"],
        default=None,
        help="Launch profile: host-safe (default, UI only), camera-preview (preview only, no input), vm-real (VM only)",
    )
    parser.add_argument(
        "--windowed",
        action="store_true",
        help="Run in maximized window mode instead of fullscreen",
    )
    parser.add_argument(
        "--fullscreen",
        action="store_true",
        help="Run in fullscreen mode",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to custom settings.toml",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=None,
        help="Logging verbosity level",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print version, git commit, and runtime environment, then exit",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    # ── Version display ────────────────────────────────────────────────────────
    if args.version:
        info = get_build_info()
        print(f"AccessOS v{info['version']} (commit {info['git_commit_short']})")
        print(f"Python: {info['python_executable']}")
        print(f"Source: {info['accessos_file']}")
        sys.exit(0)

    # ── Logging setup ──────────────────────────────────────────────────────────
    log_level = args.log_level or os.environ.get("ACCESSOS_LOG_LEVEL", "INFO")
    setup_logging(level=log_level)
    log = logging.getLogger("accessos")

    # ── Resolve and validate launch profile ────────────────────────────────────
    profile = resolve_profile(args.profile)

    # Windowed mode environment
    if args.windowed:
        os.environ["ACCESSOS_WINDOWED"] = "1"
    elif args.fullscreen:
        os.environ["ACCESSOS_WINDOWED"] = "0"
    else:
        # Default to windowed mode on host hardware for safety
        os.environ.setdefault("ACCESSOS_WINDOWED", "1")

    # Diagnostic banner logging (Requirement 1)
    banner = format_build_banner(profile=profile.value)
    for line in banner.splitlines():
        log.info(line)

    # Validate profile prerequisites (Requirement 4)
    try:
        validate_profile_prerequisites(profile)
    except HostSafetyViolationError as exc:
        log.critical("FATAL SAFETY CHECK FAILED: %s", exc)
        print(f"\nFATAL: {exc}\n", file=sys.stderr)
        sys.exit(1)

    # ── Single-instance exclusivity lock (Requirement 2) ───────────────────────
    lock = SingleInstanceLock()
    try:
        lock.acquire()
    except SingleInstanceError as exc:
        log.critical("SingleInstanceLock failed: %s", exc)
        print(f"\nERROR: {exc}\n", file=sys.stderr)
        sys.exit(2)

    # ── Configuration & Services ───────────────────────────────────────────────
    try:
        cfg_path = args.config or (Path(os.environ["ACCESSOS_CONFIG"]) if "ACCESSOS_CONFIG" in os.environ else None)
        config = Config(config_path=cfg_path)

        audio = AudioFeedback(enabled=config.get("audio", "sounds_enabled", default=True))
        launcher = AppLauncher(app_commands=config.get("apps", default={}))

        # ── GTK Application ────────────────────────────────────────────────────
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
                profile=profile,
            )
            win.show_all()
            win.present()
            log.debug("HomeScreen presented successfully under profile: %s", profile.value)

        app.connect("activate", on_activate)

        log.info("Entering GTK main loop (Profile: %s)", profile.value)
        exit_code = app.run(sys.argv[:1])  # Only pass program name to GTK
        log.info("AccessOS exited with code %s", exit_code)

    finally:
        lock.release()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
