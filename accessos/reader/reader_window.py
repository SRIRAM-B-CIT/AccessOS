"""
AccessOS Accessible Document Reader Window
===========================================
High-contrast, keyboard- and head-pointer accessible GUI for document reading
with synchronized sentence highlighting and offline speech playback.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango

from ..voice.tts_engine import TTSEngine
from .document_reader import DocumentReader, PlaybackState

log = logging.getLogger(__name__)


class DocumentReaderWindow(Gtk.Window):
    """
    Accessible Document Reader Window.
    """

    def __init__(self, tts: Optional[TTSEngine] = None, initial_file: Optional[Path | str] = None) -> None:
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_title("AccessOS Document Reader")
        self.set_default_size(880, 620)
        self.set_position(Gtk.WindowPosition.CENTER)

        self._reader = DocumentReader(
            tts=tts,
            on_sentence_changed=self._on_sentence_changed,
            on_state_changed=self._on_state_changed,
            on_completed=self._on_completed,
        )

        self._build_ui()
        self._connect_signals()

        if initial_file:
            self.load_file(initial_file)

    @property
    def reader(self) -> DocumentReader:
        return self._reader

    def _build_ui(self) -> None:
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        main_box.get_style_context().add_class("doc-reader-main")
        self.add(main_box)

        # ── 1. Header Bar ──
        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        header.set_title("Document Reader")
        header.set_subtitle("AccessOS Offline Speech")
        self.set_titlebar(header)
        self._header = header

        open_btn = Gtk.Button(label="📂 Open File (O)")
        open_btn.get_style_context().add_class("reader-header-btn")
        open_btn.connect("clicked", self._on_open_file_clicked)
        header.pack_start(open_btn)

        # ── 2. Reading Text Display ──
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        scroller.set_hexpand(True)

        self._text_view = Gtk.TextView()
        self._text_view.set_editable(False)
        self._text_view.set_cursor_visible(False)
        self._text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self._text_view.set_left_margin(24)
        self._text_view.set_right_margin(24)
        self._text_view.set_top_margin(20)
        self._text_view.set_bottom_margin(20)

        # High-contrast font size
        font_desc = Pango.FontDescription.from_string("Sans 15")
        self._text_view.override_font(font_desc)

        self._buffer = self._text_view.get_buffer()
        # Highlighting tag for active reading sentence
        self._highlight_tag = self._buffer.create_tag(
            "active-sentence",
            background="#1f6feb",
            foreground="#ffffff",
            weight=Pango.Weight.BOLD,
        )

        scroller.add(self._text_view)
        main_box.pack_start(scroller, True, True, 0)

        # ── 3. Controls & Progress Bar ──
        control_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        control_panel.set_margin_start(20)
        control_panel.set_margin_end(20)
        control_panel.set_margin_top(12)
        control_panel.set_margin_bottom(16)
        main_box.pack_start(control_panel, False, False, 0)

        # Progress bar
        self._prog_bar = Gtk.ProgressBar()
        self._prog_bar.set_fraction(0.0)
        self._prog_bar.set_show_text(True)
        self._prog_bar.set_text("No document loaded")
        control_panel.pack_start(self._prog_bar, False, False, 0)

        # Playback buttons row
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        btn_row.set_halign(Gtk.Align.CENTER)
        control_panel.pack_start(btn_row, False, False, 0)

        self._prev_btn = Gtk.Button(label="⏮ Previous")
        self._prev_btn.set_size_request(120, 48)
        self._prev_btn.connect("clicked", lambda _: self._reader.previous_sentence())
        btn_row.pack_start(self._prev_btn, False, False, 0)

        self._play_btn = Gtk.Button(label="▶ Play")
        self._play_btn.set_size_request(140, 48)
        self._play_btn.get_style_context().add_class("suggested-action")
        self._play_btn.connect("clicked", lambda _: self._reader.toggle_play_pause())
        btn_row.pack_start(self._play_btn, False, False, 0)

        self._stop_btn = Gtk.Button(label="⏹ Stop")
        self._stop_btn.set_size_request(110, 48)
        self._stop_btn.connect("clicked", lambda _: self._reader.stop())
        btn_row.pack_start(self._stop_btn, False, False, 0)

        self._next_btn = Gtk.Button(label="⏭ Next")
        self._next_btn.set_size_request(120, 48)
        self._next_btn.connect("clicked", lambda _: self._reader.next_sentence())
        btn_row.pack_start(self._next_btn, False, False, 0)

        # Speed controls
        speed_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        slower_btn = Gtk.Button(label="➖")
        slower_btn.set_size_request(44, 48)
        slower_btn.set_tooltip_text("Decrease speed")
        slower_btn.connect("clicked", self._on_decrease_speed)

        self._speed_lbl = Gtk.Label(label="1.00x")
        self._speed_lbl.set_size_request(60, 48)

        faster_btn = Gtk.Button(label="➕")
        faster_btn.set_size_request(44, 48)
        faster_btn.set_tooltip_text("Increase speed")
        faster_btn.connect("clicked", self._on_increase_speed)

        speed_box.pack_start(slower_btn, False, False, 0)
        speed_box.pack_start(self._speed_lbl, False, False, 0)
        speed_box.pack_start(faster_btn, False, False, 0)
        btn_row.pack_start(speed_box, False, False, 16)

        # Keyboard shortcuts hint
        hint_lbl = Gtk.Label()
        hint_lbl.set_markup(
            "<span font='10' color='#8b949e'>"
            "Shortcuts: <b>Space</b> Play/Pause · <b>←/→</b> Previous/Next · <b>O</b> Open File · <b>Esc</b> Close"
            "</span>"
        )
        hint_lbl.set_halign(Gtk.Align.CENTER)
        control_panel.pack_start(hint_lbl, False, False, 0)

    def _connect_signals(self) -> None:
        self.connect("key-press-event", self._on_key_press)
        self.connect("delete-event", self._on_delete)

    def _on_key_press(self, _widget: Gtk.Widget, event: Gdk.EventKey) -> bool:
        keyval = event.keyval
        if keyval == Gdk.KEY_space:
            self._reader.toggle_play_pause()
            return True
        elif keyval in (Gdk.KEY_Left, Gdk.KEY_p, Gdk.KEY_P):
            self._reader.previous_sentence()
            return True
        elif keyval in (Gdk.KEY_Right, Gdk.KEY_n, Gdk.KEY_N):
            self._reader.next_sentence()
            return True
        elif keyval in (Gdk.KEY_s, Gdk.KEY_S):
            self._reader.stop()
            return True
        elif keyval in (Gdk.KEY_o, Gdk.KEY_O) and not (event.state & Gdk.ModifierType.CONTROL_MASK):
            self._on_open_file_clicked(None)
            return True
        elif keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False

    def _on_delete(self, _widget, _event) -> bool:
        self._reader.stop()
        return False

    def _on_open_file_clicked(self, _btn) -> None:
        dialog = Gtk.FileChooserDialog(
            title="Open Document for Reading",
            parent=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.ACCEPT,
        )

        filter_all = Gtk.FileFilter()
        filter_all.set_name("All Readable Documents (*.txt, *.md, *.pdf, *.docx, *.odt, *.epub, *.html)")
        for pattern in ("*.txt", "*.md", "*.pdf", "*.docx", "*.odt", "*.epub", "*.html", "*.htm"):
            filter_all.add_pattern(pattern)
        dialog.add_filter(filter_all)

        response = dialog.run()
        if response == Gtk.ResponseType.ACCEPT:
            filename = dialog.get_filename()
            dialog.destroy()
            if filename:
                self.load_file(filename)
        else:
            dialog.destroy()

    def load_file(self, path: Path | str) -> bool:
        """Load and display document."""
        ok = self._reader.load_file(path)
        if ok:
            self._header.set_subtitle(self._reader.title)
            # Populate text view
            full_text = "\n\n".join(self._reader.sentences)
            self._buffer.set_text(full_text)
            self._update_progress_ui(1, self._reader.total_sentences)
            self._highlight_current_sentence()
        return ok

    def load_text(self, text: str, title: str = "Document") -> None:
        """Load text directly."""
        self._reader.load_text(text, title=title)
        self._header.set_subtitle(title)
        self._buffer.set_text("\n\n".join(self._reader.sentences))
        self._update_progress_ui(1, self._reader.total_sentences)
        self._highlight_current_sentence()

    def _on_increase_speed(self, _btn) -> None:
        spd = self._reader.increase_speed()
        self._speed_lbl.set_text(f"{spd:.2f}x")

    def _on_decrease_speed(self, _btn) -> None:
        spd = self._reader.decrease_speed()
        self._speed_lbl.set_text(f"{spd:.2f}x")

    def _on_sentence_changed(self, current: int, total: int, text: str) -> None:
        GLib.idle_add(self._apply_sentence_changed, current, total, text)

    def _apply_sentence_changed(self, current: int, total: int, _text: str) -> bool:
        self._update_progress_ui(current, total)
        self._highlight_current_sentence()
        return False

    def _on_state_changed(self, state: PlaybackState) -> None:
        GLib.idle_add(self._apply_state_changed, state)

    def _apply_state_changed(self, state: PlaybackState) -> bool:
        if state == PlaybackState.PLAYING:
            self._play_btn.set_label("⏸ Pause")
        else:
            self._play_btn.set_label("▶ Play")
        return False

    def _on_completed(self) -> None:
        GLib.idle_add(self._apply_completed)

    def _apply_completed(self) -> bool:
        self._prog_bar.set_fraction(1.0)
        self._prog_bar.set_text(f"Completed reading {self._reader.total_sentences} sentences")
        self._play_btn.set_label("▶ Play")
        return False

    def _update_progress_ui(self, current: int, total: int) -> None:
        frac = (current / total) if total > 0 else 0.0
        self._prog_bar.set_fraction(frac)
        self._prog_bar.set_text(f"Sentence {current} of {total} ({int(frac * 100)}% read)")

    def _highlight_current_sentence(self) -> None:
        """Highlight active sentence in text view and scroll into view."""
        self._buffer.remove_all_tags(self._buffer.get_start_iter(), self._buffer.get_end_iter())

        sentences = self._reader.sentences
        idx = self._reader.current_index
        if idx < 0 or idx >= len(sentences):
            return

        target_sentence = sentences[idx]
        start_search = self._buffer.get_start_iter()

        match = start_search.forward_search(target_sentence, Gtk.TextSearchFlags.VISIBLE_ONLY, None)
        if match:
            start_iter, end_iter = match
            self._buffer.apply_tag(self._highlight_tag, start_iter, end_iter)
            # Scroll to make visible
            self._text_view.scroll_to_iter(start_iter, 0.1, True, 0.0, 0.5)
