# AccessOS — Development Setup Guide

## Prerequisites

| Requirement | Minimum | Recommended |
|---|---|---|
| OS | Ubuntu 22.04 / Mint 21 (Noble base) | Zorin OS 18 / Mint 22.3 |
| Python | 3.11 | 3.12 |
| RAM | 4 GB | 8 GB |
| Disk free | 5 GB | 15 GB |

### Required system packages (must be present before venv creation)

```bash
# These are pre-installed on Zorin OS 18 / Mint 22.x:
python3-gi          # PyGObject — GTK Python bindings
python3-gi-cairo    # Cairo surface support
gir1.2-gtk-3.0     # GTK 3 typelib
gir1.2-gdkpixbuf-2.0
pulseaudio-utils    # paplay (for sound cues)
```

## Step 1 — Clone and enter the project

```bash
git clone https://github.com/SRIRAM-B-CIT/AccessOS.git
cd AccessOS
```

## Step 2 — Create the virtual environment

> **Important**: use `--system-site-packages` so the venv inherits system
> GTK 3 bindings.  Do NOT install PyGObject via pip.

```bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
```

Verify GTK 3 is available:

```bash
python3 -c "import gi; gi.require_version('Gtk','3.0'); \
    from gi.repository import Gtk; print('GTK3 OK')"
```

## Step 3 — Install development dependencies

```bash
pip install pytest
```

Phase 3+ will add: `opencv-python mediapipe`  
Phase 4+ will add: `vosk` and the Piper binary.

## Step 4 — Run the home screen

```bash
# Windowed mode (recommended for development)
ACCESSOS_WINDOWED=1 python3 -m accessos

# Fullscreen mode
python3 -m accessos

# Verbose logging
ACCESSOS_LOG_LEVEL=DEBUG ACCESSOS_WINDOWED=1 python3 -m accessos
```

## Step 5 — Run tests

```bash
pytest tests/ -v
```

Expected output: all tests pass, no display or camera required.

## Log file location

```
~/.local/share/accessos/logs/accessos.log
```

## Configuration override

```bash
mkdir -p ~/.config/accessos
cp config/accessos_defaults.toml ~/.config/accessos/settings.toml
# Edit ~/.config/accessos/settings.toml as needed
```
