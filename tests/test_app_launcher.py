"""
Tests for accessos.app_launcher.AppLauncher
No hardware, no display required.  Subprocess.Popen is patched.
"""
from unittest.mock import MagicMock, patch

import pytest

from accessos.app_launcher import AppLauncher, _DEFAULT_CMDS, _FALLBACKS


class TestAppLauncherSecurity:
    """Ensure the launcher never uses shell=True."""

    def test_launch_never_uses_shell(self):
        with patch("subprocess.Popen") as mock_popen:
            launcher = AppLauncher()
            launcher.launch("browser")
            _, kwargs = mock_popen.call_args
            assert kwargs.get("shell") is not True, \
                "AppLauncher must never use shell=True"

    def test_launch_uses_start_new_session(self):
        with patch("subprocess.Popen") as mock_popen:
            launcher = AppLauncher()
            launcher.launch("files")
            _, kwargs = mock_popen.call_args
            assert kwargs.get("start_new_session") is True

    def test_unknown_key_is_rejected(self):
        errors = []
        launcher = AppLauncher()
        result = launcher.launch("arbitrary_shell_command", on_error=errors.append)
        assert result is False
        assert errors, "on_error must be called for unknown app keys"

    def test_allowlist_keys_only(self):
        """Custom commands outside the allow-list must be silently ignored."""
        launcher = AppLauncher(app_commands={"evil_key": ["rm", "-rf", "/"]})
        # evil_key is not in _DEFAULT_CMDS, so it must not be stored
        assert "evil_key" not in launcher._cmds


class TestAppLauncherLaunch:
    def test_successful_launch_returns_true(self):
        with patch("subprocess.Popen"):
            launcher = AppLauncher()
            assert launcher.launch("browser") is True

    def test_command_not_found_tries_fallback(self):
        import subprocess
        call_count = [0]

        def popen_side_effect(cmd, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise FileNotFoundError("not found")
            return MagicMock()

        with patch("subprocess.Popen", side_effect=popen_side_effect):
            launcher = AppLauncher()
            result = launcher.launch("browser")
            assert result is True
            assert call_count[0] >= 2, "Should have tried at least one fallback"

    def test_all_fallbacks_fail_calls_on_error(self):
        with patch("subprocess.Popen", side_effect=FileNotFoundError("nope")):
            errors = []
            launcher = AppLauncher()
            result = launcher.launch("browser", on_error=errors.append)
            assert result is False
            assert errors

    def test_override_command_is_used(self):
        captured = []

        def capture_popen(cmd, **kwargs):
            captured.append(cmd)
            return MagicMock()

        with patch("subprocess.Popen", side_effect=capture_popen):
            launcher = AppLauncher(app_commands={"browser": ["chromium"]})
            launcher.launch("browser")
            assert captured[0][0] == "chromium"
