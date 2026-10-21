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
| **1** ✅ | Keyboard and mouse |
| **3** | Head pointer + dwell-to-click (webcam) |
| **4** | Offline voice control (Vosk) + text-to-speech (Piper) |
| **5** | Blink-to-click + experimental eye-gaze |

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
| 3 | Head pointer + dwell selection | ⏳ Planned |
| 4 | Offline voice + TTS | ⏳ Planned |
| 5 | Blink + experimental gaze | ⏳ Planned |
| 6 | ISO packaging & validation | ⏳ Planned |

---

## Credits

See [CREDITS.md](CREDITS.md) for a full list of libraries and tools used.

## License

MIT — see [LICENSE](LICENSE).
