"""
AccessOS Offline Speech Synthesis (Piper TTS)
==============================================
Fully local, natural neural speech feedback using Piper TTS.
Streams audio in-memory to ALSA (aplay). Never stores audio files on disk.
Asynchronous thread-safe worker queue prevents blocking the UI.
"""
from __future__ import annotations

import io
import logging
import queue
import shutil
import subprocess
import threading
import wave
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_DEFAULT_MODEL = Path(__file__).resolve().parent.parent.parent / "assets" / "models" / "piper" / "en_US-lessac-low.onnx"


class TTSEngine:
    """Asynchronous offline speech synthesis using Piper."""

    def __init__(self, model_path: Optional[Path] = None, enabled: bool = True) -> None:
        self.model_path = Path(model_path or _DEFAULT_MODEL)
        self.enabled = enabled
        self._voice = None
        self._queue: queue.Queue[str] = queue.Queue(maxsize=10)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # Lazy loading on first speak() prevents blocking UI / app startup

    def _load_model(self) -> bool:
        if not self.model_path.exists():
            log.warning("Piper model not found at %s — TTS disabled", self.model_path)
            return False
        try:
            import piper
            self._voice = piper.PiperVoice.load(str(self.model_path))
            log.info("Piper TTS model loaded from %s", self.model_path)
            return True
        except Exception as exc:
            log.error("Failed to load Piper voice model: %s", exc)
            self._voice = None
            return False

    def _start_worker(self) -> None:
        if self._voice is None:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._worker_loop,
            name="PiperTTSWorker",
            daemon=True,
        )
        self._thread.start()

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        if enabled and self._voice is None:
            if self._load_model():
                self._start_worker()

    def _ensure_loaded(self) -> bool:
        if self._voice is not None:
            return True
        if self._load_model():
            self._start_worker()
            return True
        return False

    def speak(self, text: str, interrupt: bool = False) -> None:
        """Enqueue speech text for synthesis."""
        if not self.enabled:
            log.debug("TTS disabled, text not spoken: '%s'", text)
            return

        if self._voice is None:
            if not self._ensure_loaded():
                log.debug("TTS model could not be loaded, text not spoken: '%s'", text)
                return

        if interrupt:
            # Clear pending utterances
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                    self._queue.task_done()
                except queue.Empty:
                    break

        try:
            self._queue.put_nowait(text)
        except queue.Full:
            log.warning("TTS queue full, dropping speech request: '%s'", text)

    def stop(self) -> None:
        self._stop_event.set()
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except queue.Empty:
                break
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None

    def _worker_loop(self) -> None:
        log.info("Piper TTS worker loop started")
        aplay_bin = shutil.which("aplay")
        if not aplay_bin:
            log.warning("aplay not found on system — speech playback disabled")
            return

        while not self._stop_event.is_set():
            try:
                text = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue

            try:
                # Synthesize in-memory (no disk writing)
                mem_buf = io.BytesIO()
                with wave.open(mem_buf, "wb") as wav_out:
                    self._voice.synthesize_wav(text, wav_out)

                wav_bytes = mem_buf.getvalue()
                if wav_bytes:
                    proc = subprocess.Popen(
                        [aplay_bin, "-q"],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    proc.communicate(input=wav_bytes, timeout=5.0)

            except Exception as exc:
                log.error("TTS synthesis error on '%s': %s", text, exc)
            finally:
                self._queue.task_done()

        log.info("Piper TTS worker loop stopped")
