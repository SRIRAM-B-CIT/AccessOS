"""
AccessOS Offline Voice Control Package
=======================================
Phase 4: Vosk offline speech recognition with strict grammar allowlists,
Piper neural text-to-speech feedback, spoken confirmation dialogs,
and keyboard-accessible microphone controls.
"""
from .command_parser import CommandAction, parse_command, COMMAND_ALLOWLIST, DANGEROUS_TOKENS
from .tts_engine import TTSEngine
from .voice_listener import VoiceListener, VoiceState
from .voice_hud import VoiceHUD

__all__ = [
    "CommandAction",
    "parse_command",
    "COMMAND_ALLOWLIST",
    "DANGEROUS_TOKENS",
    "TTSEngine",
    "VoiceListener",
    "VoiceState",
    "VoiceHUD",
]
