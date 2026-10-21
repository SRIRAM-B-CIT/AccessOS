"""
AccessOS Native X11 Mouse Controller (Re-export for backwards compatibility)
=============================================================================
Redirects to accessos.engine.mouse_backend.X11MouseBackend.
STRICT SAFETY RULE: Real injection is blocked on bare-metal host systems.
"""
from .mouse_backend import (
    X11MouseBackend as X11Mouse,
    UnsupportedSessionError,
    HostSafetyViolationError,
    check_session_supported,
)

__all__ = [
    "X11Mouse",
    "UnsupportedSessionError",
    "HostSafetyViolationError",
    "check_session_supported",
]
