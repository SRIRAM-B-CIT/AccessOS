"""
AccessOS Accessibility Engine
==============================
Phase 3: Computer vision head-pointer tracking, dwell selection,
One-Euro smoothing, deadzone filters, and X11 native pointer control.
"""
from .head_pointer import HeadPointerEngine, TrackingState
from .dwell_clicker import DwellClicker
from .filters import DeadzoneFilter, PointFilter2D, OneEuroFilter
from .x11_mouse import X11Mouse, UnsupportedSessionError, check_session_supported
from .tracking_overlay import TrackingOverlay

__all__ = [
    "HeadPointerEngine",
    "TrackingState",
    "DwellClicker",
    "DeadzoneFilter",
    "PointFilter2D",
    "OneEuroFilter",
    "X11Mouse",
    "UnsupportedSessionError",
    "check_session_supported",
    "TrackingOverlay",
]
