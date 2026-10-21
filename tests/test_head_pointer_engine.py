"""
Tests for HeadPointerEngine States, Idempotent Pause, and Input-Safety Handling
"""
from unittest.mock import MagicMock, patch
from accessos.utils.config import Config
from accessos.engine.head_pointer import HeadPointerEngine, TrackingState
from accessos.engine.mouse_backend import DryRunMouseBackend, UnsupportedSessionError


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
    mock_backend = MagicMock(spec=DryRunMouseBackend)
    mock_backend.screen_size = (1280, 720)
    mock_backend.is_real_injection = False

    engine = HeadPointerEngine(config=cfg, mouse_backend=mock_backend)

    # Simulate camera open failure or unsupported session
    with patch("accessos.engine.head_pointer.cv2.VideoCapture", side_effect=UnsupportedSessionError("Unsupported session")):
        engine._run_loop()
        assert engine.state == TrackingState.STOPPED


def test_engine_cleanup_on_emergency_stop():
    cfg = Config()
    mock_backend = MagicMock(spec=DryRunMouseBackend)
    mock_backend.screen_size = (1280, 720)

    engine = HeadPointerEngine(config=cfg, mouse_backend=mock_backend)
    engine._dwell._current_progress = 0.75

    engine.emergency_stop()
    assert engine.state == TrackingState.STOPPED
    assert engine._dwell.progress == 0.0
    mock_backend.release_all_buttons.assert_called()
