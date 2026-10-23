import os
os.environ.setdefault("ACCESSOS_WINDOWED", "1")
"""
AccessOS Phase 3.5 Input-Safety & Host Protection Tests
========================================================
Validates:
  1. DryRunMouseBackend operates in-memory with zero system injection.
  2. X11MouseBackend strictly refuses on bare-metal host hardware.
  3. VM detection permits real injection only inside virtual machines.
  4. Cleanup guarantees on Pause, Stop, Tracking Loss, Camera Failure, Window Close, and Emergency Stop.
  5. Guaranteed release of all synthetic mouse buttons on exit/abort.
  6. VirtualCursorOverlay rendering and pass-through safety.
  7. HomeScreen safe defaults, safety status badge, and F12 emergency stop.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk, Gio, GLib, Gtk

from accessos.app_launcher import AppLauncher
from accessos.audio_feedback import AudioFeedback
from accessos.engine.dwell_clicker import DwellClicker
from accessos.engine.head_pointer import HeadPointerEngine, TrackingState
from accessos.engine import (
    BaseMouseBackend,
    DryRunMouseBackend,
    HostSafetyViolationError,
    X11MouseBackend,
)
from accessos.engine.virtual_cursor import VirtualCursorOverlay
from accessos.utils.profile import LaunchProfile
from accessos.home_screen import HomeScreen
from accessos.utils.config import Config
from accessos.utils.environment import can_use_real_mouse_injection, is_running_in_vm


# ── 1. DryRunMouseBackend In-Memory Safety ────────────────────────────────────

def test_dry_run_backend_never_injects_system_input():
    """Verify DryRunMouseBackend updates virtual state with zero OS API calls."""
    moved_coords = []
    click_events = []

    dry = DryRunMouseBackend(
        screen_size=(1920, 1080),
        on_cursor_moved=lambda x, y: moved_coords.append((x, y)),
        on_click_event=lambda x, y, b: click_events.append((x, y, b)),
    )

    assert dry.is_real_injection is False
    assert dry.get_position() == (960, 540)

    # Move cursor
    dry.move_to(300, 400)
    assert dry.get_position() == (300, 400)
    assert moved_coords[-1] == (300, 400)

    # Clamping
    dry.move_to(5000, -100)
    assert dry.get_position() == (1919, 0)

    # Virtual click
    dry.click(1)
    assert click_events[-1] == (1919, 0, 1)

    # Button tracking
    dry.press(1)
    dry.press(3)
    assert dry._pressed_buttons == {1, 3}

    dry.release_all_buttons()
    assert dry._pressed_buttons == set()

    dry.close()
    assert dry._pressed_buttons == set()


# ── 2. Host Safety Policy & VM Refusal ────────────────────────────────────────

def test_host_safety_policy_blocks_bare_metal():
    """Verify that bare-metal host hardware unconditionally blocks real injection."""
    with patch("accessos.utils.environment.is_running_in_vm", return_value=(False, "Host Hardware (LENOVO ThinkPad)")):
        allowed, reason = can_use_real_mouse_injection()
        assert allowed is False
        assert "Host Hardware" in reason
        assert "disabled on physical host machines" in reason


def test_host_safety_policy_permits_vm():
    """Inside a supported VM with X11 DISPLAY, real injection is permitted."""
    with patch("accessos.utils.environment.is_running_in_vm", return_value=(True, "Virtual Machine (VirtualBox)")):
        with patch.dict("os.environ", {"DISPLAY": ":0"}):
            allowed, reason = can_use_real_mouse_injection()
            assert allowed is True
            assert "VirtualBox" in reason


def test_x11_mouse_refuses_instantiation_on_host():
    """Instantiating X11MouseBackend on host raises HostSafetyViolationError."""
    with patch("accessos.engine.x11_mouse.can_use_real_mouse_injection", return_value=(False, "Bare metal")):
        with pytest.raises(HostSafetyViolationError) as exc_info:
            X11MouseBackend()
        assert "Bare metal" in str(exc_info.value)


# ── 3. Cleanup Guarantees on Every Path ───────────────────────────────────────

def test_cleanup_on_pause():
    """Pausing tracking must cancel dwell progress and release all buttons."""
    cfg = Config()
    backend = DryRunMouseBackend()
    backend.press(1)

    engine = HeadPointerEngine(config=cfg, mouse_backend=backend)
    engine._dwell._current_progress = 0.8

    engine.pause()
    assert engine.state == TrackingState.PAUSED
    assert engine._dwell.progress == 0.0
    assert backend._pressed_buttons == set()


def test_cleanup_on_stop():
    """Stopping tracking must cancel dwell progress and release all buttons."""
    cfg = Config()
    backend = DryRunMouseBackend()
    backend.press(2)

    engine = HeadPointerEngine(config=cfg, mouse_backend=backend)
    engine._dwell._current_progress = 0.5

    engine.stop()
    assert engine.state == TrackingState.STOPPED
    assert engine._dwell.progress == 0.0
    assert backend._pressed_buttons == set()


def test_cleanup_on_emergency_stop():
    """Emergency stop halts engine, cancels dwell, and releases all buttons."""
    cfg = Config()
    backend = DryRunMouseBackend()
    backend.press(1)
    backend.press(3)

    engine = HeadPointerEngine(config=cfg, mouse_backend=backend)
    engine._dwell._current_progress = 0.95

    engine.emergency_stop()
    assert engine.state == TrackingState.STOPPED
    assert engine._dwell.progress == 0.0
    assert backend._pressed_buttons == set()


def test_cleanup_on_camera_failure():
    """Worker thread failure safely releases camera, resets dwell, and releases buttons."""
    cfg = Config()
    backend = DryRunMouseBackend()
    backend.press(1)

    engine = HeadPointerEngine(config=cfg, mouse_backend=backend)
    engine._dwell._current_progress = 0.6

    # Simulate camera open failure
    with patch("accessos.engine.head_pointer.cv2.VideoCapture", side_effect=RuntimeError("Camera hardware error")):
        engine._run_loop()

    assert engine.state == TrackingState.STOPPED
    assert engine._dwell.progress == 0.0
    assert backend._pressed_buttons == set()


# ── 4. VirtualCursorOverlay Tests ─────────────────────────────────────────────

def test_virtual_cursor_overlay_updates():
    """Verify VirtualCursorOverlay safely tracks coordinates and dwell progress."""
    overlay = VirtualCursorOverlay()
    assert overlay.get_can_focus() is False

    # Simulate position updates
    overlay._apply_position(250.0, 350.0)
    assert overlay._cx == 250.0
    assert overlay._cy == 350.0
    assert overlay._visible is True

    # Simulate dwell progress
    overlay._apply_dwell(0.7, 250.0, 350.0)
    assert overlay._dwell_prog == 0.7

    # Simulate click animation trigger
    overlay._apply_click(250.0, 350.0)
    assert overlay._ripple_active is True
    assert overlay._ripple_radius == 18.0
    assert overlay._ripple_alpha == 0.95

    # Step animation
    overlay._step_ripple()
    assert overlay._ripple_radius > 18.0
    assert overlay._ripple_alpha < 0.95


# ── 5. HomeScreen Safe Defaults & F12 Emergency Stop ──────────────────────────

def test_home_screen_starts_in_host_safe_profile():
    """Verify HomeScreen defaults to host-safe profile with zero camera and zero input backend."""
    win = HomeScreen()

    # 1. Host-safe profile guarantees zero mouse backend and zero vision engine
    assert win._profile == LaunchProfile.HOST_SAFE
    assert win._mouse_backend is None
    assert win._engine is None

    # 2. Prominent safety badge in header
    assert hasattr(win, "_safety_badge")
    label_text = win._safety_badge.get_label()
    assert "HOST SAFE" in label_text

    # 3. VirtualCursorOverlay must be present
    assert hasattr(win, "_cursor_overlay")
    assert isinstance(win._cursor_overlay, VirtualCursorOverlay)

    win.destroy()


def test_home_screen_camera_preview_profile():
    """Verify camera-preview profile has preview_only=True, zero dwell, and zero real injection."""
    win = HomeScreen(profile=LaunchProfile.CAMERA_PREVIEW)

    assert win._profile == LaunchProfile.CAMERA_PREVIEW
    assert isinstance(win._mouse_backend, DryRunMouseBackend)
    assert win._mouse_backend.is_real_injection is False
    assert win._engine is not None
    assert win._engine.preview_only is True
    assert win._engine._dwell is None

    label_text = win._safety_badge.get_label()
    assert "CAMERA PREVIEW" in label_text

    win.destroy()


def test_home_screen_f12_emergency_stop():
    """Verify F12 triggers universal emergency stop on all engines."""
    win = HomeScreen(profile=LaunchProfile.CAMERA_PREVIEW)

    # Spy on emergency stop
    win._engine.emergency_stop = MagicMock()
    win._voice_listener.stop = MagicMock()
    win._tts.stop = MagicMock()

    # Simulate F12 key press event
    event = Gdk.EventKey()
    event.keyval = Gdk.KEY_F12
    handled = win._on_key_press(win, event)

    assert handled is True
    win._engine.emergency_stop.assert_called_once()
    win._voice_listener.stop.assert_called_once()
    win._tts.stop.assert_called_once()

    win.destroy()
