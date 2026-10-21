"""
AccessOS Dwell Clicker
=======================
Automates mouse clicks when the cursor hovers in place for a specified
duration. Includes visual progress callbacks, radius thresholds,
and refractory cooldown periods to prevent unwanted repeated clicks.
"""
from __future__ import annotations

import logging
import math
import time
from typing import Callable, Tuple

log = logging.getLogger(__name__)


class DwellClicker:
    """
    Detects dwell hover states and triggers clicks.

    Parameters:
      dwell_time_ms: hover time in milliseconds before clicking (e.g. 1000)
      radius_px: maximum movement radius in pixels to stay in dwell state
      cooldown_ms: refractory pause after a click before a new dwell begins
      on_progress: optional callback(progress: float, x: int, y: int)
      on_click: optional callback(x: int, y: int)
    """

    def __init__(
        self,
        dwell_time_ms: int = 1000,
        radius_px: int = 24,
        cooldown_ms: int = 600,
        on_progress: Callable[[float, int, int], None] | None = None,
        on_click: Callable[[int, int], None] | None = None,
    ) -> None:
        self.dwell_time_ms = dwell_time_ms
        self.radius_px = radius_px
        self.cooldown_ms = cooldown_ms
        self.on_progress = on_progress
        self.on_click = on_click

        self._enabled = True
        self._anchor_pos: Tuple[int, int] | None = None
        self._dwell_start_time: float | None = None
        self._last_click_time: float = -9999.0
        self._current_progress: float = 0.0

    @property
    def progress(self) -> float:
        return self._current_progress

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        if not enabled:
            self.reset()

    def set_dwell_time(self, ms: int) -> None:
        self.dwell_time_ms = max(300, min(5000, int(ms)))

    def reset(self) -> None:
        """Cancel active dwell progress."""
        self._anchor_pos = None
        self._dwell_start_time = None
        self._current_progress = 0.0
        if self.on_progress:
            try:
                self.on_progress(0.0, 0, 0)
            except Exception as exc:
                log.debug("on_progress error: %s", exc)

    def update(self, x: int, y: int, now: float | None = None) -> bool:
        """
        Process cursor position update. Returns True if a click was triggered.
        """
        if not self._enabled:
            return False

        t = time.monotonic() if now is None else now

        # Cooldown check after previous click
        if (t - self._last_click_time) * 1000 < self.cooldown_ms:
            self._anchor_pos = (x, y)
            self._dwell_start_time = t
            return False

        # If no anchor, start new dwell
        if self._anchor_pos is None:
            self._anchor_pos = (x, y)
            self._dwell_start_time = t
            self._current_progress = 0.0
            return False

        # Calculate distance from anchor
        ax, ay = self._anchor_pos
        dist = math.hypot(x - ax, y - ay)

        if dist > self.radius_px:
            # Moved outside dwell bubble — reset anchor
            self._anchor_pos = (x, y)
            self._dwell_start_time = t
            self._current_progress = 0.0
            if self.on_progress:
                self.on_progress(0.0, x, y)
            return False

        # Inside bubble — calculate progress
        assert self._dwell_start_time is not None
        elapsed_ms = (t - self._dwell_start_time) * 1000.0
        prog = min(1.0, elapsed_ms / self.dwell_time_ms)
        self._current_progress = prog

        if self.on_progress:
            self.on_progress(prog, x, y)

        if prog >= 1.0:
            # Dwell complete: Trigger click!
            log.info("Dwell click triggered at (%d, %d)", x, y)
            self._last_click_time = t
            self.reset()
            if self.on_click:
                try:
                    self.on_click(x, y)
                except Exception as exc:
                    log.error("on_click callback failed: %s", exc)
            return True

        return False
