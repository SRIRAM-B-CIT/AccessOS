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
