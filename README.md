# AccessOS

> A lightweight, bootable, privacy-first live environment for users with visual impairments and motor-access needs.

[![Phase](https://img.shields.io/badge/Phase-1%20%E2%80%94%20Home%20Screen-blue)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)]()
[![Base](https://img.shields.io/badge/Base-Linux%20Mint%2022.3%20Xfce-green)]()

---

## About

AccessOS is a custom bootable Linux live environment built on **Linux Mint 22.3 Xfce**.  
It is designed for people who cannot use a standard mouse-and-keyboard setup, providing alternative input via:

| Phase | Input method |
|-------|-------------|
| **1** ✅ | Keyboard and mouse with high-visibility dock |
| **2** ✅ | Accessible settings, display, volume, and camera detector |
| **3** ✅ | Head pointer tracking + dwell-to-click (MediaPipe) |
| **3.5/3.6** ✅ | Input-safety redesign, profile isolation, and single-instance lock |
| **4** ✅ | Offline voice control (Vosk) + text-to-speech (Piper) |
| **5** ✅ | Deliberate blink selection + 5-point gaze calibration |
| **6** ✅ | Accessible Document Reader (Multi-format) + First-boot wizard |
| **7** ✅ | Standalone bootable AccessOS.iso packaging & live USB verification |

**All processing is local. No biometric data is uploaded. No cloud account is required.**

---

## Minimal application set

The home screen exposes exactly six applications:

| Button | Application |
|--------|------------|
| 🌐 Browser | Firefox |
| 📁 Files | Thunar |
| 💻 Terminal | XFCE Terminal |
| ⚙ Settings | AccessOS Settings (Phase 2+) |
| 🖼 Images | Ristretto |
| 🎬 Videos | Parole |

No office suite, games, email, chat, app store, or other non-essential software is exposed.

---

## Hardware requirements

- **CPU**: x86_64, quad-core recommended (i5-8350U or equivalent)
- **RAM**: 8 GB (minimum 4 GB for head tracking, 8 GB recommended)
- **GPU**: Intel integrated is sufficient — no discrete GPU required
- **Camera**: Standard RGB webcam (NOT IR-only).  ThinkPad T480: use `/dev/video2`
- **Microphone**: Built-in or external (Phase 4+)
- **Storage**: 8 GB USB drive minimum for live boot

---

## Development setup

```bash
# 1. Clone
git clone https://github.com/SRIRAM-B-CIT/AccessOS.git
cd AccessOS

# 2. Create virtual environment (uses system GTK3 / python3-gi)
python3 -m venv --system-site-packages .venv
source .venv/bin/activate

# 3. Install development dependencies (pytest only for Phase 1)
pip install pytest

# 4. Run the home screen (windowed, for development)
ACCESSOS_WINDOWED=1 python3 -m accessos

# 5. Run tests
pytest tests/ -v
```

See [docs/setup_guide.md](docs/setup_guide.md) for full setup instructions.

---

## Project structure

```
AccessOS/
├── accessos/          Python package (home screen, engine, settings)
│   ├── style.css      GTK 3 stylesheet
│   ├── home_screen.py Primary launcher interface
│   ├── status_bar.py  Live status area
│   ├── power_menu.py  Power / session options
│   ├── app_launcher.py Safe subprocess launcher
│   ├── audio_feedback.py Sound cues
│   ├── utils/         Config + logger
│   ├── settings/      Phase 2 placeholder
│   └── engine/        Phase 3+ accessibility engine placeholder
├── config/            Default TOML configuration
├── assets/            Wallpaper, icons, sounds
├── docs/              Setup, testing, dependencies, ISO build guides
├── tests/             Unit tests (no hardware required)
├── scripts/           run_accessos.sh, stop_accessos.sh
└── packaging/         Phase 6 ISO build scripts
```

---

## 🛡️ Host vs VM Safety Matrix

To prevent synthetic input events from interfering with bare-metal host hardware (e.g. freezing physical mouse clicks or capturing window manager events), AccessOS strictly enforces an architectural boundary between host development and live input injection:

| Feature | Environment Support | Backend Used | Safety Guarantee |
| :--- | :--- | :--- | :--- |
| **Home Screen & macOS Dock** | ✅ **Host Safe** | Native GTK3 | Pure UI rendering; keyboard and physical mouse navigation |
| **Settings & Configuration** | ✅ **Host Safe** | In-Memory / TOML | Safe config persistence and restore defaults |
| **Audio Feedback & Sounds** | ✅ **Host Safe** | GSound / Subprocess | Non-intrusive sound cues |
| **Head Pointer Tracking** | ✅ **Host Safe** (Dry-Run) | `DryRunMouseBackend` | Real camera tracking; moves **virtual reticle** inside window only |
| **Dwell Selection & Progress** | ✅ **Host Safe** (Dry-Run) | `VirtualCursorOverlay` | Renders animated Cairo progress arc & ripple; **no OS clicks** |
| **Safe Dry-Run Status Badge** | ✅ **Host Safe** | GTK Header Widget | Prominently displays `[🛡️ SAFE DRY-RUN — REAL MOUSE UNAFFECTED]` |
| **Voice Control (Vosk)** | ✅ **Host Safe** | In-Memory Engine | Offline speech recognition; dispatches UI actions without OS injection |
| **Speech Feedback (Piper)** | ✅ **Host Safe** | In-Memory ONNX | Neural TTS via local ALSA playback |
| **Universal Emergency Stop** | ✅ **Host Safe & VM** | Keybinding (<kbd>F12</kbd>) | Idempotently releases all synthetic buttons, stops camera, and halts tracking |
| **Real Pointer Injection** | ⛔ **VM Only** | `X11MouseBackend` (XTest) | **Strictly blocked on bare-metal host** via `HostSafetyViolationError` |
| **Real System Clicks & Dwell** | ⛔ **VM Only** | `X11MouseBackend` (XTest) | **Strictly blocked on bare-metal host**; requires clean VM snapshot |
| **Privileged Power (Shutdown/Reboot)** | ⛔ **VM Only** | `systemctl` / Polkit | Requires explicit UI/Voice confirmation; tested in VM |
| **Boot-Time Autostart & ISO** | 📀 **ISO Only** | Live Session / LightDM | Configured during live ISO squashfs build |

> **Host Safety Enforcement**: Any attempt to instantiate `X11MouseBackend` or enable real OS input injection on bare-metal host hardware raises an immediate `HostSafetyViolationError` and halts initialization.


## ⚠ Important disclaimers

- AccessOS is a **portfolio / research project**, not a certified medical device.
- Accessibility features have **not been clinically tested**. Real user testing with
  people who have visual impairments is required before any production use.
- Eye-gaze control (Phase 5) is experimental and may not be accurate enough on
  a standard integrated webcam.
- Always keep keyboard and mouse available as a fallback.

---

## Development phases

| # | Name | Status |
|---|------|--------|
| 0 | Discovery & architecture | ✅ Complete |
| 1 | Home screen foundation | ✅ Complete |
| 2 | Settings & system control | ✅ Complete |
| 3 | Head pointer + dwell selection | ✅ Complete |
| 3.5/3.6 | Host input safety & isolation | ✅ Complete |
| 4 | Offline voice + TTS | ✅ Complete |
| 5 | Deliberate blink + eye gaze | ✅ Complete |
| 6 | Document Reader & Onboarding | ✅ Complete |
| 7 | ISO packaging & live USB | ✅ Complete |

---

## Credits

See [CREDITS.md](CREDITS.md) for a full list of libraries and tools used.

## License

MIT — see [LICENSE](LICENSE).


## Desktop Session Requirement
AccessOS pointer injection relies on standard X11 protocols (`libX11` / `libXtst`).
- **Target Distribution**: Linux Mint Xfce runs native X11 by default.
- **Wayland Safety**: Pure Wayland sessions that block synthetic input events are detected at runtime; AccessOS displays a clear unsupported-session notification and refuses to start pointer injection rather than failing or crashing.
