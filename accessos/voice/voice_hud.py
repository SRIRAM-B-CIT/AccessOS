"""
AccessOS Voice HUD & Status Indicator
======================================
Compact, high-contrast visual status badge displaying real-time
microphone state (Active, Muted, Awaiting Confirmation, Off)
and last recognized command text toast.
"""
from __future__ import annotations

import logging
from typing import Callable, Optional

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

from .voice_listener import VoiceState

log = logging.getLogger(__name__)


class VoiceHUD(Gtk.Box):
    """Voice status badge and quick microphone mute toggle."""

    def __init__(
        self,
        on_toggle_mute: Optional[Callable[[], None]] = None,
        on_toggle_voice: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.on_toggle_mute = on_toggle_mute
        self.on_toggle_voice = on_toggle_voice

        self.get_style_context().add_class("voice-hud")
        self._build_ui()

    def _build_ui(self) -> None:
        # Status Pill Badge
        self._pill = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._pill.get_style_context().add_class("status-pill")
        self._pill.get_style_context().add_class("voice-off")

        self._icon_lbl = Gtk.Label(label="🎙️")
        self._status_lbl = Gtk.Label()
        self._status_lbl.set_markup("<b>Voice: OFF</b>")

        self._pill.pack_start(self._icon_lbl, False, False, 4)
        self._pill.pack_start(self._status_lbl, False, False, 4)
        self.pack_start(self._pill, False, False, 0)

        # Last Command Toast (auto-clearing text)
        self._cmd_lbl = Gtk.Label()
        self._cmd_lbl.set_markup("<span color='#8b949e' font='10'></span>")
        self.pack_start(self._cmd_lbl, False, False, 4)

        # Mute Button (M)
        self._mute_btn = Gtk.Button(label="Mute (M)")
        self._mute_btn.get_style_context().add_class("overlay-btn")
        self._mute_btn.set_tooltip_text("Mute or unmute microphone (M)")
        if self.on_toggle_mute:
            self._mute_btn.connect("clicked", lambda _: self.on_toggle_mute())
        self.pack_start(self._mute_btn, False, False, 0)

    # ── Thread-Safe Update Methods (via GLib) ─────────────────────────────────

    def update_state(self, state: VoiceState, detail: str = "") -> None:
        GLib.idle_add(self._apply_state, state, detail)

    def _apply_state(self, state: VoiceState, detail: str) -> bool:
        style = self._pill.get_style_context()
        for cls in ["voice-active", "voice-muted", "voice-waiting", "voice-off", "voice-error"]:
            style.remove_class(cls)

        if state == VoiceState.LISTENING:
            style.add_class("voice-active")
            self._icon_lbl.set_text("🎙️")
            self._status_lbl.set_markup("<b>LISTENING</b>")
            self._mute_btn.set_sensitive(True)
            self._mute_btn.set_label("Mute (M)")
        elif state == VoiceState.MUTED:
            style.add_class("voice-muted")
            self._icon_lbl.set_text("🔇")
            self._status_lbl.set_markup("<b>MIC MUTED (M)</b>")
            self._mute_btn.set_sensitive(True)
            self._mute_btn.set_label("Unmute (M)")
        elif state == VoiceState.AWAITING_CONFIRMATION:
            style.add_class("voice-waiting")
            self._icon_lbl.set_text("⚠️")
            self._status_lbl.set_markup("<b>AWAITING CONFIRMATION</b>")
            self._mute_btn.set_sensitive(True)
        elif state == VoiceState.ERROR:
            style.add_class("voice-error")
            self._icon_lbl.set_text("❌")
            self._status_lbl.set_markup("<b>MIC UNAVAILABLE</b>")
            self._mute_btn.set_sensitive(False)
        else:
            style.add_class("voice-off")
            self._icon_lbl.set_text("🎙️")
            self._status_lbl.set_markup("<b>Voice: OFF</b>")
            self._mute_btn.set_sensitive(False)

        return False

    def show_command_toast(self, cmd_name: str) -> None:
        GLib.idle_add(self._apply_cmd_toast, cmd_name)

    def _apply_cmd_toast(self, cmd_name: str) -> bool:
        esc_name = GLib.markup_escape_text(cmd_name)
        self._cmd_lbl.set_markup(f"<span color='#4f9eff' font='10'>✓ &quot;{esc_name}&quot;</span>")
        GLib.timeout_add(3000, self._clear_toast)
        return False

    def _clear_toast(self) -> bool:
        self._cmd_lbl.set_markup("")
        return False
