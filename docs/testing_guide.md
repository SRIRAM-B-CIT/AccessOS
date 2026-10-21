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
- [ ] Six buttons visible in a 3×2 grid with icons and labels
- [ ] Status bar visible at the bottom (mode, state, battery, network, time)
- [ ] Pause and Power buttons visible in the header

### Keyboard navigation
- [ ] Tab moves focus forward through buttons (visible blue focus ring)
- [ ] Shift+Tab moves focus backward
- [ ] Arrow keys navigate the 3×2 grid (Right/Left within row, Up/Down between rows)
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
