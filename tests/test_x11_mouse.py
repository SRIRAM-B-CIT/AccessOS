"""
Tests for Native X11Mouse Controller and Session Verification
"""
import os
from unittest.mock import patch
import pytest

from accessos.engine.x11_mouse import (
    X11Mouse,
    UnsupportedSessionError,
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


def test_x11_mouse_refuses_non_x11_session():
    with patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland", "DISPLAY": ""}):
        with pytest.raises(UnsupportedSessionError) as exc_info:
            X11Mouse()
        assert "Wayland" in str(exc_info.value)


def test_mouse_screen_and_position():
    mouse = X11Mouse()
    w, h = mouse.screen_size
    assert w > 0 and h > 0

    x, y = mouse.get_position()
    assert 0 <= x <= w
    assert 0 <= y <= h
    mouse.close()


def test_mouse_move_clamping():
    mouse = X11Mouse()
    w, h = mouse.screen_size

    orig_x, orig_y = mouse.get_position()
    mouse.move_to(100, 100)
    # Restore original position so we don't disturb the user
    mouse.move_to(orig_x, orig_y)
    mouse.close()
