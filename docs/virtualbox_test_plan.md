# AccessOS VirtualBox Testing Plan & VM Isolation Guide

## 1. Safety Policy Overview

> [!CAUTION]
> **STRICT SAFETY INVARIANT**: Real OS-level pointer motion, synthetic clicks, and system-wide input injection are **STRICTLY PROHIBITED** on the bare-metal host machine.
> Direct host testing must exclusively use `DryRunMouseBackend` with the `VirtualCursorOverlay`.
> Real input injection (`X11MouseBackend`) is restricted exclusively to isolated VirtualBox virtual machines running Linux Mint 22 Xfce.

---

## 2. VirtualBox VM Specifications (Linux Mint 22 Xfce)

To ensure reliable, deterministic testing of real mouse injection, camera pass-through, and speech systems, configure the test VM as follows:

| Setting | Recommended Value | Notes |
|---|---|---|
| **OS Type** | Linux / Ubuntu (64-bit) | Linux Mint 22 is Ubuntu 24.04-based |
| **Base Memory (RAM)** | 4096 MB – 8192 MB | Minimum 4 GB; 8 GB recommended for vision models |
| **Processors (vCPUs)** | 2 – 4 vCPUs | Enable PAE/NX |
| **Graphics Controller** | VMSVGA | Enable 3D Acceleration; allocate 128 MB VRAM |
| **Display Server** | X11 (Xfce default) | Wayland blocks synthetic input |
| **Webcam Pass-Through** | Integrated Chicony RGB (`/dev/video2`) | Attach via `Devices -> Webcams` in VirtualBox menu |
| **Audio Controller** | PulseAudio / Intel HD Audio | Bidirectional capture and playback enabled |
| **Network** | NAT | Required only for initial setup / dependencies |

---

## 3. Mandatory Baseline Snapshot Requirement

Before running **ANY** test involving real mouse cursor movement, synthetic clicks, dwell, blink, gaze, or privileged power actions, a clean baseline snapshot **MUST** be created.

### 3.1 Creating the Clean Baseline Snapshot
1. Boot the VM and ensure all dev dependencies are ready.
2. Verify the system is in an idle, clean desktop state with no accessibility engines running.
3. Take a snapshot named `baseline-clean`:
   ```bash
   # From host terminal (replace "AccessOS-Dev" with your VM name):
   VBoxManage snapshot "AccessOS-Dev" take "baseline-clean" --description "Clean idle desktop before input tests"
   ```
4. Verify the snapshot exists:
   ```bash
   VBoxManage snapshot "AccessOS-Dev" list
   ```

---

## 4. Snapshot Restoration (Recovery Procedure)

If a test causes input lockup, synthetic click freeze, cursor trap, or unexpected desktop behavior, **do not attempt complex troubleshooting inside the broken VM**. Immediately restore the baseline snapshot:

```bash
# 1. Force power-off the stuck VM
VBoxManage controlvm "AccessOS-Dev" poweroff

# 2. Restore the clean snapshot
VBoxManage snapshot "AccessOS-Dev" restore "baseline-clean"

# 3. Restart the VM into a guaranteed fresh state
VBoxManage startvm "AccessOS-Dev"
```

---

## 5. VM Test Execution Matrix

Execute the following test cases inside the VirtualBox VM:

### Test Case 1: VM Detection and X11MouseBackend Initialization
- **Goal**: Confirm AccessOS recognizes it is running inside VirtualBox and permits real injection.
- **Command inside VM**:
  ```bash
  cd ~/Projects/AccessOS
  ACCESSOS_ALLOW_REAL_INJECTION=1 PYTHONPATH=. .venv/bin/python3 -c "
  from accessos.engine.mouse_backend import X11MouseBackend
  mouse = X11MouseBackend()
  print('Successfully initialized X11MouseBackend inside VM:', mouse.screen_size)
  mouse.close()
  "
  ```
- **Expected Outcome**: `X11MouseBackend` initializes without `HostSafetyViolationError`.

### Test Case 2: Real Pointer Motion & Boundaries
- **Goal**: Verify head movement drives the physical X11 pointer inside the VM window.
- **Steps**:
  1. Attach host webcam to VM via VirtualBox `Devices -> Webcams`.
  2. Launch AccessOS inside VM:
     ```bash
     cd ~/Projects/AccessOS
     ACCESSOS_ALLOW_REAL_INJECTION=1 PYTHONPATH=. .venv/bin/python3 -m accessos
     ```
  3. Click `📷 Start Tracking` and confirm permission notice.
  4. Move head gently left/right and up/down.
  5. Verify the VM's OS pointer tracks head motion smoothly.
  6. Confirm pointer is clamped to VM display bounds `[0, width-1]` and `[0, height-1]`.

### Test Case 3: Real Dwell-to-Click
- **Goal**: Hover over a dock item or desktop icon and trigger an authentic X11 button 1 click.
- **Steps**:
  1. Hover the cursor over the **Files** dock button.
  2. Hold head steady within the 24px dwell bubble.
  3. Watch the visual progress arc complete.
  4. Verify Thunar File Manager launches.
  5. **Critical Safety Check**: Use the physical mouse to click other items. Verify physical clicks continue working normally!

### Test Case 4: Universal Emergency Stop (<kbd>F12</kbd>)
- **Goal**: Validate that pressing <kbd>F12</kbd> instantly kills all engines and releases all synthetic buttons.
- **Steps**:
  1. While head tracking is actively moving the cursor, press <kbd>F12</kbd>.
  2. Notice camera stops immediately, cursor halts, and audio/toast announces:
     *"EMERGENCY STOP: All control engines halted. Synthetic input released."*
  3. Verify physical keyboard and mouse are fully responsive.

### Test Case 5: Post-Test Cleanup
- Upon completing tests, power off VM and restore `baseline-clean` snapshot to leave no dangling processes or modified settings.
