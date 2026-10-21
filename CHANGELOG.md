# Changelog

All notable changes to AccessOS are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [0.2.0] - Phase 2: Settings Application & System Control

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
