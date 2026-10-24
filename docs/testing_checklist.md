# AccessOS Verification & Testing Checklist

This checklist guides step-by-step verification of the built `AccessOS.iso` in a virtual machine (VirtualBox / QEMU) and on bare-metal live USB hardware (Lenovo ThinkPad T480).

---

## Pre-Flight Check: ISO Cryptographic Verification
- [ ] Run `sha256sum -c AccessOS.iso.sha256`.
- [ ] Confirm output states: `AccessOS.iso: OK`.
- [ ] Verify file size is approximately 2.9–3.2 GB.

---

## Phase A: Virtual Machine Verification (VirtualBox / QEMU)

### 1. VM Configuration
- Type: Linux / Ubuntu 64-bit
- Memory: 4096 MB RAM (minimum 2048 MB)
- Display: 128 MB VRAM, VMSVGA or VBoxSVGA controller, Enable 3D Acceleration
- Audio: Intel HD Audio / PulseAudio
- Optical Drive: Attach `AccessOS.iso`

### 2. Boot & First-Boot Wizard
- [ ] **GRUB Bootloader**: Verify menu entry displays `Start AccessOS 1.0 (Accessible Environment)`.
- [ ] **LightDM Autologin**: Boots directly into live user desktop without password prompts.
- [ ] **Autostart**: AccessOS launches automatically in fullscreen upon desktop session startup.
- [ ] **Onboarding Wizard**:
  - [ ] Spoken voice greeting plays through audio output.
  - [ ] Step 1 (Welcome) displays spoken guidance toggle.
  - [ ] Step 2 (Modality) displays 5 interaction options.
  - [ ] Step 3 (Consent) displays detected RGB camera and microphone switches (default: OFF).
  - [ ] Step 4 (Display) allows toggling High Contrast and selecting Font Size.
  - [ ] Step 5 (Finish) saves settings to `~/.config/accessos/settings.toml`.

### 3. Desktop & Dock Verification
- [ ] **Dock Design**: Centered macOS-style dock at the bottom of the screen.
- [ ] **Six Primary Applications Only**:
  - [ ] 🌐 Browser (`firefox`)
  - [ ] 📁 Files (`thunar`)
  - [ ] 💻 Terminal (`xfce4-terminal`)
  - [ ] ⚙️ Settings (`accessos settings`)
  - [ ] 🖼️ Images (`ristretto`)
  - [ ] 🎬 Videos (`parole`)
- [ ] **No Desktop Clutter**: Desktop icons disabled; LibreOffice, Thunderbird, HexChat, games, and package managers hidden.
- [ ] **Dock Keyboard Navigation**:
  - [ ] Keys <kbd>1</kbd> to <kbd>6</kbd> focus and launch dock items.
  - [ ] Arrow keys navigate between icons with visible blue focus indicator.
  - [ ] <kbd>Enter</kbd> launches focused app.

### 4. Accessibility & Safety Controls
- [ ] **Emergency Stop**: Press <kbd>F12</kbd> -> all active tracking engines cleanly shut down.
- [ ] **Idempotent Pause**: Press <kbd>Esc</kbd> -> tracking pauses. Pressing <kbd>Esc</kbd> again maintains paused state (never resumes).
- [ ] **Explicit Resume**: Press <kbd>R</kbd> or click Resume -> tracking resumes.
- [ ] **Emergency Terminal Fallback**: Press <kbd>Ctrl + Alt + T</kbd> -> `xfce4-terminal` opens immediately.

### 5. Document Reader
- [ ] Press <kbd>Ctrl + R</kbd> -> Document Reader window appears.
- [ ] Open a sample text file -> sentences populate.
- [ ] Press <kbd>Space</kbd> -> Piper TTS reads sentence aloud with blue highlighted text.
- [ ] Press <kbd>→</kbd> / <kbd>←</kbd> -> moves to next / previous sentence.
- [ ] Press <kbd>Esc</kbd> -> Document Reader closes safely.

---

## Phase B: Bootable Live USB Verification (ThinkPad T480)

> *Pending user approval of target drive and physical flashing per `docs/usb_flashing_guide.md`.*

- [ ] Insert flashed USB into ThinkPad T480.
- [ ] Tap <kbd>F12</kbd> at power-on to select USB drive.
- [ ] Verify hardware detection:
  - [ ] Camera: Verified Chicony RGB camera (`/dev/video2`) detected; SunplusIT IR camera (`/dev/video0`) bypassed.
  - [ ] Audio: Internal ThinkPad speakers and microphone detected.
  - [ ] Wi-Fi: Intel Wireless adapter detected; networks listed in Settings.
- [ ] Enable Head Pointer Tracking:
  - [ ] Camera notice displayed before opening stream.
  - [ ] Head movement translates to smooth pointer motion with One-Euro smoothing.
  - [ ] Dwell click triggers selection on buttons.
  - [ ] Voluntary blink triggers selection without involuntary blink false positives.
  - [ ] Covering camera or moving out of frame freezes pointer and announces fallback safely.
