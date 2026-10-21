"""
AccessOS Phase 4 Voice Control & Speech Synthesis Tests
========================================================
Validates:
  1. Strict command allowlist parsing (safe actions only).
  2. Immediate rejection of dangerous tokens (sudo, rm, bash, delete, install, etc.).
  3. Proper speech normalization & Vosk grammar generation.
  4. Voice listening disabled by default; explicit start required.
  5. Microphone-unavailable behavior and error state recovery.
  6. Keyboard / HUD microphone mute toggle.
  7. Spoken confirmation state machine for restart and shutdown.
  8. Cancellation and timeout handling for protected commands.
  9. In-memory Piper TTS graceful fallback when model or aplay unavailable.
 10. VoiceHUD visual state indicators.
"""
import time
from unittest.mock import MagicMock, patch

import pytest

from accessos.voice.command_parser import (
    COMMAND_ALLOWLIST,
    DANGEROUS_TOKENS,
    CommandAction,
    get_vosk_grammar_list,
    normalize_speech,
    parse_command,
)
from accessos.voice.voice_listener import VoiceListener, VoiceState
from accessos.voice.tts_engine import TTSEngine
from accessos.voice.voice_hud import VoiceHUD


# ── 1. Command Allowlisting Tests ─────────────────────────────────────────────

def test_command_parser_safe_allowlist():
    """Verify all required Phase 4 safe commands map correctly."""
    test_cases = [
        ("open browser", CommandAction.OPEN_BROWSER),
        ("browser", CommandAction.OPEN_BROWSER),
        ("open files", CommandAction.OPEN_FILES),
        ("files", CommandAction.OPEN_FILES),
        ("open terminal", CommandAction.OPEN_TERMINAL),
        ("terminal", CommandAction.OPEN_TERMINAL),
        ("open settings", CommandAction.OPEN_SETTINGS),
        ("settings", CommandAction.OPEN_SETTINGS),
        ("open images", CommandAction.OPEN_IMAGES),
        ("images", CommandAction.OPEN_IMAGES),
        ("open videos", CommandAction.OPEN_VIDEOS),
        ("videos", CommandAction.OPEN_VIDEOS),
        ("go home", CommandAction.GO_HOME),
        ("pause control", CommandAction.PAUSE_CONTROL),
        ("resume control", CommandAction.RESUME_CONTROL),
        ("stop tracking", CommandAction.STOP_TRACKING),
        ("read status", CommandAction.READ_STATUS),
        ("help", CommandAction.HELP),
        ("volume up", CommandAction.VOLUME_UP),
        ("volume down", CommandAction.VOLUME_DOWN),
        ("restart", CommandAction.RESTART_REQUEST),
        ("shutdown", CommandAction.SHUTDOWN_REQUEST),
        ("confirm", CommandAction.CONFIRM_YES),
        ("yes", CommandAction.CONFIRM_YES),
        ("cancel", CommandAction.CONFIRM_CANCEL),
        ("no", CommandAction.CONFIRM_CANCEL),
    ]

    for phrase, expected_action in test_cases:
        action = parse_command(phrase)
        assert action == expected_action, f"Failed to parse safe phrase: {phrase}"


def test_command_parser_case_and_punctuation_insensitivity():
    """Verify normalization handles uppercase, punctuation, and extra whitespace."""
    assert parse_command("  Open Browser!  ") == CommandAction.OPEN_BROWSER
    assert parse_command("VOLUME UP...") == CommandAction.VOLUME_UP
    assert parse_command("Go, Home?") == CommandAction.GO_HOME
    assert parse_command("PAUSE CONTROL") == CommandAction.PAUSE_CONTROL


# ── 2. Rejection of Dangerous & Unapproved Commands ───────────────────────────

def test_command_parser_prohibited_tokens():
    """Verify dangerous tokens are immediately rejected by safety check."""
    prohibited_samples = [
        "rm -rf /",
        "sudo reboot",
        "delete files",
        "install browser",
        "bash test.sh",
        "kill 1",
        "apt install vlc",
        "curl http://malicious.site",
        "wget http://malicious.site",
        "chmod 777 file",
        "format disk",
        "python evil.py",
        "remove file",
        "sh script",
    ]

    for sample in prohibited_samples:
        assert parse_command(sample) is None, f"Dangerous command was NOT rejected: {sample}"


def test_command_parser_unregistered_commands():
    """Verify arbitrary speech phrases return None (not in allowlist)."""
    unregistered = [
        "open youtube",
        "play music",
        "browse the web",
        "hello computer",
        "turn off display",
        "show my passwords",
        "what time is it",
    ]
    for sample in unregistered:
        assert parse_command(sample) is None, f"Unregistered phrase was accepted: {sample}"


def test_vosk_grammar_list_safety():
    """Verify grammar list contains all allowlist phrases and no dangerous tokens."""
    grammar = get_vosk_grammar_list()
    assert "[unk]" in grammar
    assert "open browser" in grammar
    assert "stop tracking" in grammar
    assert "volume up" in grammar

    # No dangerous tokens should be stand-alone grammar elements
    for dangerous in DANGEROUS_TOKENS:
        assert dangerous not in grammar


# ── 3. VoiceListener Default State & Controls ─────────────────────────────────

def test_voice_listener_disabled_by_default():
    """Voice listening must be disabled by default."""
    tts = MagicMock(spec=TTSEngine)
    listener = VoiceListener(tts=tts)
    assert listener.state == VoiceState.OFF
    assert not listener._stop_event.is_set()


def test_voice_listener_mute_toggle():
    """Verify microphone mute toggle transitions between LISTENING and MUTED."""
    tts = MagicMock(spec=TTSEngine)
    listener = VoiceListener(tts=tts)
    listener._state = VoiceState.LISTENING

    listener.toggle_mute()
    assert listener.state == VoiceState.MUTED
    tts.speak.assert_called_with("Microphone muted")

    listener.toggle_mute()
    assert listener.state == VoiceState.LISTENING
    tts.speak.assert_called_with("Microphone active")


def test_voice_listener_microphone_unavailable():
    """Verify graceful failure when arecord is unavailable."""
    tts = MagicMock(spec=TTSEngine)
    listener = VoiceListener(tts=tts)

    with patch("shutil.which", return_value=None):
        ok = listener.start()
        assert not ok
        assert listener.state == VoiceState.ERROR


# ── 4. Spoken Confirmation State Machine Tests ────────────────────────────────

def test_confirmation_handling_restart_confirmed():
    """Verify restart requires confirmation and executes upon CONFIRM_YES."""
    tts = MagicMock(spec=TTSEngine)
    cmd_handler = MagicMock()
    listener = VoiceListener(tts=tts, on_command=cmd_handler)
    listener._state = VoiceState.LISTENING

    # Step 1: User says "restart"
    listener._handle_recognized_text("restart")
    assert listener.state == VoiceState.AWAITING_CONFIRMATION
    assert listener._pending_action == CommandAction.RESTART_REQUEST
    cmd_handler.assert_not_called()
    tts.speak.assert_called_with("Restart requested. Say confirm to proceed, or cancel to abort.")

    # Step 2: User says "confirm"
    listener._handle_recognized_text("confirm")
    assert listener.state == VoiceState.LISTENING
    assert listener._pending_action is None
    cmd_handler.assert_called_once_with(CommandAction.RESTART_REQUEST)


def test_confirmation_handling_shutdown_canceled():
    """Verify shutdown request can be aborted by saying "cancel"."""
    tts = MagicMock(spec=TTSEngine)
    cmd_handler = MagicMock()
    listener = VoiceListener(tts=tts, on_command=cmd_handler)
    listener._state = VoiceState.LISTENING

    # Step 1: User says "shutdown"
    listener._handle_recognized_text("shutdown")
    assert listener.state == VoiceState.AWAITING_CONFIRMATION
    assert listener._pending_action == CommandAction.SHUTDOWN_REQUEST
    cmd_handler.assert_not_called()

    # Step 2: User says "cancel"
    listener._handle_recognized_text("cancel")
    assert listener.state == VoiceState.LISTENING
    assert listener._pending_action is None
    cmd_handler.assert_not_called()
    tts.speak.assert_called_with("Action canceled.")


def test_confirmation_timeout():
    """Verify confirmation times out automatically after configured duration."""
    tts = MagicMock(spec=TTSEngine)
    cmd_handler = MagicMock()
    listener = VoiceListener(
        tts=tts,
        on_command=cmd_handler,
        confirmation_timeout_sec=0.1,  # Short timeout for testing
    )
    listener._state = VoiceState.AWAITING_CONFIRMATION
    listener._pending_action = CommandAction.RESTART_REQUEST
    listener._pending_timestamp = time.monotonic() - 0.2

    listener._check_confirmation_timeout()
    assert listener.state == VoiceState.LISTENING
    assert listener._pending_action is None
    cmd_handler.assert_not_called()
    tts.speak.assert_called_with("Restart canceled: confirmation timed out.")


# ── 5. TTS Engine Fallback Tests ──────────────────────────────────────────────

def test_tts_engine_missing_model():
    """Verify TTSEngine safely handles missing model file."""
    from pathlib import Path
    engine = TTSEngine(model_path=Path("/nonexistent/model.onnx"), enabled=True)
    assert engine._voice is None
    # speak() should safely do nothing without raising
    engine.speak("Hello World")
    engine.stop()


# ── 6. VoiceHUD Visual Status Tests ───────────────────────────────────────────

def test_voice_hud_state_transitions():
    """Verify VoiceHUD updates visual style context on state changes."""
    from gi.repository import GLib
    hud = VoiceHUD()

    def set_and_flush(state, detail=""):
        hud.update_state(state, detail)
        while GLib.MainContext.default().iteration(False):
            pass

    set_and_flush(VoiceState.LISTENING)
    style = hud._pill.get_style_context()
    assert style.has_class("voice-active")

    set_and_flush(VoiceState.MUTED)
    assert style.has_class("voice-muted")

    set_and_flush(VoiceState.AWAITING_CONFIRMATION)
    assert style.has_class("voice-waiting")

    set_and_flush(VoiceState.ERROR)
    assert style.has_class("voice-error")

    set_and_flush(VoiceState.OFF)
    assert style.has_class("voice-off")
