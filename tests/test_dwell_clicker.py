"""
Tests for DwellClicker State Machine
"""
from accessos.engine.dwell_clicker import DwellClicker


def test_dwell_click_lifecycle():
    clicks = []
    progress_updates = []

    dwell = DwellClicker(
        dwell_time_ms=500,
        radius_px=20,
        cooldown_ms=200,
        on_progress=lambda p, x, y: progress_updates.append(p),
        on_click=lambda x, y: clicks.append((x, y)),
    )

    # Initial position at t = 0.0
    clicked = dwell.update(200, 200, now=0.0)
    assert clicked is False
    assert dwell.progress == 0.0

    # Stationary at t = 0.25 (50% progress)
    clicked = dwell.update(202, 201, now=0.25)
    assert clicked is False
    assert 0.4 <= dwell.progress <= 0.6

    # Stationary at t = 0.55 (>100% progress -> click!)
    clicked = dwell.update(201, 200, now=0.55)
    assert clicked is True
    assert len(clicks) == 1
    assert clicks[0] == (201, 200)

    # Immediate movement during cooldown does not trigger new dwell
    clicked = dwell.update(201, 200, now=0.60)
    assert clicked is False


def test_dwell_resets_on_large_movement():
    dwell = DwellClicker(dwell_time_ms=1000, radius_px=15)

    dwell.update(100, 100, now=0.0)
    dwell.update(102, 101, now=0.5)
    assert dwell.progress > 0.0

    # Sudden head jump across screen (> 50px away)
    dwell.update(300, 300, now=0.6)
    assert dwell.progress == 0.0
