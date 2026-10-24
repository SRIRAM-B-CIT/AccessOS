## [Phase 3.6] - 2026-10-24 - Critical Host Input-Safety Hardening & Profile Isolation

### Forensic Investigation & Findings
- **Wayland / XWayland Event Desynchronization**: The host environment runs Zorin OS 18.1 on GNOME Shell 46 with Wayland and XWayland on `DISPLAY=:0`. When synthetic `XTestFakeButtonEvent` calls were dispatched to XWayland (such as during unmocked unit test runs in Phase 3/3.5), button-down events without immediate pairing or during desynchronized compositor grabs caused Mutter to treat Button 1 as permanently held down, causing physical mouse clicks to stop functioning.
- **Eager Native Imports**: Previous module structure eagerly imported `ctypes` and `X11MouseBackend` whenever `accessos.engine` was imported, even during host safe runs.
- **Unit Test Isolation Breach**: `tests/test_x11_mouse.py` previously instantiated live X11 displays and dispatched real `XTestFakeButtonEvent` releases during test execution.
- **Process Contention**: Lack of PID exclusivity allowed multiple instances to compete or linger.

### Hardened Architecture & Safeguards
- **Three Strictly Isolated Launch Profiles**:
  - `host-safe` (Default): Starts ONLY the GTK desktop window. Vision tracking and mouse backend are completely disabled (`None`). 0% chance of input interference.
  - `camera-preview` (`--profile camera-preview`): Activates webcam for local reticle rendering only. Dwell clicker is strictly disabled (`None`). Uses virtual `DryRunMouseBackend` with zero OS injection.
  - `vm-real` (`--profile vm-real`): Reserved strictly for verified VirtualBox / Live ISO sessions. Unconditionally blocked on physical host systems via `HostSafetyViolationError`.
- **Single-Instance Exclusivity Lock**:
  - Implemented `SingleInstanceLock` using `~/.cache/accessos/accessos.pid` and kernel `fcntl.flock`.
  - Refuses secondary launches with actionable diagnostic recovery instructions.
  - Automatically recovers from stale PID files after reboot or crash.
  - Guarantees lock file removal on normal exit, exception, SIGTERM, SIGINT, and atexit.
- **Permanent Removal of Host Bypasses**:
  - Completely removed `ACCESSOS_FORCE_REAL_MOUSE_UNSAFE` from interactive app logic.
  - Real pointer injection now requires verified hypervisor detection (`is_running_in_vm()`) AND an explicit VM configuration file (`config/vm_real_injection.toml`).
- **Complete Decoupling of Native Libraries**:
  - `accessos/engine/mouse_backend.py` is 100% free of `ctypes` and native dynamic libraries.
  - `accessos/engine/x11_mouse.py` dynamically loads `ctypes` only inside `X11MouseBackend.__init__` after VM verification passes.
- **Mocked Unit Test Safety**:
  - `tests/test_x11_mouse.py` now strictly mocks `ctypes.CDLL` and `find_library`. No native X11 or XTest calls reach the host display during `pytest`.
- **Static AST Safety Audit**:
  - Added `tests/test_safety_audit.py` which parses AST of all host-safe files and verifies zero imports of `ctypes`, `XTest`, `libXtst`, `xdotool`, `pyautogui`, `pynput`, etc.
- **Build & Diagnostic Transparency**:
  - Added diagnostic banner on launch printing Git commit SHA, working directory, Python executable, package path, and PID.
  - Added visible build version and short Git commit identifier in the desktop telemetry bar.
  - Enforced virtual environment Python (`.venv/bin/python`) in `scripts/run_accessos.sh`.

## [Phase 3.5] - 2026-10-21 - Input-Safety Redesign & Host Isolation

### Incident Report & Root Cause
- **Incident**: During bare-metal host testing of Phase 3 on the ThinkPad T480, physical mouse clicks froze and stopped responding to hardware input. The system had to be recovered by killing the AccessOS process and rebooting the machine.
- **Root Cause**: Synthetic mouse button press/release events injected via `libXtst` (`XTestFakeButtonEvent`) directly into the host's root X11 display window interfered with the host desktop's pointer grab and physical event dispatch queue.

### Architecture Redesign & Safety Guarantees
- **Separated Mouse Backends**:
  - `DryRunMouseBackend`: Pure in-memory coordinate and button state tracking. Completely free of XTest, X11, ctypes, `xdotool`, `pyautogui`, or any OS input injection. Used as the mandatory default on bare-metal host systems.
  - `VirtualCursorOverlay`: Transparent GTK Cairo drawing overlay with event pass-through (`gtk_overlay_set_overlay_pass_through`). Renders a distinct cyan reticle cursor, crosshairs, radial dwell progress arc, and expanding ripple animations strictly inside the AccessOS window.
  - `X11MouseBackend`: Retained strictly for VirtualBox VM testing.
- **Host Hardware Lockout & Safe Defaults**:
  - `can_use_real_mouse_injection()` inspects `systemd-detect-virt` and DMI firmware tables (`sys_vendor`, `product_name`).
  - AccessOS defaults to `DryRunMouseBackend` on host hardware.
  - Instantiating `X11MouseBackend` on bare metal unconditionally raises `HostSafetyViolationError`, refusing to start with an actionable safety error message.
  - Prominent UI safety badge displayed in the top-right header: `[🛡️ SAFE DRY-RUN — REAL MOUSE UNAFFECTED]`.
- **Full Cleanup & Button Release Guarantees**:
  - Added `release_all_buttons()` to ensure all synthetic mouse buttons are released.
  - On Pause, Stop Tracking, Tracking Loss, Camera Failure, Worker-Thread Failure, GTK Window Close, SIGINT, SIGTERM, Uncaught Exception, and Normal Exit:
    1. Dwell progress is canceled immediately;
    2. All synthetic mouse buttons are explicitly released;
    3. Pointer injection is halted;
    4. Camera device is cleanly closed;
    5. Safe dry-run state is restored.
- **Keyboard-Only Universal Emergency Stop**:
  - Bound <kbd>F12</kbd> (and <kbd>Ctrl+Alt+S</kbd>) to instantly shut down every AccessOS engine and release all resources without requiring mouse interaction.
  - Preserved idempotent pause behavior on <kbd>Esc</kbd> (pauses only; never toggles or resumes).
- **VirtualBox-Only Real Input Testing**:
  - Created comprehensive VM test plan and clean baseline snapshot procedures in `docs/virtualbox_test_plan.md`.
  - Prohibited real input injection tests on the host development machine.
- **Regression Test Suite**:
  - Added 11 automated safety tests in `tests/test_input_safety.py` covering dry-run isolation, bare-metal blocking, cleanup paths on failure, virtual cursor overlay rendering, and emergency stop shortcuts (76/76 total repository tests passing).


## [Phase 4] - 2026-10-21 - Offline Voice Control & Speech Synthesis

### Added
- **Offline Speech Recognition (Vosk)**:
  - Streaming Kaldi recognizer running locally on 16kHz audio from ALSA `arecord`.
  - Grammar restriction constrained strictly to approved command phrases.
  - Zero disk writing or cloud transmission of voice data or transcripts.
  - Disabled by default; requires explicit user consent dialog before activating microphone.
- **Offline Speech Synthesis (Piper TTS)**:
  - Low-latency neural speech synthesis via ONNX runtime model `en_US-lessac-low.onnx`.
  - In-memory WAV synthesis streamed directly to ALSA `aplay -q`.
  - Asynchronous background worker queue prevents UI thread blocking.
- **Strict Command Allowlisting**:
  - Direct actions: `open browser`, `files`, `terminal`, `settings`, `images`, `videos`, `go home`, `pause control`, `resume control`, `stop tracking`, `read status`, `help`, `volume up`, `volume down`.
  - Defense-in-depth prohibition of dangerous tokens (`sudo`, `rm`, `bash`, `delete`, `install`, etc.).
  - Recognized speech is never passed to shell or terminal.
- **Spoken Confirmation State Machine**:
  - `restart` and `shutdown` voice commands enter `AWAITING_CONFIRMATION` state.
  - Spoken confirmation required (`confirm`/`yes`); abort on `cancel`/`no` or 10-second timeout.
- **Voice HUD & Keyboard Mute**:
  - Visual status pill indicating Active, Muted, Awaiting Confirmation, Error, or Off.
  - Auto-clearing command toast displaying recognized actions.
  - Keyboard shortcut <kbd>M</kbd> toggles microphone mute instantly.
- **Test Suite & Benchmarks**:
  - 13 new unit and integration tests covering allowlists, token rejections, mic failure, confirmation state machine, and HUD styling (63 total passing tests).
  - Automated benchmark suite `scripts/benchmark_phase4.py` measuring Piper synthesis speed (0.053x RTF, 183ms latency), Vosk decoding (0% CPU idle, ~1.5ms grammar init), and process memory (~340MB peak).

# Changelog

All notable changes to AccessOS are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.0.0] - Standalone Bootable AccessOS ISO & Live USB Release

### Added
- **Reproducible ISO Build Pipeline** ([1;34m[AccessOS Build][0m Starting AccessOS ISO Build Process...
[1;34m[AccessOS Build][0m ISO root directory already present, skipping unpack.
[1;34m[AccessOS Build][0m SquashFS root already unpacked, proceeding with customizations.
[1;34m[AccessOS Build][0m Applying AccessOS system customizations...
[1;34m[AccessOS Build][0m Installing AccessOS application to /opt/accessos...
[1;34m[AccessOS Build][0m Installing /usr/local/bin/accessos launcher wrapper...
[1;34m[AccessOS Build][0m Configuring AccessOS autostart for live user session...
[1;34m[AccessOS Build][0m Pruning non-essential desktop launchers (LibreOffice, games, mail, chat)...
[1;34m[AccessOS Build][0m Configuring Xfce desktop to disable desktop clutter...
[1;34m[AccessOS Build][0m Applying AccessOS branding and wallpapers...
[1;34m[AccessOS Build][0m Updating GRUB and ISOLINUX bootloader menus...
[1;34m[AccessOS Build][0m Repacking casper/filesystem.squashfs using xz compression...
Parallel mksquashfs: Using 8 processors
Creating 4.0 filesystem on /mnt/1208154E081531E9/AccessOS/iso_build/iso_root/casper/filesystem.squashfs, block size 1048576.

[/                                                             ]    0/1084   0%
[/                                                         ]   2200/319370   0%
[/                                                         ]   4200/319370   1%
[\                                                         ]   5500/319370   1%
[\                                                         ]   5600/319370   1%
[====\                                                     ]  24000/319370   7%
[=====-                                                    ]  33100/319370  10%
[======/                                                   ]  35700/319370  11%
[======\                                                   ]  38600/319370  12%
[=======\                                                  ]  41800/319370  13%
[=============|                                            ]  73100/319370  22%
[=============/                                            ]  73500/319370  23%
[====================================-                     ] 202200/319370  63%
[===========================================/              ] 244400/319370  76%
[==============================================\           ] 262600/319370  82%
[=====================================================-    ] 299100/319370  93%
[=======================================================\  ] 311000/319370  97%
[=========================================================\] 319370/319370 100%

Exportable Squashfs 4.0 filesystem, xz compressed, data block size 1048576
	compressed data, compressed metadata, compressed fragments,
	compressed xattrs, compressed ids
	duplicates are removed
Filesystem size 2601383.97 Kbytes (2540.41 Mbytes)
	33.69% of uncompressed filesystem size (7721378.79 Kbytes)
Inode table size 3997828 bytes (3904.13 Kbytes)
	21.98% of uncompressed inode table size (18190289 bytes)
Directory table size 4875694 bytes (4761.42 Kbytes)
	35.58% of uncompressed directory table size (13704274 bytes)
Number of duplicate files found 59044
Number of inodes 511109
Number of files 325521
Number of fragments 3135
Number of symbolic links 162243
Number of device nodes 0
Number of fifo nodes 0
Number of socket nodes 0
Number of directories 23345
Number of hard-links 21
Number of ids (unique uids + gids) 1
Number of uids 1
	root (0)
Number of gids 1
	root (0)
[1;34m[AccessOS Build][0m Updating filesystem.size...
[1;34m[AccessOS Build][0m Recalculating MD5 checksums for ISO files...
[1;34m[AccessOS Build][0m Mastering bootable hybrid AccessOS.iso...
[1;34m[AccessOS Build][0m Computing SHA256 checksum for AccessOS.iso...
[1;34m[AccessOS Build][0m ======================================================================
[1;34m[AccessOS Build][0m AccessOS ISO Build COMPLETED SUCCESSFULLY!
[1;34m[AccessOS Build][0m Output ISO:  /mnt/1208154E081531E9/AccessOS/AccessOS.iso (3.0G)
[1;34m[AccessOS Build][0m SHA256:      0b8da8e68fe307dc4343217536602aa10e38c7fc4ca26e657b1a067ff70ee9ea
[1;34m[AccessOS Build][0m Checksum:    /mnt/1208154E081531E9/AccessOS/AccessOS.iso.sha256
[1;34m[AccessOS Build][0m ======================================================================):
  - Builds standalone hybrid bootable  from Linux Mint 22.3 Xfce base.
  - 100% unprivileged execution on host; zero modification to host bootloader, host partitions, or installed packages.
  - Prunes all non-essential applications (LibreOffice, Thunderbird, HexChat, Solitaire, software managers).
  - Configures LightDM live autologin, Xfce desktop decluttering (disables desktop icons), and autostarting AccessOS in fullscreen.
  - Integrates  launcher wrapper and  installation.
  - Full AccessOS branding in , , GRUB, and ISOLINUX bootloaders.
- **Accessible Document Reader** ():
  - Multi-format text extraction engine (, , ,  via pdftotext,  via zip XML,  via zip XML,  via zip XHTML, image document notice).
  - Synchronized sentence-level speech playback powered by Piper TTS with active sentence highlighting.
  - Keyboard accessibility (<kbd>Ctrl+R</kbd> open, <kbd>Space</kbd> play/pause, <kbd>Left/Right</kbd> navigate, <kbd>S</kbd> stop, <kbd>O</kbd> open file, <kbd>Esc</kbd> close).
  - Hands-free voice commands allowlisted for all reading operations.
- **First-Boot Accessible Onboarding Wizard** ():
  - Step-by-step accessible first-run configuration with spoken voice guidance (Piper).
  - Modality selector (Keyboard/Mouse, Voice Only, Head Pointer + Dwell, Head Pointer + Blink, Combined).
  - Explicit camera and microphone opt-in consent switches.
  - High-contrast visual and font size adjustments.
  - Can be re-launched at any time from Settings.
- **Flashing & User Guides**:
  - : Detailed instructions for safe flashing via , Raspberry Pi Imager, and BalenaEtcher with device identification warnings.
  - : Complete guide covering all six dock applications, input modalities, and document reading.
  - : In-depth documentation of safety profile isolation, idempotent pause, and emergency terminal recovery.
  - : Step-by-step verification checklist for VM and live USB testing.

## [0.6.0] - Deliberate Blink Detection & Experimental Eye Gaze Tracking

### Added
- **Deliberate Blink Selection Engine** ():
  - Real-time Eye Aspect Ratio (EAR) computation from 6 facial landmarks per eye.
  - Distinguishes intentional selection blinks (200ms–800ms) from natural involuntary blinks (80ms–150ms).
  - Refractory cooldown period (600ms) to prevent accidental repeated clicks.
  - Distinctive cyan ripple animation on VirtualCursorOverlay upon blink trigger.
- **Experimental 2D Eye Gaze Tracker** ():
  - Extracts iris-to-canthus normalized pupil position ratios.
  - Guided 5-point calibration workflow (Center, Top-Left, Top-Right, Bottom-Left, Bottom-Right) with visual bullseye target rendering.
  - One-Euro smoothing filter for gaze jitter reduction.
  - Documented accuracy limitation disclaimer for standard integrated 720p webcams.
- **Audio Feedback Loop Suppression**:
  - TTS speech state tracking (, ).
  - Active suppression of microphone input while Piper is speaking, with 500ms post-speech cooldown.
  - Duplicate voice command debouncing (1.5s cooldown).

## [0.5.0] - Input-Safety Redesign, Profile Isolation & Exclusivity Lock

### Added
- **Strict Profile Architecture** ():
  -  (Default): Bare-metal host safe, zero OS injection, purely in-memory virtual cursor.
  - : Camera preview only, dwell clicking and OS injection disabled.
  - : Permitted exclusively inside verified hypervisor virtual machines or live-boot sessions.
- **Single-Instance Exclusivity Lock** ():
  - POSIX  single-instance lock preventing multiple concurrent AccessOS processes.
- **Isolated X11 Mouse Backend** ():
  - Purely modular X11 injection backend isolated from base mouse classes; raises  on host hardware.
- **Transparent Virtual Cursor Overlay** ():
  - High-contrast visual cursor, dwell ring, and click pulse rendered strictly inside the AccessOS window.

---

## [1.0.0] - Standalone Bootable AccessOS ISO & Live USB Release

### Added
- **Reproducible ISO Build Pipeline** (`scripts/build_iso.sh`):
  - Builds standalone hybrid bootable `AccessOS.iso` from Linux Mint 22.3 Xfce base.
  - 100% unprivileged execution on host; zero modification to host bootloader, host partitions, or installed packages.
  - Prunes all non-essential applications (LibreOffice, Thunderbird, HexChat, Solitaire, software managers).
  - Configures LightDM live autologin, Xfce desktop decluttering (disables desktop icons), and autostarting AccessOS in fullscreen.
  - Integrates `/usr/local/bin/accessos` launcher wrapper and `/opt/accessos` installation.
  - Full AccessOS branding in `/etc/os-release`, `/etc/issue`, GRUB, and ISOLINUX bootloaders.
- **Accessible Document Reader** (`accessos.reader`):
  - Multi-format text extraction engine (`.txt`, `.md`, `.html`, `.pdf` via pdftotext, `.docx` via zip XML, `.odt` via zip XML, `.epub` via zip XHTML, image document notice).
  - Synchronized sentence-level speech playback powered by Piper TTS with active sentence highlighting.
  - Keyboard accessibility (<kbd>Ctrl+R</kbd> open, <kbd>Space</kbd> play/pause, <kbd>Left/Right</kbd> navigate, <kbd>S</kbd> stop, <kbd>O</kbd> open file, <kbd>Esc</kbd> close).
  - Hands-free voice commands allowlisted for all reading operations.
- **First-Boot Accessible Onboarding Wizard** (`accessos.onboarding.OnboardingWizard`):
  - Step-by-step accessible first-run configuration with spoken voice guidance (Piper).
  - Modality selector (Keyboard/Mouse, Voice Only, Head Pointer + Dwell, Head Pointer + Blink, Combined).
  - Explicit camera and microphone opt-in consent switches.
  - High-contrast visual and font size adjustments.
  - Can be re-launched at any time from Settings.
- **Flashing & User Guides**:
  - `docs/usb_flashing_guide.md`: Detailed instructions for safe flashing via `dd`, Raspberry Pi Imager, and BalenaEtcher with device identification warnings.
  - `docs/user_guide.md`: Complete guide covering all six dock applications, input modalities, and document reading.
  - `docs/safety_and_recovery_guide.md`: In-depth documentation of safety profile isolation, idempotent pause, and emergency terminal recovery.
  - `docs/testing_checklist.md`: Step-by-step verification checklist for VM and live USB testing.

## [0.6.0] - Deliberate Blink Detection & Experimental Eye Gaze Tracking

### Added
- **Deliberate Blink Selection Engine** (`accessos.engine.BlinkDetector`):
  - Real-time Eye Aspect Ratio (EAR) computation from 6 facial landmarks per eye.
  - Distinguishes intentional selection blinks (200ms–800ms) from natural involuntary blinks (80ms–150ms).
  - Refractory cooldown period (600ms) to prevent accidental repeated clicks.
  - Distinctive cyan ripple animation on VirtualCursorOverlay upon blink trigger.
- **Experimental 2D Eye Gaze Tracker** (`accessos.engine.GazeTracker`):
  - Extracts iris-to-canthus normalized pupil position ratios.
  - Guided 5-point calibration workflow (Center, Top-Left, Top-Right, Bottom-Left, Bottom-Right) with visual bullseye target rendering.
  - One-Euro smoothing filter for gaze jitter reduction.
  - Documented accuracy limitation disclaimer for standard integrated 720p webcams.
- **Audio Feedback Loop Suppression**:
  - TTS speech state tracking (`is_speaking`, `last_speech_ended_time`).
  - Active suppression of microphone input while Piper is speaking, with 500ms post-speech cooldown.
  - Duplicate voice command debouncing (1.5s cooldown).

## [0.5.0] - Input-Safety Redesign, Profile Isolation & Exclusivity Lock

### Added
- **Strict Profile Architecture** (`accessos.utils.LaunchProfile`):
  - `host-safe` (Default): Bare-metal host safe, zero OS injection, purely in-memory virtual cursor.
  - `camera-preview`: Camera preview only, dwell clicking and OS injection disabled.
  - `vm-real`: Permitted exclusively inside verified hypervisor virtual machines or live-boot sessions.
- **Single-Instance Exclusivity Lock** (`accessos.utils.SingleInstanceLock`):
  - POSIX `fcntl.flock` single-instance lock preventing multiple concurrent AccessOS processes.
- **Isolated X11 Mouse Backend** (`accessos.engine.x11_mouse.X11MouseBackend`):
  - Purely modular X11 injection backend isolated from base mouse classes; raises `HostSafetyViolationError` on host hardware.
- **Transparent Virtual Cursor Overlay** (`accessos.engine.VirtualCursorOverlay`):
  - High-contrast visual cursor, dwell ring, and click pulse rendered strictly inside the AccessOS window.

---

## [0.3.0] - Phase 3: Computer Vision Head Pointer & Dwell Selection

### Safety & Verification Corrections (Phase 3 Post-Review)
- **Idempotent Emergency Pause**: <kbd>Esc</kbd> is now strictly idempotent — pressing <kbd>Esc</kbd> always pauses accessibility control and never toggles or resumes it. Resuming control explicitly requires the **Resume** button, the <kbd>R</kbd> shortcut, or an approved Phase 4 voice command.
- **Accurate Latency Terminology**: Corrected performance reports to specify **19.2 ms vision-processing loop latency** (frame acquisition, RGB conversion, MediaPipe landmark detection, and filter computation), clarifying that this is not end-to-end sensor-to-photon latency.
- **X11 Session Validation & Wayland Refusal**: Added explicit session detection (`check_session_supported()`) and `UnsupportedSessionError`. AccessOS safely refuses to start pointer injection on pure Wayland sessions with an actionable guidance message, aligning with Linux Mint Xfce's native X11 architecture.
- **Automated Tests Expanded**: Added automated tests for idempotent pause behavior, explicit resume, and graceful refusal of pointer injection on non-X11 sessions (50/50 tests passing).

### Added
- **Head Pointer Vision Engine** (`accessos.engine.HeadPointerEngine`):
  - Real-time head tracking powered by MediaPipe FaceLandmarker with XNNPACK CPU acceleration.
  - Dynamically targets the verified RGB camera without hardcoding device nodes.
  - Processes frames asynchronously in a dedicated worker thread, keeping the GTK UI completely fluid.
- **Native 64-bit X11 Mouse Controller** (`accessos.engine.X11Mouse`):
  - Directly interfaces with `libX11` and `libXtst` via 64-bit typed ctypes.
  - Sub-millisecond cursor motion and click execution with zero external dependencies.
- **Signal Filtering & Stabilization** (`accessos.engine.PointFilter2D`):
  - Deadzone filter to suppress minor head tremors.
  - One-Euro adaptive low-pass filter for jitter reduction at rest and responsiveness in motion.
- **Dwell-to-Click State Machine** (`accessos.engine.DwellClicker`):
  - Automatic click generation on hover within a configurable spatial radius and dwell delay.
  - Refractory cooldown period to eliminate accidental double clicks.
- **Tracking HUD & Control Overlay** (`accessos.engine.TrackingOverlay`):
  - Persistent visual indicator showing live state (Active, Lost, Paused, Off), FPS, and latency.
  - Real-time dwell progress bar.
  - One-touch calibration (<kbd>C</kbd>) and emergency pause (<kbd>Esc</kbd>).
- **Safe Fallback & Privacy Guarantees**:
  - Tracking is never started automatically at boot; requires explicit user confirmation.
  - When tracking confidence is lost, cursor safely freezes in place, warning earcon sounds, and physical keyboard/mouse fallback is highlighted.
  - Physical keyboard and mouse remain operational at all times.
- **ThinkPad T480 Performance Benchmark**:
  - Achieved **26.5 FPS** average processing speed at **19.2 ms** latency with **197 MB** total RAM footprint.
- **Automated Test Suite**:
  - Added 9 new unit tests covering native mouse control, deadzones, low-pass filters, One-Euro filters, dwell state machine, and engine state transitions (45/45 total tests passing).

## [0.2.0] - Phase 2: Settings Application & System Control

### Corrected & Verified (Phase 2 Post-Review)
- **Centered macOS-Style Bottom Dock**: Converted the launcher from a 6-card grid to a centered macOS-style bottom dock with frosted-glass container styling, high-contrast outlines, and horizontal wrap-around keyboard navigation (`Left`/`Right`/`Home`/`End`/`1`-`6`). The top status bar remains compact and the dock is the sole application launcher.
- **Hardware-Verified Camera Metadata**: Corrected camera discovery to read device metadata dynamically from USB sysfs without vendor assumptions (`/dev/video2`: Chicony Electronics Co.,Ltd. Integrated Camera; `/dev/video0`: SunplusIT Inc Integrated IR Camera).
- **Wi-Fi Credential Protection**: Passwords are piped exclusively via `stdin` to `nmcli --ask`, preventing credential exposure in `ps aux`, `/proc/<pid>/cmdline`, or shell histories.
- **Safe Permission Rejection**: All system controls (reboot, shutdown, lock, brightness, volume, Wi-Fi) fail safely with actionable user feedback on denied permissions.

### Added
- **AccessOS Settings Application** (`accessos.settings.SettingsWindow`):
  - Accessible multi-tabbed preferences center (Accessibility, Display, Sound, Camera, Wi-Fi, System & Power).
  - 2D keyboard navigation, high-contrast outlines, screen reader markup annotations.
  - Returns cleanly to Home Screen on `Esc` or the Home button.
- **Hardware-Safe Camera Detector** (`accessos.settings.CameraDetector`):
  - Discovers V4L2 devices in sysfs and automatically classifies RGB vs IR sensors.
  - Identifies `/dev/video2` as the recommended RGB webcam without accessing video streams or requesting camera frames.
- **Guarded Power & Session Controls** (`accessos.settings.ConfirmDialog`):
  - Explicit confirmation dialog for every destructive system action (reboot, shutdown, restore defaults).
  - Safe default focus on `Cancel` to prevent accidental triggers.
  - Non-shell execution of `systemctl` / `loginctl` with argument arrays.
- **Safe Hardware Interfaces** (`accessos.settings.SystemControl`):
  - Audio volume query and adjustment via ALSA `amixer`.
  - Display brightness control via XRandR software scaling.
  - NetworkManager Wi-Fi scanning, radio toggling, and connection handling via `nmcli`.
- **Configuration Persistence & Default Restoration** (`accessos.utils.Config`):
  - Added atomic TOML serialization to `~/.config/accessos/settings.toml`.
  - Added `restore_defaults()` with deep copy and real-time listener notification.
- **Phase 2 Test Suite**:
  - 10 new unit tests covering TOML persistence, restore defaults, camera classification, volume/brightness clamping, and process execution isolation (30/30 total tests passing).

## [0.1.0] — Phase 1 — Home Screen Foundation

### Added
- Six-button home screen launcher (Browser, Files, Terminal, Settings, Images, Videos)
- High-contrast dark GTK 3 theme with 18 px+ text throughout
- Vivid blue (#4f9eff) keyboard focus ring — unmissable for low-vision users
- Full 2-D arrow-key grid navigation (arrow keys + Tab + Enter/Space)
- Emergency pause / resume via Esc key and visible header button
- Pause banner (Gtk.Revealer) that slides in below the header when paused
- Grid set_sensitive(False) when paused — buttons visually grey out
- Status bar: input mode, active/paused state, camera off, mic off, battery %, network, clock
- Power menu dialog (Phase 1 placeholders for lock / restart / shutdown)
- Return to Home action in power menu (always functional)
- Settings placeholder dialog pointing to Phase 2
- AppLauncher with allow-listed apps, no shell=True, fallback alternatives
- AudioFeedback: focus / activate / error / pause / resume cues via paplay/aplay
- Config system: TOML file with deep-merge defaults (tomllib stdlib)
- Rotating file logger: ~/.local/share/accessos/logs/accessos.log
- ACCESSOS_WINDOWED=1 env var for windowed development mode
- Unit tests for Config and AppLauncher (no hardware/display required)
- run_accessos.sh and stop_accessos.sh helper scripts
- MIT License, README, CREDITS, ARCHITECTURE, docs skeleton
