"""
Tests for Intentional Blink Detection and Experimental Eye Gaze Tracking
========================================================================
Validates:
  - Eye Aspect Ratio (EAR) computation
  - Involuntary blink rejection (< 200ms)
  - Deliberate selection click trigger (200ms - 800ms)
  - Cooldown debounce suppression
  - Gaze 5-point calibration workflow
  - Accuracy limitation disclaimers
  - Safety resets on pause and emergency stop
"""
from unittest.mock import MagicMock
from accessos.engine.blink_detector import BlinkDetector, BlinkState
from accessos.engine.gaze_tracker import GazeTracker, CALIBRATION_TARGETS
from accessos.engine.head_pointer import HeadPointerEngine, TrackingState
from accessos.engine.mouse_backend import DryRunMouseBackend
from accessos.utils.config import Config


class MockLandmark:
    def __init__(self, x: float, y: float, z: float = 0.0):
        self.x = x
        self.y = y
        self.z = z


def make_face_landmarks(eye_open_ratio: float = 0.30):
    """
    Generate synthetic 478 face landmarks with controlled eye openness.
    Higher eye_open_ratio -> eyes wide open. Lower -> eyes closed.
    """
    pts = [MockLandmark(0.5, 0.5) for _ in range(478)]

    # Left eye landmarks
    pts[33] = MockLandmark(0.35, 0.40)   # outer
    pts[133] = MockLandmark(0.45, 0.40)  # inner
    pts[160] = MockLandmark(0.40, 0.40 - eye_open_ratio * 0.05)
    pts[158] = MockLandmark(0.42, 0.40 - eye_open_ratio * 0.05)
    pts[144] = MockLandmark(0.40, 0.40 + eye_open_ratio * 0.05)
    pts[153] = MockLandmark(0.42, 0.40 + eye_open_ratio * 0.05)

    # Right eye landmarks
    pts[362] = MockLandmark(0.55, 0.40)  # inner
    pts[263] = MockLandmark(0.65, 0.40)  # outer
    pts[385] = MockLandmark(0.60, 0.40 - eye_open_ratio * 0.05)
    pts[387] = MockLandmark(0.62, 0.40 - eye_open_ratio * 0.05)
    pts[380] = MockLandmark(0.60, 0.40 + eye_open_ratio * 0.05)
    pts[373] = MockLandmark(0.62, 0.40 + eye_open_ratio * 0.05)

    # Iris landmarks
    pts[468] = MockLandmark(0.40, 0.40)  # Left iris
    pts[473] = MockLandmark(0.60, 0.40)  # Right iris

    # Lids
    pts[159] = MockLandmark(0.40, 0.38)
    pts[145] = MockLandmark(0.40, 0.42)
    pts[386] = MockLandmark(0.60, 0.38)
    pts[374] = MockLandmark(0.60, 0.42)

    return pts


# ── Blink Detector Tests ─────────────────────────────────────────────────────

def test_blink_detector_ear_open_vs_closed():
    detector = BlinkDetector(ear_threshold=0.20)

    open_landmarks = make_face_landmarks(eye_open_ratio=0.50)
    avg_ear_open, _, _ = detector.compute_ear(open_landmarks)
    assert avg_ear_open > 0.20, f"Expected open EAR > 0.20, got {avg_ear_open}"

    closed_landmarks = make_face_landmarks(eye_open_ratio=0.02)
    avg_ear_closed, _, _ = detector.compute_ear(closed_landmarks)
    assert avg_ear_closed < 0.20, f"Expected closed EAR < 0.20, got {avg_ear_closed}"


def test_involuntary_blink_ignored():
    """Blinks shorter than min_blink_ms (e.g. 100ms) must NOT trigger a click."""
    clicks = []
    detector = BlinkDetector(
        ear_threshold=0.20,
        min_blink_ms=200.0,
        max_blink_ms=800.0,
        on_blink=lambda d: clicks.append(d),
    )

    open_pts = make_face_landmarks(eye_open_ratio=0.50)
    closed_pts = make_face_landmarks(eye_open_ratio=0.02)

    t0 = 100.0
    detector.update(open_pts, now=t0)

    # Eyes close at t = 100.05
    st1 = detector.update(closed_pts, now=t0 + 0.05)
    assert st1.is_blinking is True
    assert st1.click_triggered is False

    # Eyes open at t = 100.15 (100ms duration -> natural involuntary blink)
    st2 = detector.update(open_pts, now=t0 + 0.15)
    assert st2.is_blinking is False
    assert st2.click_triggered is False
    assert len(clicks) == 0


def test_intentional_blink_triggers_click():
    """Blinks held between min_blink_ms (200ms) and max_blink_ms (800ms) trigger click."""
    clicks = []
    detector = BlinkDetector(
        ear_threshold=0.20,
        min_blink_ms=200.0,
        max_blink_ms=800.0,
        on_blink=lambda d: clicks.append(d),
    )

    open_pts = make_face_landmarks(eye_open_ratio=0.50)
    closed_pts = make_face_landmarks(eye_open_ratio=0.02)

    t0 = 100.0
    detector.update(open_pts, now=t0)

    # Eyes close at t = 100.05
    detector.update(closed_pts, now=t0 + 0.05)

    # Still closed at t = 100.35 (300ms hold -> intentional)
    st = detector.update(closed_pts, now=t0 + 0.35)
    assert st.intentional_hold is True

    # Eyes open at t = 100.40 (350ms duration)
    st_end = detector.update(open_pts, now=t0 + 0.40)
    assert st_end.click_triggered is True
    assert len(clicks) == 1
    assert 300.0 <= clicks[0] <= 400.0


def test_blink_cooldown_suppresses_rapid_double_clicks():
    """Clicks within cooldown window (600ms) are suppressed."""
    clicks = []
    detector = BlinkDetector(
        ear_threshold=0.20,
        min_blink_ms=200.0,
        max_blink_ms=800.0,
        cooldown_ms=600.0,
        on_blink=lambda d: clicks.append(d),
    )

    open_pts = make_face_landmarks(eye_open_ratio=0.50)
    closed_pts = make_face_landmarks(eye_open_ratio=0.02)

    # First deliberate blink
    t0 = 100.0
    detector.update(closed_pts, now=t0)
    detector.update(open_pts, now=t0 + 0.30)
    assert len(clicks) == 1

    # Second deliberate blink starting 200ms later (within 600ms cooldown)
    t1 = t0 + 0.50
    detector.update(closed_pts, now=t1)
    st = detector.update(open_pts, now=t1 + 0.30)
    assert st.click_triggered is False
    assert len(clicks) == 1  # Still 1, second was suppressed by cooldown


# ── Gaze Tracker Tests ───────────────────────────────────────────────────────

def test_gaze_tracker_disclaimer_and_targets():
    tracker = GazeTracker(screen_size=(1920, 1080))
    assert "experimental" in tracker.accuracy_warning.lower()
    assert len(CALIBRATION_TARGETS) == 5
    assert CALIBRATION_TARGETS[0].name == "Center"


def test_gaze_tracker_calibration_workflow():
    progress_calls = []
    completed = []

    tracker = GazeTracker(
        screen_size=(1920, 1080),
        on_calibration_progress=lambda c, t, n: progress_calls.append((c, t, n)),
        on_calibration_complete=lambda: completed.append(True),
    )

    tracker.start_calibration()
    assert tracker.is_calibrating is True
    assert tracker.is_calibrated is False
    assert len(progress_calls) == 1  # Announced Target 1 (Center)

    pts = make_face_landmarks(eye_open_ratio=0.50)

    # Feed 20 samples per target (5 targets * 20 = 100 samples)
    for _ in range(105):
        tracker.record_calibration_sample(pts)

    assert tracker.is_calibrated is True
    assert tracker.is_calibrating is False
    assert len(completed) == 1


def test_gaze_estimation_within_bounds():
    tracker = GazeTracker(screen_size=(1280, 720))
    pts = make_face_landmarks(eye_open_ratio=0.50)

    res = tracker.estimate_gaze(pts, timestamp=1.0)
    assert res is not None
    x, y, conf = res
    assert 0 <= x < 1280
    assert 0 <= y < 720
    assert 0.0 <= conf <= 1.0


# ── HeadPointerEngine Integration & Safety ────────────────────────────────────

def test_engine_blink_and_gaze_configuration():
    cfg = Config()
    backend = DryRunMouseBackend(screen_size=(1280, 720))
    engine = HeadPointerEngine(
        config=cfg,
        mouse_backend=backend,
        pointer_mode="combined",
        click_mode="both",
    )

    assert engine.pointer_mode == "combined"
    assert engine.click_mode == "both"
    assert engine.blink_detector is not None
    assert engine.gaze_tracker is not None


def test_engine_pause_resets_blink_and_dwell():
    cfg = Config()
    backend = DryRunMouseBackend()
    engine = HeadPointerEngine(config=cfg, mouse_backend=backend)

    # Set state as if tracking and mid-blink
    engine.blink_detector._is_blinking = True
    engine._dwell._current_progress = 0.8

    engine.pause()
    assert engine.state == TrackingState.PAUSED
    assert engine.blink_detector._is_blinking is False
    assert engine._dwell.progress == 0.0


def test_engine_emergency_stop_resets_all():
    cfg = Config()
    backend = DryRunMouseBackend()
    engine = HeadPointerEngine(config=cfg, mouse_backend=backend)

    engine.start_gaze_calibration()
    assert engine.gaze_tracker.is_calibrating is True

    engine.emergency_stop()
    assert engine.state == TrackingState.STOPPED
    assert engine.gaze_tracker.is_calibrating is False
    assert engine.blink_detector._is_blinking is False
