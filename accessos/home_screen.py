"""
AccessOS Home Screen — Phase 1
================================
Primary launcher interface.

Layout (top → bottom):
  ┌─────────────────────────────────────────────────────────┐
  │  🔷 AccessOS             [⏸ Pause]          [⏻ Power]  │  header
  ├─────────────────────────────────────────────────────────┤
  │  ⚠  CONTROL PAUSED  ─────────────────── [▶ Resume]     │  pause banner
  ├─────────────────────────────────────────────────────────┤
  │                                                         │
  │   ┌──────────┐  ┌──────────┐  ┌──────────┐             │
  │   │ 🌐       │  │ 📁       │  │ 💻       │             │  row 0
  │   │ Browser  │  │ Files    │  │ Terminal │             │
  │   └──────────┘  └──────────┘  └──────────┘             │
  │   ┌──────────┐  ┌──────────┐  ┌──────────┐             │
  │   │ ⚙        │  │ 🖼        │  │ 🎬       │             │  row 1
  │   │ Settings │  │ Images   │  │ Videos   │             │
  │   └──────────┘  └──────────┘  └──────────┘             │
  │                                                         │
  ├─────────────────────────────────────────────────────────┤
  │  ⌨ Keyboard/Mouse  ●ACTIVE │ Focus: …  │ 🔋 📶 12:34  │  status bar
  └─────────────────────────────────────────────────────────┘

Keyboard navigation:
  Tab / Shift+Tab : next / previous button (GTK default)
  Arrow keys      : 2-D navigation within the 3×2 grid
  Enter / Space   : activate focused button
  Esc             : toggle pause / resume

Phase 1 limitations:
  - No TTS (Phase 4).
  - No camera / head tracking / voice (Phase 3+).
  - Settings shows a "coming in Phase 2" placeholder.
  - Power actions (lock / restart / shutdown) are placeholders.
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

log = logging.getLogger(__name__)

# ── Asset paths ────────────────────────────────────────────────────────────────
_HERE   = Path(__file__).parent
_CSS    = _HERE / "style.css"

# ── Button definitions (Tab order = reading order = grid order) ────────────────
# icon-names follow the freedesktop.org icon naming specification; GTK will
# fall back gracefully to a generic icon if a name is not in the current theme.
_BUTTONS = [
    {
        "key":   "browser",
        "label": "Browser",
        "icon":  "web-browser",
        "desc":  "Open web browser",
    },
    {
        "key":   "files",
        "label": "Files",
        "icon":  "system-file-manager",
        "desc":  "Browse files",
    },
    {
        "key":   "terminal",
        "label": "Terminal",
        "icon":  "utilities-terminal",
        "desc":  "Open terminal",
    },
    {
        "key":   "settings",
        "label": "Settings",
        "icon":  "preferences-system",
        "desc":  "AccessOS settings",
    },
    {
        "key":   "images",
        "label": "Images",
        "icon":  "image-x-generic",
        "desc":  "View images",
    },
    {
        "key":   "videos",
        "label": "Videos",
        "icon":  "video-x-generic",
        "desc":  "Play videos",
    },
]

_GRID_COLS = 3
_GRID_ROWS = 2

# Pixel size for button icons (large for accessibility)
_ICON_PX = 64

# Auto-hide delay for the error notification (ms)
_ERROR_HIDE_MS = 5_000


class HomeScreen(Gtk.ApplicationWindow):
    """
    AccessOS primary home screen window.

    Constructed by :mod:`accessos.__main__` and passed a shared
    :class:`~accessos.utils.config.Config`, :class:`~accessos.app_launcher.AppLauncher`,
    and :class:`~accessos.audio_feedback.AudioFeedback` instance.
    """

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

        # Button list in grid order (index 0 = top-left)
        self._btns: list[Gtk.Button] = []
        # Index of the currently focused button
        self._focus_idx = 0

        self._setup_window()
        self._load_css()
        self._build_ui()
        self._connect_signals()

        log.info("HomeScreen ready")

    # ────────────────────────────────────────────────────────────── setup ───

    def _setup_window(self) -> None:
        self.set_title("AccessOS")
        self.set_default_size(1280, 720)
        self.get_style_context().add_class("accessos-main")
        self.set_name("accessos-main-window")

        # Run fullscreen by default; set env var for development windowed mode
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

        root.pack_start(self._build_header(),       False, False, 0)
        root.pack_start(self._build_pause_banner(), False, False, 0)
        root.pack_start(self._build_body(),         True,  True,  0)
        root.pack_start(self._build_status_bar(),   False, False, 0)

        root.show_all()
        self._pause_revealer.set_reveal_child(False)

    # ── Header ────────────────────────────────────────────────────────────────

    def _build_header(self) -> Gtk.Box:
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
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

        spacer = Gtk.Box()
        spacer.set_hexpand(True)

        # Error notification (auto-hides)
        self._err_revealer = Gtk.Revealer()
        self._err_revealer.set_transition_type(
            Gtk.RevealerTransitionType.SLIDE_LEFT
        )
        self._err_label = Gtk.Label()
        self._err_label.get_style_context().add_class("error-label")
        self._err_label.set_margin_end(8)
        self._err_revealer.add(self._err_label)

        # Pause button
        self._pause_btn = Gtk.Button(label="⏸  Pause")
        self._pause_btn.get_style_context().add_class("header-btn")
        self._pause_btn.get_style_context().add_class("pause-btn")
        self._pause_btn.set_tooltip_text(
            "Pause / resume accessibility control  (Esc)"
        )
        self._pause_btn.connect("clicked", self._on_pause_toggled)

        # Power button
        pwr_btn = Gtk.Button(label="⏻  Power")
        pwr_btn.get_style_context().add_class("header-btn")
        pwr_btn.get_style_context().add_class("power-btn")
        pwr_btn.set_tooltip_text("Power options")
        pwr_btn.connect("clicked", self._on_power_clicked)

        hbox.pack_start(brand,              False, False, 12)
        hbox.pack_start(spacer,             True,  True,  0)
        hbox.pack_start(self._err_revealer, False, False, 0)
        hbox.pack_start(self._pause_btn,    False, False, 0)
        hbox.pack_start(pwr_btn,            False, False, 12)

        return hbox

    # ── Pause banner ─────────────────────────────────────────────────────────

    def _build_pause_banner(self) -> Gtk.Revealer:
        self._pause_revealer = Gtk.Revealer()
        self._pause_revealer.set_transition_type(
            Gtk.RevealerTransitionType.SLIDE_DOWN
        )
        self._pause_revealer.set_transition_duration(200)

        banner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        banner.get_style_context().add_class("pause-banner")
        banner.set_margin_top(0)

        icon_lbl = Gtk.Label()
        icon_lbl.set_markup('<span font="16">⏸</span>')

        text_lbl = Gtk.Label()
        text_lbl.set_markup(
            '<span font="14" weight="bold">CONTROL PAUSED</span>'
            '  <span font="12" color="#c0bfa0">'
            '— Press Esc or click Resume to continue</span>'
        )
        text_lbl.set_hexpand(True)
        text_lbl.set_halign(Gtk.Align.START)

        resume_btn = Gtk.Button(label="▶  Resume")
        resume_btn.get_style_context().add_class("header-btn")
        resume_btn.connect("clicked", self._on_pause_toggled)

        banner.pack_start(icon_lbl,  False, False, 12)
        banner.pack_start(text_lbl,  True,  True,  0)
        banner.pack_end  (resume_btn, False, False, 12)

        self._pause_revealer.add(banner)
        return self._pause_revealer

    # ── Button grid ───────────────────────────────────────────────────────────

    def _build_body(self) -> Gtk.Box:
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        body.set_vexpand(True)
        body.set_hexpand(True)

        self._grid = Gtk.Grid()
        self._grid.set_column_homogeneous(True)
        self._grid.set_row_homogeneous(True)
        self._grid.set_row_spacing(16)
        self._grid.set_column_spacing(16)
        self._grid.set_margin_top(32)
        self._grid.set_margin_bottom(32)
        self._grid.set_margin_start(48)
        self._grid.set_margin_end(48)
        self._grid.set_vexpand(True)
        self._grid.set_hexpand(True)

        self._btns.clear()
        for idx, bdef in enumerate(_BUTTONS):
            row = idx // _GRID_COLS
            col = idx % _GRID_COLS
            btn = self._make_button(bdef, idx)
            self._grid.attach(btn, col, row, 1, 1)
            self._btns.append(btn)

        body.pack_start(self._grid, True, True, 0)
        return body

    def _make_button(self, bdef: dict, idx: int) -> Gtk.Button:
        """Create one large accessible launch button."""
        btn = Gtk.Button()
        btn.get_style_context().add_class("launch-button")
        btn.set_hexpand(True)
        btn.set_vexpand(True)
        btn.set_can_focus(True)
        btn.set_tooltip_text(bdef["desc"])

        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        inner.set_halign(Gtk.Align.CENTER)
        inner.set_valign(Gtk.Align.CENTER)
        inner.set_margin_top(20)
        inner.set_margin_bottom(20)
        inner.set_margin_start(16)
        inner.set_margin_end(16)

        # Icon
        icon = Gtk.Image()
        icon.set_from_icon_name(bdef["icon"], Gtk.IconSize.INVALID)
        icon.set_pixel_size(_ICON_PX)
        icon.set_halign(Gtk.Align.CENTER)

        # Name label
        name_lbl = Gtk.Label(label=bdef["label"])
        name_lbl.get_style_context().add_class("btn-label")
        name_lbl.set_halign(Gtk.Align.CENTER)

        # Description label (smaller, muted)
        desc_lbl = Gtk.Label(label=bdef["desc"])
        desc_lbl.get_style_context().add_class("btn-desc")
        desc_lbl.set_halign(Gtk.Align.CENTER)

        inner.pack_start(icon,     False, False, 0)
        inner.pack_start(name_lbl, False, False, 0)
        inner.pack_start(desc_lbl, False, False, 0)
        btn.add(inner)

        btn.connect("clicked",        self._on_btn_clicked, bdef["key"])
        btn.connect("focus-in-event", self._on_btn_focus,   idx)

        return btn

    # ── Status bar ────────────────────────────────────────────────────────────

    def _build_status_bar(self) -> Gtk.Widget:
        self._status = StatusBar()
        return self._status.widget

    # ────────────────────────────────────────────────── signal handlers ───

    def _connect_signals(self) -> None:
        self.connect("key-press-event", self._on_key_press)
        self.connect("delete-event",    self._on_delete)
        # Move focus to first button once the window is idle
        GLib.idle_add(self._move_focus, 0)

    # ── Button signals ────────────────────────────────────────────────────────

    def _on_btn_focus(self, _btn: Gtk.Button, _event: Gdk.EventFocus, idx: int) -> bool:
        self._focus_idx = idx
        bdef = _BUTTONS[idx]
        log.debug("Focus → %s", bdef["label"])
        self._audio.play("focus")
        self._status.set_focused_item(bdef["label"])
        return False   # propagate

    def _on_btn_clicked(self, _btn: Gtk.Button, key: str) -> None:
        if self._paused:
            return
        log.info("Button clicked: %s", key)
        self._audio.play("activate")

        if key == "settings":
            self._show_settings_placeholder()
            return

        self._launcher.launch(key, on_error=self._show_error)

    # ── Pause / resume ────────────────────────────────────────────────────────

    def _on_pause_toggled(self, _widget) -> None:
        self._paused = not self._paused

        if self._paused:
            self._pause_btn.set_label("▶  Resume")
            self._pause_revealer.set_reveal_child(True)
            self._grid.set_sensitive(False)
            self._audio.play("pause")
            log.info("Control PAUSED")
        else:
            self._pause_btn.set_label("⏸  Pause")
            self._pause_revealer.set_reveal_child(False)
            self._grid.set_sensitive(True)
            self._audio.play("resume")
            log.info("Control RESUMED")

        self._status.set_paused(self._paused)

    # ── Power ─────────────────────────────────────────────────────────────────

    def _on_power_clicked(self, _btn: Gtk.Button) -> None:
        menu = PowerMenu(parent=self)
        menu.run()
        menu.destroy()

    # ── Keyboard ─────────────────────────────────────────────────────────────

    def _on_key_press(self, _widget: Gtk.Widget, event: Gdk.EventKey) -> bool:
        kv = event.keyval

        # ── Emergency pause / resume (always active) ──────────────────────────
        if kv == Gdk.KEY_Escape:
            self._on_pause_toggled(None)
            return True

        # ── 2-D arrow-key navigation within the 3×2 grid ─────────────────────
        if kv in (Gdk.KEY_Right, Gdk.KEY_Left, Gdk.KEY_Down, Gdk.KEY_Up):
            self._arrow_nav(kv)
            return True

        return False   # let GTK handle Tab / Enter / Space

    def _arrow_nav(self, keyval: int) -> None:
        """Move grid focus in 2-D using arrow keys."""
        row, col = divmod(self._focus_idx, _GRID_COLS)

        if keyval == Gdk.KEY_Right:
            col = min(col + 1, _GRID_COLS - 1)
        elif keyval == Gdk.KEY_Left:
            col = max(col - 1, 0)
        elif keyval == Gdk.KEY_Down:
            row = min(row + 1, _GRID_ROWS - 1)
        elif keyval == Gdk.KEY_Up:
            row = max(row - 1, 0)

        new_idx = row * _GRID_COLS + col
        if new_idx != self._focus_idx:
            self._move_focus(new_idx)

    def _move_focus(self, idx: int) -> bool:
        """Grab keyboard focus for button *idx*; returns False (one-shot idle)."""
        if 0 <= idx < len(self._btns):
            self._btns[idx].grab_focus()
            self._focus_idx = idx
        return False

    # ── Window delete ─────────────────────────────────────────────────────────

    def _on_delete(self, _widget, _event) -> bool:
        """Allow window-manager close (for development workflow)."""
        log.info("Window close requested — exiting")
        return False   # allow close; Gtk.Application exits cleanly

    # ── Error notification ────────────────────────────────────────────────────

    def _show_error(self, message: str) -> None:
        log.warning("UI error notification: %s", message)
        self._audio.play("error")
        self._err_label.set_text(f"⚠  {message}")
        self._err_revealer.set_reveal_child(True)
        GLib.timeout_add(_ERROR_HIDE_MS, self._hide_error)

    def _hide_error(self) -> bool:
        self._err_revealer.set_reveal_child(False)
        return False   # one-shot

    # ── Settings placeholder ──────────────────────────────────────────────────

    def _show_settings_placeholder(self) -> None:
        dlg = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text="AccessOS Settings — Phase 2",
        )
        dlg.format_secondary_text(
            "The full Settings application will be built in Phase 2.\n\n"
            "Current configuration:\n"
            "  • Input mode : Keyboard & Mouse\n"
            "  • Camera     : Disabled  (Phase 3)\n"
            "  • Microphone : Disabled  (Phase 4)\n"
            "  • TTS        : Disabled  (Phase 4)\n\n"
            "Settings are stored in:\n"
            "  ~/.config/accessos/settings.toml"
        )
        dlg.run()
        dlg.destroy()
