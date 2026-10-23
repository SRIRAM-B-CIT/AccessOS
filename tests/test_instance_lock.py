"""
Phase 3.6 Single-Instance Lock & Process Exclusivity Tests
"""
import os
import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest

from accessos.utils.instance_lock import SingleInstanceLock, SingleInstanceError


def test_lock_acquire_and_release():
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_file = Path(tmpdir) / "test_accessos.pid"
        lock = SingleInstanceLock(lock_file=lock_file)

        assert not lock_file.exists()
        lock.acquire()

        assert lock_file.exists()
        pid_in_file = int(lock_file.read_text(encoding="utf-8").strip())
        assert pid_in_file == os.getpid()

        lock.release()
        assert not lock_file.exists()


def test_lock_refusal_when_instance_already_running():
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_file = Path(tmpdir) / "test_accessos.pid"
        lock1 = SingleInstanceLock(lock_file=lock_file)
        lock1.acquire()

        lock2 = SingleInstanceLock(lock_file=lock_file)
        with pytest.raises(SingleInstanceError) as exc_info:
            lock2.acquire()

        assert "already running" in str(exc_info.value)
        assert "Recovery instructions" in str(exc_info.value)

        lock1.release()
        assert not lock_file.exists()


def test_lock_stale_pid_recovery_when_process_is_dead():
    """If PID in lock file does not exist, lock must recover automatically."""
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_file = Path(tmpdir) / "test_accessos.pid"
        # Write dead PID
        lock_file.write_text("9999999\n", encoding="utf-8")

        lock = SingleInstanceLock(lock_file=lock_file)
        # Should not raise; dead PID is cleaned up
        lock.acquire()

        assert lock_file.exists()
        assert int(lock_file.read_text(encoding="utf-8").strip()) == os.getpid()
        lock.release()
        assert not lock_file.exists()


def test_lock_context_manager():
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_file = Path(tmpdir) / "test_accessos.pid"
        with SingleInstanceLock(lock_file=lock_file) as lock:
            assert lock_file.exists()
            assert lock._acquired is True

        assert not lock_file.exists()
