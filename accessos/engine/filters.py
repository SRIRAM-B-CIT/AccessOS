"""
AccessOS Cursor Filters & Smoothing
====================================
Jitter reduction, dead-zone suppression, and adaptive low-pass filtering
for head and eye tracking signals.
"""
from __future__ import annotations

import math
import time
from typing import Tuple


class DeadzoneFilter:
    """Suppresses micro-movements within a circular dead-zone radius."""

    def __init__(self, threshold: float = 0.02) -> None:
        self.threshold = threshold

    def apply(self, dx: float, dy: float) -> Tuple[float, float]:
        dist = math.hypot(dx, dy)
        if dist <= self.threshold:
            return (0.0, 0.0)
        # Rescale remaining vector smoothly starting from 0 at the boundary
        factor = (dist - self.threshold) / (1.0 - self.threshold) if self.threshold < 1.0 else 0.0
        scale = max(0.0, factor) / dist
        return (dx * scale, dy * scale)


class LowPassFilter:
    """Standard exponential moving average filter."""

    def __init__(self, alpha: float = 0.5) -> None:
        self.alpha = max(0.01, min(1.0, alpha))
        self._val: float | None = None

    def filter(self, val: float, alpha: float | None = None) -> float:
        a = self.alpha if alpha is None else alpha
        if self._val is None:
            self._val = val
        else:
            self._val = a * val + (1.0 - a) * self._val
        return self._val

    def reset(self) -> None:
        self._val = None


class OneEuroFilter:
    """
    One Euro Filter (Casiez et al., 2012).
    Adaptive 1st-order low-pass filter for interactive cursor control.
    Reduces jitter at low speed while avoiding lag during fast movement.
    """

    def __init__(
        self,
        min_cutoff: float = 1.0,
        beta: float = 0.007,
        d_cutoff: float = 1.0,
    ) -> None:
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff

        self._x_filter = LowPassFilter()
        self._dx_filter = LowPassFilter()
        self._last_time: float | None = None

    @staticmethod
    def _alpha(rate: float, cutoff: float) -> float:
        tau = 1.0 / (2.0 * math.pi * cutoff)
        te = 1.0 / rate if rate > 0 else 0.033
        return 1.0 / (1.0 + tau / te)

    def filter(self, val: float, timestamp: float | None = None) -> float:
        now = time.monotonic() if timestamp is None else timestamp

        if self._last_time is None or self._last_time >= now:
            rate = 30.0
        else:
            dt = now - self._last_time
            rate = 1.0 / dt if dt > 0 else 30.0
        self._last_time = now

        # Estimate derivative (speed of change)
        prev_x = self._x_filter._val
        dx = 0.0 if prev_x is None else (val - prev_x) * rate
        d_alpha = self._alpha(rate, self.d_cutoff)
        edx = self._dx_filter.filter(dx, d_alpha)

        # Dynamic cutoff frequency based on velocity
        cutoff = self.min_cutoff + self.beta * abs(edx)
        alpha = self._alpha(rate, cutoff)

        return self._x_filter.filter(val, alpha)

    def reset(self) -> None:
        self._x_filter.reset()
        self._dx_filter.reset()
        self._last_time = None


class PointFilter2D:
    """Applies independent One-Euro filters and dead-zones to 2D coordinates."""

    def __init__(
        self,
        deadzone: float = 0.015,
        min_cutoff: float = 1.2,
        beta: float = 0.01,
    ) -> None:
        self.deadzone_filter = DeadzoneFilter(threshold=deadzone)
        self.fx = OneEuroFilter(min_cutoff=min_cutoff, beta=beta)
        self.fy = OneEuroFilter(min_cutoff=min_cutoff, beta=beta)

    def filter(self, x: float, y: float, timestamp: float | None = None) -> Tuple[float, float]:
        sx = self.fx.filter(x, timestamp)
        sy = self.fy.filter(y, timestamp)
        return (sx, sy)

    def reset(self) -> None:
        self.fx.reset()
        self.fy.reset()
