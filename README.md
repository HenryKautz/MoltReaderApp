# MoltReader

A web-based text-to-speech reader for Moltbook posts and comments.

## Features

- **Smart Content Extraction**: Reads only the post and comments from Moltbook pages, ignoring navigation and UI elements
- **Multiple Voices**: Assigns a unique voice to each poster/commenter, chosen randomly from 25 high-quality neural voices
- **Voice Persistence**: Remembers voice assignments so the same author always uses the same voice within a session
- **Full Audio Controls**: Play, Pause, Skip, and Stop buttons
- **Clean Web UI**: Simple interface for pasting URLs and controlling playback

## Live Demo

Deployed at: [https://moltreader.onrender.com](https://moltreader.onrender.com)

## Local Development

```bash
# Clone the repository
git clone https://github.com/HenryKautz/MoltReaderApp.git
cd MoltReaderApp

# Install dependencies
pip install -r requirements_web.txt

# Install Chromium browser for Playwright (required for JavaScript rendering)
playwright install chromium

# Run the app
python app.py
# Open http://localhost:5001
```

## Usage

1. Paste a Moltbook URL (e.g., `https://www.moltbook.com/post/39a5bb00-3de9-4b0a-bfa2-314dc643fdb3`)
2. Click **Load** to fetch the page
3. Click **Play** to start reading
4. Use **Pause** to pause/resume, **Skip** to jump to the next comment, **Stop** to reset to the beginning

## How It Works

1. **Fetches** the Moltbook page using Playwright headless browser (renders JavaScript)
2. **Parses** the rendered HTML to extract post content and comments
3. **Assigns** random neural voices to each unique author (using Microsoft Edge TTS)
4. **Streams** audio to your browser for each post/comment

## Deployment

This app is configured for deployment on [Render](https://render.com):

1. Fork or clone this repository
2. Connect to Render and create a new Web Service
3. Render will auto-detect the `render.yaml` configuration

## License

MIT License - Open Source
