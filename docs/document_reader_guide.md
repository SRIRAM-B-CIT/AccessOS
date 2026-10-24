# AccessOS Document Reader Guide

The AccessOS Document Reader provides an accessible, fully offline text-to-speech reading environment for users with motor, cognitive, and visual accessibility needs. It integrates directly with **Piper TTS** to read documents aloud with natural speech while highlighting each sentence in real time.

---

## Supported File Formats

The Document Reader extracts clean text and sentence structures from multiple standard formats without external cloud services or proprietary tools:

| Format | Extension | Extraction Method |
|---|---|---|
| **Plain Text** | `.txt`, `.log`, `.csv`, `.tsv` | Native multi-encoding loader (`utf-8`, `latin-1`, `cp1252`) |
| **Markdown** | `.md` | Strips syntax markers, headers, and code fences |
| **HTML** | `.html`, `.htm` | Clean DOM text parser skipping scripts and style tags |
| **Word Documents** | `.docx` | Standard-library zip XML stream extraction (`word/document.xml`) |
| **OpenDocument** | `.odt` | Standard-library zip XML stream extraction (`content.xml`) |
| **EPUB Books** | `.epub` | Standard-library zip XHTML sequential chapter extraction |
| **PDF Documents** | `.pdf` | System `pdftotext` layout engine |
| **Image Documents** | `.png`, `.jpg`, `.jpeg`, `.bmp` | Displays accessible notice guiding OCR workflow |

---

## Interaction & Control Modalities

### 1. Graphical Interface
- **High-Contrast Text View**: Large 15pt readable font with word wrap and smooth autoscroll.
- **Active Sentence Highlighting**: The currently read sentence is highlighted in high-contrast blue/white.
- **Progress Tracking**: Real-time progress bar displaying sentence count and percentage read.
- **Speed Controls**: Adjustable speech rate from **0.75x** to **1.75x** in 0.25x increments.

### 2. Keyboard Shortcuts
| Key | Action |
|---|---|
| <kbd>Ctrl + R</kbd> | Open Document Reader from HomeScreen |
| <kbd>Space</kbd> | Toggle Play / Pause |
| <kbd>←</kbd> or <kbd>P</kbd> | Previous Sentence |
| <kbd>→</kbd> or <kbd>N</kbd> | Next Sentence |
| <kbd>S</kbd> | Stop playback and return to start |
| <kbd>O</kbd> | Open File dialog |
| <kbd>Esc</kbd> | Close Document Reader window |

### 3. Hands-Free Voice Commands (Offline Vosk)
When voice control is active, the reader can be fully operated hands-free:
- `"read document"` or `"read aloud"`: Opens Document Reader
- `"pause reading"`: Pauses speech at the current sentence
- `"resume reading"`: Resumes speech from the paused sentence
- `"stop reading"`: Halts playback and resets to beginning
- `"next sentence"` or `"next"`: Advances to the next sentence
- `"previous sentence"` or `"previous"`: Moves back to the previous sentence
- `"read faster"`: Increases playback speed by 0.25x
- `"read slower"`: Decreases playback speed by 0.25x

---

## Privacy & Offline Guarantees
- **100% Local**: No network connections, telemetry, or external APIs.
- **In-Memory Audio**: Speech is synthesized in-memory and piped directly to ALSA (`aplay`).
- **No Document Storage**: Documents opened in the reader are read from their existing local paths and never cached externally.
