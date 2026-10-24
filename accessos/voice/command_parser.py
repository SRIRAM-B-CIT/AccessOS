"""
AccessOS Voice Command Parser & Strict Allowlist
=================================================
Security-first speech command parser.
Guarantees:
  - Recognized speech is NEVER passed to a shell, terminal, or generic command runner.
  - Matches exclusively against an explicit allowlist of safe commands.
  - Rejects any dangerous tokens (rm, sudo, bash, delete, install, etc.).
  - Distinguishes direct commands from actions requiring spoken confirmation.
  - Includes document reader accessibility control commands.
"""
from __future__ import annotations

import enum
import logging
import re
from typing import Dict, List, Set

log = logging.getLogger(__name__)


class CommandAction(enum.Enum):
    # App launch commands
    OPEN_BROWSER      = "OPEN_BROWSER"
    OPEN_FILES        = "OPEN_FILES"
    OPEN_TERMINAL     = "OPEN_TERMINAL"
    OPEN_SETTINGS     = "OPEN_SETTINGS"
    OPEN_IMAGES       = "OPEN_IMAGES"
    OPEN_VIDEOS       = "OPEN_VIDEOS"

    # Navigation & control
    GO_HOME           = "GO_HOME"
    PAUSE_CONTROL     = "PAUSE_CONTROL"
    RESUME_CONTROL    = "RESUME_CONTROL"
    STOP_TRACKING     = "STOP_TRACKING"
    READ_STATUS       = "READ_STATUS"
    HELP              = "HELP"
    VOLUME_UP         = "VOLUME_UP"
    VOLUME_DOWN       = "VOLUME_DOWN"

    # Document reading controls (Accessibility feature)
    READ_DOCUMENT     = "READ_DOCUMENT"
    PAUSE_READING     = "PAUSE_READING"
    RESUME_READING    = "RESUME_READING"
    STOP_READING      = "STOP_READING"
    READING_FASTER    = "READING_FASTER"
    READING_SLOWER    = "READING_SLOWER"
    NEXT_SENTENCE     = "NEXT_SENTENCE"
    PREVIOUS_SENTENCE = "PREVIOUS_SENTENCE"

    # Protected system actions (require spoken confirmation)
    RESTART_REQUEST   = "RESTART_REQUEST"
    SHUTDOWN_REQUEST  = "SHUTDOWN_REQUEST"

    # Confirmation responses
    CONFIRM_YES       = "CONFIRM_YES"
    CONFIRM_CANCEL    = "CONFIRM_CANCEL"


# Strict token blacklist — immediately rejects any recognized string containing these
DANGEROUS_TOKENS: Set[str] = {
    "rm", "sudo", "apt", "bash", "sh", "eval", "delete", "remove",
    "install", "chmod", "chown", "kill", "pkill", "dd", "format",
    "curl", "wget", "nc", "exec", "python", "su"
}

# Explicit phrase mapping to approved actions
COMMAND_ALLOWLIST: Dict[str, CommandAction] = {
    # Browser
    "open browser":       CommandAction.OPEN_BROWSER,
    "launch browser":     CommandAction.OPEN_BROWSER,
    "web browser":        CommandAction.OPEN_BROWSER,
    "browser":            CommandAction.OPEN_BROWSER,

    # Files
    "open files":         CommandAction.OPEN_FILES,
    "launch files":       CommandAction.OPEN_FILES,
    "file manager":       CommandAction.OPEN_FILES,
    "files":              CommandAction.OPEN_FILES,

    # Terminal
    "open terminal":      CommandAction.OPEN_TERMINAL,
    "launch terminal":    CommandAction.OPEN_TERMINAL,
    "terminal":           CommandAction.OPEN_TERMINAL,

    # Settings
    "open settings":      CommandAction.OPEN_SETTINGS,
    "launch settings":    CommandAction.OPEN_SETTINGS,
    "settings":           CommandAction.OPEN_SETTINGS,

    # Images
    "open images":        CommandAction.OPEN_IMAGES,
    "view images":        CommandAction.OPEN_IMAGES,
    "pictures":           CommandAction.OPEN_IMAGES,
    "images":             CommandAction.OPEN_IMAGES,

    # Videos
    "open videos":        CommandAction.OPEN_VIDEOS,
    "play videos":        CommandAction.OPEN_VIDEOS,
    "media player":       CommandAction.OPEN_VIDEOS,
    "videos":             CommandAction.OPEN_VIDEOS,

    # Navigation & control
    "go home":            CommandAction.GO_HOME,
    "home screen":        CommandAction.GO_HOME,
    "home":               CommandAction.GO_HOME,

    "pause control":      CommandAction.PAUSE_CONTROL,
    "pause":              CommandAction.PAUSE_CONTROL,

    "resume control":     CommandAction.RESUME_CONTROL,
    "resume":             CommandAction.RESUME_CONTROL,

    "stop tracking":      CommandAction.STOP_TRACKING,
    "stop camera":        CommandAction.STOP_TRACKING,
    "disable camera":     CommandAction.STOP_TRACKING,

    "read status":        CommandAction.READ_STATUS,
    "status":             CommandAction.READ_STATUS,
    "system status":      CommandAction.READ_STATUS,

    "help":               CommandAction.HELP,
    "what can i say":     CommandAction.HELP,
    "commands":           CommandAction.HELP,

    "volume up":          CommandAction.VOLUME_UP,
    "increase volume":    CommandAction.VOLUME_UP,
    "louder":             CommandAction.VOLUME_UP,

    "volume down":        CommandAction.VOLUME_DOWN,
    "decrease volume":    CommandAction.VOLUME_DOWN,
    "softer":             CommandAction.VOLUME_DOWN,
    "quieter":            CommandAction.VOLUME_DOWN,

    # Document reading controls
    "read document":      CommandAction.READ_DOCUMENT,
    "read aloud":         CommandAction.READ_DOCUMENT,
    "read file":          CommandAction.READ_DOCUMENT,
    "pause reading":      CommandAction.PAUSE_READING,
    "resume reading":     CommandAction.RESUME_READING,
    "stop reading":       CommandAction.STOP_READING,
    "read faster":        CommandAction.READING_FASTER,
    "faster":             CommandAction.READING_FASTER,
    "read slower":        CommandAction.READING_SLOWER,
    "slower":             CommandAction.READING_SLOWER,
    "next sentence":      CommandAction.NEXT_SENTENCE,
    "next":               CommandAction.NEXT_SENTENCE,
    "previous sentence":  CommandAction.PREVIOUS_SENTENCE,
    "previous":           CommandAction.PREVIOUS_SENTENCE,

    # System Power (Protected)
    "restart":            CommandAction.RESTART_REQUEST,
    "reboot system":      CommandAction.RESTART_REQUEST,
    "restart computer":   CommandAction.RESTART_REQUEST,

    "shutdown":           CommandAction.SHUTDOWN_REQUEST,
    "power off":          CommandAction.SHUTDOWN_REQUEST,
    "shut down":          CommandAction.SHUTDOWN_REQUEST,
    "shut down computer": CommandAction.SHUTDOWN_REQUEST,

    # Spoken Confirmation
    "confirm":            CommandAction.CONFIRM_YES,
    "yes":                CommandAction.CONFIRM_YES,
    "confirm restart":    CommandAction.CONFIRM_YES,
    "confirm shutdown":   CommandAction.CONFIRM_YES,

    "cancel":             CommandAction.CONFIRM_CANCEL,
    "no":                 CommandAction.CONFIRM_CANCEL,
    "abort":              CommandAction.CONFIRM_CANCEL,
}


def normalize_speech(text: str) -> str:
    """Strip punctuation, multiple spaces, and convert to lower-case."""
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", "", text)
    return " ".join(cleaned.lower().split())


def get_vosk_grammar_list() -> List[str]:
    """Return list of phrases for Vosk grammar restriction."""
    phrases = sorted(list(COMMAND_ALLOWLIST.keys()))
    phrases.append("[unk]")
    return phrases


def parse_command(raw_text: str) -> CommandAction | None:
    """
    Parses speech text against the strict allowlist.
    Returns CommandAction if valid, or None if rejected.
    """
    cleaned = normalize_speech(raw_text)
    if not cleaned:
        return None

    # Defense in depth: reject any input containing dangerous tokens
    tokens = set(cleaned.split())
    if tokens & DANGEROUS_TOKENS:
        log.warning("Security rejection: speech contained prohibited token: %s", cleaned)
        return None

    # Check strict allowlist
    action = COMMAND_ALLOWLIST.get(cleaned)
    if action:
        log.info("Voice command recognized: '%s' -> %s", cleaned, action.value)
        return action

    log.debug("Unrecognized voice command ignored: '%s'", cleaned)
    return None
