"""
AccessOS Tracking Status & Control Overlay
==========================================
A high-contrast visual HUD displaying real-time head-pointer state,
FPS, latency, dwell click progress, and quick calibration/pause controls.
"""
from __future__ import annotations

import logging
from typing import Callable

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from .head_pointer import TrackingState

log = logging.getLogger(__name__)


class TrackingOverlay(Gtk.Box):
    """
    Visual HUD component showing live head-pointer state & dwell progress.
    Can be placed in the header, floating overlay, or status bar.
    """

    def __init__(
        self,
        on_calibrate: Callable[[], None] | None = None,
        on_toggle_pause: Callable[[], None] | None = None,
        on_stop: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.on_calibrate = on_calibrate
        self.on_toggle_pause = on_toggle_pause
        self.on_stop = on_stop

        self.get_style_context().add_class("tracking-overlay")
        self._build_ui()

    def _build_ui(self) -> None:
        # Status Badge Pill
        self._status_badge = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._status_badge.get_style_context().add_class("status-pill")

        self._status_icon = Gtk.Label(label="⚪")
        self._status_label = Gtk.Label()
        self._status_label.set_markup("<b>Camera: OFF</b>")
        self._status_badge.pack_start(self._status_icon, False, False, 4)
        self._status_badge.pack_start(self._status_label, False, False, 4)
        self.pack_start(self._status_badge, False, False, 0)

        # Dwell progress bar
        self._dwell_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._dwell_lbl = Gtk.Label()
        self._dwell_lbl.set_markup("<span font='10' color='#8b949e'>Dwell:</span>")
        self._dwell_bar = Gtk.ProgressBar()
        self._dwell_bar.set_fraction(0.0)
        self._dwell_bar.set_size_request(90, 14)
        self._dwell_box.pack_start(self._dwell_lbl, False, False, 0)
        self._dwell_box.pack_start(self._dwell_bar, False, False, 0)
        self.pack_start(self._dwell_box, False, False, 0)

        # Telemetry info
        self._metrics_lbl = Gtk.Label()
        self._metrics_lbl.set_markup("<span color='#8b949e' font='10'>-- FPS</span>")
        self.pack_start(self._metrics_lbl, False, False, 0)

        # Quick Calibrate Button (C)
        self._calib_btn = Gtk.Button(label="🎯 Center (C)")
        self._calib_btn.get_style_context().add_class("overlay-btn")
        self._calib_btn.set_tooltip_text("Calibrate head position to screen center (C)")
        if self.on_calibrate:
            self._calib_btn.connect("clicked", lambda _: self.on_calibrate())
        self.pack_start(self._calib_btn, False, False, 0)

    # ── Update Methods (Thread-safe via GLib) ─────────────────────────────────

    def update_state(self, state: TrackingState, detail: str = "") -> None:
        GLib.idle_add(self._apply_state, state, detail)

    def _apply_state(self, state: TrackingState, detail: str) -> bool:
        style = self._status_badge.get_style_context()
        for cls in ["state-active", "state-lost", "state-paused", "state-off"]:
            style.remove_class(cls)

        if state == TrackingState.TRACKING:
            style.add_class("state-active")
            self._status_icon.set_text("🟢")
            self._status_label.set_markup("<b>HEAD TRACKING ACTIVE</b>")
        elif state == TrackingState.LOST:
            style.add_class("state-lost")
            self._status_icon.set_text("🟡")
            self._status_label.set_markup("<b>TRACKING LOST · KEYBOARD/MOUSE ACTIVE</b>")
        elif state == TrackingState.PAUSED:
            style.add_class("state-paused")
            self._status_icon.set_text("⏸")
            self._status_label.set_markup("<b>CONTROL PAUSED (Esc)</b>")
        else:
            style.add_class("state-off")
            self._status_icon.set_text("⚪")
            self._status_label.set_markup("<b>Camera: OFF</b>")

        return False

    def update_metrics(self, fps: float, latency_ms: float) -> None:
        GLib.idle_add(self._apply_metrics, fps, latency_ms)

    def _apply_metrics(self, fps: float, latency_ms: float) -> bool:
        self._metrics_lbl.set_markup(f"<span color='#8b949e' font='10'>{fps:.0f} FPS · {latency_ms:.0f}ms</span>")
        return False

    def update_dwell_progress(self, progress: float) -> None:
        GLib.idle_add(self._apply_dwell, progress)

    def _apply_dwell(self, progress: float) -> bool:
        self._dwell_bar.set_fraction(max(0.0, min(1.0, progress)))
        return False
