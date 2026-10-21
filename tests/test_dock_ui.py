"""
Tests for macOS-Style Centered Bottom Dock UI
"""
import os
import pytest

# Ensure headless GTK can initialize if display is present
os.environ.setdefault("ACCESSOS_WINDOWED", "1")

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, Gio

from accessos.utils.config import Config
from accessos.audio_feedback import AudioFeedback
from accessos.app_launcher import AppLauncher
from accessos.home_screen import HomeScreen, _DOCK_ITEMS


def test_dock_item_definitions():
    assert len(_DOCK_ITEMS) == 6
    expected_labels = ["Browser", "Files", "Terminal", "Settings", "Images", "Videos"]
    expected_keys   = ["browser", "files", "terminal", "settings", "images", "videos"]
    assert [item["label"] for item in _DOCK_ITEMS] == expected_labels
    assert [item["key"] for item in _DOCK_ITEMS] == expected_keys


def test_dock_instantiation():
    app = Gtk.Application(
        application_id="org.accessos.testdocksuite",
        flags=Gio.ApplicationFlags.NON_UNIQUE,
    )
    cfg = Config()
    audio = AudioFeedback(enabled=False)
    launcher = AppLauncher()

    win = HomeScreen(app=app, config=cfg, launcher=launcher, audio=audio)
    assert len(win._dock_btns) == 6

    # Verify each dock button has icon and correct label
    for idx, (btn, defn) in enumerate(zip(win._dock_btns, _DOCK_ITEMS)):
        box = btn.get_child()
        children = box.get_children()
        icon, lbl = children[0], children[1]
        assert isinstance(icon, Gtk.Image)
        assert isinstance(lbl, Gtk.Label)
        assert lbl.get_text() == defn["label"]


def test_dock_horizontal_navigation():
    app = Gtk.Application(
        application_id="org.accessos.testdocknav",
        flags=Gio.ApplicationFlags.NON_UNIQUE,
    )
    cfg = Config()
    audio = AudioFeedback(enabled=False)
    launcher = AppLauncher()
    win = HomeScreen(app=app, config=cfg, launcher=launcher, audio=audio)

    # Starts at 0
    win._move_focus(0)
    assert win._focus_idx == 0

    # Right arrow moves forward
    win._dock_nav(Gdk.KEY_Right)
    assert win._focus_idx == 1

    # End jumps to last item (5)
    win._dock_nav(Gdk.KEY_End)
    assert win._focus_idx == 5

    # Right arrow wraps around to 0
    win._dock_nav(Gdk.KEY_Right)
    assert win._focus_idx == 0

    # Left arrow wraps around to 5
    win._dock_nav(Gdk.KEY_Left)
    assert win._focus_idx == 5

    # Home jumps to 0
    win._dock_nav(Gdk.KEY_Home)
    assert win._focus_idx == 0
