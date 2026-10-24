# AccessOS Architecture & System Design

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              User / Operator                                │
│       Keyboard · Mouse · Head Pointer · Voice · Blink · Eye Gaze            │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                     AccessOS Application Layer (Python)                     │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                            HomeScreen                                 │  │
│  │   Top Status Bar │ Centered macOS-Style Dock (6 Apps) │ Overlay HUD   │  │
│  └──────────────────────┬────────────────────────────────────────────────┘  │
│                         │                                                   │
│  ┌──────────────────────┼─────────────────────────┬──────────────────────┐  │
│  │                      │                         │                      │  │
│  ▼                      ▼                         ▼                      ▼  │
│ ┌───────────────┐ ┌────────────────────┐ ┌───────────────────┐ ┌──────────┐ │
│ │ Engine Layer  │ │ Voice Engine       │ │ Document Reader   │ │ Settings │ │
│ │ HeadPointer   │ │ Vosk Speech Model  │ │ Extractor (.docx, │ │ Tabs &   │ │
│ │ DwellClicker  │ │ Piper Neural TTS   │ │   .odt, .epub,    │ │ Camera   │ │
│ │ BlinkDetector │ │ Command Allowlist  │ │   .pdf, .txt, .md)│ │ Controls │ │
│ │ GazeTracker   │ │ Loop Suppression   │ │ Speech Playback   │ └──────────┘ │
│ └───────┬───────┘ └────────────────────┘ └───────────────────┘              │
│         │                                                                   │
│         ▼                                                                   │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                     Input Safety & Backend Router                     │  │
│  │  Host-Safe: DryRunMouseBackend + VirtualCursorOverlay (No host grab)   │  │
│  │  VM-Real / Live: X11MouseBackend (libXtst XTest Fake Input)           │  │
│  │  SingleInstanceLock · Universal Emergency Stop (F12) · Esc Pause (Idem)│
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                        Shared Infrastructure                          │  │
│  │  Config (TOML) · Logging · AudioFeedback (Earcons) · AppLauncher      │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                    Linux Mint 22.3 Xfce (Base Operating System)             │
│   X11 Server · LightDM Autologin · ALSA / PulseAudio · V4L2 Webcams         │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Design & Responsibilities

### 2.1 UI Layer
- **`accessos.home_screen.HomeScreen`**:
  - Implements the primary user interface: a compact top status bar and a **centered macOS-style bottom dock** showing exclusively the six allowed apps: Browser, Files, Terminal, Settings, Images, Videos.
  - Supports full keyboard 1-D navigation (<kbd>←</kbd>, <kbd>→</kbd>, <kbd>Home</kbd>, <kbd>End</kbd>, <kbd>1</kbd>–<kbd>6</kbd>, <kbd>Enter</kbd>).
  - Integrates the `VirtualCursorOverlay` as an unmapped, non-grabbing visual layer.
- **`accessos.onboarding.OnboardingWizard`**:
  - First-boot accessible configuration wizard with spoken voice guidance (Piper TTS).
  - Guides user through modality selection (Keyboard/Mouse, Voice, Head Dwell, Head Blink, Combined).
  - Explicit camera and microphone opt-in permissions.

### 2.2 Computer Vision Engine Layer (`accessos.engine`)
- **`HeadPointerEngine`**:
  - Processes RGB camera frames via MediaPipe FaceLandmarker in a dedicated background worker.
  - Normalizes nose-tip displacement relative to center baseline.
  - Applies deadzone filtering and One-Euro adaptive smoothing to eliminate hand/head tremor jitter while retaining sub-frame dynamic response.
- **`BlinkDetector`**:
  - Computes Eye Aspect Ratio (EAR) across 6 landmarks per eye.
  - Distinguishes deliberate selection blinks (200ms–800ms) from involuntary blinks (80ms–150ms).
  - Refractory cooldown prevents repeated double-clicks.
- **`GazeTracker`**:
  - Normalizes pupil-to-canthus ratios to estimate gaze direction.
  - Guided 5-point calibration workflow (Center, Top-Left, Top-Right, Bottom-Left, Bottom-Right).
- **`DwellClicker`**:
  - Temporal accumulation of motionless focus to trigger synthetic click events.

### 2.3 Input Safety Architecture
- **Host Development Isolation**:
  - `LaunchProfile.HOST_SAFE`: Mandatory default on physical host machines. Operates purely in-memory with zero native mouse library loading (`libXtst` / `ctypes` excluded).
  - `LaunchProfile.CAMERA_PREVIEW`: Camera frames rendered locally; dwell clicking and input backends completely disabled.
  - `LaunchProfile.VM_REAL`: Permitted only inside verified hypervisor virtual machines or live-boot media. Refuses bare-metal host execution with `HostSafetyViolationError`.
- **`SingleInstanceLock`**:
  - POSIX `fcntl.flock` file locking ensures exactly one AccessOS instance can run at any time.

### 2.4 Offline Voice & Speech Layer (`accessos.voice`)
- **`VoiceListener`**:
  - Offline Vosk acoustic decoding against a strict, finite command allowlist.
  - Zero raw audio or transcripts written to disk.
  - Piper TTS speech suppression loop: microphone input is automatically muted while TTS is speaking, with a 500ms post-speech cooldown.
  - Command debounce (1.5s cooldown) prevents duplicate triggers.
- **`TTSEngine`**:
  - Neural speech synthesis using Piper (`en_US-lessac-low.onnx`).
  - Synthesizes in-memory and pipes directly to ALSA (`aplay`).

### 2.5 Document Reader (`accessos.reader`)
- Multi-format extraction engine (`DocumentExtractor`):
  - `.txt`, `.md`: encoding-safe plain text.
  - `.html`: DOM parser ignoring script and style tags.
  - `.docx`, `.odt`: native standard-library zipfile XML parsing.
  - `.epub`: zipfile chapter XHTML extraction.
  - `.pdf`: layout-preserving extraction via `pdftotext`.
- Synchronized reading controller (`DocumentReader`):
  - Sentence splitting with abbreviation awareness.
  - Highlights active sentence in real time with autoscroll.

---

## 3. Standalone ISO Architecture
- Built from **Linux Mint 22.3 Xfce (64-bit)** base.
- Customizations applied directly to root SquashFS:
  - AccessOS installed into `/opt/accessos`.
  - Non-essential applications stripped (LibreOffice, Thunderbird, HexChat, Solitaire).
  - Xfce desktop icons disabled so AccessOS dock is the primary focal UI.
  - Autostart configured via LightDM live session autologin.
  - Full AccessOS branding in GRUB, ISOLINUX, and `/etc/os-release`.
