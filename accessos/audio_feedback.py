"""
AccessOS Audio Feedback
========================
Lightweight, non-blocking sound playback for focus and activation cues.

Phase 1 scope:
  - Plays focus/activate/error/pause/resume sounds.
  - Uses ``paplay`` (PulseAudio) or ``aplay`` (ALSA) — whichever is found.
  - Searches bundled ``assets/sounds/`` first, then XDG system sounds.
  - Every playback runs in a daemon thread so it never blocks the GTK loop.
  - Fails silently with a debug log if no player or no sound file is found.

NOT in Phase 1:
  - Text-to-speech (Piper) — that is Phase 4.
"""
from __future__ import annotations

import logging
import subprocess
import threading
from pathlib import Path

log = logging.getLogger(__name__)

# Bundled sounds directory (relative to this file's parent)
_BUNDLED_DIR = Path(__file__).parent.parent / "assets" / "sounds"

# XDG system sound search patterns (tried in order)
_SYSTEM_PATTERNS = [
    "/usr/share/sounds/freedesktop/stereo/button-pressed.oga",
    "/usr/share/sounds/Yaru/stereo/button-pressed.ogg",
    "/usr/share/sounds/ubuntu/stereo/button-pressed.ogg",
    "/usr/share/sounds/gnome/default/alerts/bark.ogg",
]

# Bundled sound file names (Phase 1 uses a single universal click sound;
# individual files for each event can be swapped in later)
_SOUND_MAP: dict[str, list[str]] = {
    "focus":    ["focus.oga",    "focus.wav",    "focus.ogg"],
    "activate": ["activate.oga", "activate.wav", "activate.ogg"],
    "error":    ["error.oga",    "error.wav",    "error.ogg"],
    "pause":    ["pause.oga",    "pause.wav",    "pause.ogg"],
    "resume":   ["resume.oga",   "resume.wav",   "resume.ogg"],
}


class AudioFeedback:
    """
    Play short UI sound cues.

    Parameters
    ----------
    enabled:
        Set ``False`` to silence all output (e.g. when audio is disabled
        via AccessOS Settings in Phase 2+).
    """

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._player: str | None = None
        self._fallback_sound: Path | None = None

        if enabled:
            self._detect_player()
            self._find_fallback_system_sound()

    # ── Initialisation ─────────────────────────────────────────────────────────

    def _detect_player(self) -> None:
        for tool in ("paplay", "aplay"):
            try:
                subprocess.run(
                    ["which", tool],
                    check=True, capture_output=True, timeout=2,
                )
                self._player = tool
                log.debug("Audio player detected: %s", tool)
                return
            except (subprocess.CalledProcessError, FileNotFoundError,
                    subprocess.TimeoutExpired):
                continue
        log.warning(
            "No audio player found (tried paplay, aplay). "
            "Sound feedback disabled."
        )
        self.enabled = False

    def _find_fallback_system_sound(self) -> None:
        """Cache a system sound to use when a bundled file is missing."""
        for pattern in _SYSTEM_PATTERNS:
            p = Path(pattern)
            if p.exists():
                self._fallback_sound = p
                log.debug("Fallback system sound: %s", p)
                return
        log.debug("No system fallback sound found; bundled sounds only.")

    # ── Public API ─────────────────────────────────────────────────────────────

    def play(self, event: str) -> None:
        """
        Trigger a sound for *event* (e.g. ``"focus"``, ``"activate"``).
        Returns immediately; playback runs on a daemon thread.
        """
        if not self.enabled:
            return

        sound_path = self._resolve(event)
        if sound_path is None:
            log.debug("No sound resolved for event '%s' — skipping", event)
            return

        threading.Thread(
            target=self._play_file,
            args=(sound_path,),
            daemon=True,
            name=f"accessos-sound-{event}",
        ).start()

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable audio feedback at runtime."""
        self.enabled = enabled
        if enabled and self._player is None:
            self._detect_player()
            self._find_fallback_system_sound()

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _resolve(self, event: str) -> Path | None:
        """Return the best available sound file for *event*."""
        for filename in _SOUND_MAP.get(event, []):
            candidate = _BUNDLED_DIR / filename
            if candidate.exists():
                return candidate

        # All specific files missing — use the generic fallback
        return self._fallback_sound

    def _play_file(self, path: Path) -> None:
        """Blocking playback (called on a daemon thread)."""
        try:
            subprocess.run(
                [self._player, str(path)],
                capture_output=True,
                timeout=5,
            )
        except subprocess.TimeoutExpired:
            log.debug("Sound playback timed out for %s", path)
        except Exception as exc:
            log.debug("Sound playback error (%s): %s", path, exc)
