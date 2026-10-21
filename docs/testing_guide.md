# AccessOS — Testing Guide

## 🛡️ Host vs VM Safety Matrix

AccessOS enforces complete isolation between the host machine and synthetic input events:

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

---

## Host Safe-Mode Testing (Bare Metal)

During host testing, AccessOS runs exclusively with `DryRunMouseBackend` and `VirtualCursorOverlay`.

### Manual Test Procedure on Host
1. Launch AccessOS in windowed mode:
   ```bash
   ACCESSOS_WINDOWED=1 python3 -m accessos
   ```
2. **Verify Safety Badge**: Check that the top-right header displays:
   `[🛡️ SAFE DRY-RUN — REAL MOUSE UNAFFECTED]`
3. **Verify Physical Mouse Freedom**:
   - Move your physical mouse and click buttons, terminal, or dock items.
   - Physical mouse pointer and clicks must remain 100% normal and unhindered.
4. **Verify Virtual Cursor Overlay**:
   - Start head tracking.
   - As head moves, verify the cyan reticle cursor moves inside the AccessOS window.
   - Dwell over a dock item: verify the circular dwell arc fills without moving the system pointer or generating OS clicks.
   - On dwell completion, verify the expanding ripple animation triggers.
5. **Verify Idempotent Pause**:
   - Press <kbd>Esc</kbd>. The tracking indicator switches to **PAUSED**, and the pause banner slides down.
   - Press <kbd>Esc</kbd> again: tracking remains **PAUSED** (idempotent, never toggles or resumes).
   - Press <kbd>R</kbd> or click **Resume** to restore tracking.
6. **Verify Universal Emergency Stop**:
   - Press <kbd>F12</kbd> (or <kbd>Ctrl+Alt+S</kbd>).
   - Verify tracking halts immediately, dwell progress resets to 0, camera stream closes, and state returns to safe stopped mode.

---

## VirtualBox VM Testing (Real Input Injection)

> ⚠️ **CRITICAL SAFETY REQUIREMENT**: Real input injection (`X11MouseBackend`), real OS clicks, dwell clicking, and power controls are tested **strictly inside a VirtualBox VM with a clean baseline snapshot**. Never run real input injection on bare-metal host hardware.

Refer to [`docs/virtualbox_test_plan.md`](virtualbox_test_plan.md) for the complete VirtualBox testing guide:
- VM Setup: Linux Mint 22.3 Xfce 64-bit with VirtualBox Guest Additions and USB Webcam passthrough.
- Snapshot creation: `VBoxManage snapshot "AccessOS-Mint-Xfce" take "baseline-clean"`
- Execution of real input tests inside the VM.
- Snapshot restoration upon any fault: `VBoxManage snapshot "AccessOS-Mint-Xfce" restore "baseline-clean"`

---

## Unit tests (no hardware required)

```bash
source .venv/bin/activate
pytest tests/ -v
```

Tests cover:
- `test_config.py`: defaults, TOML override, deep merge, reload, malformed TOML
- `test_app_launcher.py`: security (no shell=True), allow-list enforcement,
  fallback logic, custom command override

## Phase 1 manual test procedure

After running `ACCESSOS_WINDOWED=1 python3 -m accessos`:

### Visual tests
- [ ] Window opens maximised with dark (#0d1117) background
- [ ] AccessOS title and subtitle visible in the header
- [ ] Six buttons visible in a centered macOS-style bottom dock with icons and labels
- [ ] Status bar visible at the bottom (mode, state, battery, network, time)
- [ ] Pause and Power buttons visible in the header

### Keyboard navigation
- [ ] Tab moves focus forward through buttons (visible blue focus ring)
- [ ] Shift+Tab moves focus backward
- [ ] Arrow keys navigate the centered macOS-style bottom dock (Right/Left within row, Up/Down between rows)
- [ ] Enter / Space activates the focused button
- [ ] Esc toggles pause / resume
- [ ] Pause banner slides in below the header when paused
- [ ] Buttons grey out when paused; clicking them does nothing
- [ ] Pause banner disappears and buttons are restored when resumed

### Application launching
- [ ] Browser button opens a web browser (or shows an error if not found)
- [ ] Files button opens a file manager
- [ ] Terminal button opens a terminal emulator
- [ ] Images button opens an image viewer
- [ ] Videos button opens a media player
- [ ] Settings button shows the Phase 2 placeholder dialog

### Power menu
- [ ] Power button opens the power menu dialog
- [ ] Lock / Restart / Shutdown buttons show the Phase 1 placeholder message
- [ ] Return to Home closes the dialog
- [ ] Cancel closes the dialog

### Error handling
- [ ] If an app is not found, an error notification slides in from the right
- [ ] Error notification auto-hides after 5 seconds

### Audio feedback (optional — requires speaker)
- [ ] Subtle sound plays when Tab / arrows move focus between buttons
- [ ] Different sound plays when a button is activated
- [ ] If no audio player is found, everything still works silently


## Phase 3 Testing — Head Pointer & Dwell Selection

### 1. Automated Test Suite
Run the full unit and component test suite:
```bash
source .venv/bin/activate
pytest tests/ -v
```

### 2. Manual Verification Workflow
1. Launch AccessOS in windowed development mode:
   ```bash
   ./scripts/run_accessos.sh
   ```
2. Verify that camera tracking is **OFF** at startup (privacy compliance).
3. Click **[📷 Start Tracking]** in the header.
4. Verify that the **Camera Start Notice** modal appears.
5. Click **Enable Camera**:
   - The status pill turns green: `🟢 HEAD TRACKING ACTIVE`.
   - The FPS counter displays ~25–30 FPS with ~18–20 ms latency.
6. Move head smoothly: verify the system mouse cursor tracks head movements.
7. Press <kbd>C</kbd>: verify calibration baseline resets to current position.
8. Hover cursor stationary over a dock item:
   - Observe the dwell progress bar filling from 0% to 100%.
   - At 100%, observe the click activation sound and app launch.
9. Block the webcam lens or look away:
   - Observe immediate transition to `🟡 TRACKING LOST · KEYBOARD/MOUSE ACTIVE`.
   - Observe warning audio tone.
   - Confirm cursor freezes safely without jumping.
10. Press <kbd>Esc</kbd>:
   - Observe immediate transition to `⏸ CONTROL PAUSED`.
   - Press <kbd>Esc</kbd> again to resume.
11. Click **[⏹ Stop Tracking]** to release the webcam cleanly.

## Phase 4 Verification: Offline Voice Control & Piper Speech Synthesis

### Automated Tests
Run the automated test suite including all Phase 4 voice tests:
```bash
PYTHONPATH=. .venv/bin/pytest tests/test_voice_control.py -v
PYTHONPATH=. .venv/bin/pytest
```

### Performance & Resource Benchmark
Run the Phase 4 hardware benchmark on the ThinkPad T480:
```bash
PYTHONPATH=. .venv/bin/python3 scripts/benchmark_phase4.py
```
Expected performance:
- Piper TTS synthesis latency: ~60ms - 200ms per utterance (Real-Time Factor < 0.1x).
- Vosk grammar initialization latency: ~1.5ms.
- Vosk decoding CPU utilization: < 5% CPU on Intel Core i5.
- RAM footprint: ~340 MB RSS total for combined Piper + Vosk engines.

### Manual Verification Steps
1. Launch AccessOS in windowed mode:
   ```bash
   ACCESSOS_WINDOWED=1 PYTHONPATH=. .venv/bin/python3 -m accessos
   ```
2. **Verify Default Disabled State**:
   - Notice the Voice HUD status badge displays `🎙️ Voice: OFF`.
   - The microphone is completely inactive; no audio is recorded.
3. **Explicit Consent Flow**:
   - Click the `🎙️ Start Voice` button in the top right.
   - Verify the privacy notice modal appears:
     - Clarifies all audio is processed strictly locally.
     - Confirms zero transcripts or recordings are stored.
     - Confirms shell/terminal command execution is blocked.
   - Click `Enable Microphone`.
   - The Voice HUD turns green: `🎙️ LISTENING`, and button changes to `⏹ Stop Voice`.
4. **Command Execution**:
   - Say: *"open browser"* -> Hear speech feedback *"Opening Browser"* and watch the browser launch.
   - Say: *"volume up"* -> Hear speech feedback *"Volume X percent"* and watch volume increase.
   - Say: *"read status"* -> Hear synthesized system status report.
   - Say: *"help"* -> Hear available voice commands list.
5. **Microphone Mute / Pause**:
   - Press <kbd>M</kbd> on the keyboard.
   - Voice HUD immediately changes to amber: `🔇 MIC MUTED (M)`, and speaker says *"Microphone muted"*.
   - Say any command -> nothing is executed.
   - Press <kbd>M</kbd> again -> HUD returns to green `🎙️ LISTENING` and announces *"Microphone active"*.
6. **Confirmation Safety for Power Actions**:
   - Say: *"restart"* -> Voice enters `⚠️ AWAITING CONFIRMATION`, and speech says: *"Restart requested. Say confirm to proceed, or cancel to abort."*
   - Say: *"cancel"* -> Status returns to listening, speech says: *"Action canceled."* (System does NOT reboot).
   - Say: *"restart"* -> Wait 10 seconds without speaking -> Confirmation automatically times out and aborts safely.
7. **Prohibited Command Rejection**:
   - Say: *"delete files"*, *"sudo reboot"*, or *"install app"*.
   - The system completely ignores the utterance and never executes generic terminal commands.

