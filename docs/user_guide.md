# AccessOS User Guide

Welcome to **AccessOS**, an accessible operating environment built for hands-free, voice, adaptive, and motor-accessible computing.

---

## 1. Desktop Interface & Navigation

AccessOS features a clean, focused, distraction-free desktop interface centered around a **macOS-style bottom dock**:

```
+-------------------------------------------------------------------------------+
|  AccessOS Status Bar   [Profile Badge]   [Volume]   [Time]   [Pause/Resume]   |
+-------------------------------------------------------------------------------+
|                                                                               |
|                                                                               |
|                                                                               |
|                                                                               |
|                                                                               |
|         +-----------------------------------------------------------+         |
|         | [Browser] [Files] [Terminal] [Settings] [Images] [Videos] |         |
|         +-----------------------------------------------------------+         |
+-------------------------------------------------------------------------------+
```

### The Six Allowed Applications:
AccessOS displays exclusively the six primary accessible applications:
1. 🌐 **Browser** (`firefox`): Web browsing with keyboard accessibility.
2. 📁 **Files** (`thunar`): Local file browser and document manager.
3. 💻 **Terminal** (`xfce4-terminal`): Command line shell. Also accessible via <kbd>Ctrl+Alt+T</kbd>.
4. ⚙️ **Settings** (`accessos settings`): Accessibility configuration, camera detection, volume, display, Wi-Fi.
5. 🖼️ **Images** (`ristretto`): Photo and image viewer.
6. 🎬 **Videos** (`parole`): Media and video player.

---

## 2. Input Modalities

### ⌨️ Standard Keyboard & Physical Mouse
- **Always Active**: Guaranteed fallback across all operating modes.
- **Dock Navigation**:
  - <kbd>1</kbd> to <kbd>6</kbd>: Instantly focus and launch the corresponding dock app.
  - <kbd>←</kbd> / <kbd>→</kbd>: Move focus left and right across the dock.
  - <kbd>Home</kbd> / <kbd>End</kbd>: Jump to first (Browser) or last (Videos) application.
  - <kbd>Enter</kbd> / <kbd>Space</kbd>: Launch the currently focused application.

### 🎙️ Offline Voice Control (Vosk + Piper)
- **Local & Private**: Powered by the lightweight offline Vosk English speech model (`small-en-us`). Audio streams are processed entirely in memory; recordings are never saved to disk.
- **Mic Toggle**: Press <kbd>M</kbd> or click the microphone icon in the header to mute/unmute.
- **Approved Commands**:
  - `"open browser"`, `"open files"`, `"open terminal"`, `"open settings"`, `"open images"`, `"open videos"`
  - `"go home"`, `"read status"`, `"help"`
  - `"volume up"`, `"volume down"`
  - `"read document"`, `"pause reading"`, `"resume reading"`, `"stop reading"`
  - `"restart"` or `"shut down"` *(prompts for spoken confirmation: `"yes"` or `"cancel"`)*

### 🎯 Head Pointer Tracking
- **Webcam-Driven**: Tracks nose-tip displacement relative to your calibrated baseline position using MediaPipe FaceLandmarker.
- **One-Euro Smoothing**: Automatically damps jitter while remaining responsive during rapid head turns.
- **Center Baseline Calibration**: Press <kbd>C</kbd> or click **🎯 Center** on the status HUD while looking at the screen center.

### ⏱️ Dwell Clicking
- Hover the cursor motionless over any button or interactive target.
- An animated progress ring accumulates around the reticle.
- When the ring completes (default 1000ms), a click event is triggered.

### 👁️ Intentional Blink Selection
- Replaces or supplements dwell clicking.
- Deliberate voluntary blinks held between **200ms and 800ms** trigger a click at the current cursor position.
- Natural involuntary blinks (80ms–150ms) and prolonged closures (>800ms) are filtered out.
- A distinctive cyan ripple animation confirms successful blink selection.

### 🔬 Experimental Eye Gaze
- Computes pupil-to-canthus ratios from facial landmarks.
- Features a guided 5-point calibration wizard (Center, Top-Left, Top-Right, Bottom-Left, Bottom-Right).
- *Hardware Note*: Integrated 720p webcams without dedicated infrared eye trackers provide coarse gaze tracking (~100–150px accuracy). Combining eye gaze with dwell or head tracking is recommended.

---

## 3. Accessible Document Reader
Press <kbd>Ctrl + R</kbd> or speak `"read document"` to open the Document Reader:
- Reads `.txt`, `.md`, `.html`, `.pdf`, `.docx`, `.odt`, and `.epub` documents aloud using Piper neural speech synthesis.
- Active sentence is highlighted in high-contrast blue/white with automatic scrolling.
- Controls: <kbd>Space</kbd> (play/pause), <kbd>←/→</kbd> (navigate sentences), <kbd>S</kbd> (stop), <kbd>O</kbd> (open file).

---

## 4. First-Boot Setup Wizard
When booting AccessOS for the first time, the accessible Onboarding Wizard guides you through:
1. Spoken welcome & Piper speech introduction.
2. Selection of your preferred primary input modality.
3. Explicit opt-in hardware consent for camera and microphone.
4. High-contrast theme and font size selection.
The wizard can be re-launched at any time from **Settings -> Run First-Boot Setup Wizard**.
