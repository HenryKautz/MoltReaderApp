# MoltReader

A cross-platform text-to-speech reader for Moltbook posts and comments.

## Features

- **Smart Content Extraction**: Reads only the post and comments from Moltbook pages, ignoring navigation and UI elements
- **Multiple Voices**: Assigns a unique voice to each poster/commenter, chosen randomly from 25 high-quality neural voices
- **Voice Persistence**: Remembers voice assignments so the same author always uses the same voice within a session
- **Standard Audio Controls**: Play, Pause, Skip, Stop, and Quit buttons
- **Clean UI**: Simple interface for pasting URLs and controlling playback

## Requirements

- Python 3.7+
- Works on macOS, Windows, and Linux

## Installation

```bash
# Clone the repository
git clone https://github.com/HenryKautz/MoltReader.git
cd MoltReader

# Install dependencies
pip install -r requirements.txt

# Install Chromium browser for Playwright (required for JavaScript rendering)
playwright install chromium
```

## Usage

```bash
python moltreader.py
```

1. Paste a Moltbook URL (e.g., `https://www.moltbook.com/post/39a5bb00-3de9-4b0a-bfa2-314dc643fdb3`)
2. Click **Load** to fetch the page
3. Click **Play** to start reading
4. Use **Pause** to pause/resume, **Skip** to jump to the next comment, **Stop** to reset to the beginning
5. Click **Quit** to exit

## How It Works

1. **Fetches** the Moltbook page using Playwright headless browser (renders JavaScript)
2. **Parses** the rendered HTML to extract post content and comments
3. **Assigns** random neural voices to each unique author (using Microsoft Edge TTS)
4. **Speaks** each post/comment using the assigned voice

## macOS-Only Version

There is also a macOS-specific version (`moltreader_mac_tts.py`) that uses the built-in `say` command instead of edge-tts. This version has fewer dependencies but only works on macOS.

```bash
# Install macOS version dependencies
pip install -r requirements_mac_tts.txt
playwright install chromium

# Run macOS version
python moltreader_mac_tts.py
```

## License

MIT License - Open Source
