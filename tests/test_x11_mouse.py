"""
Tests for Native X11Mouse Controller, Safety Boundaries, and Session Verification
"""
import os
from unittest.mock import MagicMock, patch
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
    with patch("accessos.engine.x11_mouse.can_use_real_mouse_injection", return_value=(False, "Blocked on host")):
        with pytest.raises(HostSafetyViolationError) as exc_info:
            X11Mouse(allow_host_override=False)
        assert "Blocked on host" in str(exc_info.value)


def test_x11_mouse_refuses_non_x11_session_in_vm():
    """Inside a VM, it must still refuse if X11 display is missing."""
    with patch("accessos.engine.x11_mouse.can_use_real_mouse_injection", return_value=(True, "Inside VM")):
        with patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland", "DISPLAY": ""}):
            with pytest.raises(UnsupportedSessionError) as exc_info:
                X11Mouse(allow_host_override=True)
            assert "Wayland" in str(exc_info.value)


def test_mouse_screen_and_position_with_mocked_x11():
    """When simulating VM, screen size and position query work with mocked X11."""
    fake_x11 = MagicMock()
    fake_x11.XOpenDisplay.return_value = 12345
    fake_x11.XDefaultRootWindow.return_value = 1
    fake_x11.XDisplayWidth.return_value = 1920
    fake_x11.XDisplayHeight.return_value = 1080
    fake_x11.XQueryPointer.return_value = 1

    fake_xtst = MagicMock()

    def fake_cdll(path):
        if "X11" in path:
            return fake_x11
        return fake_xtst

    with patch("accessos.engine.x11_mouse.can_use_real_mouse_injection", return_value=(True, "Simulated VM")), \
         patch("ctypes.CDLL", side_effect=fake_cdll), \
         patch("ctypes.util.find_library", side_effect=lambda lib: f"/mock/lib/{lib}.so"):

        mouse = X11Mouse(allow_host_override=True)
        w, h = mouse.screen_size
        assert (w, h) == (1920, 1080)

        pos = mouse.get_position()
        assert isinstance(pos, tuple)
        mouse.close()


def test_mouse_release_all_buttons_mocked():
    """Verify release_all_buttons() clears pressed buttons set and invokes mock xtst release."""
    fake_x11 = MagicMock()
    fake_x11.XOpenDisplay.return_value = 12345
    fake_x11.XDefaultRootWindow.return_value = 1
    fake_x11.XDisplayWidth.return_value = 1920
    fake_x11.XDisplayHeight.return_value = 1080

    fake_xtst = MagicMock()

    def fake_cdll(path):
        if "X11" in path:
            return fake_x11
        return fake_xtst

    with patch("accessos.engine.x11_mouse.can_use_real_mouse_injection", return_value=(True, "Simulated VM")), \
         patch("ctypes.CDLL", side_effect=fake_cdll), \
         patch("ctypes.util.find_library", side_effect=lambda lib: f"/mock/lib/{lib}.so"):

        mouse = X11Mouse(allow_host_override=True)
        mouse._pressed_buttons.add(1)
        mouse._pressed_buttons.add(2)
        mouse.release_all_buttons()
        assert len(mouse._pressed_buttons) == 0
        assert fake_xtst.XTestFakeButtonEvent.called
        mouse.close()
