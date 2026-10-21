# AccessOS Architecture

## Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                       User / Operator                               │
│        Keyboard · Mouse · Head · Voice · Blink · Gaze              │
└─────────────────────┬───────────────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────────────┐
│                  AccessOS Application Layer (Python)                │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                   home_screen.py                             │   │
│  │   Header │ Pause Banner │ 6-button Grid │ Status Bar        │   │
│  └──────────────────────┬──────────────────────────────────────┘   │
│                         │                                           │
│  ┌──────────┐  ┌────────▼───────┐  ┌──────────────────────────┐   │
│  │ Settings │  │ AccessEngine   │  │    power_menu.py          │   │
│  │ (Phase2) │  │ (Phase3+)      │  │    (placeholder P1)       │   │
│  └──────────┘  │  HeadPointer   │  └──────────────────────────┘   │
│                │  DwellClick    │                                   │
│                │  VoiceControl  │  ┌──────────────────────────┐   │
│                │  TTS           │  │    app_launcher.py        │   │
│                │  BlinkClick    │  │    (allow-list, Popen)    │   │
│                │  EyeGaze       │  └──────────────────────────┘   │
│                └────────────────┘                                   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              Shared Infrastructure                           │   │
│  │  utils/config.py · utils/logger.py · audio_feedback.py     │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────────────┐
│               Linux Mint 22.3 Xfce (base OS)                       │
│   GTK 3 · Xfce WM · PulseAudio · ALSA · V4L2 · NetworkManager     │
└─────────────────────────────────────────────────────────────────────┘
```

## Key design decisions

### Why GTK 3 (not GTK 4)?
GTK 3 is the native toolkit for Xfce on Linux Mint 22.3.  It is stable,
well-supported, and PyGObject 3.48+ is pre-installed.  GTK 4 would require
additional packaging effort with no benefit for Mint Xfce compatibility.

### Why Vosk (not whisper.cpp) for Phase 4?
Vosk models start at ~50 MB and run in real time on an i5 with 8 GB RAM.
whisper.cpp requires 150 MB–1.5 GB models and is slower on CPU-only hardware.
Vosk is the right starting point; whisper.cpp can replace it if accuracy
proves insufficient.

### Why Python venv with --system-site-packages?
PyGObject (python3-gi) cannot be installed via pip without compiling C
extensions against the system GTK development headers.  Using
`--system-site-packages` gives the venv access to the system GTK bindings
while keeping all other dependencies isolated.

### Camera device assignment
ThinkPad T480 exposes four V4L2 nodes:
  /dev/video0  SunplusIT IR camera    ← NOT usable for face/eye tracking
  /dev/video1  Metadata node for IR
  /dev/video2  Chicony RGB camera     ← PRIMARY camera for AccessOS
  /dev/video3  Metadata node for RGB

All tracking code must open /dev/video2 (configurable via settings.toml).

### Security model for app launching
- `AppLauncher` uses `subprocess.Popen` with `shell=False` only.
- Commands are allow-listed; only the six defined app keys are accepted.
- Voice commands (Phase 4) map to named intents, never to raw shell strings.
- Destructive actions (power off, restart) require explicit confirmation.

## Data flow (Phase 3+)

```
Webcam (/dev/video2)
    └── OpenCV frame capture (30 FPS target)
        └── MediaPipe Face Mesh
            ├── Head pose estimation → virtual mouse pointer
            └── Eye landmark extraction → gaze vector (Phase 5)

Microphone
    └── Vosk streaming recogniser
        └── Intent classifier (allow-list)
            └── Action dispatcher → home_screen / app_launcher

Piper TTS
    └── text → WAV → paplay (async thread)
```

## Configuration layering

```
Built-in Python defaults (_DEFAULTS dict)
  ← config/accessos_defaults.toml   (project defaults, version-controlled)
    ← ~/.config/accessos/settings.toml  (user overrides, not tracked)
```

## File layout

See README.md § Project structure.


## Security & Permission Boundaries (Phase 2)
1. **Wi-Fi Credential Isolation**: Network passwords are never passed via `argv` (process command line), environment variables, logs, or persistent configuration files. Credentials are typed directly into a secure memory buffer and transmitted to `nmcli --ask` exclusively via standard input (`stdin`).
2. **Safe Permission Failures**: Privileged actions (reboot, shutdown, session lock, brightness, audio, Wi-Fi) fail safely with explicit, human-readable error dialogs if Polkit authorization or system permission is denied.
3. **Camera Privacy**: No video streams or frame captures are opened during discovery. Device enumeration is performed strictly via read-only sysfs queries.


## Desktop Session Scope & Pointer Injection Boundary (Phase 3)
1. **X11 Session Requirement**: `X11Mouse` uses `libX11` and `libXtst` to inject synthetic pointer movement and clicks into the active X11 display server. This matches the target Linux Mint Xfce live environment.
2. **Wayland Refusal**: Pure Wayland sessions block synthetic input for compositor-level security isolation. `check_session_supported()` detects non-X11 environments and raises `UnsupportedSessionError`, which `HeadPointerEngine` catches to halt gracefully with user-facing guidance.
3. **Idempotent Emergency Pause**: <kbd>Esc</kbd> acts as a one-way safety latch (`pause_control()`). Repeatedly pressing <kbd>Esc</kbd> always leaves control paused and never inadvertently resumes movement. Resuming requires an explicit action (<kbd>R</kbd>, "Resume" button, or an approved voice command in Phase 4).

## Offline Voice Control & Speech Synthesis Boundaries (Phase 4)
1. **Zero-Cloud & In-Memory Audio Pipeline**:
   - Audio is captured via ALSA `arecord` (16kHz 16-bit mono) in a dedicated streaming thread directly into memory. Zero audio recordings, buffers, or transcripts are ever written to disk or transmitted over the network.
   - Speech synthesis uses on-device Piper TTS (`en_US-lessac-low.onnx`), streaming generated WAV frames directly from memory (`io.BytesIO`) into ALSA `aplay -q`.
2. **Grammar-Constrained Decoding & Allowlist Isolation**:
   - Speech recognition is constrained at the Kaldi lattice level by compiling an explicit grammar of safe phrases.
   - The secondary `command_parser` applies strict defense-in-depth token blacklists (`rm`, `sudo`, `bash`, `delete`, `install`, `eval`, etc.).
   - Recognized commands map strictly to internal `CommandAction` enums. Under no circumstances is voice text passed to a shell, terminal, or generic command runner.
3. **Protected Power State Machine**:
   - Commands requesting system power changes (`restart`, `shutdown`) enter an explicit confirmation state.
   - Action requires a subsequent spoken `confirm` or `yes`. Saying `cancel` or waiting for the 10-second timeout safely aborts the request.
4. **Consent, Visual HUD, & Keyboard Mute**:
   - Voice listening is strictly disabled by default at startup and only starts upon explicit user consent.
   - A dedicated `VoiceHUD` provides clear visual feedback of listening, muted, awaiting confirmation, and error states.
   - <kbd>M</kbd> provides an instantaneous keyboard-accessible microphone pause/mute control.

