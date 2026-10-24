# AccessOS ♿🖥️

> **A Lightweight, Bootable, Privacy-First Accessible Operating Environment**  
> Specially crafted for individuals with **blindness, low vision, and motor disabilities** (including quadriplegia, ALS, cerebral palsy, severe tremors, and upper-limb mobility limitations).

[![Hugging Face](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-sri123454321%2FACCESSOS-yellow)](https://huggingface.co/datasets/sri123454321/ACCESSOS)
[![Version](https://img.shields.io/badge/Release-v1.0.0-green.svg)](https://huggingface.co/datasets/sri123454321/ACCESSOS)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Base](https://img.shields.io/badge/Base-Linux%20Mint%2022.3%20Xfce-teal)]()
[![Privacy](https://img.shields.io/badge/Privacy-100%25%20Offline%20%7C%20Zero%20Cloud-success)]()

---

## 🌟 Mission: Computing for Everyone

Computers are essential for learning, communication, work, and personal independence. However, standard desktop environments rely heavily on physical mice, keyboards, and complex multi-layered menus that exclude millions of users with disabilities.

**AccessOS** transforms any computer into an autonomous, accessible environment without requiring proprietary expensive hardware:
- **For Blind & Visually Impaired Users**: End-to-end spoken audio guidance powered by neural speech synthesis (Piper TTS), complete hands-free offline voice control, an accessible multi-format document reader with sentence-by-sentence spoken playback, high-contrast visual themes, and scalable large typography.
- **For Users with Severe Motor Disabilities** (e.g., Spinal Cord Injury, ALS, Cerebral Palsy, Muscular Dystrophy, Amputation): Complete hands-free computing through **head-pointer tracking** using an ordinary webcam, **dwell-to-click** selection, **deliberate blink-to-click** detection, **5-point eye-gaze tracking**, and voice commands.

🔒 **100% Local & Privacy-First**: All computer vision, speech recognition, and neural text-to-speech models run locally on-device. **Zero telemetry. Zero internet required. No cloud subscriptions. No biometrics ever leave the computer.**

---

## 📥 Download AccessOS ISO

The official bootable image (3.0 GB) and checksums are hosted on Hugging Face:

📦 **Hugging Face Repository**: [sri123454321/ACCESSOS](https://huggingface.co/datasets/sri123454321/ACCESSOS)

| File | Size | Direct Download Link | Web View |
| :--- | :--- | :--- | :--- |
| **`AccessOS.iso`** | **3.0 GB** | [⬇️ Download AccessOS.iso](https://huggingface.co/datasets/sri123454321/ACCESSOS/resolve/main/AccessOS.iso?download=true) | [View on HF](https://huggingface.co/datasets/sri123454321/ACCESSOS/blob/main/AccessOS.iso) |
| **`AccessOS.iso.sha256`** | **79 B** | [⬇️ Download Checksum (Raw)](https://huggingface.co/datasets/sri123454321/ACCESSOS/raw/main/AccessOS.iso.sha256) | [View on HF](https://huggingface.co/datasets/sri123454321/ACCESSOS/blob/main/AccessOS.iso.sha256) |

### ⚡ Quick Download via Terminal (Recommended)

You can download both the ISO and checksum directly in your terminal using `wget` or `curl`:

```bash
# 1. Download the bootable ISO (3.0 GB)
wget --content-disposition "https://huggingface.co/datasets/sri123454321/ACCESSOS/resolve/main/AccessOS.iso?download=true" -O AccessOS.iso

# 2. Download the SHA256 checksum file (79 B)
wget "https://huggingface.co/datasets/sri123454321/ACCESSOS/raw/main/AccessOS.iso.sha256" -O AccessOS.iso.sha256
```

### 🔍 Integrity Verification

Always verify the integrity of your download before writing to a USB:

```bash
# Option A: Verify using the downloaded .sha256 file
sha256sum -c AccessOS.iso.sha256

# Option B: Verify directly without downloading the checksum file
echo "ba817a5c996535d70e556391f62989431544ea2cc500e7c1797c3e7a0996e734  AccessOS.iso" | sha256sum -c
```
Expected output:
```text
AccessOS.iso: OK
```

---

## ✨ Key Features

### 1. 🎯 Head-Pointer Tracking & Dwell-to-Click (Hands-Free Motor Access)
- **Webcam-Based Tracking**: Uses MediaPipe Face Mesh on standard RGB webcams to translate natural nose-tip rotation into smooth, jitter-free cursor movements.
- **One-Euro Filtering**: Dynamic adaptive smoothing eliminates micro-tremors when holding still while preserving instantaneous tracking during rapid movements.
- **Dwell-to-Click**: Hover over any button or link to trigger a click, complete with an animated visual countdown arc and distinct audio feedback chime.
- **Tracking Loss Protection**: If lighting fails or face leaves frame, pointer safely freezes in place with auditory alert; never jumps or clicks randomly.
- **Idempotent Emergency Pause (<kbd>Esc</kbd>)**: Hitting <kbd>Esc</kbd> unconditionally disarms pointer tracking instantly. Resuming requires explicit confirmation (<kbd>R</kbd> or clicking *Resume*).

### 2. 👁️ Deliberate Blink Selection
- **Intentional Blink vs Involuntary Blink**: Calculates Eye Aspect Ratio (EAR) across 6 eye landmarks. Natural involuntary blinks (80–150 ms) are ignored, while deliberate prolonged blinks (200–800 ms) trigger precise click actions.
- **Refractory Cooldown**: A 600 ms lockout interval prevents accidental double-clicking.
- **Visual & Audio Ripples**: Displays a distinct animated ripple overlay and plays an audio click confirmation.

### 3. 👀 5-Point Guided Eye-Gaze Tracking
- **Interactive Calibration Wizard**: 5-point on-screen guided calibration (Center, Top-Left, Top-Right, Bottom-Left, Bottom-Right) maps pupil-to-canthus ratios.
- **Combined Mode**: Option to combine gaze for coarse regional pointing with head movement for fine target alignment.

### 4. 🎙️ 100% Offline Voice Control (Vosk)
- **No Cloud Required**: Operates completely offline with zero latency or privacy exposure.
- **Strict Command Allowlisting**: Only safe, predefined accessibility actions are executed (e.g. `open browser`, `open files`, `pause control`, `resume control`, `read status`, `help`, `volume up`, `volume down`, `read document`).
- **Acoustic Feedback Suppression**: Vosk listening automatically pauses while Piper TTS speaks to prevent recursive audio feedback loops.
- **Protected Actions**: System shutdown and restart require explicit spoken two-step confirmation.

### 5. 📖 Multi-Format Accessible Document Reader (Visual Impairments)
- **Zero-Dependency Text Extraction**: Reads `.pdf` (via pdftotext), `.docx`, `.odt`, `.epub`, `.html`, `.txt`, and `.md` files without heavy office suites.
- **Synchronized Neural Speech**: Piper neural TTS reads sentences aloud at adjustable speeds (0.75x–1.75x).
- **Active Sentence Highlighting**: Visually highlights the current sentence in real time with high-contrast text and font scaling.
- **Full Hotkey & Voice Support**: Press <kbd>Ctrl+R</kbd> or say *"read document"* to open; navigate with <kbd>Space</kbd> (play/pause), <kbd>Left/Right</kbd> (previous/next sentence).

### 6. 🧭 First-Boot Accessible Onboarding Wizard
- **Spoken Setup Guidance**: Speaks instructions aloud upon initial boot, walking the user through display scaling, high contrast, and modality setup.
- **Modality Picker**: Easily choose between *Keyboard/Mouse Only*, *Voice Only*, *Head Dwell*, *Head Blink*, or *Combined Access*.
- **Explicit Consent**: Hardware switches require explicit opt-in before opening camera or microphone streams.

### 7. 🚀 High-Visibility Centered macOS Dock
- **Curated 6 Applications**: Strictly Browser, Files, Terminal, Settings, Images, and Videos.
- **Zero Bloat**: No distracting office suites, complex games, confusing menus, or desktop clutter.
- **High Contrast**: Clean glassmorphism dock with clear iconography, hover scaling, and keyboard focus outlines.

---

## 💿 Installation & Live USB Flashing

AccessOS is delivered as a **live bootable hybrid ISO**. You can run it directly from a USB flash drive without installing or touching your existing hard drive!

### What You Need:
- A USB 3.0 flash drive (8 GB or larger).
- The downloaded `AccessOS.iso` and `AccessOS.iso.sha256`.

---

### Method A: Flashing on Linux or macOS (Terminal)

1. Insert your USB drive and locate its device identifier:
   ```bash
   lsblk
   ```
   *(Example: `/dev/sdb` or `/dev/sdc` — **Caution**: Never select your internal disk like `sda` or `nvme0n1`!)*

2. Write the ISO to the USB using `dd`:
   ```bash
   sudo dd if=AccessOS.iso of=/dev/sdX bs=4M status=progress conv=fsync oflag=direct
   ```
   *(Replace `/dev/sdX` with your exact USB device node).*

---

### Method B: Graphical Flashing (Windows, Linux, or macOS)

You can use any standard open-source flashing utility:

- **Raspberry Pi Imager** *(Recommended)*:
  1. Open Raspberry Pi Imager.
  2. Click **Choose OS** $\rightarrow$ select **Use custom** $\rightarrow$ choose `AccessOS.iso`.
  3. Click **Choose Storage** $\rightarrow$ select your USB drive.
  4. Click **Write**.
- **Rufus (Windows)**:
  1. Select your USB drive under *Device*.
  2. Select `AccessOS.iso` under *Boot selection*.
  3. Partition scheme: **MBR** (or GPT for modern UEFI).
  4. Click **Start** (choose *Write in DD Image mode* if prompted).
- **BalenaEtcher**:
  1. Click **Flash from file** $\rightarrow$ select `AccessOS.iso`.
  2. Select target USB drive $\rightarrow$ click **Flash!**

For detailed step-by-step instructions and safety tips, see the [USB Flashing Guide](docs/usb_flashing_guide.md).

---

### 🖥️ Booting AccessOS

1. Insert the flashed USB drive into the target computer (e.g., Lenovo ThinkPad T480 or any standard x86_64 PC).
2. Power on the computer and press the boot menu key:
   - **Lenovo**: <kbd>F12</kbd> (or <kbd>Enter</kbd> then <kbd>F12</kbd>)
   - **Dell**: <kbd>F12</kbd>
   - **HP**: <kbd>F9</kbd>
   - **Asus / Acer**: <kbd>F8</kbd> or <kbd>F12</kbd>
3. Select your USB drive from the boot menu.
4. From the AccessOS bootloader menu, select **Start AccessOS 1.0 (Accessible Environment)**.
5. AccessOS will automatically boot into the live session and start the accessible onboarding wizard!

---

### 🧪 Testing in a Virtual Machine (VirtualBox / QEMU)

If you wish to test AccessOS in a VM before bare-metal hardware:
- **RAM**: 4096 MB (8192 MB recommended)
- **CPUs**: 2 to 4 vCPUs
- **Display**: VMSVGA with 128 MB video memory and 3D acceleration enabled
- **Optical Drive**: Attach `AccessOS.iso`
- **Webcam Passthrough** *(Optional for head-tracking)*: Attach host webcam under *Devices $\rightarrow$ Webcams*.

Detailed VM testing steps are documented in the [Testing Checklist](docs/testing_checklist.md).

---

## ⌨️ Essential Keyboard Shortcuts

At all times, standard keyboard and mouse inputs remain fully operational as an immediate fallback:

| Shortcut | Action |
| :--- | :--- |
| <kbd>Esc</kbd> | **Emergency Pause**: Instantly freezes head pointer, gaze, and dwell |
| <kbd>R</kbd> | **Resume Tracking**: Explicitly unfreezes accessibility controls |
| <kbd>Ctrl</kbd> + <kbd>R</kbd> | Open the **Accessible Document Reader** |
| <kbd>Ctrl</kbd> + <kbd>Alt</kbd> + <kbd>T</kbd> | Open standard fallback terminal |
| <kbd>Space</kbd> | Play / Pause document reader audio |
| <kbd>Left</kbd> / <kbd>Right</kbd> | Previous / Next sentence in document reader |
| <kbd>F12</kbd> | Hardware emergency stop & input unbind |

---

## 🗣️ Common Voice Commands

Voice control runs 100% offline via local Vosk recognition:

| Spoken Phrase | Action |
| :--- | :--- |
| `"open browser"` | Launches Firefox web browser |
| `"open files"` | Launches Thunar file manager |
| `"open terminal"` | Launches Xfce terminal |
| `"open settings"` | Opens AccessOS accessibility settings |
| `"read document"` | Opens the Accessible Document Reader |
| `"pause reading"` / `"resume reading"` | Toggles speech reading playback |
| `"pause control"` | Immediately pauses head pointer tracking |
| `"resume control"` | Resumes head pointer tracking |
| `"volume up"` / `"volume down"` | Adjusts system audio volume |
| `"read status"` | Speaks battery, Wi-Fi, and tracking state aloud |
| `"help"` | Speaks available accessibility commands |

---

## 🛠️ Local Development & Testing

```bash
# 1. Clone repository
git clone https://github.com/SRIRAM-B-CIT/AccessOS.git
cd AccessOS

# 2. Set up virtual environment
python3 -m venv --system-site-packages .venv
source .venv/bin/activate

# 3. Run safe windowed development mode (uses virtual cursor overlay; never touches host mouse)
ACCESSOS_WINDOWED=1 python3 -m accessos

# 4. Run automated test suite (124 tests)
pytest tests/ -v
```

---

## 🛡️ Host Safety Architecture

AccessOS has a strict architectural separation between host development and live boot sessions:
- On development host machines, **`DryRunMouseBackend`** and **`VirtualCursorOverlay`** are used exclusively.
- All pointer movements, dwell timers, and deliberate blinks are drawn strictly onto an in-window virtual reticle.
- **Zero real mouse injection (XTest/X11) is ever executed on the host system**, ensuring your host environment remains completely safe from accidental mouse freezes.

---

## 📚 Documentation Reference

- 📖 **[User Guide](docs/user_guide.md)** — Comprehensive user guide for all modalities.
- ⚡ **[USB Flashing Guide](docs/usb_flashing_guide.md)** — Detailed flashing guide with safety precautions.
- 📋 **[Testing Checklist](docs/testing_checklist.md)** — Step-by-step verification protocols.
- 🛡️ **[Safety and Recovery Guide](docs/safety_and_recovery_guide.md)** — Emergency pauses, recovery mechanisms, and launch profiles.
- 📑 **[Document Reader Guide](docs/document_reader_guide.md)** — Text extraction formats and TTS navigation.
- 🏛️ **[Architecture Specification](ARCHITECTURE.md)** — High-level module design and state machines.
- 📜 **[Changelog](CHANGELOG.md)** — Full release notes for Version 1.0.0.

---

## 📜 License & Disclaimers

- AccessOS is licensed under the **[MIT License](LICENSE)**.
- **Medical Disclaimer**: AccessOS is a research and assistive technology platform, not an FDA-cleared or certified medical device. Always ensure traditional keyboard and mouse fallbacks are accessible.
