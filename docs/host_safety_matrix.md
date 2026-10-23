# AccessOS Host Safety Matrix & Manual Verification Guide

## 1. Safety Profiles Matrix

| Dimension | `host-safe` (DEFAULT) | `camera-preview` | `vm-real` |
| :--- | :--- | :--- | :--- |
| **Target Environment** | Bare-metal host hardware | Bare-metal host hardware | VirtualBox / Target Live ISO |
| **Launch Command** | `./scripts/run_accessos.sh` | `./scripts/run_accessos.sh --profile camera-preview` | `./scripts/run_accessos.sh --profile vm-real` |
| **UI Presented** | Full desktop dock & settings | Full desktop dock & settings | Full desktop dock & settings |
| **Vision Engine** | **DISABLED** (`None`) | Active (local preview) | Active (full tracking) |
| **Dwell Clicker** | **DISABLED** (`None`) | **DISABLED** (`None`) | Active |
| **Mouse Backend** | **DISABLED** (`None`) | `DryRunMouseBackend` (In-memory) | `X11MouseBackend` (libXtst) |
| **Real OS Injection** | **IMPOSSIBLE** | **IMPOSSIBLE** | Active (Inside VM only) |
| **Host Mouse Affected?** | **NO (0% impact)** | **NO (0% impact)** | N/A (Runs inside VM) |
| **Host Execution** | **PERMITTED** | **PERMITTED** | **BLOCKED** (`HostSafetyViolationError`) |
| **UI Safety Badge** | `🛡️ HOST SAFE PROFILE — UI ONLY` | `📷 HOST CAMERA PREVIEW ONLY` | `⚠️ VM REAL INJECTION ACTIVE` |

---

## 2. Safe Launch Commands

### Standard Host Safe Mode (Default)
Starts the AccessOS UI only. Vision tracking and pointer control backends are completely dormant:
```bash
./scripts/run_accessos.sh
```

### Host Camera Preview Only Mode
Opens the verified RGB webcam to display face tracking reticle and FPS/latency metrics locally. Dwell clicking and pointer injection are completely disabled:
```bash
./scripts/run_accessos.sh --profile camera-preview
```

### Stop Running Instance
Gracefully terminates any active AccessOS process and removes PID lock:
```bash
./scripts/stop_accessos.sh
```

---

## 3. Recovery Guide

If AccessOS ever crashes or reports an active instance lock:

1. **Check for Running Processes:**
   ```bash
   ./scripts/stop_accessos.sh
   ```

2. **Inspect Process Table:**
   ```bash
   pgrep -f "accessos"
   ```
   If a PID is found, terminate it:
   ```bash
   kill -9 <PID>
   ```

3. **Clean Stale Lock File (if needed):**
   ```bash
   rm -f ~/.cache/accessos/accessos.pid
   ```

4. **Verify Physical Mouse:**
   Physical mouse left-click, right-click, and cursor motion remain functional at all times.

---

## 4. Manual Verification Protocol

### Test Step 1: Host-Safe UI Mode (10 Minutes)
1. Run `./scripts/run_accessos.sh` on the host machine.
2. Verify the green safety badge is displayed: `🛡️ HOST SAFE PROFILE — UI ONLY (NO CAMERA / NO INJECTION)`.
3. Verify the bottom telemetry bar displays build information: `v0.4.0 (<commit>) · PID <pid> · host-safe`.
4. Perform continuous physical mouse interactions for 10 minutes:
   - Move physical cursor across all desktop areas.
   - Left-click dock icons (Browser, Files, Terminal, Settings, Images, Videos).
   - Right-click and middle-click outside the window.
   - Scroll web pages or file lists.
   - Switch between applications using Alt-Tab or desktop panel.
   - Close and reopen windows.
5. Verify that physical mouse clicks and responsiveness never degrade.
6. Close AccessOS via the window close button or Ctrl-C.

### Test Step 2: Host Camera-Preview-Only Mode (10 Minutes)
1. Run `./scripts/run_accessos.sh --profile camera-preview`.
2. Verify the amber safety badge is displayed: `📷 HOST CAMERA PREVIEW ONLY — NO DWELL / NO INPUT`.
3. Click "📷 Start Preview" and confirm the camera permission dialog.
4. Verify the camera preview reticle and telemetry (FPS, loop latency) update as your head moves.
5. Incline head and hover over dock buttons for several seconds:
   - **Verify:** Zero dwell accumulation ring appears.
   - **Verify:** Zero synthetic clicks are triggered.
   - **Verify:** Physical mouse cursor does NOT jump or move to head position.
6. Test physical mouse input for 10 minutes:
   - Click outside the AccessOS window.
   - Click inside the AccessOS window.
   - Verify zero interruption to physical clicks.
7. Click "⏹ Stop Preview".
8. Close AccessOS.

### Test Step 3: VirtualBox Real Injection (VM Only)
Only after Steps 1 and 2 pass on the host:
1. Boot a fresh VirtualBox snapshot of Linux Mint 22.3 Xfce.
2. Inside the VM, run `./scripts/run_accessos.sh --profile vm-real`.
3. Test real head-pointer tracking, dwell clicking, and Esc emergency pause inside the VM.
