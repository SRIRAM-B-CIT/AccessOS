# Changelog

All notable changes to AccessOS are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [0.3.0] - Phase 3: Computer Vision Head Pointer & Dwell Selection

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
