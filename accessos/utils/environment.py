"""
AccessOS Virtualization & Host Safety Environment Utilities
=============================================================
Detects whether AccessOS is running on bare-metal host hardware
or inside a hypervisor virtual machine (VirtualBox, QEMU/KVM, VMware).

Safety Invariant:
  Real OS-level mouse pointer injection and synthetic clicks are
  STRICTLY PROHIBITED on host machines to prevent physical input lockups.
  Real injection is permitted exclusively inside verified virtual machines.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Tuple

log = logging.getLogger(__name__)


class HostSafetyViolationError(RuntimeError):
    """
    Raised when real mouse injection is attempted directly on host hardware
    instead of inside a supported virtual machine.
    """
    pass


def is_running_in_vm() -> Tuple[bool, str]:
    """
    Detect if the current environment is running inside a virtual machine.
    Returns:
        (is_vm: bool, description: str)
    """
    # 1. Check systemd-detect-virt if available
    sd_virt = shutil.which("systemd-detect-virt")
    if sd_virt:
        try:
            res = subprocess.run(
                [sd_virt],
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            out = res.stdout.strip().lower()
            if res.returncode == 0 and out and out != "none":
                log.info("Detected VM via systemd-detect-virt: %s", out)
                return True, f"Virtual Machine ({out})"
        except Exception as exc:
            log.debug("systemd-detect-virt check failed: %s", exc)

    # 2. Check DMI product_name and sys_vendor (sysfs)
    dmi_path = Path("/sys/class/dmi/id")
    if dmi_path.exists():
        try:
            prod_file = dmi_path / "product_name"
            vendor_file = dmi_path / "sys_vendor"
            prod = prod_file.read_text(encoding="utf-8").strip() if prod_file.exists() else ""
            vendor = vendor_file.read_text(encoding="utf-8").strip() if vendor_file.exists() else ""

            combined = f"{vendor} {prod}".lower()
            vm_keywords = ["virtualbox", "innotek", "qemu", "kvm", "vmware", "xen", "hyper-v", "bochs"]
            for kw in vm_keywords:
                if kw in combined:
                    log.info("Detected VM via DMI table: %s %s", vendor, prod)
                    return True, f"Virtual Machine ({vendor} {prod})"

            log.info("Host hardware detected via DMI: %s %s", vendor, prod)
            return False, f"Host Hardware ({vendor} {prod})"
        except Exception as exc:
            log.debug("DMI check error: %s", exc)

    # Default to host hardware for safety
    return False, "Host Hardware (Unknown DMI)"


def can_use_real_mouse_injection() -> Tuple[bool, str]:
    """
    Evaluate if real mouse injection is permitted in the current environment.
    Rule:
      - Blocked unconditionally on physical host hardware.
      - Permitted inside supported virtual machines with an X11 session.
      - Can be forcefully overridden ONLY via ACCESSOS_FORCE_REAL_MOUSE_UNSAFE=1 (for automated CI/tests).
    """
    # Explicit unsafe override flag (must be explicitly exported)
    if os.environ.get("ACCESSOS_FORCE_REAL_MOUSE_UNSAFE", "0") == "1":
        log.warning("SAFETY OVERRIDE: ACCESSOS_FORCE_REAL_MOUSE_UNSAFE is set!")
        return True, "Forced unsafe mode via environment variable."

    is_vm, desc = is_running_in_vm()
    if not is_vm:
        return False, (
            f"Blocked by Input-Safety Policy: {desc}. "
            "Real mouse injection is disabled on physical host machines to prevent physical input lockups. "
            "Dry-run mode with Virtual Cursor will be used instead. "
            "Real input testing must be performed inside a VirtualBox virtual machine."
        )

    # Inside VM: ensure X11 session is active
    display = os.environ.get("DISPLAY")
    if not display:
        return False, "Inside VM, but no active X11 display found (DISPLAY is unset)."

    return True, f"Permitted: running inside {desc} with active X11 display."
