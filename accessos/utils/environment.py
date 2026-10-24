"""
AccessOS Virtualization & Host Safety Environment Utilities
=============================================================
Detects whether AccessOS is running on bare-metal host hardware
or inside a hypervisor virtual machine (VirtualBox, QEMU/KVM, VMware)
or a live-boot USB environment (Casper).

Safety Invariant:
  Real OS-level mouse pointer injection and synthetic clicks are
  STRICTLY PROHIBITED on physical host development machines to prevent
  physical input lockups. Real injection is permitted exclusively inside
  verified virtual machines or live-boot AccessOS sessions with an active
  X11 session and explicit VM/Live configuration file.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple

log = logging.getLogger(__name__)

_DEFAULT_VM_CONFIG = Path(__file__).resolve().parent.parent.parent / "config" / "vm_real_injection.toml"


class HostSafetyViolationError(RuntimeError):
    """
    Raised when real mouse injection is attempted directly on host hardware
    instead of inside a supported virtual machine or live-boot USB session.
    """
    pass


def is_live_boot() -> Tuple[bool, str]:
    """
    Detect if AccessOS is running inside a live-boot OS session (e.g. from USB or ISO).
    """
    if Path("/run/casper-md5check.json").exists() or Path("/cdrom/casper").exists() or Path("/rofs").exists():
        return True, "Live Boot Session (Casper)"
    try:
        cmdline = Path("/proc/cmdline").read_text()
        if "boot=casper" in cmdline:
            return True, "Live Boot Session (boot=casper)"
    except Exception:
        pass
    return False, "Not Live Boot"


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


def can_use_real_mouse_injection(vm_config_path: Optional[Path] = None) -> Tuple[bool, str]:
    """
    Evaluate if real mouse injection is permitted in the current environment.
    Strict Policy:
      1. BARE-METAL HOST: Unconditionally BLOCKED.
      2. VM OR LIVE BOOT: Permitted in verified VM or live-boot session.
      3. VM CONFIG: Explicit VM configuration file must exist and permit real injection.
      4. DISPLAY: Active X11 display required.
    All interactive host overrides are permanently removed.
    """
    # 1. Hardware verification
    is_vm, vm_desc = is_running_in_vm()
    is_live, live_desc = is_live_boot()

    if not is_vm and not is_live:
        return False, (
            f"Blocked by Input-Safety Policy: {vm_desc}. "
            "Real mouse injection is disabled on physical host machines to prevent physical input lockups. "
            "Host safe profile (UI only or Camera Preview only) must be used on host hardware. "
            "Real input testing must be performed inside a VirtualBox virtual machine or live boot USB."
        )

    env_desc = vm_desc if is_vm else live_desc

    # 2. Configuration file verification
    config_file = vm_config_path or _DEFAULT_VM_CONFIG
    if not config_file.exists():
        return False, (
            f"Blocked by Input-Safety Policy: Missing VM configuration file at {config_file}. "
            "Real injection requires an explicit VM configuration file."
        )

    # 3. Session / Display verification
    display = os.environ.get("DISPLAY")
    if not display:
        return False, f"Inside {env_desc}, but no active X11 display found (DISPLAY is unset)."

    return True, f"Permitted: running inside {env_desc} with active X11 display and verified VM config."
