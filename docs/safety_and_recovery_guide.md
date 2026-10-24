# AccessOS Input Safety & System Recovery Guide

AccessOS is built with strict safety guarantees to ensure that physical keyboard and mouse controls remain responsive at all times and that users cannot be locked out of their system.

---

## 1. Safety Profiles & Isolation Model

AccessOS enforces three strictly separated execution profiles based on the detected hardware environment:

| Profile | Target Environment | Camera Tracking | OS Mouse Injection | Dwell Clicking |
|---|---|:---:|:---:|:---:|
| **`host-safe`** *(Default)* | Physical host machine | ❌ Disabled | ❌ Zero injection (Virtual overlay only) | ❌ Disabled |
| **`camera-preview`** | Physical host machine | ✔️ Preview Only | ❌ Zero injection (Virtual overlay only) | ❌ Disabled |
| **`vm-real`** | Verified VM / Live Boot USB | ✔️ Full Tracking | ✔️ X11 XTest Injection | ✔️ Enabled |

### Invariants:
1. **Host Safety**: Bare-metal physical host systems unconditionally reject real mouse injection with a `HostSafetyViolationError`.
2. **VirtualCursorOverlay**: In host mode, pointer motion and dwell indicators render exclusively inside the local AccessOS window as a transparent, non-grabbing GTK overlay. Physical mouse clicks pass through unimpeded.

---

## 2. Emergency Controls & Fail-Safes

### Universal Emergency Kill Switch: <kbd>F12</kbd>
Pressing <kbd>F12</kbd> at any time triggers the universal emergency stop:
- Immediately cancels any active dwell timers.
- Resets all intentional blink detectors.
- Halts and joins background camera worker threads.
- Releases all synthetic mouse buttons and keys.
- Safely transitions tracking state to `STOPPED`.

### Idempotent Safety Pause: <kbd>Esc</kbd>
Pressing <kbd>Esc</kbd> pauses pointer and selection actions immediately.
> **Idempotency Guarantee**: Pressing <kbd>Esc</kbd> repeatedly will **never** toggle or accidentally resume pointer actions. It only pauses.

### Explicit Resume: <kbd>R</kbd> or On-Screen Button
To resume pointer control after a pause, the user must explicitly:
- Press the <kbd>R</kbd> key, or
- Click the on-screen **Resume** button, or
- Speak the approved voice command `"resume control"`.

### Tracking Loss Protection
If the camera stream fails or the user moves outside the camera frame:
- The pointer is immediately frozen at its last known coordinates.
- All synthetic buttons are released.
- Dwell progress is reset to 0%.
- Visual status switches to `🟡 TRACKING LOST · KEYBOARD/MOUSE ACTIVE`.
- Spoken feedback informs the user that manual controls are active.

---

## 3. Keyboard Recovery & Emergency Terminal

Even if the visual environment or dock freezes:
- <kbd>Ctrl + Alt + T</kbd> launches `xfce4-terminal` directly from the Xfce keybinding daemon.
- <kbd>Alt + F4</kbd> closes the active window.
- <kbd>Ctrl + Alt + F1</kbd> through <kbd>F6</kbd> opens standard Linux virtual console TTYs for root recovery.

### Stopping AccessOS from the Command Line:
If needed, AccessOS can be cleanly terminated using:
```bash
pkill -f "python.*accessos"
```
Or by running the provided script:
```bash
./scripts/stop_accessos.sh
```
