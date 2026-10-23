# Phase 3.6 Incident & Root-Cause Investigation Report
**System:** Lenovo ThinkPad T480  
**Operating System:** Zorin OS 18.1 (Ubuntu 24.04 Noble base)  
**Desktop Environment:** GNOME Shell 46.0 on Wayland with XWayland (`DISPLAY=:0`)  
**Repository Branch/Commit:** `main` @ `8eefcc9`  
**Date:** 2026-10-24  

---

## 1. Executive Summary

During direct host testing, physical mouse clicks repeatedly became unresponsive, requiring AccessOS to be terminated and the host system rebooted. This investigation was conducted under Phase 3.6 to identify the exact mechanisms involved, audit every input path in the codebase, and implement provable architectural safeguards preventing physical input lockup during host development.

---

## 2. Environment & Forensic Discoveries

Inspection of the host system revealed several critical environmental factors:

1. **Wayland / XWayland Hybrid Session:**
   - `XDG_SESSION_TYPE`: `wayland`
   - `XDG_CURRENT_DESKTOP`: `zorin:GNOME` (GNOME Shell 46.0 / Mutter)
   - `DISPLAY`: `:0` (provided by XWayland)
   - *Impact*: Previously, `check_session_supported()` returned `True` because `DISPLAY` was set, treating XWayland as a native X11 server.

2. **XWayland Synthetic Button Desynchronization:**
   - Under Mutter (GNOME Shell's Wayland compositor), XWayland processes synthetic XTest events (`XTestFakeButtonEvent`).
   - If an XTest button-down event (Button 1) is injected without an atomic, perfectly paired button-up event (or if the application process terminates or is killed while a synthetic button is registered), the XWayland server and Mutter compositor treat mouse button 1 as permanently held down.
   - When a mouse button is held down at the compositor level, physical mouse motion continues to track, but physical clicks on windows, desktop icons, or panels fail because the compositor believes an active window grab / drag-and-drop operation is underway.

3. **Eager Imports & Test Execution on Host Display:**
   - In earlier iterations, `accessos.engine` eagerly imported `mouse_backend.py`, which imported `ctypes` and `ctypes.util` at module level.
   - In `tests/test_x11_mouse.py`, unit tests used `X11Mouse(allow_host_override=True)` without mocking `ctypes.CDLL`. When running `pytest`, real calls to `XOpenDisplay(None)` and `XTestFakeButtonEvent(display, btn, 0, 0)` were dispatched to the host's live `:0` XWayland server.

4. **Multi-Instance / Stale Process Risks:**
   - Prior to Phase 3.6, AccessOS lacked a single-instance lock file or PID tracking mechanism. If a previous instance hung or was launched twice, multiple processes competed for camera and input state.

---

## 3. Comprehensive Codebase Input Audit

Every source file, script, configuration, and subprocess call in the repository was audited for input injection, grabbing, and native access APIs:

| Component / File | Mechanism | Line / Pattern | Reachable in Host Safe Mode? | Safety Mitigation |
| :--- | :--- | :--- | :--- | :--- |
| `accessos/engine/x11_mouse.py` | `libXtst` / `XTestFakeButtonEvent` | Synthetic mouse button press/release | **NO** | Isolated in VM-only file. Raises `HostSafetyViolationError` on host. Requires VM config file. |
| `accessos/engine/x11_mouse.py` | `libXtst` / `XTestFakeMotionEvent` | Synthetic cursor movement | **NO** | Blocked on bare-metal host. `ctypes` loaded dynamically only inside VM. |
| `accessos/engine/x11_mouse.py` | `libX11` / `XOpenDisplay`, `XQueryPointer` | X11 display query | **NO** | Blocked on bare-metal host. |
| `accessos/engine/mouse_backend.py` | `ctypes` / `ctypes.util` | Module-level C library loading | **NO** | Completely removed. `mouse_backend.py` now has 0 ctypes imports. |
| `accessos/engine/mouse_backend.py` | `DryRunMouseBackend` | Pure in-memory coordinates | **YES** | Safe. Pure Python data structure; updates only local coordinates. |
| `accessos/engine/head_pointer.py` | `HeadPointerEngine` | MediaPipe + DwellClicker | **NO in host-safe** | In default `host-safe` profile, engine is NOT instantiated (`self._engine = None`). |
| `accessos/engine/head_pointer.py` | `DwellClicker` | Automatic timer click | **NO in host-safe & preview** | In `camera-preview` profile, `self._dwell = None` (strictly disabled). |
| `accessos/home_screen.py` | `Gtk.Widget.grab_focus()` | GTK widget keyboard focus | **YES** | Safe. Standard GTK internal widget focus (dock buttons); does not grab OS pointer. |
| `accessos/power_menu.py` | `Gtk.Dialog(modal=True)` | GTK modal window | **YES** | Safe. Standard GTK dialog modal; closed on Esc or button click. |
| `accessos/app_launcher.py` | `subprocess.Popen` | Launching external apps | **YES** | Safe. Uses strict allow-list, `shell=False`, `start_new_session=True`. |
| `accessos/settings/system_control.py` | `subprocess.run` (amixer, nmcli) | Volume & Wi-Fi status | **YES** | Safe. Read-only system queries via standard CLI tools with timeouts. |

---

## 4. Architectural Safety Hardening (Phase 3.6)

To make host development provably unable to affect system input, the following architecture was implemented:

### 1. Three Isolated Launch Profiles
- **`host-safe` (Default)**: Starts ONLY the UI desktop window.
  - Zero camera tracking engine initialized (`self._engine = None`).
  - Zero mouse backend loaded (`self._mouse_backend = None`).
  - Real input injection is physically impossible.
- **`camera-preview`**: Explicit camera preview mode (`--profile camera-preview`).
  - Opens webcam and displays face tracking reticle locally in AccessOS window.
  - Dwell clicker is strictly disabled (`self._dwell = None`).
  - Pointer backend is forced to in-memory `DryRunMouseBackend` (`is_real_injection = False`).
  - Zero OS synthetic events sent.
- **`vm-real`**: Reserved strictly for VirtualBox or target Linux Mint ISO (`--profile vm-real`).
  - Refuses execution on bare-metal host with `HostSafetyViolationError`.
  - Requires hypervisor detection (`is_running_in_vm() == True`).
  - Requires explicit VM configuration file (`config/vm_real_injection.toml`).
  - Requires verified X11 display.

### 2. Elimination of Interactive Host Bypasses
- Removed `ACCESSOS_FORCE_REAL_MOUSE_UNSAFE` from interactive application entry points.
- Bare-metal host hardware detection is unconditional and cannot be bypassed from CLI or environment flags.

### 3. Decoupling of Native Libraries
- `accessos/engine/mouse_backend.py` is 100% free of `ctypes`, `ctypes.util`, or native libraries.
- `X11MouseBackend` is isolated in `accessos/engine/x11_mouse.py` and imports `ctypes` dynamically only inside `__init__` after VM authorization passes.

### 4. Process Exclusivity & Single-Instance Lock
- Implemented `SingleInstanceLock` utilizing `~/.cache/accessos/accessos.pid` and kernel `fcntl.flock`.
- On startup, inspects running processes:
  - If another instance is running, refuses to launch with clear diagnostic recovery instructions.
  - If a stale PID file exists from a previous crash or reboot, automatically cleans it up.
  - Automatically cleans up lock on all exit paths (normal exit, exception, `SIGTERM`, `SIGINT`, `atexit`).

### 5. Mocked Unit Tests
- Rewrote `tests/test_x11_mouse.py` to mock `ctypes.CDLL` and `ctypes.util.find_library`.
- Unit tests run under `pytest` never call `XOpenDisplay` or `XTestFakeButtonEvent` on the host display.

---

## 5. Automated Verification Evidence

The full test suite was executed:
- **Total Tests Passed:** 99
- **AST Static Audit:** Passed (zero forbidden input libraries imported by host-safe modules).
- **Profile Enforcement:** Passed (host-safe profile initializes zero engine; camera-preview profile initializes zero dwell).
- **Lock Enforcement:** Passed (single-instance exclusivity and stale PID recovery verified).
- **VM Block Enforcement:** Passed (`./scripts/run_accessos.sh --profile vm-real` exits with code 1 on host).
