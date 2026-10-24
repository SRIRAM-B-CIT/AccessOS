"""
AccessOS Virtual Cursor Overlay
================================
Draws a smooth, high-contrast virtual pointer reticle, dwell progress ring,
click ripple animations, deliberate blink feedback, and eye-gaze calibration targets
directly inside the AccessOS window.

Key Safety Feature:
  Confined 100% inside the AccessOS window.
  Does NOT call any OS-level input injection or grab host input.
  Overlay pass-through allows physical mouse clicks and keyboard focus
  to pass through to underlying widgets unimpeded.
"""
from __future__ import annotations

import logging
import math
from typing import Optional, Tuple

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

log = logging.getLogger(__name__)


class VirtualCursorOverlay(Gtk.DrawingArea):
    """
    Transparent visual cursor overlay layer for safe host dry-run mode.
    Renders pointer position, dwell accumulation ring, click pulse,
    deliberate blink feedback, and gaze calibration targets.
    """

    def __init__(self) -> None:
        super().__init__()
        self.set_name("virtual-cursor-overlay")
        self.set_can_focus(False)

        self._cx: float = -100.0
        self._cy: float = -100.0
        self._visible: bool = False
        self._dwell_prog: float = 0.0

        # Click ripple animation state (dwell)
        self._ripple_active: bool = False
        self._ripple_x: float = 0.0
        self._ripple_y: float = 0.0
        self._ripple_radius: float = 16.0
        self._ripple_alpha: float = 0.0
        self._ripple_timer_id: Optional[int] = None

        # Blink click ripple state
        self._blink_active: bool = False
        self._blink_x: float = 0.0
        self._blink_y: float = 0.0
        self._blink_radius: float = 12.0
        self._blink_alpha: float = 0.0
        self._blink_timer_id: Optional[int] = None

        # Gaze calibration target state
        self._calib_target: Optional[Tuple[float, float, str]] = None

        self.connect("draw", self._on_draw)

    def set_active(self, active: bool) -> None:
        """Enable or disable rendering of the virtual cursor."""
        GLib.idle_add(self._apply_active, active)

    def _apply_active(self, active: bool) -> bool:
        self._visible = active
        if not active:
            self._dwell_prog = 0.0
        self.queue_draw()
        return False

    def update_position(self, x: int, y: int) -> None:
        """Update virtual cursor coordinates (thread-safe)."""
        GLib.idle_add(self._apply_position, float(x), float(y))

    def _apply_position(self, x: float, y: float) -> bool:
        self._cx = x
        self._cy = y
        self._visible = True
        self.queue_draw()
        return False

    def update_dwell_progress(self, progress: float, x: int, y: int) -> None:
        """Update dwell progress [0.0 .. 1.0] (thread-safe)."""
        GLib.idle_add(self._apply_dwell, float(progress), float(x), float(y))

    def _apply_dwell(self, progress: float, x: float, y: float) -> bool:
        self._dwell_prog = max(0.0, min(1.0, progress))
        if x > 0 and y > 0:
            self._cx = x
            self._cy = y
        self.queue_draw()
        return False

    def trigger_click(self, x: int, y: int) -> None:
        """Trigger expanding ripple click animation (thread-safe)."""
        GLib.idle_add(self._apply_click, float(x), float(y))

    def _apply_click(self, x: float, y: float) -> bool:
        self._ripple_active = True
        self._ripple_x = x
        self._ripple_y = y
        self._ripple_radius = 18.0
        self._ripple_alpha = 0.95
        self._dwell_prog = 0.0

        if self._ripple_timer_id is None:
            self._ripple_timer_id = GLib.timeout_add(16, self._step_ripple)

        self.queue_draw()
        return False

    def _step_ripple(self) -> bool:
        self._ripple_radius += 2.5
        self._ripple_alpha -= 0.06

        if self._ripple_alpha <= 0.0:
            self._ripple_active = False
            self._ripple_timer_id = None
            self.queue_draw()
            return False

        self.queue_draw()
        return True

    def trigger_blink_click(self, x: int, y: int) -> None:
        """Trigger distinct deliberate blink click animation (thread-safe)."""
        GLib.idle_add(self._apply_blink_click, float(x), float(y))

    def _apply_blink_click(self, x: float, y: float) -> bool:
        self._blink_active = True
        self._blink_x = x
        self._blink_y = y
        self._blink_radius = 14.0
        self._blink_alpha = 1.0
        self._dwell_prog = 0.0

        if self._blink_timer_id is None:
            self._blink_timer_id = GLib.timeout_add(16, self._step_blink)

        self.queue_draw()
        return False

    def _step_blink(self) -> bool:
        self._blink_radius += 3.2
        self._blink_alpha -= 0.05

        if self._blink_alpha <= 0.0:
            self._blink_active = False
            self._blink_timer_id = None
            self.queue_draw()
            return False

        self.queue_draw()
        return True

    def set_calibration_target(self, norm_x: float, norm_y: float, label: str) -> None:
        """Display a guided gaze calibration target on the overlay."""
        GLib.idle_add(self._apply_calibration_target, norm_x, norm_y, label)

    def _apply_calibration_target(self, norm_x: float, norm_y: float, label: str) -> bool:
        self._calib_target = (norm_x, norm_y, label)
        self.queue_draw()
        return False

    def clear_calibration_target(self) -> None:
        """Clear gaze calibration target."""
        GLib.idle_add(self._apply_clear_calibration_target)

    def _apply_clear_calibration_target(self) -> bool:
        self._calib_target = None
        self.queue_draw()
        return False

    def _on_draw(self, _widget: Gtk.Widget, cr) -> bool:
        alloc = self.get_allocation()
        win_w, win_h = alloc.width, alloc.height

        # ── 0. Gaze Calibration Target (if active) ──
        if self._calib_target is not None:
            nx, ny, label = self._calib_target
            tx = nx * win_w
            ty = ny * win_h

            cr.save()
            # Outer pulsing ring
            cr.set_line_width(4.0)
            cr.set_source_rgba(1.0, 0.8, 0.0, 0.85)  # Gold
            cr.arc(tx, ty, 32.0, 0.0, 2.0 * math.pi)
            cr.stroke()

            # Inner bullseye ring
            cr.set_line_width(2.5)
            cr.set_source_rgba(0.0, 0.85, 1.0, 0.95)  # Cyan
            cr.arc(tx, ty, 16.0, 0.0, 2.0 * math.pi)
            cr.stroke()

            # Center focal dot
            cr.set_source_rgba(1.0, 1.0, 1.0, 1.0)
            cr.arc(tx, ty, 5.0, 0.0, 2.0 * math.pi)
            cr.fill()

            # Crosshairs
            cr.set_line_width(2.0)
            cr.set_source_rgba(1.0, 0.8, 0.0, 0.9)
            cr.move_to(tx - 40, ty)
            cr.line_to(tx - 34, ty)
            cr.move_to(tx + 34, ty)
            cr.line_to(tx + 40, ty)
            cr.move_to(tx, ty - 40)
            cr.line_to(tx, ty - 34)
            cr.move_to(tx, ty + 34)
            cr.line_to(tx, ty + 40)
            cr.stroke()

            # Label banner
            cr.select_font_face("Sans", 0, 1)
            cr.set_font_size(14.0)
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.95)
            cr.move_to(tx - 50, ty + 50)
            cr.show_text(f"Look here: {label}")
            cr.restore()

        if not self._visible or self._cx < 0 or self._cy < 0:
            return False

        cx, cy = self._cx, self._cy

        # ── 1. Reticle Outer Ring ──
        cr.save()
        cr.set_line_width(2.5)
        cr.set_source_rgba(0.31, 0.62, 1.0, 0.85)  # #4f9eff
        cr.arc(cx, cy, 18.0, 0.0, 2.0 * math.pi)
        cr.stroke()

        # ── 2. Center Target Dot ──
        cr.set_source_rgba(1.0, 1.0, 1.0, 1.0)
        cr.arc(cx, cy, 3.5, 0.0, 2.0 * math.pi)
        cr.fill()

        # Crosshairs ticks
        cr.set_line_width(1.5)
        cr.set_source_rgba(0.31, 0.62, 1.0, 0.6)
        cr.move_to(cx - 24, cy)
        cr.line_to(cx - 19, cy)
        cr.move_to(cx + 19, cy)
        cr.line_to(cx + 24, cy)
        cr.move_to(cx, cy - 24)
        cr.line_to(cx, cy - 19)
        cr.move_to(cx, cy + 19)
        cr.line_to(cx, cy + 24)
        cr.stroke()
        cr.restore()

        # ── 3. Dwell Progress Arc ──
        if self._dwell_prog > 0.0:
            cr.save()
            cr.set_line_width(3.5)
            # Interpolate from amber (0.0) to emerald green (1.0)
            r = 1.0 - (0.75 * self._dwell_prog)
            g = 0.84 + (0.16 * self._dwell_prog)
            b = 0.0
            cr.set_source_rgba(r, g, b, 0.95)

            start_angle = -math.pi / 2.0
            end_angle = start_angle + (self._dwell_prog * 2.0 * math.pi)
            cr.arc(cx, cy, 23.0, start_angle, end_angle)
            cr.stroke()
            cr.restore()

        # ── 4. Click Ripple Wave (Dwell) ──
        if self._ripple_active and self._ripple_alpha > 0.0:
            cr.save()
            cr.set_line_width(3.0)
            cr.set_source_rgba(0.0, 1.0, 0.8, self._ripple_alpha)
            cr.arc(self._ripple_x, self._ripple_y, self._ripple_radius, 0.0, 2.0 * math.pi)
            cr.stroke()
            cr.restore()

        # ── 5. Blink Click Ripple Wave (Teal / Purple distinct double ripple) ──
        if self._blink_active and self._blink_alpha > 0.0:
            cr.save()
            cr.set_line_width(3.5)
            cr.set_source_rgba(0.0, 0.9, 1.0, self._blink_alpha)
            cr.arc(self._blink_x, self._blink_y, self._blink_radius, 0.0, 2.0 * math.pi)
            cr.stroke()
            # Secondary ring
            if self._blink_radius > 18:
                cr.set_line_width(2.0)
                cr.set_source_rgba(0.8, 0.4, 1.0, self._blink_alpha * 0.7)
                cr.arc(self._blink_x, self._blink_y, self._blink_radius - 8, 0.0, 2.0 * math.pi)
                cr.stroke()
            cr.restore()

        return False
