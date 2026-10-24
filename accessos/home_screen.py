"""
AccessOS Primary Home Screen
=============================
Presents the accessible live environment with a centered macOS-style
bottom dock as the primary application launcher.

Features:
  - Centered macOS-style bottom dock with 6 primary applications:
      1. 🌐 Browser   (Firefox)
      2. 📁 Files     (Thunar)
      3. 💻 Terminal  (XFCE Terminal)
      4. ⚙️ Settings  (AccessOS Settings)
      5. 🖼️ Images    (Ristretto)
      6. 🎬 Videos    (Parole)
  - Full keyboard navigation:
      <Left> / <Right>  : cycle through dock items (with wrap-around)
      <Home> / <End>    : jump to first / last dock item
      <1> - <6>         : instant number shortcut for each dock item
      <Enter> / <Space> : activate focused dock item
      <Esc>             : pause / resume accessibility control
  - Prominent high-contrast focus outlines (4px #4f9eff)
  - Dynamic listener for settings changes (updates status bar live)
  - Protected power menu in top header
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk

from .app_launcher import AppLauncher
from .audio_feedback import AudioFeedback
from .power_menu import PowerMenu
from .status_bar import StatusBar
from .utils.config import Config
from .settings import SettingsWindow, ConfirmDialog, SystemControl
from .voice import TTSEngine, VoiceListener, VoiceState, VoiceHUD, CommandAction
from .engine import HeadPointerEngine, TrackingState, TrackingOverlay, DryRunMouseBackend, VirtualCursorOverlay, check_session_supported
from .utils.profile import LaunchProfile, resolve_profile
from .utils.build_info import get_build_info

log = logging.getLogger(__name__)

_HERE = Path(__file__).parent
_CSS  = _HERE / "style.css"

# ── Primary 6 Dock Applications ────────────────────────────────────────────────
_DOCK_ITEMS = [
    {
        "key":   "browser",
        "label": "Browser",
        "icon":  "web-browser",
        "desc":  "Open web browser (1)",
    },
    {
        "key":   "files",
        "label": "Files",
        "icon":  "system-file-manager",
        "desc":  "Browse files (2)",
    },
    {
        "key":   "terminal",
        "label": "Terminal",
        "icon":  "utilities-terminal",
        "desc":  "Open terminal (3)",
    },
    {
        "key":   "settings",
        "label": "Settings",
        "icon":  "preferences-system",
        "desc":  "AccessOS settings (4)",
    },
    {
        "key":   "images",
        "label": "Images",
        "icon":  "image-x-generic",
        "desc":  "View images (5)",
    },
    {
        "key":   "videos",
        "label": "Videos",
        "icon":  "video-x-generic",
        "desc":  "Play videos (6)",
    },
]

_ICON_PX = 58
_ERROR_HIDE_MS = 5000


class HomeScreen(Gtk.ApplicationWindow):
    """AccessOS Primary Desktop Window with Centered macOS-Style Dock."""

    def __init__(
        self,
        app: Gtk.Application | None = None,
        config: Config | None = None,
        launcher: AppLauncher | None = None,
        audio: AudioFeedback | None = None,
        profile: LaunchProfile | None = None,
    ) -> None:
        super().__init__(application=app)
        self._config   = config or Config()
        self._launcher = launcher or AppLauncher()
        self._audio    = audio or AudioFeedback(enabled=False)
        self._profile  = profile or resolve_profile()
        self._paused   = False

        self._dock_btns: list[Gtk.Button] = []
        self._focus_idx = 0

        log.info("HomeScreen initializing under profile: %s", self._profile.value)

        # Profile-driven engine and mouse backend setup
        if self._profile == LaunchProfile.HOST_SAFE:
            self._mouse_backend = None
            self._engine = None
        elif self._profile == LaunchProfile.CAMERA_PREVIEW:
            self._mouse_backend = DryRunMouseBackend(
                screen_size=(1280, 720),
                on_cursor_moved=self._on_cursor_moved,
                on_click_event=self._on_virtual_click,
            )
            self._engine = HeadPointerEngine(
                config=self._config,
                mouse_backend=self._mouse_backend,
                preview_only=True,
                on_state_changed=self._on_tracking_state_changed,
                on_metrics_updated=self._on_tracking_metrics,
                on_dwell_progress=self._on_dwell_progress,
                on_click=self._on_dwell_click,
            )
        elif self._profile == LaunchProfile.VM_REAL:
            from .engine.x11_mouse import X11MouseBackend
            self._mouse_backend = X11MouseBackend()
            self._engine = HeadPointerEngine(
                config=self._config,
                mouse_backend=self._mouse_backend,
                preview_only=False,
                on_state_changed=self._on_tracking_state_changed,
                on_metrics_updated=self._on_tracking_metrics,
                on_dwell_progress=self._on_dwell_progress,
                on_click=self._on_dwell_click,
            )
        else:
            self._mouse_backend = None
            self._engine = None

        self._tracking_overlay = TrackingOverlay(
            on_calibrate=self._engine.calibrate if self._engine else None,
            on_toggle_pause=self._on_header_pause_clicked,
            on_stop=self._stop_tracking if self._engine else None,
        )

        # Phase 4: Voice Control & Speech Synthesis (dormant until user enables)
        self._tts = TTSEngine(enabled=True)
        self._voice_hud = VoiceHUD(
            on_toggle_mute=self._on_voice_hud_toggle_mute,
            on_toggle_voice=self._on_voice_toggle_clicked,
        )
        self._voice_listener = VoiceListener(
            tts=self._tts,
            on_command=self._on_voice_command,
            on_state_changed=self._on_voice_state_changed,
        )
        self._reader_win = None

        self._setup_window()
        self._load_css()
        self._build_ui()
        self._connect_signals()

        self._config.add_change_listener(self._on_config_changed)
        log.info("HomeScreen ready with centered macOS-style dock")

    # ────────────────────────────────────────────────────────── setup ───

    def _setup_window(self) -> None:
        self.set_title("AccessOS")
        self.set_default_size(1280, 720)
        self.get_style_context().add_class("accessos-main")
        self.set_name("accessos-main-window")

        if os.environ.get("PYTEST_CURRENT_TEST"):
            pass  # Keep default size during unit tests without blocking WM
        elif os.environ.get("ACCESSOS_WINDOWED", "0") == "1":
            self.maximize()
        else:
            self.fullscreen()

    def _load_css(self) -> None:
        provider = Gtk.CssProvider()
        screen   = Gdk.Screen.get_default()

        if _CSS.exists():
            try:
                provider.load_from_path(str(_CSS))
                Gtk.StyleContext.add_provider_for_screen(
                    screen,
                    provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
                )
                log.debug("CSS loaded: %s", _CSS)
            except Exception as exc:
                log.warning("CSS failed to load: %s", exc)
        else:
            log.warning("CSS file not found: %s", _CSS)

    # ────────────────────────────────────────────────────────── UI build ───

    def _build_ui(self) -> None:
        self._overlay_container = Gtk.Overlay()
        self.add(self._overlay_container)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._overlay_container.add(root)

        # Phase 3.5: Virtual Cursor Overlay (layered on top with event pass-through)
        self._cursor_overlay = VirtualCursorOverlay()
        self._overlay_container.add_overlay(self._cursor_overlay)
        self._overlay_container.set_overlay_pass_through(self._cursor_overlay, True)

        # 1. Compact Top Bar (Header + Status Controls)
        root.pack_start(self._build_header(), False, False, 0)

        # 2. Pause overlay banner (revealed when paused)
        root.pack_start(self._build_pause_banner(), False, False, 0)

        # 3. Main Desktop Area (wallpaper background)
        self._desktop_canvas = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._desktop_canvas.set_vexpand(True)
        self._desktop_canvas.set_hexpand(True)
        root.pack_start(self._desktop_canvas, True, True, 0)

        # 4. Centered macOS-Style Bottom Dock
        root.pack_start(self._build_dock_area(), False, False, 0)

        # 5. Compact bottom telemetry bar
        root.pack_start(self._build_status_bar(), False, False, 0)

        root.show_all()
        self._pause_revealer.set_reveal_child(False)

    # ── Header ────────────────────────────────────────────────────────────────

    def _build_header(self) -> Gtk.Box:
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        hbox.get_style_context().add_class("header-bar")

        # Branding
        brand = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        t_lbl = Gtk.Label(label="AccessOS")
        t_lbl.get_style_context().add_class("app-title")
        t_lbl.set_halign(Gtk.Align.START)
        s_lbl = Gtk.Label(label="Accessible Live Environment")
        s_lbl.get_style_context().add_class("app-subtitle")
        s_lbl.set_halign(Gtk.Align.START)
        brand.pack_start(t_lbl, False, False, 0)
        brand.pack_start(s_lbl, False, False, 0)
        hbox.pack_start(brand, False, False, 0)

        # Profile Safety Badge
        self._safety_badge = Gtk.Label()
        self._safety_badge.get_style_context().add_class("safety-badge")
        if self._profile == LaunchProfile.HOST_SAFE:
            self._safety_badge.set_markup(
                "<span font='9' weight='bold' color='#3fb950'> 🛡️ HOST SAFE PROFILE — UI ONLY (NO CAMERA / NO INJECTION) </span>"
            )
            self._safety_badge.set_tooltip_text(
                "Host Safety: UI-only mode with zero camera tracking and zero mouse injection. "
                "Physical mouse and keyboard are 100% unaffected. "
                "Launch with --profile camera-preview to test camera preview."
            )
        elif self._profile == LaunchProfile.CAMERA_PREVIEW:
            self._safety_badge.set_markup(
                "<span font='9' weight='bold' color='#e3b341'> 📷 HOST CAMERA PREVIEW ONLY — NO DWELL / NO INPUT </span>"
            )
            self._safety_badge.set_tooltip_text(
                "Host Camera Preview: Renders camera preview and virtual reticle inside window only. "
                "Dwell clicks and OS input injection are strictly disabled."
            )
        else:
            self._safety_badge.set_markup(
                "<span font='9' weight='bold' color='#f85149'> ⚠️ VM REAL INJECTION ACTIVE </span>"
            )
            self._safety_badge.set_tooltip_text("VM Real Injection mode active inside verified hypervisor.")
        hbox.pack_start(self._safety_badge, False, False, 12)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        hbox.pack_start(spacer, True, True, 0)

        # Error notification toast (auto-hides)
        self._err_revealer = Gtk.Revealer()
        self._err_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_LEFT)
        self._err_label = Gtk.Label()
        self._err_label.get_style_context().add_class("error-label")
        self._err_label.set_margin_end(10)
        self._err_revealer.add(self._err_label)
        hbox.pack_start(self._err_revealer, False, False, 0)

        # Tracking HUD Overlay
        hbox.pack_start(self._tracking_overlay, False, False, 6)

        # Camera Toggle Button
        self._cam_btn = Gtk.Button()
        self._cam_btn.get_style_context().add_class("header-btn")
        if self._profile == LaunchProfile.HOST_SAFE:
            self._cam_btn.set_label("📷  Camera (Disabled)")
            self._cam_btn.set_tooltip_text("Camera tracking is disabled in host-safe profile. Run with --profile camera-preview for preview.")
        elif self._profile == LaunchProfile.CAMERA_PREVIEW:
            self._cam_btn.set_label("📷  Start Preview")
            self._cam_btn.set_tooltip_text("Start or stop local camera preview (dwell clicking and OS input are disabled)")
        else:
            self._cam_btn.set_label("📷  Start Tracking")
            self._cam_btn.set_tooltip_text("Enable or disable camera head-pointer tracking (VM real injection)")
        self._cam_btn.connect("clicked", self._on_cam_toggle_clicked)
        hbox.pack_start(self._cam_btn, False, False, 0)

        # Voice Control HUD Overlay
        hbox.pack_start(self._voice_hud, False, False, 6)

        # Voice Control Start/Stop Toggle Button
        self._voice_btn = Gtk.Button(label="🎙️  Start Voice")
        self._voice_btn.get_style_context().add_class("header-btn")
        self._voice_btn.set_tooltip_text("Enable or disable offline voice control (Vosk)")
        self._voice_btn.connect("clicked", self._on_voice_toggle_clicked)
        hbox.pack_start(self._voice_btn, False, False, 0)

        # Pause / Resume button
        self._pause_btn = Gtk.Button(label="⏸  Pause")
        self._pause_btn.get_style_context().add_class("header-btn")
        self._pause_btn.get_style_context().add_class("pause-btn")
        self._pause_btn.set_tooltip_text("Pause / resume accessibility control  (Esc)")
        self._pause_btn.connect("clicked", self._on_header_pause_clicked)
        hbox.pack_start(self._pause_btn, False, False, 0)

        # Power menu button (protected dialog)
        pwr_btn = Gtk.Button(label="⏻  Power")
        pwr_btn.get_style_context().add_class("header-btn")
        pwr_btn.get_style_context().add_class("power-btn")
        pwr_btn.set_tooltip_text("Power and session options")
        pwr_btn.connect("clicked", self._on_power_clicked)
        hbox.pack_start(pwr_btn, False, False, 0)

        return hbox

    # ── Pause banner ──────────────────────────────────────────────────────────

    def _build_pause_banner(self) -> Gtk.Revealer:
        self._pause_revealer = Gtk.Revealer()
        self._pause_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self._pause_revealer.set_transition_duration(200)

        banner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        banner.get_style_context().add_class("pause-banner")

        icon_lbl = Gtk.Label(label="⚠️")
        icon_lbl.get_style_context().add_class("pause-icon")

        text_lbl = Gtk.Label(
            label="CONTROL PAUSED  ·  Keyboard and mouse fallback is active  ·  Press Esc to resume"
        )
        text_lbl.set_hexpand(True)
        text_lbl.set_halign(Gtk.Align.START)

        resume_btn = Gtk.Button(label="▶  Resume")
        resume_btn.get_style_context().add_class("header-btn")
        resume_btn.connect("clicked", lambda _: self.resume_control())

        banner.pack_start(icon_lbl, False, False, 12)
        banner.pack_start(text_lbl, True, True, 0)
        banner.pack_end(resume_btn, False, False, 12)

        self._pause_revealer.add(banner)
        return self._pause_revealer

    # ── macOS-Style Centered Bottom Dock ──────────────────────────────────────

    def _build_dock_area(self) -> Gtk.Box:
        wrapper = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        wrapper.get_style_context().add_class("dock-wrapper")
        wrapper.set_halign(Gtk.Align.CENTER)
        wrapper.set_valign(Gtk.Align.END)
        wrapper.set_margin_bottom(20)

        # Dock glass container
        self._dock = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        self._dock.get_style_context().add_class("dock-container")

        self._dock_btns.clear()
        for idx, item in enumerate(_DOCK_ITEMS):
            btn = self._make_dock_button(item, idx)
            self._dock.pack_start(btn, False, False, 0)
            self._dock_btns.append(btn)

        wrapper.pack_start(self._dock, True, True, 0)
        return wrapper

    def _make_dock_button(self, item: dict, idx: int) -> Gtk.Button:
        btn = Gtk.Button()
        btn.get_style_context().add_class("dock-item")
        btn.set_can_focus(True)
        btn.set_tooltip_text(item["desc"])

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)

        icon = Gtk.Image.new_from_icon_name(item["icon"], Gtk.IconSize.INVALID)
        icon.set_pixel_size(_ICON_PX)
        icon.set_halign(Gtk.Align.CENTER)

        lbl = Gtk.Label(label=item["label"])
        lbl.get_style_context().add_class("dock-label")
        lbl.set_halign(Gtk.Align.CENTER)

        box.pack_start(icon, False, False, 0)
        box.pack_start(lbl, False, False, 0)
        btn.add(box)

        btn.connect("clicked", self._on_btn_clicked, item["key"])
        btn.connect("focus-in-event", self._on_btn_focus, idx)

        return btn

    # ── Status bar ────────────────────────────────────────────────────────────

    def _build_status_bar(self) -> Gtk.Widget:
        self._status = StatusBar()
        mode = self._config.get("accessibility", "mode", default="keyboard_mouse")
        mode_display = {
            "keyboard_mouse": "Keyboard & Mouse",
            "head_pointer": "Head Pointer (P3)",
            "dwell_selection": "Dwell (P3)",
            "voice_control": "Voice (P4)",
        }.get(mode, mode)
        self._status.set_active_mode(mode_display)

        # Visible build info & git commit identifier inside UI (Requirement 1)
        info = get_build_info(profile=self._profile.value)
        build_str = f"v{info['version']} ({info['git_commit_short']}) · PID {info['pid']} · {self._profile.value}"
        self._status.set_build_info(build_str)
        return self._status.widget

    # ── Signal wiring ─────────────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        self.connect("key-press-event", self._on_key_press)
        self.connect("delete-event",    self._on_delete)
        self.connect("size-allocate",   self._on_window_size_allocate)
        GLib.idle_add(self._initial_focus)

    def _initial_focus(self) -> bool:
        if self._dock_btns:
            self._dock_btns[0].grab_focus()
            self._focus_idx = 0
            self._status.set_focused_item(_DOCK_ITEMS[0]["label"])
        return False

    # ── Button signals ────────────────────────────────────────────────────────

    def _on_btn_focus(self, _btn: Gtk.Button, _event: Gdk.EventFocus, idx: int) -> bool:
        self._focus_idx = idx
        item = _DOCK_ITEMS[idx]
        log.debug("Dock focus → %s", item["label"])
        self._audio.play("focus")
        self._status.set_focused_item(item["label"])
        return False

    def _on_btn_clicked(self, _btn: Gtk.Button, key: str) -> None:
        if self._paused:
            return
        log.info("Dock item activated: %s", key)
        self._audio.play("activate")

        if key == "settings":
            self._open_settings()
            return

        self._launcher.launch(key, on_error=self._show_error)

    # ── Settings Window ───────────────────────────────────────────────────────

    def _open_settings(self) -> None:
        log.info("Opening SettingsWindow")
        win = SettingsWindow(
            config=self._config,
            audio=self._audio,
            parent=self,
        )
        win.show_all()
        win.present()

    def _on_config_changed(self, key_path: str, value) -> None:
        log.debug("HomeScreen received config change: %s = %s", key_path, value)
        if "audio" in key_path or key_path == "all":
            enabled = self._config.get("audio", "sounds_enabled", default=True)
            self._audio.set_enabled(enabled)
            self._status.set_audio_state(enabled)

        if "accessibility" in key_path or key_path == "all":
            mode = self._config.get("accessibility", "mode", default="keyboard_mouse")
            mode_display = {
                "keyboard_mouse": "Keyboard & Mouse",
                "head_pointer": "Head Pointer (P3)",
                "dwell_selection": "Dwell (P3)",
                "voice_control": "Voice (P4)",
            }.get(mode, mode)
            self._status.set_active_mode(mode_display)

    # ── Pause / resume ────────────────────────────────────────────────────────

    def pause_control(self) -> None:
        """
        Idempotent emergency pause: ALWAYS pauses, NEVER resumes.
        Safe against repeated Esc key presses.
        """
        if not self._paused:
            self._paused = True
            self._pause_btn.set_label("▶  Resume (R)")
            self._pause_revealer.set_reveal_child(True)
            self._dock.set_sensitive(False)
            self._audio.play("pause")
            self._cursor_overlay.set_active(False)
            if self._engine and self._engine.state == TrackingState.TRACKING:
                self._engine.pause()
            log.info("Control PAUSED via emergency pause (idempotent)")
            self._status.set_paused(True)

    def resume_control(self) -> None:
        """
        Explicit resume: requires explicit action (Resume button or R shortcut).
        """
        if self._paused:
            self._paused = False
            self._pause_btn.set_label("⏸  Pause (Esc)")
            self._pause_revealer.set_reveal_child(False)
            self._dock.set_sensitive(True)
            self._audio.play("resume")
            self._cursor_overlay.set_active(True)
            if self._engine and self._engine.state == TrackingState.PAUSED:
                self._engine.resume()
            log.info("Control RESUMED explicitly")
            self._status.set_paused(False)

    def _on_header_pause_clicked(self, _btn: Gtk.Button) -> None:
        if self._paused:
            self.resume_control()
        else:
            self.pause_control()

    # ── Power ─────────────────────────────────────────────────────────────────

    def _on_power_clicked(self, _btn: Gtk.Button) -> None:
        menu = PowerMenu(parent=self)
        menu.run()
        menu.destroy()

    # ── Keyboard Navigation ───────────────────────────────────────────────────

    def _on_key_press(self, _widget: Gtk.Widget, event: Gdk.EventKey) -> bool:
        kv = event.keyval

        # Ctrl+R: OPEN ACCESSIBLE DOCUMENT READER
        if (event.state & Gdk.ModifierType.CONTROL_MASK) and kv in (Gdk.KEY_r, Gdk.KEY_R):
            self._open_document_reader()
            return True

        # F12: UNIVERSAL EMERGENCY STOP (shuts down all engines without needing mouse)
        if kv == Gdk.KEY_F12:
            self._emergency_stop_all()
            return True

        # Esc: IDEMPOTENT EMERGENCY PAUSE (always pauses, never resumes)
        if kv == Gdk.KEY_Escape:
            self.pause_control()
            return True

        # R / r: EXPLICIT RESUME (only when control is currently paused)
        if kv in (Gdk.KEY_r, Gdk.KEY_R) and self._paused:
            self.resume_control()
            return True

        # C / c: CALIBRATION / CENTER BASELINE
        if kv in (Gdk.KEY_c, Gdk.KEY_C):
            if self._engine and self._engine.state == TrackingState.TRACKING:
                self._engine.calibrate()
                self._audio.play("activate")
                return True

        # M / m: MICROPHONE MUTE TOGGLE
        if kv in (Gdk.KEY_m, Gdk.KEY_M):
            if self._voice_listener.state != VoiceState.OFF:
                self._voice_listener.toggle_mute()
                return True

        # Number shortcuts 1-6
        if Gdk.KEY_1 <= kv <= Gdk.KEY_6:
            idx = kv - Gdk.KEY_1
            if 0 <= idx < len(self._dock_btns):
                self._move_focus(idx)
                self._dock_btns[idx].clicked()
                return True

        # Horizontal dock navigation with wrap-around
        if kv in (Gdk.KEY_Right, Gdk.KEY_Left, Gdk.KEY_Home, Gdk.KEY_End):
            self._dock_nav(kv)
            return True

        return False

    def _dock_nav(self, keyval: int) -> None:
        count = len(self._dock_btns)
        if count == 0:
            return

        if keyval == Gdk.KEY_Right:
            new_idx = (self._focus_idx + 1) % count
        elif keyval == Gdk.KEY_Left:
            new_idx = (self._focus_idx - 1) % count
        elif keyval == Gdk.KEY_Home:
            new_idx = 0
        elif keyval == Gdk.KEY_End:
            new_idx = count - 1
        else:
            return

        self._move_focus(new_idx)

    def _move_focus(self, idx: int) -> bool:
        if 0 <= idx < len(self._dock_btns):
            self._dock_btns[idx].grab_focus()
            self._focus_idx = idx
        return False

    # ── Window delete ─────────────────────────────────────────────────────────

    def _on_window_size_allocate(self, _widget, alloc) -> None:
        if self._mouse_backend and isinstance(self._mouse_backend, DryRunMouseBackend):
            self._mouse_backend.set_screen_size(alloc.width, alloc.height)

    def _on_cursor_moved(self, x: int, y: int) -> None:
        self._cursor_overlay.update_position(x, y)

    def _on_virtual_click(self, x: int, y: int, button: int) -> None:
        self._cursor_overlay.trigger_click(x, y)
        self._audio.play("activate")

    def _emergency_stop_all(self) -> None:
        """Universal emergency stop: halts all vision and voice engines and releases input."""
        log.warning("Universal Emergency Stop activated")
        if self._engine:
            self._engine.emergency_stop()
        self._voice_listener.stop()
        self._tts.stop()
        self._cursor_overlay.set_active(False)
        cam_lbl = "📷  Camera (Disabled)" if self._profile == LaunchProfile.HOST_SAFE else ("📷  Start Preview" if self._profile == LaunchProfile.CAMERA_PREVIEW else "📷  Start Tracking")
        self._cam_btn.set_label(cam_lbl)
        self._voice_btn.set_label("🎙️  Start Voice")
        self._show_error("EMERGENCY STOP: All control engines halted.")
        self._audio.play("error")

    def _on_delete(self, _widget, _event) -> bool:
        log.info("Window close requested — performing full emergency cleanup")
        self._emergency_stop_all()
        return False

    # ── Error notification ────────────────────────────────────────────────────

    def _show_error(self, message: str) -> None:
        log.warning("UI error notification: %s", message)
        self._audio.play("error")
        self._err_label.set_text(f"⚠️  {message}")
        self._err_revealer.set_reveal_child(True)
        GLib.timeout_add(_ERROR_HIDE_MS, self._hide_error)

    def _hide_error(self) -> bool:
        self._err_revealer.set_reveal_child(False)
        return False

    # ── Phase 3 Vision Engine Handlers ────────────────────────────────────────

    def _on_cam_toggle_clicked(self, _btn: Gtk.Button) -> None:
        if self._profile == LaunchProfile.HOST_SAFE:
            self._show_error("Camera tracking is disabled in host-safe profile. Restart with: --profile camera-preview")
            return
        if self._engine is None:
            return
        if self._engine.state in (TrackingState.TRACKING, TrackingState.LOST, TrackingState.PAUSED):
            self._stop_tracking()
        else:
            if self._profile == LaunchProfile.CAMERA_PREVIEW:
                self._start_preview_flow()
            else:
                self._start_tracking_flow()

    def _start_preview_flow(self) -> None:
        """Local camera preview flow without dwell or system input."""
        confirmed = ConfirmDialog.ask(
            parent=self,
            title="Enable Camera Preview?",
            message="AccessOS will activate your verified RGB webcam for local reticle preview.",
            detail="Safety Guarantee:\n• PREVIEW ONLY: Dwell clicks and OS input injection are strictly DISABLED.\n• Video frames are processed locally and never recorded or transmitted.\n• Physical keyboard and mouse remain fully functional at all times.",
            confirm_label="Start Preview",
            is_destructive=False,
        )
        if confirmed:
            log.info("User confirmed camera preview permission")
            self._cursor_overlay.set_active(True)
            ok = self._engine.start()
            if ok:
                self._cam_btn.set_label("⏹  Stop Preview")
                self._audio.play("activate")
            else:
                self._show_error("Failed to start camera preview")

    def _start_tracking_flow(self) -> None:
        """Explicit user permission notice before opening the webcam."""
        # Validate session compatibility
        session_ok, session_msg = check_session_supported()
        if not session_ok:
            self._show_error(session_msg)
            return

        confirmed = ConfirmDialog.ask(
            parent=self,
            title="Enable Camera Head Tracking?",
            message="AccessOS will activate your verified RGB webcam to track head movements for pointer control.",
            detail="Notice:\n• Video frames are processed entirely locally and never recorded or transmitted.\n• Physical keyboard and mouse remain fully functional at all times.\n• Press Esc at any time to immediately pause camera pointer actions (Resume with R).",
            confirm_label="Enable Camera",
            is_destructive=False,
        )
        if confirmed:
            log.info("User confirmed camera access permission")
            self._cursor_overlay.set_active(True)
            ok = self._engine.start()
            if ok:
                self._cam_btn.set_label("⏹  Stop Tracking")
                self._audio.play("activate")
            else:
                self._show_error("Failed to start camera tracking")

    def _stop_tracking(self) -> None:
        if self._engine:
            self._engine.stop()
        self._cursor_overlay.set_active(False)
        cam_lbl = "📷  Start Preview" if self._profile == LaunchProfile.CAMERA_PREVIEW else "📷  Start Tracking"
        self._cam_btn.set_label(cam_lbl)
        self._tracking_overlay.update_state(TrackingState.STOPPED)
        self._tracking_overlay.update_dwell_progress(0.0)
        self._audio.play("activate")

    def _on_tracking_state_changed(self, state: TrackingState, detail: str) -> None:
        self._tracking_overlay.update_state(state, detail)
        if state == TrackingState.LOST:
            self._audio.play("error")
        elif state == TrackingState.TRACKING:
            self._cam_btn.set_label("⏹  Stop Tracking")

    def _on_tracking_metrics(self, fps: float, latency_ms: float) -> None:
        self._tracking_overlay.update_metrics(fps, latency_ms)

    def _on_dwell_progress(self, progress: float, x: int, y: int) -> None:
        self._tracking_overlay.update_dwell_progress(progress)

    def _on_dwell_click(self, x: int, y: int) -> None:
        self._audio.play("activate")

    # ── Phase 4 Voice Control Handlers ────────────────────────────────────────

    def _on_voice_hud_toggle_mute(self) -> None:
        if self._voice_listener.state != VoiceState.OFF:
            self._voice_listener.toggle_mute()

    def _on_voice_toggle_clicked(self, _btn: Gtk.Button = None) -> None:
        if self._voice_listener.state != VoiceState.OFF:
            self._stop_voice()
        else:
            self._start_voice_flow()

    def _start_voice_flow(self) -> None:
        """Explicit user consent before opening the microphone."""
        confirmed = ConfirmDialog.ask(
            parent=self,
            title="Enable Offline Voice Control?",
            message="AccessOS will activate your microphone for offline speech recognition (Vosk).",
            detail="Privacy Notice:\n• Audio is processed strictly locally using on-device models.\n• No recordings, transcripts, or voice data are ever saved or transmitted.\n• Only approved safety commands are executed; generic shell commands are blocked.\n• Press M at any time to mute the microphone.",
            confirm_label="Enable Microphone",
            is_destructive=False,
        )
        if confirmed:
            log.info("User confirmed microphone access permission")
            ok = self._voice_listener.start()
            if ok:
                self._voice_btn.set_label("⏹  Stop Voice")
                self._audio.play("activate")
            else:
                self._show_error("Failed to start voice listener")

    def _stop_voice(self) -> None:
        self._voice_listener.stop()
        self._voice_btn.set_label("🎙️  Start Voice")
        self._voice_hud.update_state(VoiceState.OFF)
        self._audio.play("activate")

    def _on_voice_state_changed(self, state: VoiceState, detail: str) -> None:
        self._voice_hud.update_state(state, detail)
        if state == VoiceState.LISTENING:
            self._voice_btn.set_label("⏹  Stop Voice")

    def _on_voice_command(self, action: CommandAction) -> None:
        log.info("Executing approved voice command: %s", action.value)
        self._voice_hud.show_command_toast(action.value)
        self._audio.play("activate")

        if action == CommandAction.OPEN_BROWSER:
            self._tts.speak("Opening Browser")
            self._launcher.launch("browser", on_error=self._show_error)

        elif action == CommandAction.OPEN_FILES:
            self._tts.speak("Opening Files")
            self._launcher.launch("files", on_error=self._show_error)

        elif action == CommandAction.OPEN_TERMINAL:
            self._tts.speak("Opening Terminal")
            self._launcher.launch("terminal", on_error=self._show_error)

        elif action == CommandAction.OPEN_SETTINGS:
            self._tts.speak("Opening Settings")
            self._open_settings()

        elif action == CommandAction.OPEN_IMAGES:
            self._tts.speak("Opening Images")
            self._launcher.launch("images", on_error=self._show_error)

        elif action == CommandAction.OPEN_VIDEOS:
            self._tts.speak("Opening Videos")
            self._launcher.launch("videos", on_error=self._show_error)

        elif action == CommandAction.GO_HOME:
            self._tts.speak("Home Screen")
            self._move_focus(0)

        elif action == CommandAction.PAUSE_CONTROL:
            self._tts.speak("Control Paused")
            self.pause_control()

        elif action == CommandAction.RESUME_CONTROL:
            self._tts.speak("Control Resumed")
            self.resume_control()

        elif action == CommandAction.STOP_TRACKING:
            self._tts.speak("Stopping Camera Tracking")
            self._stop_tracking()

        elif action == CommandAction.READ_STATUS:
            cur_vol = SystemControl.get_volume()
            mode = self._config.get("accessibility", "mode", default="keyboard_mouse")
            status_text = f"System online. Active mode: {mode}. Master volume: {cur_vol} percent."
            self._tts.speak(status_text)

        elif action == CommandAction.HELP:
            help_text = (
                "Voice commands available: open browser, open files, open terminal, "
                "open settings, open images, open videos, go home, pause control, "
                "resume control, stop tracking, volume up, or volume down."
            )
            self._tts.speak(help_text)

        elif action == CommandAction.VOLUME_UP:
            cur_vol = SystemControl.get_volume()
            new_vol = min(100, cur_vol + 10)
            SystemControl.set_volume(new_vol)
            self._tts.speak(f"Volume {new_vol} percent")

        elif action == CommandAction.VOLUME_DOWN:
            cur_vol = SystemControl.get_volume()
            new_vol = max(0, cur_vol - 10)
            SystemControl.set_volume(new_vol)
            self._tts.speak(f"Volume {new_vol} percent")

        elif action == CommandAction.RESTART_REQUEST:
            SystemControl.restart_system()

        elif action == CommandAction.SHUTDOWN_REQUEST:
            SystemControl.poweroff_system()

        elif action == CommandAction.READ_DOCUMENT:
            self._tts.speak("Opening Document Reader")
            self._open_document_reader()

        elif action == CommandAction.PAUSE_READING:
            if self._reader_win:
                self._reader_win.reader.pause()
                self._tts.speak("Reading Paused")

        elif action == CommandAction.RESUME_READING:
            if self._reader_win:
                self._reader_win.reader.resume()
                self._tts.speak("Reading Resumed")

        elif action == CommandAction.STOP_READING:
            if self._reader_win:
                self._reader_win.reader.stop()
                self._tts.speak("Reading Stopped")

        elif action == CommandAction.NEXT_SENTENCE:
            if self._reader_win:
                self._reader_win.reader.next_sentence()

        elif action == CommandAction.PREVIOUS_SENTENCE:
            if self._reader_win:
                self._reader_win.reader.previous_sentence()

        elif action == CommandAction.READING_FASTER:
            if self._reader_win:
                spd = self._reader_win.reader.increase_speed()
                self._tts.speak(f"Speed {spd:.2f}x")

        elif action == CommandAction.READING_SLOWER:
            if self._reader_win:
                spd = self._reader_win.reader.decrease_speed()
                self._tts.speak(f"Speed {spd:.2f}x")

    def _open_document_reader(self, initial_file=None) -> None:
        from .reader.reader_window import DocumentReaderWindow
        if self._reader_win is None:
            self._reader_win = DocumentReaderWindow(tts=self._tts, initial_file=initial_file)
            self._reader_win.connect("destroy", self._on_reader_win_closed)
        self._reader_win.show_all()
        self._reader_win.present()

    def _on_reader_win_closed(self, _widget) -> None:
        self._reader_win = None
