"""
AccessOS Document Reader Playback Controller
=============================================
Manages document reading sessions, sentence navigation, speech playback (Piper TTS),
and real-time reading progress tracking.
"""
from __future__ import annotations

import enum
import logging
import threading
import time
from pathlib import Path
from typing import Callable, List, Optional

from ..voice.tts_engine import TTSEngine
from .extractor import DocumentExtractor

log = logging.getLogger(__name__)


class PlaybackState(enum.Enum):
    STOPPED = "STOPPED"
    PLAYING = "PLAYING"
    PAUSED  = "PAUSED"


class DocumentReader:
    """
    Playback controller for hands-free and voice-driven document reading.
    """

    def __init__(
        self,
        tts: Optional[TTSEngine] = None,
        on_sentence_changed: Optional[Callable[[int, int, str], None]] = None,
        on_state_changed: Optional[Callable[[PlaybackState], None]] = None,
        on_completed: Optional[Callable[[], None]] = None,
    ) -> None:
        self._tts = tts or TTSEngine(enabled=True)
        self.on_sentence_changed = on_sentence_changed
        self.on_state_changed = on_state_changed
        self.on_completed = on_completed

        self._title: str = "Untitled Document"
        self._file_path: Optional[Path] = None
        self._sentences: List[str] = []
        self._current_index: int = 0
        self._speed: float = 1.0  # Range: 0.75x to 1.75x

        self._state: PlaybackState = PlaybackState.STOPPED
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None

    @property
    def title(self) -> str:
        return self._title

    @property
    def file_path(self) -> Optional[Path]:
        return self._file_path

    @property
    def sentences(self) -> List[str]:
        return list(self._sentences)

    @property
    def current_index(self) -> int:
        return self._current_index

    @property
    def total_sentences(self) -> int:
        return len(self._sentences)

    @property
    def state(self) -> PlaybackState:
        return self._state

    @property
    def speed(self) -> float:
        return self._speed

    @property
    def progress(self) -> float:
        if not self._sentences:
            return 0.0
        return min(1.0, max(0.0, self._current_index / len(self._sentences)))

    def _set_state(self, new_state: PlaybackState) -> None:
        self._state = new_state
        log.info("DocumentReader state -> %s (sentence %d/%d)", new_state.value, self._current_index + 1, len(self._sentences))
        if self.on_state_changed:
            try:
                self.on_state_changed(new_state)
            except Exception as exc:
                log.error("on_state_changed callback error: %s", exc)

    def load_file(self, path: Path | str) -> bool:
        """Extract and load a document from a file."""
        file_path = Path(path)
        try:
            raw_text = DocumentExtractor.extract_text(file_path)
            self.load_text(raw_text, title=file_path.name)
            self._file_path = file_path
            return True
        except Exception as exc:
            log.error("Failed to load document %s: %s", file_path, exc)
            return False

    def load_text(self, text: str, title: str = "Document") -> None:
        """Load document from plain text."""
        self.stop()
        self._title = title
        self._file_path = None
        self._sentences = DocumentExtractor.split_sentences(text)
        self._current_index = 0
        log.info("Loaded document '%s' with %d sentences", title, len(self._sentences))

    def play(self) -> None:
        """Start reading from the current sentence index."""
        if not self._sentences:
            log.warning("No document loaded to read")
            return

        if self._state == PlaybackState.PLAYING:
            return

        if self._state == PlaybackState.PAUSED:
            self.resume()
            return

        self._stop_event.clear()
        self._pause_event.clear()
        self._set_state(PlaybackState.PLAYING)

        self._worker_thread = threading.Thread(
            target=self._playback_loop,
            name="AccessOS-DocumentReader-Worker",
            daemon=True,
        )
        self._worker_thread.start()

    def pause(self) -> None:
        """Pause playback at current sentence."""
        if self._state != PlaybackState.PLAYING:
            return
        self._pause_event.set()
        if self._tts:
            self._tts.speak("", interrupt=True)
        self._set_state(PlaybackState.PAUSED)

    def resume(self) -> None:
        """Resume reading from paused position."""
        if self._state != PlaybackState.PAUSED:
            return
        self._pause_event.clear()
        self._set_state(PlaybackState.PLAYING)

    def stop(self) -> None:
        """Stop playback and reset to beginning."""
        self._stop_event.set()
        self._pause_event.clear()
        if self._tts:
            self._tts.speak("", interrupt=True)

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.0)
        self._worker_thread = None

        self._current_index = 0
        self._set_state(PlaybackState.STOPPED)

    def toggle_play_pause(self) -> None:
        """Toggle between Play and Pause."""
        if self._state == PlaybackState.PLAYING:
            self.pause()
        else:
            self.play()

    def next_sentence(self) -> None:
        """Advance to next sentence and speak it if playing."""
        if self._current_index < len(self._sentences) - 1:
            self._current_index += 1
            self._on_sentence_updated()
            if self._state == PlaybackState.PLAYING and self._tts:
                self._tts.speak(self._sentences[self._current_index], interrupt=True)

    def previous_sentence(self) -> None:
        """Go back to previous sentence and speak it if playing."""
        if self._current_index > 0:
            self._current_index -= 1
            self._on_sentence_updated()
            if self._state == PlaybackState.PLAYING and self._tts:
                self._tts.speak(self._sentences[self._current_index], interrupt=True)

    def jump_to(self, index: int) -> None:
        """Jump to specific sentence index."""
        if not self._sentences:
            return
        target = max(0, min(len(self._sentences) - 1, index))
        self._current_index = target
        self._on_sentence_updated()
        if self._state == PlaybackState.PLAYING and self._tts:
            self._tts.speak(self._sentences[self._current_index], interrupt=True)

    def set_speed(self, speed: float) -> None:
        self._speed = max(0.5, min(2.0, round(speed, 2)))
        log.info("DocumentReader reading speed set to: %.2fx", self._speed)

    def increase_speed(self) -> float:
        self.set_speed(self._speed + 0.25)
        return self._speed

    def decrease_speed(self) -> float:
        self.set_speed(self._speed - 0.25)
        return self._speed

    def _on_sentence_updated(self) -> None:
        if 0 <= self._current_index < len(self._sentences):
            text = self._sentences[self._current_index]
            if self.on_sentence_changed:
                try:
                    self.on_sentence_changed(self._current_index + 1, len(self._sentences), text)
                except Exception as exc:
                    log.error("on_sentence_changed callback error: %s", exc)

    def _playback_loop(self) -> None:
        log.info("Document reading playback loop started")
        try:
            while not self._stop_event.is_set() and self._current_index < len(self._sentences):
                # Check pause
                while self._pause_event.is_set():
                    if self._stop_event.is_set():
                        return
                    time.sleep(0.05)

                current_text = self._sentences[self._current_index]
                self._on_sentence_updated()

                # Speak sentence
                if self._tts:
                    self._tts.speak(current_text, interrupt=True)

                # Wait for utterance to finish
                words = len(current_text.split())
                # Base speech speed ~2.6 words/sec, scaled by speed multiplier
                est_seconds = max(1.2, (words / (2.6 * self._speed)))
                start_t = time.monotonic()

                # Wait with early exit if stopped or paused
                while time.monotonic() - start_t < est_seconds:
                    if self._stop_event.is_set() or self._pause_event.is_set():
                        break
                    time.sleep(0.05)

                if self._stop_event.is_set():
                    return

                if not self._pause_event.is_set():
                    self._current_index += 1

            # Reached end of document
            if self._current_index >= len(self._sentences) and not self._stop_event.is_set():
                log.info("Reached end of document '%s'", self._title)
                self._set_state(PlaybackState.STOPPED)
                if self.on_completed:
                    try:
                        self.on_completed()
                    except Exception as exc:
                        log.error("on_completed callback error: %s", exc)
        finally:
            log.info("Playback worker loop exiting")
