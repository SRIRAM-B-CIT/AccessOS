"""
Tests for Deadzone, LowPassFilter, and OneEuroFilter
"""
from accessos.engine.filters import DeadzoneFilter, LowPassFilter, OneEuroFilter, PointFilter2D


def test_deadzone_suppression():
    dz = DeadzoneFilter(threshold=0.05)

    # Within deadzone -> (0.0, 0.0)
    assert dz.apply(0.01, 0.01) == (0.0, 0.0)
    assert dz.apply(-0.02, 0.03) == (0.0, 0.0)

    # Outside deadzone -> smoothly scaled non-zero vector
    out_x, out_y = dz.apply(0.1, 0.0)
    assert out_x > 0.0
    assert out_y == 0.0


def test_low_pass_filter():
    lpf = LowPassFilter(alpha=0.5)
    assert lpf.filter(10.0) == 10.0
    # Step input of 20 -> 0.5 * 20 + 0.5 * 10 = 15.0
    assert lpf.filter(20.0) == 15.0


def test_one_euro_filter():
    oef = OneEuroFilter(min_cutoff=1.0, beta=0.01)
    val1 = oef.filter(100.0, timestamp=1.0)
    assert val1 == 100.0

    # Slight perturbation filtered smoothly
    val2 = oef.filter(102.0, timestamp=1.033)
    assert 100.0 < val2 < 102.0


def test_point_filter_2d():
    pf = PointFilter2D(deadzone=0.02)
    sx, sy = pf.filter(500.0, 300.0, timestamp=1.0)
    assert sx == 500.0
    assert sy == 300.0
    pf.reset()
