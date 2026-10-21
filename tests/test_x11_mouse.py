"""
Tests for Native X11Mouse Controller, Safety Boundaries, and Session Verification
"""
import os
from unittest.mock import patch
import pytest

from accessos.engine.x11_mouse import (
    X11Mouse,
    UnsupportedSessionError,
    HostSafetyViolationError,
    check_session_supported,
)


def test_check_session_supported_wayland_without_display():
    with patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland", "DISPLAY": ""}):
        ok, msg = check_session_supported()
        assert ok is False
        assert "Wayland" in msg


def test_check_session_supported_missing_display():
    with patch.dict(os.environ, {"XDG_SESSION_TYPE": "x11", "DISPLAY": ""}):
        ok, msg = check_session_supported()
        assert ok is False
        assert "DISPLAY" in msg


def test_x11_mouse_blocked_on_host_hardware():
    """Verify X11Mouse unconditionally raises HostSafetyViolationError on host."""
    with patch("accessos.engine.mouse_backend.can_use_real_mouse_injection", return_value=(False, "Blocked on host")):
        with pytest.raises(HostSafetyViolationError) as exc_info:
            X11Mouse(allow_host_override=False)
        assert "Blocked on host" in str(exc_info.value)


def test_x11_mouse_refuses_non_x11_session_in_vm():
    """Inside a VM, it must still refuse if X11 display is missing."""
    with patch("accessos.engine.mouse_backend.can_use_real_mouse_injection", return_value=(True, "Inside VM")):
        with patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland", "DISPLAY": ""}):
            with pytest.raises(UnsupportedSessionError) as exc_info:
                X11Mouse(allow_host_override=True)
            assert "Wayland" in str(exc_info.value)


def test_mouse_screen_and_position_with_override():
    """When explicitly allowed (simulating VM), screen size and position query work."""
    with patch("accessos.engine.mouse_backend.can_use_real_mouse_injection", return_value=(True, "Simulated VM")):
        mouse = X11Mouse(allow_host_override=True)
        w, h = mouse.screen_size
        assert w > 0 and h > 0

        x, y = mouse.get_position()
        assert 0 <= x <= w
        assert 0 <= y <= h
        mouse.close()


def test_mouse_release_all_buttons():
    """Verify release_all_buttons() clears pressed buttons set and sends release events."""
    with patch("accessos.engine.mouse_backend.can_use_real_mouse_injection", return_value=(True, "Simulated VM")):
        mouse = X11Mouse(allow_host_override=True)
        mouse._pressed_buttons.add(1)
        mouse._pressed_buttons.add(2)
        mouse.release_all_buttons()
        assert len(mouse._pressed_buttons) == 0
        mouse.close()
