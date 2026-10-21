"""
Tests for HeadPointerEngine States and Calibration
"""
from accessos.utils.config import Config
from accessos.engine.head_pointer import HeadPointerEngine, TrackingState


def test_engine_state_transitions():
    cfg = Config()
    states = []

    engine = HeadPointerEngine(
        config=cfg,
        on_state_changed=lambda st, dt: states.append(st),
    )

    assert engine.state == TrackingState.STOPPED

    # Test pause and resume
    engine.pause()
    assert engine.state == TrackingState.PAUSED

    engine.resume()
    assert engine.state == TrackingState.TRACKING

    # Test calibrate resets flag
    engine._calibrated = True
    engine.calibrate()
    assert engine._calibrated is False

    engine.stop()
    assert engine.state == TrackingState.STOPPED
