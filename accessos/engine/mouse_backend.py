"""
AccessOS Mouse Backend Architecture (Input-Safety Redesign)
============================================================
Defines two completely isolated mouse backends:

1. DryRunMouseBackend (DEFAULT & HOST-SAFE):
   - Used for all host development and testing.
   - Operates purely in-memory; updates virtual coordinates and fires callbacks.
   - NEVER calls XTest, X11, xdotool, ctypes, or any OS-level input injection.
   - Physical mouse and keyboard are 100% unaffected.

2. X11MouseBackend (VM-ONLY):
   - Reserved strictly for VirtualBox or target Linux Mint Xfce live ISO.
   - Blocked by default on physical host machines via HostSafetyViolationError.
   - Renders 64-bit XTest pointer motion and synthetic clicks with guaranteed
     button release cleanup.
"""
from __future__ import annotations

import abc
import ctypes
import ctypes.util
import logging
import os
from typing import Callable, Optional, Set, Tuple

from ..utils.environment import HostSafetyViolationError, can_use_real_mouse_injection

log = logging.getLogger(__name__)


class UnsupportedSessionError(RuntimeError):
    """Raised when pointer injection is attempted on an unsupported session (e.g. pure Wayland)."""
    pass


class BaseMouseBackend(abc.ABC):
    """Abstract base class for pointer controllers."""

    @property
    @abc.abstractmethod
    def is_real_injection(self) -> bool:
        """True if the backend injects real events into the OS desktop server."""
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def screen_size(self) -> Tuple[int, int]:
        """Virtual or physical screen resolution (width, height)."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_position(self) -> Tuple[int, int]:
        """Return current cursor coordinates (x, y)."""
        raise NotImplementedError

    @abc.abstractmethod
    def move_to(self, x: int, y: int) -> None:
        """Move cursor to coordinate (x, y)."""
        raise NotImplementedError

    @abc.abstractmethod
    def click(self, button: int = 1) -> None:
        """Simulate a mouse button click (press + release)."""
        raise NotImplementedError

    @abc.abstractmethod
    def press(self, button: int = 1) -> None:
        """Press down a mouse button."""
        raise NotImplementedError

    @abc.abstractmethod
    def release(self, button: int = 1) -> None:
        """Release a held mouse button."""
        raise NotImplementedError

    @abc.abstractmethod
    def release_all_buttons(self) -> None:
        """Guarantee every synthetic mouse button is released."""
        raise NotImplementedError

    @abc.abstractmethod
    def close(self) -> None:
        """Release resources and ensure no input remains held."""
        raise NotImplementedError


# ─────────────────────────────────────────────────────────────────────────────
# DryRunMouseBackend (Host Safe & Default)
# ─────────────────────────────────────────────────────────────────────────────

class DryRunMouseBackend(BaseMouseBackend):
    """
    In-memory virtual mouse backend for safe host development.
    Does NOT call any system-wide input API.
    """

    def __init__(
        self,
        screen_size: Tuple[int, int] = (1280, 720),
        on_cursor_moved: Optional[Callable[[int, int], None]] = None,
        on_click_event: Optional[Callable[[int, int, int], None]] = None,
    ) -> None:
        self._screen_w, self._screen_h = screen_size
        self._x = self._screen_w // 2
        self._y = self._screen_h // 2
        self._pressed_buttons: Set[int] = set()

        self.on_cursor_moved = on_cursor_moved
        self.on_click_event = on_click_event

        log.info("DryRunMouseBackend initialized: %dx%d (SAFE MODE — zero host input injection)", self._screen_w, self._screen_h)

    @property
    def is_real_injection(self) -> bool:
        return False

    @property
    def screen_size(self) -> Tuple[int, int]:
        return (self._screen_w, self._screen_h)

    def set_screen_size(self, width: int, height: int) -> None:
        self._screen_w = max(100, width)
        self._screen_h = max(100, height)

    def get_position(self) -> Tuple[int, int]:
        return (self._x, self._y)

    def move_to(self, x: int, y: int) -> None:
        cx = max(0, min(self._screen_w - 1, int(x)))
        cy = max(0, min(self._screen_h - 1, int(y)))
        self._x, self._y = cx, cy

        if self.on_cursor_moved:
            try:
                self.on_cursor_moved(cx, cy)
            except Exception as exc:
                log.debug("on_cursor_moved callback failed: %s", exc)

    def click(self, button: int = 1) -> None:
        log.info("Virtual click on button %d at (%d, %d)", button, self._x, self._y)
        if self.on_click_event:
            try:
                self.on_click_event(self._x, self._y, button)
            except Exception as exc:
                log.debug("on_click_event callback failed: %s", exc)

    def press(self, button: int = 1) -> None:
        self._pressed_buttons.add(button)

    def release(self, button: int = 1) -> None:
        self._pressed_buttons.discard(button)

    def release_all_buttons(self) -> None:
        self._pressed_buttons.clear()

    def close(self) -> None:
        self.release_all_buttons()


# ─────────────────────────────────────────────────────────────────────────────
# X11MouseBackend (VM-Only Real Injection)
# ─────────────────────────────────────────────────────────────────────────────

def check_session_supported() -> Tuple[bool, str]:
    """Compatibility check for X11 sessions."""
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    display = os.environ.get("DISPLAY")

    if session_type == "wayland" and not display:
        return False, (
            "AccessOS pointer injection requires an X11 desktop session. "
            "Pure Wayland sessions do not allow simulated pointer injection."
        )

    if not display:
        return False, (
            "No X11 display found (DISPLAY environment variable is unset). "
            "AccessOS pointer injection requires an active X11 desktop session."
        )

    return True, "X11 session active."


class X11MouseBackend(BaseMouseBackend):
    """
    Real OS-level mouse controller using X11 and XTest.
    STRICT SAFETY RULE: Refuses to initialize on bare-metal host machines.
    Must only be executed inside a verified virtual machine.
    """

    def __init__(self, allow_host_override: bool = False) -> None:
        self._display = None
        self._pressed_buttons: Set[int] = set()
        self._screen_w = 1280
        self._screen_h = 720

        # Step 1: Input-safety policy verification
        allowed, reason = can_use_real_mouse_injection()
        if not allowed and not allow_host_override:
            log.critical("SAFETY VIOLATION PREVENTED: %s", reason)
            raise HostSafetyViolationError(reason)

        # Step 2: Validate X11 session
        supported, session_reason = check_session_supported()
        if not supported:
            raise UnsupportedSessionError(session_reason)

        # Step 3: Load X11 and Xtst libraries
        x11_path = ctypes.util.find_library("X11")
        if not x11_path:
            raise UnsupportedSessionError("libX11 library not found.")
        self._x11 = ctypes.CDLL(x11_path)

        xtst_path = ctypes.util.find_library("Xtst")
        if not xtst_path:
            raise UnsupportedSessionError("libXtst library not found.")
        self._xtst = ctypes.CDLL(xtst_path)

        # Explicit 64-bit signatures
        self._x11.XOpenDisplay.restype = ctypes.c_void_p
        self._x11.XOpenDisplay.argtypes = [ctypes.c_char_p]

        self._x11.XCloseDisplay.restype = ctypes.c_int
        self._x11.XCloseDisplay.argtypes = [ctypes.c_void_p]

        self._x11.XFlush.restype = ctypes.c_int
        self._x11.XFlush.argtypes = [ctypes.c_void_p]

        self._x11.XDefaultRootWindow.restype = ctypes.c_ulong
        self._x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]

        self._x11.XDisplayWidth.restype = ctypes.c_int
        self._x11.XDisplayWidth.argtypes = [ctypes.c_void_p, ctypes.c_int]

        self._x11.XDisplayHeight.restype = ctypes.c_int
        self._x11.XDisplayHeight.argtypes = [ctypes.c_void_p, ctypes.c_int]

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
            raise UnsupportedSessionError("Failed to open X11 Display.")

        self._root = self._x11.XDefaultRootWindow(self._display)
        self._screen_w = self._x11.XDisplayWidth(self._display, 0)
        self._screen_h = self._x11.XDisplayHeight(self._display, 0)
        self._pressed_buttons: Set[int] = set()

        log.warning("X11MouseBackend initialized for VM REAL INJECTION: screen %dx%d", self._screen_w, self._screen_h)

    @property
    def is_real_injection(self) -> bool:
        return True

    @property
    def screen_size(self) -> Tuple[int, int]:
        return (self._screen_w, self._screen_h)

    def get_position(self) -> Tuple[int, int]:
        if not self._display:
            return (0, 0)
        root_ret = ctypes.c_ulong()
        child_ret = ctypes.c_ulong()
        root_x, root_y = ctypes.c_int(), ctypes.c_int()
        win_x, win_y = ctypes.c_int(), ctypes.c_int()
        mask = ctypes.c_uint()

        self._x11.XQueryPointer(
            self._display, self._root,
            ctypes.byref(root_ret), ctypes.byref(child_ret),
            ctypes.byref(root_x), ctypes.byref(root_y),
            ctypes.byref(win_x), ctypes.byref(win_y),
            ctypes.byref(mask),
        )
        return (root_x.value, root_y.value)

    def move_to(self, x: int, y: int) -> None:
        if not self._display:
            return
        cx = max(0, min(self._screen_w - 1, int(x)))
        cy = max(0, min(self._screen_h - 1, int(y)))
        self._xtst.XTestFakeMotionEvent(self._display, -1, cx, cy, 0)
        self._x11.XFlush(self._display)

    def press(self, button: int = 1) -> None:
        if not self._display:
            return
        self._pressed_buttons.add(button)
        self._xtst.XTestFakeButtonEvent(self._display, button, 1, 0)
        self._x11.XFlush(self._display)

    def release(self, button: int = 1) -> None:
        if not self._display:
            return
        self._pressed_buttons.discard(button)
        self._xtst.XTestFakeButtonEvent(self._display, button, 0, 0)
        self._x11.XFlush(self._display)

    def click(self, button: int = 1) -> None:
        """Simulate mouse click with guaranteed release in finally block."""
        if not self._display:
            return
        try:
            self.press(button)
        finally:
            self.release(button)

    def release_all_buttons(self) -> None:
        """
        Guaranteed safety release: iterates through every tracked button
        plus standard buttons (1, 2, 3) to ensure zero buttons remain down.
        """
        if not self._display:
            return
        to_release = set(self._pressed_buttons) | {1, 2, 3}
        for btn in to_release:
            try:
                self._xtst.XTestFakeButtonEvent(self._display, btn, 0, 0)
            except Exception as exc:
                log.debug("Error releasing button %d: %s", btn, exc)
        self._pressed_buttons.clear()
        try:
            self._x11.XFlush(self._display)
            log.info("X11MouseBackend: all synthetic buttons released and flushed")
        except Exception:
            pass

    def close(self) -> None:
        self.release_all_buttons()
        if hasattr(self, "_display") and self._display:
            try:
                self._x11.XCloseDisplay(self._display)
            except Exception:
                pass
            self._display = None

    def __del__(self) -> None:
        self.close()


# Alias for backward compatibility in imports
X11Mouse = X11MouseBackend
