"""
AccessOS Offline Voice Listener (Vosk Speech Recognition)
==========================================================
Continuous local voice recognition using Vosk with grammar constraints.
Zero cloud network calls, zero audio storage. Runs in a dedicated
background thread feeding 16kHz audio from ALSA arecord.
"""
from __future__ import annotations

import enum
import json
import logging
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Optional

import vosk

from .command_parser import (
    CommandAction,
    get_vosk_grammar_list,
    parse_command,
)
from .tts_engine import TTSEngine

log = logging.getLogger(__name__)

_DEFAULT_MODEL = Path(__file__).resolve().parent.parent.parent / "assets" / "models" / "vosk-model-small-en-us-0.15"


class VoiceState(enum.Enum):
    OFF                   = "OFF"
    LISTENING             = "LISTENING"
    MUTED                 = "MUTED"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    ERROR                 = "ERROR"


class VoiceListener:
    """Offline speech recognition engine with safety confirmations."""

    def __init__(
        self,
        tts: TTSEngine,
        model_path: Optional[Path] = None,
        on_command: Optional[Callable[[CommandAction], None]] = None,
        on_state_changed: Optional[Callable[[VoiceState, str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        confirmation_timeout_sec: float = 10.0,
    ) -> None:
        self._tts = tts
        self._model_path = Path(model_path or _DEFAULT_MODEL)
        self.on_command = on_command
        self.on_state_changed = on_state_changed
        self.on_error = on_error
        self.confirmation_timeout_sec = confirmation_timeout_sec

        self._state = VoiceState.OFF
        self._model = None
        self._recognizer = None

        self._stop_event = threading.Event()
        self._mute_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None

        # Confirmation state tracking
        self._pending_action: Optional[CommandAction] = None
        self._pending_timestamp: float = 0.0

    @property
    def state(self) -> VoiceState:
        return self._state

    def _set_state(self, new_state: VoiceState, detail: str = "") -> None:
        if self._state != new_state:
            old = self._state
            self._state = new_state
            log.info("VoiceListener state: %s -> %s (%s)", old.value, new_state.value, detail)
            if self.on_state_changed:
                try:
                    self.on_state_changed(new_state, detail)
                except Exception as exc:
                    log.debug("on_state_changed callback error: %s", exc)

    def toggle_mute(self) -> bool:
        """Toggle microphone mute (<kbd>M</kbd> shortcut)."""
        if self._state == VoiceState.OFF:
            return False
        if self._mute_event.is_set():
            self._mute_event.clear()
            self._set_state(VoiceState.LISTENING, "Microphone unmuted")
            self._tts.speak("Microphone active")
            return False
        else:
            self._mute_event.set()
            self._set_state(VoiceState.MUTED, "Microphone muted")
            self._tts.speak("Microphone muted")
            return True

    def start(self) -> bool:
        """Start offline listening thread."""
        if self._worker_thread and self._worker_thread.is_alive():
            log.warning("VoiceListener already running")
            return True

        if not self._model_path.exists():
            msg = f"Vosk speech model not found at {self._model_path}"
            log.error(msg)
            self._set_state(VoiceState.ERROR, msg)
            if self.on_error:
                self.on_error(msg)
            return False

        if not shutil.which("arecord"):
            msg = "ALSA recording utility (arecord) not found on system"
            log.error(msg)
            self._set_state(VoiceState.ERROR, msg)
            if self.on_error:
                self.on_error(msg)
            return False

        try:
            if self._model is None:
                log.info("Loading Vosk speech model from %s", self._model_path)
                # Vosk logs to stdout/stderr; suppress overly verbose debug
                vosk.SetLogLevel(-1)
                self._model = vosk.Model(str(self._model_path))

            grammar = json.dumps(get_vosk_grammar_list())
            self._recognizer = vosk.KaldiRecognizer(self._model, 16000, grammar)
        except Exception as exc:
            msg = f"Failed to initialize Vosk recognizer: {exc}"
            log.error(msg)
            self._set_state(VoiceState.ERROR, msg)
            if self.on_error:
                self.on_error(msg)
            return False

        self._stop_event.clear()
        self._mute_event.clear()
        self._pending_action = None
        self._set_state(VoiceState.LISTENING, "Listening for commands")

        self._worker_thread = threading.Thread(
            target=self._run_loop,
            name="VoiceListenerWorker",
            daemon=True,
        )
        self._worker_thread.start()
        self._tts.speak("Voice control active")
        return True

    def stop(self) -> None:
        """Stop offline listening."""
        log.info("Stopping VoiceListener")
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
        self._worker_thread = None
        self._set_state(VoiceState.OFF, "Voice control stopped")

    def _run_loop(self) -> None:
        log.info("VoiceListener worker thread running")
        cmd = [
            "arecord",
            "-q",
            "-r", "16000",
            "-c", "1",
            "-f", "S16_LE",
            "-t", "raw",
        ]

        proc = None
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=4096,
            )

            # Check immediate startup failure
            time.sleep(0.1)
            if proc.poll() is not None:
                err = proc.stderr.read().decode("utf-8", errors="ignore").strip() if proc.stderr else "Microphone unavailable"
                msg = f"Microphone capture failed: {err}"
                log.error(msg)
                self._set_state(VoiceState.ERROR, msg)
                if self.on_error:
                    self.on_error(msg)
                return

            chunk_size = 4000  # 4000 bytes = 125ms of 16kHz 16-bit audio

            while not self._stop_event.is_set():
                # Check confirmation timeout
                self._check_confirmation_timeout()

                data = proc.stdout.read(chunk_size)
                if not data:
                    time.sleep(0.02)
                    continue

                if self._mute_event.is_set():
                    # Muted: drop audio chunks immediately
                    continue

                if self._recognizer.AcceptWaveform(data):
                    res = json.loads(self._recognizer.Result())
                    text = res.get("text", "").strip()
                    if text:
                        self._handle_recognized_text(text)

        except Exception as exc:
            log.error("Exception in VoiceListener loop: %s", exc, exc_info=True)
            self._set_state(VoiceState.ERROR, str(exc))
            if self.on_error:
                self.on_error(f"Voice error: {exc}")
        finally:
            if proc:
                try:
                    proc.terminate()
                    proc.wait(timeout=1.0)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
            log.info("VoiceListener worker loop terminated")

    def _check_confirmation_timeout(self) -> None:
        if self._pending_action and self._state == VoiceState.AWAITING_CONFIRMATION:
            if time.monotonic() - self._pending_timestamp > self.confirmation_timeout_sec:
                action_name = "Restart" if self._pending_action == CommandAction.RESTART_REQUEST else "Shutdown"
                log.info("Voice confirmation timed out for %s", action_name)
                self._pending_action = None
                self._set_state(VoiceState.LISTENING, "Confirmation timed out")
                self._tts.speak(f"{action_name} canceled: confirmation timed out.")

    def _handle_recognized_text(self, text: str) -> None:
        log.info("Raw recognized speech: '%s'", text)
        action = parse_command(text)
        if not action:
            return

        # ── Confirmation State Handling ──
        if self._state == VoiceState.AWAITING_CONFIRMATION:
            if action == CommandAction.CONFIRM_YES:
                target_action = self._pending_action
                self._pending_action = None
                self._set_state(VoiceState.LISTENING, "Confirmed")
                if target_action == CommandAction.RESTART_REQUEST:
                    self._tts.speak("Restart confirmed. Restarting computer now.")
                elif target_action == CommandAction.SHUTDOWN_REQUEST:
                    self._tts.speak("Shutdown confirmed. Powering off computer now.")

                if self.on_command and target_action:
                    self.on_command(target_action)
                return

            elif action == CommandAction.CONFIRM_CANCEL:
                log.info("User explicitly canceled %s", self._pending_action)
                self._pending_action = None
                self._set_state(VoiceState.LISTENING, "Canceled")
                self._tts.speak("Action canceled.")
                return

            else:
                # Any other recognized command while awaiting confirmation
                log.info("Expected confirm or cancel, got '%s'", text)
                self._tts.speak("Please say confirm or cancel.")
                return

        # ── Protected Power Requests (Require Confirmation) ──
        if action == CommandAction.RESTART_REQUEST:
            self._pending_action = CommandAction.RESTART_REQUEST
            self._pending_timestamp = time.monotonic()
            self._set_state(VoiceState.AWAITING_CONFIRMATION, "Awaiting restart confirmation")
            self._tts.speak("Restart requested. Say confirm to proceed, or cancel to abort.")
            return

        if action == CommandAction.SHUTDOWN_REQUEST:
            self._pending_action = CommandAction.SHUTDOWN_REQUEST
            self._pending_timestamp = time.monotonic()
            self._set_state(VoiceState.AWAITING_CONFIRMATION, "Awaiting shutdown confirmation")
            self._tts.speak("Shut down requested. Say confirm to proceed, or cancel to abort.")
            return

        # ── Standard Safe Commands ──
        if self.on_command:
            try:
                self.on_command(action)
            except Exception as exc:
                log.error("Command execution error for %s: %s", action.value, exc)
