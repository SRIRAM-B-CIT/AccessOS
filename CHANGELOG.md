# Changelog

All notable changes to AccessOS are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

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
