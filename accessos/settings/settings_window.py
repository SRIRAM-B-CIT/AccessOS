"""
AccessOS Accessible Settings Window
====================================
Comprehensive settings application with full keyboard navigation,
large high-contrast touch targets, screen-reader annotations,
and explicit confirmation protection for all power/system operations.
"""
from __future__ import annotations

import logging
from typing import Any

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from ..utils.config import Config
from ..audio_feedback import AudioFeedback
from .camera_detector import CameraDetector, CameraDevice
from .system_control import SystemControl, WifiNetwork
from .confirm_dialog import ConfirmDialog

log = logging.getLogger(__name__)


class SettingsWindow(Gtk.Window):
    """AccessOS full system and accessibility settings interface."""

    def __init__(
        self,
        config: Config,
        audio: AudioFeedback,
        parent: Gtk.Window | None = None,
    ) -> None:
        super().__init__(
            title="AccessOS Settings",
            transient_for=parent,
            modal=True,
            destroy_with_parent=True,
        )
        self._config = config
        self._audio = audio
        self._camera_detector = CameraDetector()

        self.set_default_size(900, 620)
        self.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        self.get_style_context().add_class("settings-window")

        self._build_ui()
        self.connect("key-press-event", self._on_key_press)
        log.info("SettingsWindow initialized")

    # ── UI Construction ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(main_box)

        # ── Top Bar ────────────────────────────────────────────────────────────
        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        top_bar.get_style_context().add_class("settings-top-bar")
        top_bar.set_margin_start(20)
        top_bar.set_margin_end(20)
        top_bar.set_margin_top(16)
        top_bar.set_margin_bottom(16)

        # Back to Home button
        back_btn = Gtk.Button(label="←  Home")
        back_btn.get_style_context().add_class("btn-back")
        back_btn.set_tooltip_text("Return to AccessOS Home Screen (Esc)")
        back_btn.connect("clicked", lambda _: self.close())
        top_bar.pack_start(back_btn, False, False, 0)

        # Title
        title_lbl = Gtk.Label()
        title_lbl.set_markup('<span font="18" weight="bold">AccessOS Settings</span>')
        title_lbl.set_xalign(0.0)
        top_bar.pack_start(title_lbl, True, True, 0)

        main_box.pack_start(top_bar, False, False, 0)

        # ── Body (Sidebar + Content Stack) ─────────────────────────────────────
        body_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        main_box.pack_start(body_box, True, True, 0)

        # Sidebar navigation
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        sidebar.get_style_context().add_class("settings-sidebar")
        sidebar.set_size_request(240, -1)
        sidebar.set_margin_start(16)
        sidebar.set_margin_end(16)
        sidebar.set_margin_top(10)
        sidebar.set_margin_bottom(16)

        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._stack.set_transition_duration(150)
        self._stack.get_style_context().add_class("settings-content")

        # Sidebar buttons
        self._nav_buttons: list[Gtk.RadioButton] = []
        categories = [
            ("accessibility", "♿  Accessibility", self._build_accessibility_page),
            ("display",       "🖥️  Display &amp; Theme", self._build_display_page),
            ("sound",         "🔊  Sound &amp; Feedback", self._build_sound_page),
            ("camera",        "📷  Camera Input", self._build_camera_page),
            ("network",       "📶  Wi-Fi Network", self._build_network_page),
            ("system",        "⚙️  System &amp; Power", self._build_system_page),
        ]

        group = None
        for tag, label, page_builder in categories:
            page_widget = page_builder()
            self._stack.add_named(page_widget, tag)

            btn = Gtk.RadioButton.new_with_label_from_widget(group, label)
            btn.set_property("draw-indicator", False)
            btn.get_style_context().add_class("nav-tab-btn")
            btn.connect("toggled", self._on_tab_toggled, tag)
            if group is None:
                group = btn
                btn.set_active(True)
            sidebar.pack_start(btn, False, False, 0)
            self._nav_buttons.append(btn)

        body_box.pack_start(sidebar, False, False, 0)

        # Scrollable container for the stack
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.add(self._stack)
        body_box.pack_start(scrolled, True, True, 0)

    def _on_tab_toggled(self, btn: Gtk.RadioButton, tag: str) -> None:
        if btn.get_active():
            self._stack.set_visible_child_name(tag)
            self._audio.play("focus")

    # ── Page 1: Accessibility &amp; Input ──────────────────────────────────────────

    def _build_accessibility_page(self) -> Gtk.Widget:
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        page.set_margin_start(24)
        page.set_margin_end(24)
        page.set_margin_top(16)
        page.set_margin_bottom(24)

        # Section Title
        lbl = Gtk.Label()
        lbl.set_markup('<span font="16" weight="bold">Input Modality</span>')
        lbl.set_xalign(0.0)
        page.pack_start(lbl, False, False, 0)

        # Fallback guarantee banner
        banner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        banner.get_style_context().add_class("info-banner")
        info_icon = Gtk.Image.new_from_icon_name("emblem-default", Gtk.IconSize.LARGE_TOOLBAR)
        banner.pack_start(info_icon, False, False, 0)
        info_txt = Gtk.Label(
            label="Keyboard and mouse input are permanently active as guaranteed fallbacks across all modes."
        )
        info_txt.set_line_wrap(True)
        info_txt.set_xalign(0.0)
        banner.pack_start(info_txt, True, True, 0)
        page.pack_start(banner, False, False, 0)

        current_mode = self._config.get("accessibility", "mode", default="keyboard_mouse")

        modes = [
            ("keyboard_mouse", "⌨️ 🖱️ Standard Keyboard &amp; Mouse (Active)", "Traditional input with high-visibility focus"),
            ("head_pointer",   "👤 Head Pointer Tracking (Phase 3)", "Control pointer via head movements and webcam"),
            ("dwell_selection","⏱️ Dwell Selection (Phase 3)", "Hover pointer to click automatically without buttons"),
            ("voice_control",  "🎙️ Voice Control (Phase 4)", "Control AccessOS via offline Vosk speech recognition"),
        ]

        m_group = None
        for key, name, desc in modes:
            rbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            rbtn = Gtk.RadioButton.new_with_label_from_widget(m_group, name)
            if m_group is None:
                m_group = rbtn
            if key == current_mode:
                rbtn.set_active(True)
            rbtn.connect("toggled", self._on_mode_toggled, key)
            rbox.pack_start(rbtn, False, False, 0)

            sub_lbl = Gtk.Label()
            sub_lbl.set_markup(f'<span color="#8b949e" font="10">{desc}</span>')
            sub_lbl.set_xalign(0.0)
            sub_lbl.set_margin_start(24)
            rbox.pack_start(sub_lbl, False, False, 0)
            page.pack_start(rbox, False, False, 0)

        # Dwell Time Slider
        dwell_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        dwell_lbl = Gtk.Label()
        current_dwell = self._config.get("accessibility", "dwell_time_ms", default=1000)
        dwell_lbl.set_markup(f'<b>Dwell Click Delay:</b> <span color="#4f9eff">{current_dwell} ms</span>')
        dwell_lbl.set_xalign(0.0)
        dwell_box.pack_start(dwell_lbl, False, False, 0)

        dwell_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 500, 3000, 100)
        dwell_scale.set_value(float(current_dwell))
        dwell_scale.set_digits(0)
        dwell_scale.connect("value-changed", self._on_dwell_changed, dwell_lbl)
        dwell_box.pack_start(dwell_scale, False, False, 0)
        page.pack_start(dwell_box, False, False, 0)

        # Head Pointer Sensitivity
        sens_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        sens_lbl = Gtk.Label()
        current_sens = self._config.get("accessibility", "head_sensitivity", default=0.5)
        sens_lbl.set_markup(f'<b>Head Tracking Sensitivity:</b> <span color="#4f9eff">{current_sens:.1f}</span>')
        sens_lbl.set_xalign(0.0)
        sens_box.pack_start(sens_lbl, False, False, 0)

        sens_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.1, 1.0, 0.1)
        sens_scale.set_value(float(current_sens))
        sens_scale.connect("value-changed", self._on_sens_changed, sens_lbl)
        sens_box.pack_start(sens_scale, False, False, 0)
        page.pack_start(sens_box, False, False, 0)

        return page

    def _on_mode_toggled(self, btn: Gtk.RadioButton, mode_key: str) -> None:
        if btn.get_active():
            log.info("Accessibility mode changed: %s", mode_key)
            self._config.set("accessibility", "mode", value=mode_key)
            self._config.save()
            self._audio.play("activate")

    def _on_dwell_changed(self, scale: Gtk.Scale, lbl: Gtk.Label) -> None:
        val = int(scale.get_value())
        lbl.set_markup(f'<b>Dwell Click Delay:</b> <span color="#4f9eff">{val} ms</span>')
        self._config.set("accessibility", "dwell_time_ms", value=val)
        self._config.save()

    def _on_sens_changed(self, scale: Gtk.Scale, lbl: Gtk.Label) -> None:
        val = round(scale.get_value(), 2)
        lbl.set_markup(f'<b>Head Tracking Sensitivity:</b> <span color="#4f9eff">{val:.1f}</span>')
        self._config.set("accessibility", "head_sensitivity", value=val)
        self._config.save()

    # ── Page 2: Display &amp; Theme ────────────────────────────────────────────────

    def _build_display_page(self) -> Gtk.Widget:
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        page.set_margin_start(24)
        page.set_margin_end(24)
        page.set_margin_top(16)
        page.set_margin_bottom(24)

        # Title
        lbl = Gtk.Label()
        lbl.set_markup('<span font="16" weight="bold">Display &amp; High-Contrast Theme</span>')
        lbl.set_xalign(0.0)
        page.pack_start(lbl, False, False, 0)

        # Font Size Selector
        font_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        font_lbl = Gtk.Label()
        font_lbl.set_markup("<b>Interface Font Scaling:</b>")
        font_lbl.set_xalign(0.0)
        font_box.pack_start(font_lbl, False, False, 0)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        cur_font = self._config.get("theme", "font_size", default=18)
        sizes = [(14, "Normal (14px)"), (18, "Large (18px)"), (22, "Extra (22px)"), (26, "Maximum (26px)")]

        f_group = None
        for sz, label in sizes:
            f_btn = Gtk.RadioButton.new_with_label_from_widget(f_group, label)
            if f_group is None:
                f_group = f_btn
            if sz == cur_font:
                f_btn.set_active(True)
            f_btn.connect("toggled", self._on_font_size_toggled, sz)
            btn_box.pack_start(f_btn, False, False, 0)

        font_box.pack_start(btn_box, False, False, 0)
        page.pack_start(font_box, False, False, 0)

        # High Contrast Switch
        contrast_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        contrast_lbl = Gtk.Label()
        contrast_lbl.set_markup("<b>High Contrast Dark Mode</b>\n<span color='#8b949e' font='10'>Deep charcoal canvas with electric blue accessible outlines</span>")
        contrast_lbl.set_xalign(0.0)
        contrast_box.pack_start(contrast_lbl, True, True, 0)

        contrast_sw = Gtk.Switch()
        contrast_sw.set_active(self._config.get("theme", "high_contrast", default=True))
        contrast_sw.connect("notify::active", self._on_contrast_toggled)
        contrast_box.pack_start(contrast_sw, False, False, 0)
        page.pack_start(contrast_box, False, False, 0)

        # Brightness Control
        bright_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        bright_lbl = Gtk.Label()
        cur_bright = self._config.get("theme", "brightness", default=100)
        bright_lbl.set_markup(f'<b>Screen Brightness:</b> <span color="#4f9eff">{cur_bright}%</span>')
        bright_lbl.set_xalign(0.0)
        bright_box.pack_start(bright_lbl, False, False, 0)

        bright_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 10, 100, 5)
        bright_scale.set_value(float(cur_bright))
        bright_scale.connect("value-changed", self._on_brightness_changed, bright_lbl)
        bright_box.pack_start(bright_scale, False, False, 0)
        page.pack_start(bright_box, False, False, 0)

        return page

    def _on_font_size_toggled(self, btn: Gtk.RadioButton, sz: int) -> None:
        if btn.get_active():
            self._config.set("theme", "font_size", value=sz)
            self._config.save()
            self._audio.play("activate")

    def _on_contrast_toggled(self, sw: Gtk.Switch, _param) -> None:
        val = sw.get_active()
        self._config.set("theme", "high_contrast", value=val)
        self._config.save()
        self._audio.play("activate")

    def _on_brightness_changed(self, scale: Gtk.Scale, lbl: Gtk.Label) -> None:
        val = int(scale.get_value())
        lbl.set_markup(f'<b>Screen Brightness:</b> <span color="#4f9eff">{val}%</span>')
        self._config.set("theme", "brightness", value=val)
        self._config.save()
        SystemControl.set_brightness(val)

    # ── Page 3: Sound &amp; Feedback ───────────────────────────────────────────────

    def _build_sound_page(self) -> Gtk.Widget:
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        page.set_margin_start(24)
        page.set_margin_end(24)
        page.set_margin_top(16)
        page.set_margin_bottom(24)

        lbl = Gtk.Label()
        lbl.set_markup('<span font="16" weight="bold">Audio &amp; Feedback Controls</span>')
        lbl.set_xalign(0.0)
        page.pack_start(lbl, False, False, 0)

        # Master System Volume
        vol_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        cur_vol = SystemControl.get_volume()
        vol_lbl = Gtk.Label()
        vol_lbl.set_markup(f'<b>Master Volume:</b> <span color="#4f9eff">{cur_vol}%</span>')
        vol_lbl.set_xalign(0.0)
        vol_box.pack_start(vol_lbl, False, False, 0)

        vol_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 5)
        vol_scale.set_value(float(cur_vol))
        vol_scale.connect("value-changed", self._on_volume_changed, vol_lbl)
        vol_box.pack_start(vol_scale, False, False, 0)
        page.pack_start(vol_box, False, False, 0)

        # Audio Feedback Earcons Switch
        snd_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        snd_lbl = Gtk.Label()
        snd_lbl.set_markup("<b>Navigation Audio Feedback</b>\n<span color='#8b949e' font='10'>Play subtle sine-wave clicks on focus changes and activation</span>")
        snd_lbl.set_xalign(0.0)
        snd_box.pack_start(snd_lbl, True, True, 0)

        snd_sw = Gtk.Switch()
        snd_sw.set_active(self._config.get("audio", "sounds_enabled", default=True))
        snd_sw.connect("notify::active", self._on_sounds_toggled)
        snd_box.pack_start(snd_sw, False, False, 0)
        page.pack_start(snd_box, False, False, 0)

        # Piper Speech TTS status (Phase 4)
        tts_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        tts_box.get_style_context().add_class("status-card")
        tts_icon = Gtk.Image.new_from_icon_name("audio-speakers", Gtk.IconSize.LARGE_TOOLBAR)
        tts_box.pack_start(tts_icon, False, False, 0)
        tts_info = Gtk.Label()
        tts_info.set_markup("<b>Piper Offline TTS:</b> <span color='#ffd700'>Scheduled for Phase 4</span>\n<span color='#8b949e' font='10'>No network connection or API keys required. Currently dormant for lightweight operation.</span>")
        tts_info.set_xalign(0.0)
        tts_box.pack_start(tts_info, True, True, 0)
        page.pack_start(tts_box, False, False, 0)

        return page

    def _on_volume_changed(self, scale: Gtk.Scale, lbl: Gtk.Label) -> None:
        val = int(scale.get_value())
        lbl.set_markup(f'<b>Master Volume:</b> <span color="#4f9eff">{val}%</span>')
        self._config.set("audio", "volume", value=val)
        self._config.save()
        SystemControl.set_volume(val)

    def _on_sounds_toggled(self, sw: Gtk.Switch, _param) -> None:
        val = sw.get_active()
        self._config.set("audio", "sounds_enabled", value=val)
        self._config.save()
        self._audio.set_enabled(val)
        if val:
            self._audio.play("activate")

    # ── Page 4: Camera Selection ───────────────────────────────────────────────

    def _build_camera_page(self) -> Gtk.Widget:
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        page.set_margin_start(24)
        page.set_margin_end(24)
        page.set_margin_top(16)
        page.set_margin_bottom(24)

        lbl = Gtk.Label()
        lbl.set_markup('<span font="16" weight="bold">Camera Hardware Selection</span>')
        lbl.set_xalign(0.0)
        page.pack_start(lbl, False, False, 0)

        # Safety notice
        notice = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        notice.get_style_context().add_class("info-banner")
        icon = Gtk.Image.new_from_icon_name("security-high", Gtk.IconSize.LARGE_TOOLBAR)
        notice.pack_start(icon, False, False, 0)
        ntxt = Gtk.Label(
            label="Camera hardware is detected safely via sysfs. No video streams or camera frames are accessed until Phase 3 head tracking is enabled."
        )
        ntxt.set_line_wrap(True)
        ntxt.set_xalign(0.0)
        notice.pack_start(ntxt, True, True, 0)
        page.pack_start(notice, False, False, 0)

        # Detected Cameras list
        cameras = self._camera_detector.detect_cameras()
        saved_device = self._config.get("camera", "device", default="/dev/video2")

        c_group = None
        for cam in cameras:
            cbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            cbox.get_style_context().add_class("camera-card")
            cbox.set_margin_top(4)
            cbox.set_margin_bottom(4)

            # Device title with recommendation badge
            badge = " <span color='#4f9eff' weight='bold'>[RECOMMENDED RGB WEBCAM]</span>" if cam.is_recommended else ""
            if cam.is_ir:
                badge = " <span color='#f85149'>[IR SENSOR - NOT RECOMMENDED]</span>"

            rbtn = Gtk.RadioButton.new_with_label_from_widget(c_group, f"{cam.device_node} — {cam.name}")
            if c_group is None:
                c_group = rbtn
            if cam.device_node == saved_device:
                rbtn.set_active(True)
            rbtn.connect("toggled", self._on_camera_toggled, cam)
            cbox.pack_start(rbtn, False, False, 0)

            # Description
            desc_lbl = Gtk.Label()
            desc_lbl.set_markup(f'<span color="#8b949e" font="10">{cam.description}{badge}</span>')
            desc_lbl.set_xalign(0.0)
            desc_lbl.set_margin_start(24)
            cbox.pack_start(desc_lbl, False, False, 0)

            page.pack_start(cbox, False, False, 0)

        return page

    def _on_camera_toggled(self, btn: Gtk.RadioButton, cam: CameraDevice) -> None:
        if btn.get_active():
            log.info("Selected camera device: %s (%s)", cam.device_node, cam.name)
            self._config.set("camera", "device", value=cam.device_node)
            self._config.set("camera", "model", value=cam.name)
            self._config.save()
            self._audio.play("activate")

    # ── Page 5: Wi-Fi &amp; Network ────────────────────────────────────────────────

    def _build_network_page(self) -> Gtk.Widget:
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        page.set_margin_start(24)
        page.set_margin_end(24)
        page.set_margin_top(16)
        page.set_margin_bottom(24)

        # Header with toggle
        hdr_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        lbl = Gtk.Label()
        lbl.set_markup('<span font="16" weight="bold">Wi-Fi Network</span>')
        lbl.set_xalign(0.0)
        hdr_box.pack_start(lbl, True, True, 0)

        wifi_sw = Gtk.Switch()
        wifi_sw.set_active(SystemControl.is_wifi_enabled())
        wifi_sw.connect("notify::active", self._on_wifi_toggled)
        hdr_box.pack_start(wifi_sw, False, False, 0)
        page.pack_start(hdr_box, False, False, 0)

        # Network list
        self._wifi_list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._populate_wifi_networks()
        page.pack_start(self._wifi_list_box, True, True, 0)

        # Refresh button
        ref_btn = Gtk.Button(label="🔄  Scan for Networks")
        ref_btn.connect("clicked", lambda _: self._populate_wifi_networks())
        page.pack_start(ref_btn, False, False, 0)

        return page

    def _populate_wifi_networks(self) -> None:
        # Clear existing
        for child in self._wifi_list_box.get_children():
            self._wifi_list_box.remove(child)

        networks = SystemControl.list_wifi_networks()
        if not networks:
            empty_lbl = Gtk.Label(label="No Wi-Fi networks found or Wi-Fi radio is off.")
            empty_lbl.set_xalign(0.0)
            self._wifi_list_box.pack_start(empty_lbl, False, False, 0)
            self._wifi_list_box.show_all()
            return

        for net in networks[:8]:  # show top 8
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            row.get_style_context().add_class("network-row")

            # Icon
            icon_name = "network-wireless-signal-excellent-symbolic" if net.signal > 70 else "network-wireless-signal-good-symbolic"
            w_icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.LARGE_TOOLBAR)
            row.pack_start(w_icon, False, False, 0)

            # SSID and security
            status_tag = " <span color='#3fb950' weight='bold'>[CONNECTED]</span>" if net.in_use else ""
            txt_lbl = Gtk.Label()
            txt_lbl.set_markup(f"<b>{net.ssid}</b>{status_tag}\n<span color='#8b949e' font='10'>{net.security} · Signal: {net.signal}%</span>")
            txt_lbl.set_xalign(0.0)
            row.pack_start(txt_lbl, True, True, 0)

            # Connect button if not currently in use
            if not net.in_use:
                c_btn = Gtk.Button(label="Connect")
                c_btn.connect("clicked", self._on_connect_clicked, net.ssid, net.security)
                row.pack_start(c_btn, False, False, 0)

            self._wifi_list_box.pack_start(row, False, False, 0)

        self._wifi_list_box.show_all()

    def _on_wifi_toggled(self, sw: Gtk.Switch, _param) -> None:
        enabled = sw.get_active()
        SystemControl.set_wifi_enabled(enabled)
        self._config.set("network", "wifi_enabled", value=enabled)
        self._config.save()
        GLib.timeout_add(1000, lambda: self._populate_wifi_networks() or False)

    def _on_connect_clicked(self, _btn: Gtk.Button, ssid: str, security: str) -> None:
        password = None
        if "WPA" in security or "WEP" in security:
            # Show simple password entry dialog
            dlg = Gtk.Dialog(
                title=f"Connect to {ssid}",
                transient_for=self,
                modal=True,
            )
            dlg.set_default_size(360, 160)
            box = dlg.get_content_area()
            box.set_spacing(10)
            box.set_margin_start(16)
            box.set_margin_end(16)
            box.set_margin_top(16)

            plbl = Gtk.Label(label=f"Enter password for '{ssid}':")
            plbl.set_xalign(0.0)
            box.pack_start(plbl, False, False, 0)

            entry = Gtk.Entry()
            entry.set_visibility(False)
            box.pack_start(entry, False, False, 0)

            dlg.add_button("Cancel", Gtk.ResponseType.CANCEL)
            dlg.add_button("Connect", Gtk.ResponseType.OK)
            dlg.show_all()

            if dlg.run() == Gtk.ResponseType.OK:
                password = entry.get_text()
            dlg.destroy()

        if password is not None or "Open" in security:
            ok, msg = SystemControl.connect_wifi(ssid, password)
            self._audio.play("activate" if ok else "error")
            self._populate_wifi_networks()

    # ── Page 6: System &amp; Power ─────────────────────────────────────────────────

    def _build_system_page(self) -> Gtk.Widget:
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        page.set_margin_start(24)
        page.set_margin_end(24)
        page.set_margin_top(16)
        page.set_margin_bottom(24)

        lbl = Gtk.Label()
        lbl.set_markup('<span font="16" weight="bold">System Maintenance &amp; Session Controls</span>')
        lbl.set_xalign(0.0)
        page.pack_start(lbl, False, False, 0)

        # Restore Factory Defaults card
        def_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        def_card.get_style_context().add_class("settings-card")
        def_card.set_margin_top(6)
        def_card.set_margin_bottom(6)

        dtitle = Gtk.Label()
        dtitle.set_markup("<b>Restore AccessOS Defaults</b>")
        dtitle.set_xalign(0.0)
        def_card.pack_start(dtitle, False, False, 0)

        ddesc = Gtk.Label(
            label="Safely restore theme, dwell delay, volume, and input configuration back to the factory defaults."
        )
        ddesc.set_xalign(0.0)
        ddesc.set_line_wrap(True)
        def_card.pack_start(ddesc, False, False, 0)

        reset_btn = Gtk.Button(label="↺  Restore Defaults")
        reset_btn.get_style_context().add_class("btn-warning")
        reset_btn.connect("clicked", self._on_restore_defaults_clicked)
        def_card.pack_start(reset_btn, False, False, 0)
        page.pack_start(def_card, False, False, 0)

        # Protected Power Actions Header
        p_hdr = Gtk.Label()
        p_hdr.set_markup("<b>Protected Power Actions</b>\n<span color='#8b949e' font='10'>Every power action requires an explicit confirmation step before executing.</span>")
        p_hdr.set_xalign(0.0)
        page.pack_start(p_hdr, False, False, 0)

        # Power actions buttons
        btn_grid = Gtk.Grid()
        btn_grid.set_column_spacing(14)
        btn_grid.set_row_spacing(10)

        # 1. Lock
        lock_btn = Gtk.Button(label="🔒  Lock Session")
        lock_btn.get_style_context().add_class("pwr-action-btn")
        lock_btn.connect("clicked", self._on_lock_clicked)
        btn_grid.attach(lock_btn, 0, 0, 1, 1)

        # 2. Restart
        restart_btn = Gtk.Button(label="🔄  Restart Computer")
        restart_btn.get_style_context().add_class("pwr-action-btn")
        restart_btn.connect("clicked", self._on_restart_clicked)
        btn_grid.attach(restart_btn, 1, 0, 1, 1)

        # 3. Power Off
        poweroff_btn = Gtk.Button(label="⏻  Shut Down")
        poweroff_btn.get_style_context().add_class("pwr-action-btn-danger")
        poweroff_btn.connect("clicked", self._on_poweroff_clicked)
        btn_grid.attach(poweroff_btn, 2, 0, 1, 1)

        page.pack_start(btn_grid, False, False, 0)

        return page

    # ── Power & Defaults Handlers ──────────────────────────────────────────────

    def _on_restore_defaults_clicked(self, _btn: Gtk.Button) -> None:
        confirmed = ConfirmDialog.ask(
            parent=self,
            title="Restore Defaults",
            message="Are you sure you want to restore all AccessOS settings to factory defaults?",
            detail="Your current dwell delay, contrast theme, volume, and camera selections will be reset.",
            confirm_label="Restore Defaults",
            is_destructive=False,
        )
        if confirmed:
            self._config.restore_defaults()
            self._audio.play("activate")
            log.info("Settings restored to factory defaults by user")
            # Close and reopen or reload current tab
            self.close()

    def _on_lock_clicked(self, _btn: Gtk.Button) -> None:
        confirmed = ConfirmDialog.ask(
            parent=self,
            title="Lock Session",
            message="Lock AccessOS session now?",
            detail="You will need to enter your password or accessibility unlock to resume.",
            confirm_label="Lock Now",
            is_destructive=False,
        )
        if confirmed:
            SystemControl.lock_session()

    def _on_restart_clicked(self, _btn: Gtk.Button) -> None:
        confirmed = ConfirmDialog.ask(
            parent=self,
            title="Restart AccessOS",
            message="Are you sure you want to restart your computer?",
            detail="All open applications will close and unsaved data will be lost.",
            confirm_label="Restart Now",
            is_destructive=True,
        )
        if confirmed:
            SystemControl.restart_system()

    def _on_poweroff_clicked(self, _btn: Gtk.Button) -> None:
        confirmed = ConfirmDialog.ask(
            parent=self,
            title="Shut Down AccessOS",
            message="Are you sure you want to shut down your computer?",
            detail="All running programs will terminate and the system will power off.",
            confirm_label="Shut Down Now",
            is_destructive=True,
        )
        if confirmed:
            SystemControl.poweroff_system()

    # ── Keyboard Handling ──────────────────────────────────────────────────────

    def _on_key_press(self, _widget: Gtk.Widget, event: Gdk.EventKey) -> bool:
        if event.keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False
