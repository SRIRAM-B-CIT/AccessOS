"""
AccessOS Host-Safe Mouse Backend Architecture
==============================================
Defines the safe in-memory mouse backends used for development and host testing.

Guarantees:
  - DryRunMouseBackend operates purely in-memory; updates virtual coordinates and fires callbacks.
  - ZERO imports of ctypes, ctypes.util, or native C dynamic libraries.
  - ZERO calls to XTest, X11, xdotool, or any OS-level input injection.
  - Physical mouse and keyboard are 100% unaffected.
"""
from __future__ import annotations

import abc
import logging
from typing import Callable, Optional, Set, Tuple

from ..utils.environment import HostSafetyViolationError

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
    Does NOT call any system-wide input API or load native injection libraries.
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
        if width > 0 and height > 0:
            self._screen_w = width
            self._screen_h = height

    def get_position(self) -> Tuple[int, int]:
        return (self._x, self._y)

    def move_to(self, x: int, y: int) -> None:
        cx = max(0, min(self._screen_w - 1, int(x)))
        cy = max(0, min(self._screen_h - 1, int(y)))
        self._x = cx
        self._y = cy

        if self.on_cursor_moved:
            try:
                self.on_cursor_moved(cx, cy)
            except Exception as exc:
                log.debug("on_cursor_moved callback error: %s", exc)

    def click(self, button: int = 1) -> None:
        self.press(button)
        self.release(button)
        if self.on_click_event:
            try:
                self.on_click_event(self._x, self._y, button)
            except Exception as exc:
                log.debug("on_click_event callback error: %s", exc)

    def press(self, button: int = 1) -> None:
        self._pressed_buttons.add(button)

    def release(self, button: int = 1) -> None:
        self._pressed_buttons.discard(button)

    def release_all_buttons(self) -> None:
        self._pressed_buttons.clear()

    def close(self) -> None:
        self.release_all_buttons()


class NullMouseBackend(BaseMouseBackend):
    """No-op backend for host UI-only mode."""

    @property
    def is_real_injection(self) -> bool:
        return False

    @property
    def screen_size(self) -> Tuple[int, int]:
        return (1280, 720)

    def get_position(self) -> Tuple[int, int]:
        return (640, 360)

    def move_to(self, x: int, y: int) -> None:
        pass

    def click(self, button: int = 1) -> None:
        pass

    def press(self, button: int = 1) -> None:
        pass

    def release(self, button: int = 1) -> None:
        pass

    def release_all_buttons(self) -> None:
        pass

    def close(self) -> None:
        pass
