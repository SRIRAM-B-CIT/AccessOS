"""
AccessOS Safe System Controls
==============================
Interfaces with Linux system services (NetworkManager, ALSA/amixer,
XRandR/backlight, systemd/loginctl) using explicit argument arrays
(never shell=True) and robust error handling.
"""
from __future__ import annotations

import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class WifiNetwork:
    ssid: str
    signal: int           # 0 to 100
    security: str         # e.g. "WPA2", "Open"
    in_use: bool          # True if currently connected


class SystemControl:
    """Provides safe hardware and session controls."""

    # ── Audio Volume (amixer) ──────────────────────────────────────────────────

    @staticmethod
    def get_volume() -> int:
        """Return current Master volume percentage (0 - 100)."""
        if not shutil.which("amixer"):
            return 80
        try:
            res = subprocess.run(
                ["amixer", "sget", "Master"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            # Find percentages like [85%]
            matches = re.findall(r"\[(\d+)%\]", res.stdout)
            if matches:
                return int(matches[0])
        except Exception as exc:
            log.warning("Could not read volume via amixer: %s", exc)
        return 80

    @staticmethod
    def set_volume(percent: int) -> bool:
        """Set master volume (0 - 100%)."""
        clamped = max(0, min(100, int(percent)))
        if not shutil.which("amixer"):
            log.warning("amixer not installed; volume change ignored")
            return False
        try:
            res = subprocess.run(
                ["amixer", "-q", "sset", "Master", f"{clamped}%"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            return res.returncode == 0
        except Exception as exc:
            log.error("Failed to set volume: %s", exc)
            return False

    # ── Display Brightness ────────────────────────────────────────────────────

    @staticmethod
    def get_connected_display() -> str:
        """Identify primary or connected X11 display name."""
        if not shutil.which("xrandr"):
            return "eDP-1"
        try:
            res = subprocess.run(
                ["xrandr", "--query"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            for line in res.stdout.splitlines():
                if " connected" in line:
                    return line.split()[0]
        except Exception as exc:
            log.warning("Could not query xrandr display: %s", exc)
        return "eDP-1"

    @classmethod
    def set_brightness(cls, percent: int) -> bool:
        """
        Set display brightness (10% to 100%).
        Uses XRandR software scaling as safe, non-privileged control.
        """
        clamped = max(10, min(100, int(percent)))
        scale = clamped / 100.0
        display = cls.get_connected_display()
        if not shutil.which("xrandr"):
            return False
        try:
            res = subprocess.run(
                ["xrandr", "--output", display, "--brightness", f"{scale:.2f}"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            return res.returncode == 0
        except Exception as exc:
            log.error("Failed to set brightness: %s", exc)
            return False

    # ── Wi-Fi (nmcli) ──────────────────────────────────────────────────────────

    @staticmethod
    def is_wifi_enabled() -> bool:
        """Check whether Wi-Fi radio is currently enabled."""
        if not shutil.which("nmcli"):
            return False
        try:
            res = subprocess.run(
                ["nmcli", "radio", "wifi"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            return res.stdout.strip().lower() == "enabled"
        except Exception:
            return False

    @staticmethod
    def set_wifi_enabled(enabled: bool) -> bool:
        """Turn Wi-Fi radio on or off."""
        if not shutil.which("nmcli"):
            return False
        state = "on" if enabled else "off"
        try:
            res = subprocess.run(
                ["nmcli", "radio", "wifi", state],
                capture_output=True,
                text=True,
                timeout=3,
            )
            return res.returncode == 0
        except Exception as exc:
            log.error("Failed to toggle Wi-Fi: %s", exc)
            return False

    @staticmethod
    def list_wifi_networks() -> list[WifiNetwork]:
        """Scan and list available Wi-Fi networks via nmcli."""
        networks: list[WifiNetwork] = []
        if not shutil.which("nmcli"):
            return networks
        try:
            # -t (terse/colon-separated), -f (SSID,SIGNAL,SECURITY,IN-USE)
            res = subprocess.run(
                ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY,IN-USE", "device", "wifi", "list"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            seen_ssids: set[str] = set()
            for line in res.stdout.splitlines():
                parts = line.strip().split(":")
                if len(parts) >= 4:
                    ssid = parts[0].strip()
                    if not ssid or ssid in seen_ssids:
                        continue
                    seen_ssids.add(ssid)
                    try:
                        signal = int(parts[1].strip())
                    except ValueError:
                        signal = 50
                    sec = parts[2].strip() or "Open"
                    in_use = (parts[3].strip() == "*")
                    networks.append(
                        WifiNetwork(
                            ssid=ssid,
                            signal=signal,
                            security=sec,
                            in_use=in_use,
                        )
                    )
        except Exception as exc:
            log.warning("Could not list Wi-Fi networks: %s", exc)
        return networks

    @staticmethod
    def connect_wifi(ssid: str, password: str | None = None) -> tuple[bool, str]:
        """Connect to a Wi-Fi network."""
        if not shutil.which("nmcli"):
            return False, "NetworkManager CLI (nmcli) is not available"
        cmd = ["nmcli", "device", "wifi", "connect", ssid]
        if password:
            cmd.extend(["password", password])
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15,
            )
            if res.returncode == 0:
                return True, f"Successfully connected to {ssid}"
            return False, res.stderr.strip() or res.stdout.strip() or "Failed to connect"
        except Exception as exc:
            return False, str(exc)

    # ── Power & Session (Protected — executed only after confirmation) ─────────

    @staticmethod
    def lock_session() -> bool:
        """Lock user session safely."""
        for cmd in (["loginctl", "lock-session"], ["xflock4"], ["xdg-screensaver", "lock"]):
            if shutil.which(cmd[0]):
                try:
                    subprocess.Popen(cmd)
                    log.info("Locked session via %s", cmd[0])
                    return True
                except Exception as exc:
                    log.warning("Could not lock with %s: %s", cmd[0], exc)
        return False

    @staticmethod
    def restart_system() -> bool:
        """Reboot machine safely."""
        for cmd in (["systemctl", "reboot"], ["loginctl", "reboot"]):
            if shutil.which(cmd[0]):
                try:
                    subprocess.Popen(cmd)
                    log.info("Requested reboot via %s", cmd[0])
                    return True
                except Exception as exc:
                    log.error("Reboot command failed: %s", exc)
        return False

    @staticmethod
    def poweroff_system() -> bool:
        """Shut down machine safely."""
        for cmd in (["systemctl", "poweroff"], ["loginctl", "poweroff"]):
            if shutil.which(cmd[0]):
                try:
                    subprocess.Popen(cmd)
                    log.info("Requested poweroff via %s", cmd[0])
                    return True
                except Exception as exc:
                    log.error("Poweroff command failed: %s", exc)
        return False
