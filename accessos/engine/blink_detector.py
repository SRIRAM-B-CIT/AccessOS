"""
AccessOS Intentional Blink Detection Engine
============================================
Detects voluntary, deliberate eye blinks as an accessible selection method.
Distinguishes intentional selection blinks (200ms–600ms hold) from
involuntary, natural blinks (80ms–150ms).

Safety & Invariants:
  - Does NOT generate OS-level events directly.
  - Fires callbacks and updates virtual state.
  - Includes refractory cooldown to prevent accidental repeated clicks.
"""
from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Tuple

log = logging.getLogger(__name__)

# MediaPipe landmark indices for Eye Aspect Ratio (EAR) computation
# Left Eye
_L_CORNER_OUTER = 33
_L_CORNER_INNER = 133
_L_UPPER_1      = 160
_L_UPPER_2      = 158
_L_LOWER_1      = 144
_L_LOWER_2      = 153

# Right Eye
_R_CORNER_OUTER = 362
_R_CORNER_INNER = 263
_R_UPPER_1      = 385
_R_UPPER_2      = 387
_R_LOWER_1      = 380
_R_LOWER_2      = 373


@dataclass
class BlinkState:
    is_blinking: bool          # Eyes are currently closed below threshold
    ear: float                  # Current average Eye Aspect Ratio
    duration_ms: float          # Current closure duration in milliseconds
    intentional_hold: bool      # Duration has reached intentional threshold
    click_triggered: bool       # Selection click was triggered on this update


class BlinkDetector:
    """
    Computes Eye Aspect Ratio (EAR) from face landmarks and identifies
    deliberate selection blinks.
    """

    def __init__(
        self,
        ear_threshold: float = 0.20,
        min_blink_ms: float = 200.0,
        max_blink_ms: float = 800.0,
        cooldown_ms: float = 600.0,
        on_blink: Optional[Callable[[float], None]] = None,
    ) -> None:
        self.ear_threshold = ear_threshold
        self.min_blink_ms = min_blink_ms
        self.max_blink_ms = max_blink_ms
        self.cooldown_ms = cooldown_ms
        self.on_blink = on_blink

        self._blink_start_time: Optional[float] = None
        self._last_click_time: float = -9999.0
        self._is_blinking: bool = False
        self._intentional_announced: bool = False

    def reset(self) -> None:
        """Reset blink state tracking."""
        self._blink_start_time = None
        self._is_blinking = False
        self._intentional_announced = False

    @staticmethod
    def _dist(p1: Any, p2: Any) -> float:
        return math.hypot(p1.x - p2.x, p1.y - p2.y)

    def compute_ear(self, landmarks: List[Any]) -> Tuple[float, float, float]:
        """
        Compute Eye Aspect Ratio for left, right, and average.
        Returns: (avg_ear, left_ear, right_ear)
        """
        if len(landmarks) < 468:
            return 0.3, 0.3, 0.3

        try:
            # Left EAR
            l_v1 = self._dist(landmarks[_L_UPPER_1], landmarks[_L_LOWER_1])
            l_v2 = self._dist(landmarks[_L_UPPER_2], landmarks[_L_LOWER_2])
            l_h  = self._dist(landmarks[_L_CORNER_OUTER], landmarks[_L_CORNER_INNER])
            l_ear = (l_v1 + l_v2) / (2.0 * max(1e-6, l_h))

            # Right EAR
            r_v1 = self._dist(landmarks[_R_UPPER_1], landmarks[_R_LOWER_1])
            r_v2 = self._dist(landmarks[_R_UPPER_2], landmarks[_R_LOWER_2])
            r_h  = self._dist(landmarks[_R_CORNER_OUTER], landmarks[_R_CORNER_INNER])
            r_ear = (r_v1 + r_v2) / (2.0 * max(1e-6, r_h))

            avg_ear = (l_ear + r_ear) / 2.0
            return avg_ear, l_ear, r_ear
        except Exception as exc:
            log.debug("Error computing EAR: %s", exc)
            return 0.3, 0.3, 0.3

    def update(self, landmarks: List[Any], now: Optional[float] = None) -> BlinkState:
        """
        Update with new video frame landmarks and evaluate deliberate blink click.
        """
        t = time.monotonic() if now is None else now
        avg_ear, _, _ = self.compute_ear(landmarks)

        click_triggered = False
        duration_ms = 0.0
        intentional_hold = False

        if avg_ear < self.ear_threshold:
            # Eyes closed
            if not self._is_blinking:
                self._is_blinking = True
                self._blink_start_time = t
                self._intentional_announced = False
            else:
                assert self._blink_start_time is not None
                duration_ms = (t - self._blink_start_time) * 1000.0
                if duration_ms >= self.min_blink_ms and duration_ms <= self.max_blink_ms:
                    intentional_hold = True
                    if not self._intentional_announced:
                        self._intentional_announced = True
                        log.debug("Intentional blink hold reached: %.1f ms", duration_ms)
        else:
            # Eyes open
            if self._is_blinking and self._blink_start_time is not None:
                duration_ms = (t - self._blink_start_time) * 1000.0
                # Deliberate selection check
                if self.min_blink_ms <= duration_ms <= self.max_blink_ms:
                    cooldown_elapsed = (t - self._last_click_time) * 1000.0
                    if cooldown_elapsed >= self.cooldown_ms:
                        log.info("Deliberate blink click confirmed! (duration: %.1f ms)", duration_ms)
                        click_triggered = True
                        self._last_click_time = t
                        if self.on_blink:
                            try:
                                self.on_blink(duration_ms)
                            except Exception as exc:
                                log.error("on_blink callback error: %s", exc)
                    else:
                        log.debug("Blink click suppressed by cooldown (%.1f ms < %.1f ms)", cooldown_elapsed, self.cooldown_ms)
                elif duration_ms < self.min_blink_ms:
                    log.debug("Natural involuntary blink ignored (%.1f ms < %.1f ms)", duration_ms, self.min_blink_ms)
                else:
                    log.debug("Prolonged eye closure ignored (%.1f ms > %.1f ms)", duration_ms, self.max_blink_ms)

                self._is_blinking = False
                self._blink_start_time = None
                self._intentional_announced = False

        return BlinkState(
            is_blinking=self._is_blinking,
            ear=avg_ear,
            duration_ms=duration_ms,
            intentional_hold=intentional_hold,
            click_triggered=click_triggered,
        )
