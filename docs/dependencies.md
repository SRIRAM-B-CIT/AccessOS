# AccessOS — Dependency Reference

## Phase 1 — Runtime

| Package | Source | Install method |
|---|---|---|
| python3-gi (PyGObject ≥ 3.44) | System APT | Pre-installed on Mint/Zorin |
| gir1.2-gtk-3.0 | System APT | Pre-installed |
| gir1.2-gdkpixbuf-2.0 | System APT | Pre-installed |
| gir1.2-glib-2.0 | System APT | Pre-installed |
| paplay (pulseaudio-utils) | System APT | Pre-installed |
| aplay (alsa-utils) | System APT | Pre-installed |

## Phase 1 — Development only

| Package | Install |
|---|---|
| pytest | `pip install pytest` (inside .venv) |

## Phase 3 — Planned (head pointer)

| Package | pip package | Version |
|---|---|---|
| OpenCV | `opencv-python` | ≥ 4.8 |
| MediaPipe | `mediapipe` | ≥ 0.10 |

## Phase 4 — Planned (voice + TTS)

| Component | Source | Notes |
|---|---|---|
| Vosk | `pip install vosk` | + download vosk-model-small-en-us |
| Piper | GitHub releases binary | + download a voice model (.onnx) |

## Phase 6 — ISO build tools

| Tool | APT package | Already installed? |
|---|---|---|
| xorriso | `xorriso` | ❌ (install in Phase 6) |
| mksquashfs | `squashfs-tools` | ✅ |
| genisoimage | `genisoimage` | ✅ |

## Notes

- Never install PyGObject via pip — it will fail without GTK dev headers.
- Use `--system-site-packages` when creating the venv.
- All pip installs go into `.venv/` only; never use `pip install --system`.
