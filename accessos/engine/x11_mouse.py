"""
AccessOS Native X11 Mouse Controller
=====================================
Direct, high-performance cursor manipulation and click simulation
via libX11 and libXtst using 64-bit typed ctypes.

Session Scope:
  Supports X11 sessions ONLY (standard on Linux Mint Xfce).
  Fails safely with UnsupportedSessionError if invoked on an unsupported
  desktop session (e.g. pure Wayland).
"""
from __future__ import annotations

import ctypes
import ctypes.util
import logging
import os
from typing import Tuple

log = logging.getLogger(__name__)


class UnsupportedSessionError(RuntimeError):
    """Raised when pointer injection is attempted on an unsupported session (e.g. Wayland)."""
    pass


def check_session_supported() -> Tuple[bool, str]:
    """
    Verify that the current desktop environment is a supported X11 session.
    Linux Mint Xfce runs X11 natively. Pure Wayland environments block
    standard synthetic input injection for security isolation.
    """
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    display = os.environ.get("DISPLAY")

    if session_type == "wayland" and not display:
        return False, (
            "AccessOS pointer injection requires an X11 desktop session. "
            "Pure Wayland sessions do not allow simulated pointer injection. "
            "Linux Mint Xfce runs an X11 session by default."
        )

    if not display:
        return False, (
            "No X11 display found (DISPLAY environment variable is unset). "
            "AccessOS pointer injection requires an active X11 desktop session."
        )

    return True, "X11 session active."


class X11Mouse:
    """Simulates mouse motion and clicks on X11 displays with 64-bit safety."""

    def __init__(self) -> None:
        # Validate session compatibility
        supported, reason = check_session_supported()
        if not supported:
            raise UnsupportedSessionError(reason)

        x11_name = ctypes.util.find_library("X11") or "libX11.so.6"
        xtst_name = ctypes.util.find_library("Xtst") or "libXtst.so.6"

        try:
            self._x11 = ctypes.CDLL(x11_name)
            self._xtst = ctypes.CDLL(xtst_name)
        except Exception as exc:
            raise UnsupportedSessionError(f"Could not load X11/Xtst libraries: {exc}")

        # Explicitly declare 64-bit restypes and argtypes to prevent pointer truncation
        self._x11.XOpenDisplay.restype = ctypes.c_void_p
        self._x11.XOpenDisplay.argtypes = [ctypes.c_char_p]

        self._x11.XCloseDisplay.restype = ctypes.c_int
        self._x11.XCloseDisplay.argtypes = [ctypes.c_void_p]

        self._x11.XDefaultRootWindow.restype = ctypes.c_ulong
        self._x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]

        self._x11.XDisplayWidth.restype = ctypes.c_int
        self._x11.XDisplayWidth.argtypes = [ctypes.c_void_p, ctypes.c_int]

        self._x11.XDisplayHeight.restype = ctypes.c_int
        self._x11.XDisplayHeight.argtypes = [ctypes.c_void_p, ctypes.c_int]

        self._x11.XFlush.restype = ctypes.c_int
        self._x11.XFlush.argtypes = [ctypes.c_void_p]

        self._x11.XQueryPointer.restype = ctypes.c_int
        self._x11.XQueryPointer.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_uint)
        ]

        self._xtst.XTestFakeMotionEvent.restype = ctypes.c_int
        self._xtst.XTestFakeMotionEvent.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ulong
        ]

        self._xtst.XTestFakeButtonEvent.restype = ctypes.c_int
        self._xtst.XTestFakeButtonEvent.argtypes = [
            ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong
        ]

        self._display = self._x11.XOpenDisplay(None)
        if not self._display:
            raise UnsupportedSessionError(
                "Failed to open X11 Display. Ensure an X11 server is running (standard on Linux Mint Xfce)."
            )

        self._root = self._x11.XDefaultRootWindow(self._display)
        self._screen_w = self._x11.XDisplayWidth(self._display, 0)
        self._screen_h = self._x11.XDisplayHeight(self._display, 0)
        log.info("X11Mouse initialized: screen %dx%d (display %s)", self._screen_w, self._screen_h, hex(self._display))

    def close(self) -> None:
        if hasattr(self, "_display") and self._display:
            try:
                self._x11.XCloseDisplay(self._display)
            except Exception:
                pass
            self._display = None

    def __del__(self) -> None:
        self.close()

    @property
    def screen_size(self) -> Tuple[int, int]:
        return (self._screen_w, self._screen_h)

    def get_position(self) -> Tuple[int, int]:
        """Return current (x, y) cursor coordinates."""
        if not self._display:
            return (0, 0)
        root_ret = ctypes.c_ulong()
        child_ret = ctypes.c_ulong()
        root_x = ctypes.c_int()
        root_y = ctypes.c_int()
        win_x = ctypes.c_int()
        win_y = ctypes.c_int()
        mask = ctypes.c_uint()

        self._x11.XQueryPointer(
            self._display,
            self._root,
            ctypes.byref(root_ret),
            ctypes.byref(child_ret),
            ctypes.byref(root_x),
            ctypes.byref(root_y),
            ctypes.byref(win_x),
            ctypes.byref(win_y),
            ctypes.byref(mask),
        )
        return (root_x.value, root_y.value)

    def move_to(self, x: int, y: int) -> None:
        """Move system pointer to absolute coordinates (clamped to screen)."""
        if not self._display:
            return
        cx = max(0, min(self._screen_w - 1, int(x)))
        cy = max(0, min(self._screen_h - 1, int(y)))

        self._xtst.XTestFakeMotionEvent(self._display, -1, cx, cy, 0)
        self._x11.XFlush(self._display)

    def click(self, button: int = 1) -> None:
        """Simulate mouse button click."""
        if not self._display:
            return
        self._xtst.XTestFakeButtonEvent(self._display, button, 1, 0)
        self._xtst.XTestFakeButtonEvent(self._display, button, 0, 0)
        self._x11.XFlush(self._display)
        log.debug("Simulated click on button %d", button)
