"""
AccessOS Safe System Controls
==============================
Interfaces with Linux system services (NetworkManager, ALSA/amixer,
XRandR/backlight, systemd/loginctl) using explicit argument arrays
(never shell=True) and robust permission failure handling.

Security guarantees:
  - Wi-Fi passwords are NEVER written to logs, config files, command history,
    or process argument lists (passed exclusively via stdin to nmcli --ask).
  - All operations fail safely with explicit, user-intelligible permission error
    messages if Polkit or system permissions are denied.
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
    """Provides safe hardware, network, and session controls."""

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
            matches = re.findall(r"\[(\d+)%\]", res.stdout)
            if matches:
                return int(matches[0])
        except Exception as exc:
            log.warning("Could not query audio volume: %s", exc)
        return 80

    @staticmethod
    def set_volume(percent: int) -> tuple[bool, str]:
        """
        Set master volume (0 - 100%).
        Returns (success: bool, message: str).
        """
        clamped = max(0, min(100, int(percent)))
        amixer = shutil.which("amixer")
        if not amixer:
            return False, "Audio control utility (amixer) is not installed."
        try:
            res = subprocess.run(
                [amixer, "-q", "sset", "Master", f"{clamped}%"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if res.returncode == 0:
                return True, f"Volume set to {clamped}%"
            err = res.stderr.strip() or "Audio control permission denied or device busy."
            log.error("Failed to set volume: %s", err)
            return False, f"Audio permission error: {err}"
        except Exception as exc:
            log.error("Exception setting volume: %s", exc)
            return False, f"Audio control failed: {exc}"

    # ── Display Brightness ────────────────────────────────────────────────────

    @staticmethod
    def get_connected_display() -> str:
        """Identify primary or connected X11 display name."""
        xrandr = shutil.which("xrandr")
        if not xrandr:
            return "eDP-1"
        try:
            res = subprocess.run(
                [xrandr, "--query"],
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
    def set_brightness(cls, percent: int) -> tuple[bool, str]:
        """
        Set display brightness (10% to 100%).
        Uses XRandR software scaling as safe, non-privileged control.
        Returns (success: bool, message: str).
        """
        clamped = max(10, min(100, int(percent)))
        scale = clamped / 100.0
        display = cls.get_connected_display()
        xrandr = shutil.which("xrandr")
        if not xrandr:
            return False, "Display utility (xrandr) is not available."
        try:
            res = subprocess.run(
                [xrandr, "--output", display, "--brightness", f"{scale:.2f}"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if res.returncode == 0:
                return True, f"Brightness set to {clamped}%"
            err = res.stderr.strip() or "Display brightness permission denied or output unavailable."
            log.error("Failed to set brightness: %s", err)
            return False, f"Brightness error: {err}"
        except Exception as exc:
            log.error("Exception setting brightness: %s", exc)
            return False, f"Brightness control failed: {exc}"

    # ── Wi-Fi (nmcli) ──────────────────────────────────────────────────────────

    @staticmethod
    def is_wifi_enabled() -> bool:
        """Check whether Wi-Fi radio is currently enabled."""
        nmcli = shutil.which("nmcli")
        if not nmcli:
            return False
        try:
            res = subprocess.run(
                [nmcli, "radio", "wifi"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            return res.stdout.strip().lower() == "enabled"
        except Exception:
            return False

    @staticmethod
    def set_wifi_enabled(enabled: bool) -> tuple[bool, str]:
        """Turn Wi-Fi radio on or off. Returns (success, message)."""
        nmcli = shutil.which("nmcli")
        if not nmcli:
            return False, "NetworkManager CLI (nmcli) is not installed."
        state = "on" if enabled else "off"
        try:
            res = subprocess.run(
                [nmcli, "radio", "wifi", state],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if res.returncode == 0:
                return True, f"Wi-Fi turned {state}"
            err = res.stderr.strip() or "Permission denied to toggle Wi-Fi radio."
            log.error("Failed to toggle Wi-Fi: %s", err)
            return False, f"Wi-Fi permission error: {err}"
        except Exception as exc:
            log.error("Exception toggling Wi-Fi: %s", exc)
            return False, f"Wi-Fi control failed: {exc}"

    @staticmethod
    def list_wifi_networks() -> list[WifiNetwork]:
        """Scan and list available Wi-Fi networks via nmcli."""
        networks: list[WifiNetwork] = []
        nmcli = shutil.which("nmcli")
        if not nmcli:
            return networks
        try:
            res = subprocess.run(
                [nmcli, "-t", "-f", "SSID,SIGNAL,SECURITY,IN-USE", "device", "wifi", "list"],
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
        """
        Connect to a Wi-Fi network.
        SECURITY: Passwords are NEVER passed in argv/command-line arguments.
        When a password is provided, nmcli --ask is invoked and the secret
        is piped strictly through standard input (stdin).
        """
        nmcli = shutil.which("nmcli")
        if not nmcli:
            return False, "NetworkManager CLI (nmcli) is not available"

        log.info("Attempting Wi-Fi connection to SSID: '%s' (password protected: %s)", ssid, bool(password))

        try:
            if password:
                # Use --ask flag so nmcli reads password from stdin, NOT argv
                proc = subprocess.Popen(
                    [nmcli, "--ask", "device", "wifi", "connect", ssid],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                stdout, stderr = proc.communicate(input=f"{password}\n", timeout=15)
                ret = proc.returncode
            else:
                proc = subprocess.run(
                    [nmcli, "device", "wifi", "connect", ssid],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                stdout, stderr = proc.stdout, proc.stderr
                ret = proc.returncode

            if ret == 0:
                log.info("Wi-Fi connected successfully to '%s'", ssid)
                return True, f"Successfully connected to {ssid}"

            err = stderr.strip() or stdout.strip() or "Authentication failed or permission denied."
            log.warning("Wi-Fi connection to '%s' failed: %s", ssid, err)
            return False, f"Connection failed: {err}"
        except subprocess.TimeoutExpired:
            return False, "Wi-Fi connection timed out."
        except Exception as exc:
            log.error("Wi-Fi connection exception: %s", exc)
            return False, f"Connection error: {exc}"

    # ── Power & Session (Protected — executed only after confirmation) ─────────

    @staticmethod
    def lock_session() -> tuple[bool, str]:
        """Lock user session safely. Returns (success, message)."""
        candidates = [
            ["loginctl", "lock-session"],
            ["xflock4"],
            ["xdg-screensaver", "lock"],
        ]
        for cmd in candidates:
            binary = shutil.which(cmd[0])
            if binary:
                try:
                    res = subprocess.run(
                        [binary] + cmd[1:],
                        capture_output=True,
                        text=True,
                        timeout=3,
                    )
                    if res.returncode == 0:
                        log.info("Locked session via %s", cmd[0])
                        return True, "Session locked successfully."
                    log.warning("Lock via %s returned code %d: %s", cmd[0], res.returncode, res.stderr)
                except Exception as exc:
                    log.warning("Could not lock with %s: %s", cmd[0], exc)

        return False, "Session lock failed: permission denied or no screen locker found."

    @staticmethod
    def restart_system() -> tuple[bool, str]:
        """Reboot machine safely. Returns (success, message)."""
        candidates = [
            ["systemctl", "reboot"],
            ["loginctl", "reboot"],
        ]
        for cmd in candidates:
            binary = shutil.which(cmd[0])
            if binary:
                try:
                    res = subprocess.run(
                        [binary] + cmd[1:],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if res.returncode == 0:
                        log.info("Requested reboot via %s", cmd[0])
                        return True, "Reboot initiated."
                    err = res.stderr.strip() or "System restart permission denied."
                    log.error("Reboot command failed (%s): %s", cmd[0], err)
                    return False, f"Restart failed: {err}"
                except Exception as exc:
                    log.error("Reboot exception (%s): %s", cmd[0], exc)
                    return False, f"Restart failed: {exc}"

        return False, "System reboot failed: systemctl/loginctl not found or permission denied."

    @staticmethod
    def poweroff_system() -> tuple[bool, str]:
        """Shut down machine safely. Returns (success, message)."""
        candidates = [
            ["systemctl", "poweroff"],
            ["loginctl", "poweroff"],
        ]
        for cmd in candidates:
            binary = shutil.which(cmd[0])
            if binary:
                try:
                    res = subprocess.run(
                        [binary] + cmd[1:],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if res.returncode == 0:
                        log.info("Requested poweroff via %s", cmd[0])
                        return True, "Power off initiated."
                    err = res.stderr.strip() or "System power off permission denied."
                    log.error("Poweroff command failed (%s): %s", cmd[0], err)
                    return False, f"Power off failed: {err}"
                except Exception as exc:
                    log.error("Poweroff exception (%s): %s", cmd[0], exc)
                    return False, f"Power off failed: {exc}"

        return False, "System shutdown failed: systemctl/loginctl not found or permission denied."
