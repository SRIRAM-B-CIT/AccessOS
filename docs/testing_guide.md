# AccessOS — Testing Guide

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
