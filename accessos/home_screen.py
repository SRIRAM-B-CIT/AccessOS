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
from .settings import SettingsWindow, ConfirmDialog
from .engine import HeadPointerEngine, TrackingState, TrackingOverlay

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
        app: Gtk.Application,
        config: Config,
        launcher: AppLauncher,
        audio: AudioFeedback,
    ) -> None:
        super().__init__(application=app)
        self._config   = config
        self._launcher = launcher
        self._audio    = audio
        self._paused   = False

        self._dock_btns: list[Gtk.Button] = []
        self._focus_idx = 0

        # Phase 3: Vision Engine & Overlay (dormant until explicitly started)
        self._engine = HeadPointerEngine(
            config=self._config,
            on_state_changed=self._on_tracking_state_changed,
            on_metrics_updated=self._on_tracking_metrics,
            on_dwell_progress=self._on_dwell_progress,
            on_click=self._on_dwell_click,
        )
        self._tracking_overlay = TrackingOverlay(
            on_calibrate=self._engine.calibrate,
            on_toggle_pause=self._on_pause_toggled,
            on_stop=self._stop_tracking,
        )

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

        if os.environ.get("ACCESSOS_WINDOWED", "0") == "1":
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
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(root)

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
        hbox.pack_start(self._tracking_overlay, False, False, 8)

        # Camera Tracking Start/Stop Toggle Button
        self._cam_btn = Gtk.Button(label="📷  Start Tracking")
        self._cam_btn.get_style_context().add_class("header-btn")
        self._cam_btn.set_tooltip_text("Enable or disable camera head-pointer tracking")
        self._cam_btn.connect("clicked", self._on_cam_toggle_clicked)
        hbox.pack_start(self._cam_btn, False, False, 0)

        # Pause / Resume button
        self._pause_btn = Gtk.Button(label="⏸  Pause")
        self._pause_btn.get_style_context().add_class("header-btn")
        self._pause_btn.get_style_context().add_class("pause-btn")
        self._pause_btn.set_tooltip_text("Pause / resume accessibility control  (Esc)")
        self._pause_btn.connect("clicked", self._on_pause_toggled)
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
        resume_btn.connect("clicked", self._on_pause_toggled)

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
        return self._status.widget

    # ── Signal wiring ─────────────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        self.connect("key-press-event", self._on_key_press)
        self.connect("delete-event",    self._on_delete)
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

    def _on_pause_toggled(self, _widget=None) -> None:
        self._paused = not self._paused

        if self._paused:
            self._pause_btn.set_label("▶  Resume")
            self._pause_revealer.set_reveal_child(True)
            self._dock.set_sensitive(False)
            self._audio.play("pause")
            if self._engine.state == TrackingState.TRACKING:
                self._engine.pause()
            log.info("Control PAUSED (keyboard/mouse fallback active)")
        else:
            self._pause_btn.set_label("⏸  Pause")
            self._pause_revealer.set_reveal_child(False)
            self._dock.set_sensitive(True)
            self._audio.play("resume")
            if self._engine.state == TrackingState.PAUSED:
                self._engine.resume()
            log.info("Control RESUMED")

        self._status.set_paused(self._paused)

    # ── Power ─────────────────────────────────────────────────────────────────

    def _on_power_clicked(self, _btn: Gtk.Button) -> None:
        menu = PowerMenu(parent=self)
        menu.run()
        menu.destroy()

    # ── Keyboard Navigation ───────────────────────────────────────────────────

    def _on_key_press(self, _widget: Gtk.Widget, event: Gdk.EventKey) -> bool:
        kv = event.keyval

        if kv == Gdk.KEY_Escape:
            self._on_pause_toggled(None)
            return True

        if kv in (Gdk.KEY_c, Gdk.KEY_C):
            if self._engine.state == TrackingState.TRACKING:
                self._engine.calibrate()
                self._audio.play("activate")
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

    def _on_delete(self, _widget, _event) -> bool:
        log.info("Window close requested — stopping engine")
        self._engine.stop()
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
        if self._engine.state in (TrackingState.TRACKING, TrackingState.LOST, TrackingState.PAUSED):
            self._stop_tracking()
        else:
            self._start_tracking_flow()

    def _start_tracking_flow(self) -> None:
        """Explicit user permission notice before opening the webcam."""
        confirmed = ConfirmDialog.ask(
            parent=self,
            title="Enable Camera Head Tracking?",
            message="AccessOS will activate your verified RGB webcam to track head movements for pointer control.",
            detail="Notice:\n• Video frames are processed entirely locally and never recorded or transmitted.\n• Physical keyboard and mouse remain fully functional at all times.\n• Press Esc at any time to immediately pause camera pointer actions.",
            confirm_label="Enable Camera",
            is_destructive=False,
        )
        if confirmed:
            log.info("User confirmed camera access permission")
            ok = self._engine.start()
            if ok:
                self._cam_btn.set_label("⏹  Stop Tracking")
                self._audio.play("activate")
            else:
                self._show_error("Failed to start camera tracking")

    def _stop_tracking(self) -> None:
        self._engine.stop()
        self._cam_btn.set_label("📷  Start Tracking")
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
