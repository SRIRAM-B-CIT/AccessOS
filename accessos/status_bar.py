"""
AccessOS Status Bar
====================
A persistent horizontal strip shown at the bottom of the Home Screen that
displays live system state at a glance.

Phase 1 items displayed:
  Left  : input mode | active / paused state
  Centre: currently focused button label
  Right : camera state | mic state | battery | network | clock

Camera and mic show "OFF" in Phase 1 (enabled in Phase 3 / Phase 4).
Updates every 5 seconds via :func:`GLib.timeout_add`.
"""
from __future__ import annotations

import datetime
import logging
from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

log = logging.getLogger(__name__)

# ── Sysfs paths ───────────────────────────────────────────────────────────────
_BAT_CAP   = Path("/sys/class/power_supply/BAT0/capacity")
_BAT_STAT  = Path("/sys/class/power_supply/BAT0/status")
_NET_ROOT  = Path("/sys/class/net")

_UPDATE_INTERVAL_MS = 5_000   # 5 s


class StatusBar:
    """
    Builds and manages the status bar widget.

    Access the GTK widget via :attr:`widget` and embed it in a layout.
    """

    def __init__(self) -> None:
        self._paused       = False
        self._focused_name = ""
        self._build()
        self._update()
        GLib.timeout_add(_UPDATE_INTERVAL_MS, self._on_timer)

    # ── Public API ─────────────────────────────────────────────────────────────

    @property
    def widget(self) -> Gtk.Box:
        """The root GTK widget to embed in a layout."""
        return self._root

    def set_paused(self, paused: bool) -> None:
        """Update the active/paused state indicator."""
        self._paused = paused
        self._update_state()

    def set_focused_item(self, name: str) -> None:
        """Update the centre label with the currently focused button name."""
        self._focused_name = name
        self._lbl_focus.set_markup(
            f'<span color="#9fa8da" size="small">'
            f'Focus: <b>{GLib.markup_escape_text(name)}</b></span>'
            if name else ""
        )

    # ── Widget construction ────────────────────────────────────────────────────

    def _build(self) -> None:
        self._root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self._root.get_style_context().add_class("status-bar")

        # Left section
        left = Gtk.Box(spacing=10)
        self._lbl_mode  = self._make_label("")
        self._lbl_sep1  = self._make_sep()
        self._lbl_state = self._make_label("")
        left.pack_start(self._lbl_mode,  False, False, 0)
        left.pack_start(self._lbl_sep1,  False, False, 0)
        left.pack_start(self._lbl_state, False, False, 0)

        # Centre section (expands)
        centre = Gtk.Box()
        centre.set_hexpand(True)
        centre.set_halign(Gtk.Align.CENTER)
        self._lbl_focus = self._make_label("")
        centre.pack_start(self._lbl_focus, False, False, 0)

        # Right section
        right = Gtk.Box(spacing=10)
        right.set_halign(Gtk.Align.END)
        self._lbl_cam  = self._make_label("")
        self._lbl_mic  = self._make_label("")
        self._lbl_bat  = self._make_label("")
        self._lbl_net  = self._make_label("")
        self._lbl_time = self._make_label("")
        for lbl in (self._lbl_cam, self._make_sep(),
                    self._lbl_mic, self._make_sep(),
                    self._lbl_bat, self._make_sep(),
                    self._lbl_net, self._make_sep(),
                    self._lbl_time):
            right.pack_start(lbl, False, False, 0)

        self._root.pack_start(left,   False, False, 12)
        self._root.pack_start(centre, True,  True,  0)
        self._root.pack_end  (right,  False, False, 12)

    @staticmethod
    def _make_label(text: str) -> Gtk.Label:
        lbl = Gtk.Label(label=text)
        lbl.get_style_context().add_class("status-label")
        return lbl

    @staticmethod
    def _make_sep() -> Gtk.Label:
        sep = Gtk.Label(label="│")
        sep.get_style_context().add_class("status-separator")
        return sep

    # ── Update logic ───────────────────────────────────────────────────────────

    def _on_timer(self) -> bool:
        """Called by GLib every _UPDATE_INTERVAL_MS ms.  Return True to repeat."""
        self._update()
        return True

    def _update(self) -> None:
        self._update_state()
        self._update_static()
        self._update_battery()
        self._update_network()
        self._update_clock()

    def _update_state(self) -> None:
        self._lbl_mode.set_markup(
            '<span color="#9fa8da" size="small">⌨  Keyboard / Mouse</span>'
        )
        if self._paused:
            self._lbl_state.set_markup(
                '<span color="#ffd166" weight="bold" size="small">⏸  PAUSED</span>'
            )
        else:
            self._lbl_state.set_markup(
                '<span color="#4caf50" size="small">●  ACTIVE</span>'
            )

    def _update_static(self) -> None:
        """Items that never change in Phase 1."""
        self._lbl_cam.set_markup(
            '<span color="#606878" size="small">📷  Camera: OFF</span>'
        )
        self._lbl_mic.set_markup(
            '<span color="#606878" size="small">🎤  Mic: OFF</span>'
        )

    def _update_battery(self) -> None:
        try:
            cap    = int(_BAT_CAP.read_text().strip())
            status = _BAT_STAT.read_text().strip()

            if status == "Charging":
                icon, color = "⚡", "#ffd166"
            elif cap >= 50:
                icon, color = "🔋", "#4caf50"
            elif cap >= 20:
                icon, color = "🔋", "#ffd166"
            else:
                icon, color = "🪫", "#ff6b6b"

            self._lbl_bat.set_markup(
                f'<span color="{color}" size="small">{icon}  {cap}%</span>'
            )
        except Exception:
            self._lbl_bat.set_markup(
                '<span color="#606878" size="small">🔋  N/A</span>'
            )

    def _update_network(self) -> None:
        connected = False
        try:
            for iface_dir in _NET_ROOT.iterdir():
                if iface_dir.name.startswith("wl") or iface_dir.name.startswith("en"):
                    state = (iface_dir / "operstate").read_text().strip()
                    if state == "up":
                        connected = True
                        break
        except Exception:
            pass

        if connected:
            self._lbl_net.set_markup(
                '<span color="#4caf50" size="small">📶</span>'
            )
        else:
            self._lbl_net.set_markup(
                '<span color="#606878" size="small">📵</span>'
            )

    def _update_clock(self) -> None:
        now = datetime.datetime.now().strftime("%H:%M")
        self._lbl_time.set_markup(
            f'<span color="#9fa8da" size="small">{now}</span>'
        )
