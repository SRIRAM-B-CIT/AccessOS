"""
AccessOS Launch Profiles & Safety Modes
========================================
Defines three strictly isolated execution profiles:

1. LaunchProfile.HOST_SAFE ("host-safe", DEFAULT):
   - Mandatory default for physical host hardware development.
   - Starts ONLY the UI.
   - Zero camera tracking engine initialized.
   - Zero mouse backend loaded (real OS injection is physically impossible).
   - Safe against any physical mouse/keyboard disruption.

2. LaunchProfile.CAMERA_PREVIEW ("camera-preview"):
   - Host camera preview only.
   - Opens the camera and renders face tracking reticle/telemetry in local overlay.
   - STRICT INVARIANT: Dwell clicking is NOT initialized.
   - STRICT INVARIANT: No OS input backend is initialized. Zero system events sent.

3. LaunchProfile.VM_REAL ("vm-real"):
   - Reserved exclusively for verified virtual machines (VirtualBox / Mint Xfce ISO).
   - Requires verified VM detection (is_running_in_vm() == True).
   - Requires explicit VM configuration file (config/vm_real_injection.toml).
   - Requires active X11 display session.
   - Refuses to launch on bare-metal host hardware with HostSafetyViolationError.
"""
from __future__ import annotations

import enum
import logging
import os
from pathlib import Path
from typing import Optional

from .environment import HostSafetyViolationError, can_use_real_mouse_injection

log = logging.getLogger(__name__)


class LaunchProfile(str, enum.Enum):
    HOST_SAFE = "host-safe"
    CAMERA_PREVIEW = "camera-preview"
    VM_REAL = "vm-real"

    @classmethod
    def from_str(cls, val: str) -> LaunchProfile:
        normalized = val.strip().lower()
        for member in cls:
            if member.value == normalized:
                return member
        valid = ", ".join(m.value for m in cls)
        raise ValueError(f"Unknown launch profile '{val}'. Valid profiles are: {valid}")


def resolve_profile(raw_profile: Optional[str] = None) -> LaunchProfile:
    """
    Resolve active profile from explicit argument, environment variable, or safe default.
    Priority:
      1. raw_profile argument (CLI --profile)
      2. ACCESSOS_PROFILE environment variable
      3. LaunchProfile.HOST_SAFE (default)
    """
    if raw_profile:
        return LaunchProfile.from_str(raw_profile)

    env_val = os.environ.get("ACCESSOS_PROFILE")
    if env_val:
        return LaunchProfile.from_str(env_val)

    return LaunchProfile.HOST_SAFE


def validate_profile_prerequisites(
    profile: LaunchProfile,
    vm_config_path: Optional[Path] = None,
) -> None:
    """
    Strict safety validation before profile execution.
    Raises HostSafetyViolationError if VM_REAL is attempted on host or without VM config.
    """
    if profile == LaunchProfile.VM_REAL:
        allowed, reason = can_use_real_mouse_injection(vm_config_path=vm_config_path)
        if not allowed:
            log.critical("FATAL: VM_REAL profile rejected: %s", reason)
            raise HostSafetyViolationError(
                f"VM_REAL profile cannot be activated: {reason}\n"
                "Real mouse injection is forbidden on physical host systems.\n"
                "To run safely on host, use: --profile host-safe or --profile camera-preview"
            )
        log.info("VM_REAL profile validated for virtual machine execution.")
    else:
        log.info("Active profile '%s' is verified host-safe.", profile.value)
