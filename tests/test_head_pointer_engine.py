"""
Tests for HeadPointerEngine States, Idempotent Pause, and Non-X11 Session Handling
"""
from unittest.mock import patch
from accessos.utils.config import Config
from accessos.engine.head_pointer import HeadPointerEngine, TrackingState
from accessos.engine.x11_mouse import UnsupportedSessionError


def test_engine_idempotent_pause_behavior():
    cfg = Config()
    states = []

    engine = HeadPointerEngine(
        config=cfg,
        on_state_changed=lambda st, dt: states.append(st),
    )

    # Initial state
    assert engine.state == TrackingState.STOPPED

    # First pause -> PAUSED
    engine.pause()
    assert engine.state == TrackingState.PAUSED

    # IDEMPOTENCY CHECK: Repeated calls to pause() MUST NEVER resume or toggle
    engine.pause()
    assert engine.state == TrackingState.PAUSED

    engine.pause()
    assert engine.state == TrackingState.PAUSED

    # Only explicit resume() restores tracking
    engine.resume()
    assert engine.state == TrackingState.TRACKING

    engine.stop()
    assert engine.state == TrackingState.STOPPED


def test_engine_handles_unsupported_session_safely():
    cfg = Config()
    engine = HeadPointerEngine(config=cfg)

    # Mock X11Mouse to raise UnsupportedSessionError
    with patch("accessos.engine.head_pointer.X11Mouse", side_effect=UnsupportedSessionError("Wayland not supported")):
        engine._run_loop()
        assert engine.state == TrackingState.STOPPED
