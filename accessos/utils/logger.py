"""
AccessOS Logging Setup
========================
Call :func:`setup_logging` once at program startup to configure the root
logger with both a console handler and a rotating file handler.

Log files live in ``~/.local/share/accessos/logs/accessos.log``.
"""
from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path


def setup_logging(
    log_dir: Path | None = None,
    level: str = "INFO",
) -> Path:
    """
    Configure console + rotating-file logging for AccessOS.

    Parameters
    ----------
    log_dir:
        Directory for log files.  Defaults to
        ``~/.local/share/accessos/logs/``.
    level:
        Logging level string, e.g. ``"DEBUG"``, ``"INFO"``, ``"WARNING"``.

    Returns
    -------
    Path
        The path of the log file that was opened.
    """
    if log_dir is None:
        log_dir = Path.home() / ".local" / "share" / "accessos" / "logs"

    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "accessos.log"

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(name)-35s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Avoid duplicate handlers if called more than once (e.g. in tests)
    if root.handlers:
        return log_file

    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    root.addHandler(ch)

    # Rotating file handler: 5 MB max, keep 3 backups
    fh = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    fh.setFormatter(fmt)
    root.addHandler(fh)

    logging.getLogger("accessos").info(
        "AccessOS logging started  →  %s", log_file
    )
    return log_file
