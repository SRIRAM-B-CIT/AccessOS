"""
AccessOS Accessibility Engine
==============================
Phase 3 & Phase 3.5: Computer vision head-pointer tracking, dwell selection,
One-Euro smoothing, deadzone filters, safe DryRunMouseBackend, VirtualCursorOverlay,
and isolated VM-only X11MouseBackend.
"""
from .head_pointer import HeadPointerEngine, TrackingState
from .dwell_clicker import DwellClicker
from .filters import DeadzoneFilter, PointFilter2D, OneEuroFilter
from .mouse_backend import (
    BaseMouseBackend,
    DryRunMouseBackend,
    X11MouseBackend,
    X11Mouse,
    UnsupportedSessionError,
    HostSafetyViolationError,
    check_session_supported,
)
from .virtual_cursor import VirtualCursorOverlay
from .tracking_overlay import TrackingOverlay

__all__ = [
    "HeadPointerEngine",
    "TrackingState",
    "DwellClicker",
    "DeadzoneFilter",
    "PointFilter2D",
    "OneEuroFilter",
    "BaseMouseBackend",
    "DryRunMouseBackend",
    "X11MouseBackend",
    "X11Mouse",
    "UnsupportedSessionError",
    "HostSafetyViolationError",
    "check_session_supported",
    "VirtualCursorOverlay",
    "TrackingOverlay",
]
