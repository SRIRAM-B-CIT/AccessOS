
## [Phase 4] - 2026-10-21 - Offline Voice Control & Speech Synthesis

### Added
- **Offline Speech Recognition (Vosk)**:
  - Streaming Kaldi recognizer running locally on 16kHz audio from ALSA `arecord`.
  - Grammar restriction constrained strictly to approved command phrases.
  - Zero disk writing or cloud transmission of voice data or transcripts.
  - Disabled by default; requires explicit user consent dialog before activating microphone.
- **Offline Speech Synthesis (Piper TTS)**:
  - Low-latency neural speech synthesis via ONNX runtime model `en_US-lessac-low.onnx`.
  - In-memory WAV synthesis streamed directly to ALSA `aplay -q`.
  - Asynchronous background worker queue prevents UI thread blocking.
- **Strict Command Allowlisting**:
  - Direct actions: `open browser`, `files`, `terminal`, `settings`, `images`, `videos`, `go home`, `pause control`, `resume control`, `stop tracking`, `read status`, `help`, `volume up`, `volume down`.
  - Defense-in-depth prohibition of dangerous tokens (`sudo`, `rm`, `bash`, `delete`, `install`, etc.).
  - Recognized speech is never passed to shell or terminal.
- **Spoken Confirmation State Machine**:
  - `restart` and `shutdown` voice commands enter `AWAITING_CONFIRMATION` state.
  - Spoken confirmation required (`confirm`/`yes`); abort on `cancel`/`no` or 10-second timeout.
- **Voice HUD & Keyboard Mute**:
  - Visual status pill indicating Active, Muted, Awaiting Confirmation, Error, or Off.
  - Auto-clearing command toast displaying recognized actions.
  - Keyboard shortcut <kbd>M</kbd> toggles microphone mute instantly.
- **Test Suite & Benchmarks**:
  - 13 new unit and integration tests covering allowlists, token rejections, mic failure, confirmation state machine, and HUD styling (63 total passing tests).
  - Automated benchmark suite `scripts/benchmark_phase4.py` measuring Piper synthesis speed (0.053x RTF, 183ms latency), Vosk decoding (0% CPU idle, ~1.5ms grammar init), and process memory (~340MB peak).

# Changelog

All notable changes to AccessOS are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [0.3.0] - Phase 3: Computer Vision Head Pointer & Dwell Selection

### Safety & Verification Corrections (Phase 3 Post-Review)
- **Idempotent Emergency Pause**: <kbd>Esc</kbd> is now strictly idempotent — pressing <kbd>Esc</kbd> always pauses accessibility control and never toggles or resumes it. Resuming control explicitly requires the **Resume** button, the <kbd>R</kbd> shortcut, or an approved Phase 4 voice command.
- **Accurate Latency Terminology**: Corrected performance reports to specify **19.2 ms vision-processing loop latency** (frame acquisition, RGB conversion, MediaPipe landmark detection, and filter computation), clarifying that this is not end-to-end sensor-to-photon latency.
- **X11 Session Validation & Wayland Refusal**: Added explicit session detection (`check_session_supported()`) and `UnsupportedSessionError`. AccessOS safely refuses to start pointer injection on pure Wayland sessions with an actionable guidance message, aligning with Linux Mint Xfce's native X11 architecture.
- **Automated Tests Expanded**: Added automated tests for idempotent pause behavior, explicit resume, and graceful refusal of pointer injection on non-X11 sessions (50/50 tests passing).

### Added
- **Head Pointer Vision Engine** (`accessos.engine.HeadPointerEngine`):
  - Real-time head tracking powered by MediaPipe FaceLandmarker with XNNPACK CPU acceleration.
  - Dynamically targets the verified RGB camera without hardcoding device nodes.
  - Processes frames asynchronously in a dedicated worker thread, keeping the GTK UI completely fluid.
- **Native 64-bit X11 Mouse Controller** (`accessos.engine.X11Mouse`):
  - Directly interfaces with `libX11` and `libXtst` via 64-bit typed ctypes.
  - Sub-millisecond cursor motion and click execution with zero external dependencies.
- **Signal Filtering & Stabilization** (`accessos.engine.PointFilter2D`):
  - Deadzone filter to suppress minor head tremors.
  - One-Euro adaptive low-pass filter for jitter reduction at rest and responsiveness in motion.
- **Dwell-to-Click State Machine** (`accessos.engine.DwellClicker`):
  - Automatic click generation on hover within a configurable spatial radius and dwell delay.
  - Refractory cooldown period to eliminate accidental double clicks.
- **Tracking HUD & Control Overlay** (`accessos.engine.TrackingOverlay`):
  - Persistent visual indicator showing live state (Active, Lost, Paused, Off), FPS, and latency.
  - Real-time dwell progress bar.
  - One-touch calibration (<kbd>C</kbd>) and emergency pause (<kbd>Esc</kbd>).
- **Safe Fallback & Privacy Guarantees**:
  - Tracking is never started automatically at boot; requires explicit user confirmation.
  - When tracking confidence is lost, cursor safely freezes in place, warning earcon sounds, and physical keyboard/mouse fallback is highlighted.
  - Physical keyboard and mouse remain operational at all times.
- **ThinkPad T480 Performance Benchmark**:
  - Achieved **26.5 FPS** average processing speed at **19.2 ms** latency with **197 MB** total RAM footprint.
- **Automated Test Suite**:
  - Added 9 new unit tests covering native mouse control, deadzones, low-pass filters, One-Euro filters, dwell state machine, and engine state transitions (45/45 total tests passing).

## [0.2.0] - Phase 2: Settings Application & System Control

### Corrected & Verified (Phase 2 Post-Review)
- **Centered macOS-Style Bottom Dock**: Converted the launcher from a 6-card grid to a centered macOS-style bottom dock with frosted-glass container styling, high-contrast outlines, and horizontal wrap-around keyboard navigation (`Left`/`Right`/`Home`/`End`/`1`-`6`). The top status bar remains compact and the dock is the sole application launcher.
- **Hardware-Verified Camera Metadata**: Corrected camera discovery to read device metadata dynamically from USB sysfs without vendor assumptions (`/dev/video2`: Chicony Electronics Co.,Ltd. Integrated Camera; `/dev/video0`: SunplusIT Inc Integrated IR Camera).
- **Wi-Fi Credential Protection**: Passwords are piped exclusively via `stdin` to `nmcli --ask`, preventing credential exposure in `ps aux`, `/proc/<pid>/cmdline`, or shell histories.
- **Safe Permission Rejection**: All system controls (reboot, shutdown, lock, brightness, volume, Wi-Fi) fail safely with actionable user feedback on denied permissions.

### Added
- **AccessOS Settings Application** (`accessos.settings.SettingsWindow`):
  - Accessible multi-tabbed preferences center (Accessibility, Display, Sound, Camera, Wi-Fi, System & Power).
  - 2D keyboard navigation, high-contrast outlines, screen reader markup annotations.
  - Returns cleanly to Home Screen on `Esc` or the Home button.
- **Hardware-Safe Camera Detector** (`accessos.settings.CameraDetector`):
  - Discovers V4L2 devices in sysfs and automatically classifies RGB vs IR sensors.
  - Identifies `/dev/video2` as the recommended RGB webcam without accessing video streams or requesting camera frames.
- **Guarded Power & Session Controls** (`accessos.settings.ConfirmDialog`):
  - Explicit confirmation dialog for every destructive system action (reboot, shutdown, restore defaults).
  - Safe default focus on `Cancel` to prevent accidental triggers.
  - Non-shell execution of `systemctl` / `loginctl` with argument arrays.
- **Safe Hardware Interfaces** (`accessos.settings.SystemControl`):
  - Audio volume query and adjustment via ALSA `amixer`.
  - Display brightness control via XRandR software scaling.
  - NetworkManager Wi-Fi scanning, radio toggling, and connection handling via `nmcli`.
- **Configuration Persistence & Default Restoration** (`accessos.utils.Config`):
  - Added atomic TOML serialization to `~/.config/accessos/settings.toml`.
  - Added `restore_defaults()` with deep copy and real-time listener notification.
- **Phase 2 Test Suite**:
  - 10 new unit tests covering TOML persistence, restore defaults, camera classification, volume/brightness clamping, and process execution isolation (30/30 total tests passing).

## [0.1.0] — Phase 1 — Home Screen Foundation

### Added
- Six-button home screen launcher (Browser, Files, Terminal, Settings, Images, Videos)
- High-contrast dark GTK 3 theme with 18 px+ text throughout
- Vivid blue (#4f9eff) keyboard focus ring — unmissable for low-vision users
- Full 2-D arrow-key grid navigation (arrow keys + Tab + Enter/Space)
- Emergency pause / resume via Esc key and visible header button
- Pause banner (Gtk.Revealer) that slides in below the header when paused
- Grid set_sensitive(False) when paused — buttons visually grey out
- Status bar: input mode, active/paused state, camera off, mic off, battery %, network, clock
- Power menu dialog (Phase 1 placeholders for lock / restart / shutdown)
- Return to Home action in power menu (always functional)
- Settings placeholder dialog pointing to Phase 2
- AppLauncher with allow-listed apps, no shell=True, fallback alternatives
- AudioFeedback: focus / activate / error / pause / resume cues via paplay/aplay
- Config system: TOML file with deep-merge defaults (tomllib stdlib)
- Rotating file logger: ~/.local/share/accessos/logs/accessos.log
- ACCESSOS_WINDOWED=1 env var for windowed development mode
- Unit tests for Config and AppLauncher (no hardware/display required)
- run_accessos.sh and stop_accessos.sh helper scripts
- MIT License, README, CREDITS, ARCHITECTURE, docs skeleton
