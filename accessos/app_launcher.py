"""
AccessOS Application Launcher
===============================
Launches the six permitted AccessOS applications as isolated subprocesses.

Security rules (enforced here):
  - Never uses ``shell=True``.
  - Never constructs command strings from untrusted/voice input.
  - Commands are always lists of strings from the config allow-list.
  - Each app runs in a new session (``start_new_session=True``) so it is
    independent of the AccessOS process.

Fallback logic:
  If the configured command is not found, tries a list of well-known
  alternatives before giving up and calling the optional ``on_error``
  callback.
"""
from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable, Sequence

log = logging.getLogger(__name__)

# ── Default commands ──────────────────────────────────────────────────────────
# These match what is pre-installed on Linux Mint 22.3 Xfce.
# On the development host (Zorin OS) the fallbacks cover what is available.
_DEFAULT_CMDS: dict[str, list[str]] = {
    "browser":  ["firefox"],
    "files":    ["thunar"],
    "terminal": ["xfce4-terminal"],
    "images":   ["ristretto"],
    "videos":   ["parole"],
    # "settings" is handled specially in HomeScreen (shows placeholder in P1)
}

# ── Fallbacks (tried in order when the primary command is not found) ───────────
_FALLBACKS: dict[str, list[list[str]]] = {
    "browser":  [["firefox-esr"], ["chromium-browser"], ["chromium"],
                 ["epiphany-browser"]],
    "files":    [["nautilus"], ["pcmanfm"], ["nemo"]],
    "terminal": [["gnome-terminal"], ["xterm"], ["konsole"], ["lxterminal"]],
    "images":   [["eog"], ["gpicview"], ["feh"], ["shotwell"]],
    "videos":   [["vlc"], ["mpv"], ["totem"], ["celluloid"]],
}

ErrorCallback = Callable[[str], None]


class AppLauncher:
    """
    Launch approved AccessOS applications.

    Parameters
    ----------
    app_commands:
        Optional override mapping of app-key → command list, typically
        read from ``config/accessos_defaults.toml``.
    """

    def __init__(self, app_commands: dict | None = None) -> None:
        self._cmds: dict[str, list[str]] = dict(_DEFAULT_CMDS)
        if app_commands:
            # Only accept keys that are in our allow-list
            for key in _DEFAULT_CMDS:
                if key in app_commands and isinstance(app_commands[key], list):
                    self._cmds[key] = [str(x) for x in app_commands[key]]

    # ── Public API ─────────────────────────────────────────────────────────────

    def launch(self, app_key: str, on_error: ErrorCallback | None = None) -> bool:
        """
        Launch *app_key*.  Returns ``True`` on success, ``False`` otherwise.

        The optional *on_error* callback receives a human-readable error
        string so the caller can display it to the user.
        """
        cmd = self._cmds.get(app_key)
        if cmd is None:
            msg = f"'{app_key}' is not in the application allow-list."
            log.error(msg)
            if on_error:
                on_error(msg)
            return False

        return self._try_launch(app_key, cmd, on_error)

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _try_launch(
        self,
        app_key: str,
        cmd: Sequence[str],
        on_error: ErrorCallback | None,
    ) -> bool:
        try:
            subprocess.Popen(
                list(cmd),
                shell=False,               # Never shell=True
                start_new_session=True,    # Isolate from AccessOS PID group
                close_fds=True,
            )
            log.info("Launched '%s': %s", app_key, cmd)
            return True
        except FileNotFoundError:
            log.warning("Command not found: %s — trying fallbacks", cmd[0])
            return self._try_fallbacks(app_key, on_error)
        except PermissionError as exc:
            msg = f"Permission denied launching {cmd[0]}: {exc}"
            log.error(msg)
            if on_error:
                on_error(msg)
            return False
        except Exception as exc:
            msg = f"Unexpected error launching {cmd[0]}: {exc}"
            log.error(msg)
            if on_error:
                on_error(msg)
            return False

    def _try_fallbacks(
        self,
        app_key: str,
        on_error: ErrorCallback | None,
    ) -> bool:
        for fallback_cmd in _FALLBACKS.get(app_key, []):
            try:
                subprocess.Popen(
                    fallback_cmd,
                    shell=False,
                    start_new_session=True,
                    close_fds=True,
                )
                log.info("Launched fallback for '%s': %s", app_key, fallback_cmd)
                return True
            except FileNotFoundError:
                continue
            except Exception as exc:
                log.debug("Fallback %s failed: %s", fallback_cmd, exc)

        msg = (
            f"Could not find any application for '{app_key}'. "
            "Check that the required software is installed."
        )
        log.error(msg)
        if on_error:
            on_error(msg)
        return False
