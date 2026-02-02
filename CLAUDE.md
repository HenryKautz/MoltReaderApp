# MoltReader

A web-based text-to-speech reader for Moltbook posts and comments.

## Tech Stack
- **Backend**: Flask (Python)
- **Scraping**: Playwright with Chromium for JavaScript-rendered pages
- **TTS**: edge-tts (Microsoft neural voices)
- **Frontend**: Vanilla HTML/CSS/JS with HTML5 Audio API
- **Deployment**: Render.com with Docker

## Key Files
- `app.py` - Flask backend with API endpoints (/api/load, /api/audio/<index>)
- `templates/index.html` - Frontend UI
- `static/app.js` - JavaScript playback controls (play, pause, skip, stop)
- `static/style.css` - Dark theme styling
- `Dockerfile` - Uses `mcr.microsoft.com/playwright/python:v1.58.0-noble`
- `render.yaml` - Render deployment config (Docker runtime)
- `requirements_web.txt` - Python dependencies

## Architecture
1. User enters Moltbook URL and clicks Load
2. Backend scrapes page with Playwright, extracts posts/comments
3. Each author is assigned a random neural voice (persisted per session)
4. Audio is generated on-demand with edge-tts and streamed to browser
5. Frontend handles playback with HTML5 Audio element

## Local Development
```bash
pip install -r requirements_web.txt
playwright install chromium
python app.py
# Open http://localhost:5001
```

## Deployment Notes
- Render free tier works but has cold starts
- Must use Docker runtime (not Python) because Playwright needs system dependencies
- Keep Dockerfile Playwright version in sync with pip package version
- No environment variables required (SECRET_KEY has default fallback)

## Live URL
https://moltreader.onrender.com
