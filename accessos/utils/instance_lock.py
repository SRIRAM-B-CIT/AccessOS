"""
AccessOS Single-Instance Lock Mechanism
=======================================
Guarantees that only one AccessOS process can run at a time to prevent
input interference, device contention (webcam/audio), and ghost processes.

Enforces:
  1. Safe PID tracking in ~/.cache/accessos/accessos.pid.
  2. Kernel-level advisory locking via fcntl.flock (LOCK_EX | LOCK_NB).
  3. Stale PID detection and automatic recovery after system reboots/crashes.
  4. Active process refusal with clear recovery instructions.
  5. Guaranteed lock release on all exit paths (atexit, SIGTERM, SIGINT, exceptions).
"""
from __future__ import annotations

import atexit
import fcntl
import logging
import os
import signal
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_DEFAULT_LOCK_DIR = Path.home() / ".cache" / "accessos"
_DEFAULT_LOCK_FILE = _DEFAULT_LOCK_DIR / "accessos.pid"


class SingleInstanceError(RuntimeError):
    """Raised when another AccessOS process is already running."""
    pass


class SingleInstanceLock:
    """Manages process exclusivity via a safe PID file and fcntl lock."""

    def __init__(self, lock_file: Optional[Path] = None) -> None:
        self.lock_file = lock_file or _DEFAULT_LOCK_FILE
        self._fd: Optional[int] = None
        self._acquired: bool = False
        self._old_sigterm = None
        self._old_sigint = None

    def acquire(self) -> None:
        """Acquire single-instance lock or raise SingleInstanceError."""
        if self._acquired:
            return

        self.lock_file.parent.mkdir(parents=True, exist_ok=True)

        # Check existing PID file before opening
        if self.lock_file.exists():
            try:
                content = self.lock_file.read_text(encoding="utf-8").strip()
                if content.isdigit():
                    old_pid = int(content)
                    if self._is_process_alive(old_pid):
                        if self._is_accessos_process(old_pid):
                            msg = (
                                f"AccessOS is already running (PID: {old_pid}).\n"
                                "Only one AccessOS instance can run at a time to prevent input interference.\n\n"
                                "Recovery instructions:\n"
                                f"  1. Switch to the active AccessOS window (PID {old_pid}).\n"
                                f"  2. Or stop it cleanly: ./scripts/stop_accessos.sh  (or: kill {old_pid})\n"
                                f"  3. If the process crashed and PID is stale, delete: {self.lock_file}"
                            )
                            log.error("SingleInstanceLock refusal: %s", msg)
                            raise SingleInstanceError(msg)
                        else:
                            log.warning("Stale lock file PID %d belongs to unrelated process; reclaiming.", old_pid)
                            self.lock_file.unlink(missing_ok=True)
                    else:
                        log.info("Stale lock file detected (PID %d is dead); reclaiming.", old_pid)
                        self.lock_file.unlink(missing_ok=True)
            except (ValueError, OSError) as exc:
                log.debug("Error reading existing lock file: %s", exc)

        # Open and flock
        try:
            self._fd = os.open(str(self.lock_file), os.O_CREAT | os.O_RDWR | os.O_TRUNC, 0o644)
            fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            os.write(self._fd, f"{os.getpid()}\n".encode("utf-8"))
            os.fsync(self._fd)
            self._acquired = True
            log.info("SingleInstanceLock acquired (PID: %d, file: %s)", os.getpid(), self.lock_file)
        except (BlockingIOError, OSError) as exc:
            if self._fd is not None:
                try:
                    os.close(self._fd)
                except Exception:
                    pass
                self._fd = None
            msg = (
                f"Could not acquire AccessOS lock file ({self.lock_file}): {exc}.\n"
                "Another instance holds an active file lock.\n"
                "Recovery: Run ./scripts/stop_accessos.sh before launching."
            )
            raise SingleInstanceError(msg) from exc

        # Register exit hooks
        atexit.register(self.release)
        self._install_signal_handlers()

    def release(self) -> None:
        """Release lock and remove lock file."""
        if not self._acquired:
            return

        self._acquired = False
        log.info("Releasing SingleInstanceLock (PID: %d)", os.getpid())

        if self._fd is not None:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
                os.close(self._fd)
            except Exception as exc:
                log.debug("Error releasing flock/closing fd: %s", exc)
            self._fd = None

        try:
            if self.lock_file.exists():
                content = self.lock_file.read_text(encoding="utf-8").strip()
                if content == str(os.getpid()):
                    self.lock_file.unlink(missing_ok=True)
                    log.debug("Lock file %s removed", self.lock_file)
        except Exception as exc:
            log.debug("Error unlinking lock file: %s", exc)

    def _is_process_alive(self, pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True

    def _is_accessos_process(self, pid: int) -> bool:
        cmdline_file = Path(f"/proc/{pid}/cmdline")
        if cmdline_file.exists():
            try:
                raw = cmdline_file.read_bytes().replace(bytes([0]), b" ").decode("utf-8", errors="ignore").lower()
                return "accessos" in raw
            except Exception:
                pass
        return True

    def _install_signal_handlers(self) -> None:
        def _handler(signum, frame):
            log.info("Signal %s received; cleaning up single-instance lock", signum)
            self.release()
            os._exit(128 + signum)

        try:
            self._old_sigterm = signal.signal(signal.SIGTERM, _handler)
            self._old_sigint = signal.signal(signal.SIGINT, _handler)
        except (ValueError, AttributeError):
            pass

    def __enter__(self) -> SingleInstanceLock:
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()
