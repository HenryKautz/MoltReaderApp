#!/usr/bin/env python3
"""
MoltReader Web App - Flask-based web version of MoltReader

A web application that reads Moltbook posts and comments aloud using
Microsoft's neural text-to-speech via edge-tts.
"""

import asyncio
import io
import os
import re
import random
import uuid
from typing import Dict, List, Tuple, Optional

from flask import Flask, render_template, request, jsonify, Response, session
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import edge_tts

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Server-side session storage (in production, use Redis or similar)
sessions: Dict[str, dict] = {}


class EdgeTTSVoiceManager:
    """
    Manages Microsoft Edge text-to-speech voices.
    """

    ENGLISH_VOICES = [
        ("en-US-AvaNeural", "Ava", "female"),
        ("en-US-AndrewNeural", "Andrew", "male"),
        ("en-US-EmmaNeural", "Emma", "female"),
        ("en-US-BrianNeural", "Brian", "male"),
        ("en-US-JennyNeural", "Jenny", "female"),
        ("en-US-GuyNeural", "Guy", "male"),
        ("en-US-AriaNeural", "Aria", "female"),
        ("en-US-ChristopherNeural", "Christopher", "male"),
        ("en-US-EricNeural", "Eric", "male"),
        ("en-US-MichelleNeural", "Michelle", "female"),
        ("en-US-RogerNeural", "Roger", "male"),
        ("en-US-SteffanNeural", "Steffan", "male"),
        ("en-US-AnaNeural", "Ana", "female"),
        ("en-GB-SoniaNeural", "Sonia", "female"),
        ("en-GB-RyanNeural", "Ryan", "male"),
        ("en-GB-LibbyNeural", "Libby", "female"),
        ("en-GB-MaisieNeural", "Maisie", "female"),
        ("en-GB-ThomasNeural", "Thomas", "male"),
        ("en-AU-NatashaNeural", "Natasha", "female"),
        ("en-CA-ClaraNeural", "Clara", "female"),
        ("en-CA-LiamNeural", "Liam", "male"),
        ("en-IE-EmilyNeural", "Emily", "female"),
        ("en-IE-ConnorNeural", "Connor", "male"),
        ("en-NZ-MollyNeural", "Molly", "female"),
        ("en-NZ-MitchellNeural", "Mitchell", "male"),
    ]

    def __init__(self):
        self.agent_voices: Dict[str, Tuple[str, str]] = {}
        self.available_voices = [(v[0], v[1]) for v in self.ENGLISH_VOICES]
        self.assigned_voices: List[str] = []

    def get_voice_for_agent(self, agent_name: str) -> Tuple[str, str]:
        """Get or assign a voice for a given agent."""
        if agent_name in self.agent_voices:
            return self.agent_voices[agent_name]

        unassigned = [v for v in self.available_voices if v[0] not in self.assigned_voices]

        if unassigned:
            voice = random.choice(unassigned)
        else:
            voice = random.choice(self.available_voices)

        self.agent_voices[agent_name] = voice
        self.assigned_voices.append(voice[0])

        return voice

    def reset(self):
        """Reset all voice assignments."""
        self.agent_voices.clear()
        self.assigned_voices.clear()

    def to_dict(self) -> dict:
        """Serialize for session storage."""
        return {
            'agent_voices': self.agent_voices,
            'assigned_voices': self.assigned_voices
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'EdgeTTSVoiceManager':
        """Deserialize from session storage."""
        manager = cls()
        manager.agent_voices = data.get('agent_voices', {})
        manager.assigned_voices = data.get('assigned_voices', [])
        return manager


class MoltbookScraper:
    """Scrapes Moltbook pages to extract posts and comments."""

    def fetch_page(self, url: str) -> Tuple[List[Tuple[str, str]], Optional[str]]:
        """Fetch and parse a Moltbook page."""
        try:
            if 'moltbook.com' not in url:
                return [], "URL must be from moltbook.com"

            html_content = self._fetch_with_playwright(url)
            soup = BeautifulSoup(html_content, 'html.parser')
            content_items = self._extract_content(soup)

            if not content_items:
                return [], "No posts or comments found on this page"

            return content_items, None

        except PlaywrightTimeout:
            return [], "Page load timed out. Please try again."
        except Exception as e:
            return [], f"Error fetching page: {str(e)}"

    def _fetch_with_playwright(self, url: str) -> str:
        """Fetch a page using Playwright headless browser."""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until='networkidle', timeout=30000)
            page.wait_for_selector('h1.text-xl', timeout=15000)

            try:
                page.wait_for_selector('h2:has-text("Comments")', timeout=10000)
            except PlaywrightTimeout:
                pass

            html_content = page.content()
            browser.close()
            return html_content

    def _extract_content(self, soup: BeautifulSoup) -> List[Tuple[str, str]]:
        """Extract post and comment content."""
        content_items = []

        main_post = self._find_main_post(soup)
        if main_post:
            content_items.append(main_post)

        comments = self._find_comments(soup)
        content_items.extend(comments)

        return content_items

    def _find_main_post(self, soup: BeautifulSoup) -> Optional[Tuple[str, str]]:
        """Find the main post on the page."""
        title_elem = soup.select_one('h1.text-xl')
        if not title_elem:
            return None

        title = title_elem.get_text(strip=True)

        post_container = title_elem.find_parent('div', class_=lambda c: c and 'flex-1' in c)
        if not post_container:
            post_container = title_elem.find_parent('div', class_=lambda c: c and 'rounded-lg' in c)

        if not post_container:
            return None

        author = "Author"
        author_link = post_container.select_one('a[href^="/u/"]')

        if not author_link:
            parent = post_container.parent
            if parent:
                author_link = parent.select_one('a[href^="/u/"]')

        if not author_link:
            parent_of_title = title_elem.parent
            if parent_of_title:
                author_link = parent_of_title.select_one('a[href^="/u/"]')

        if not author_link:
            comments_header = soup.find('h2', string=lambda s: s and 'Comments' in s)
            all_user_links = soup.select('a[href^="/u/"]')
            for link in all_user_links:
                if comments_header and link.find_parent() == comments_header.find_parent():
                    break
                author_link = link
                break

        if author_link:
            author = author_link.get_text(strip=True)
            if author.startswith('u/'):
                author = author[2:]

        prose_div = post_container.select_one('div.prose')
        if prose_div:
            content = self._extract_prose_text(prose_div)
        else:
            content = ""

        full_text = f"{title}. {content}" if content else title
        return (author, full_text)

    def _find_comments(self, soup: BeautifulSoup) -> List[Tuple[str, str]]:
        """Find all comments on the page."""
        comments = []

        comments_header = soup.find('h2', string=lambda s: s and 'Comments' in s)
        if not comments_header:
            comments_header = soup.find('h2', class_=lambda c: c and 'text-lg' in c and 'font-bold' in c)

        if not comments_header:
            return comments

        comments_container = comments_header.find_next_sibling('div')
        if not comments_container:
            parent = comments_header.parent
            if parent:
                comments_container = parent.select_one('div.rounded-lg')

        if not comments_container:
            return comments

        comment_divs = comments_container.select('div.py-2')

        for comment_div in comment_divs:
            author = "Commenter"
            author_link = comment_div.select_one('a[href^="/u/"]')
            if author_link:
                author = author_link.get_text(strip=True)
                if author.startswith('u/'):
                    author = author[2:]

            prose_div = comment_div.select_one('div.prose')
            if prose_div:
                content = self._extract_prose_text(prose_div)
                if content:
                    comments.append((author, content))

        return comments

    def _extract_prose_text(self, prose_element) -> str:
        """Extract clean text from a Moltbook prose div."""
        if not prose_element:
            return ""

        text_parts = []

        for elem in prose_element.find_all(['p', 'li', 'pre', 'code', 'em', 'strong'], recursive=True):
            if elem.parent.name in ['p', 'li']:
                continue

            text = elem.get_text(separator=' ', strip=True)
            if text:
                text_parts.append(text)

        if not text_parts:
            text = prose_element.get_text(separator=' ', strip=True)
            text_parts = [text] if text else []

        full_text = ' '.join(text_parts)
        full_text = re.sub(r'\s+', ' ', full_text)

        return full_text.strip()


def get_session_data(session_id: str) -> dict:
    """Get or create session data."""
    if session_id not in sessions:
        sessions[session_id] = {
            'content': [],
            'voice_manager': EdgeTTSVoiceManager().to_dict()
        }
    return sessions[session_id]


async def generate_audio(text: str, voice_id: str) -> bytes:
    """Generate audio using edge-tts."""
    communicate = edge_tts.Communicate(text, voice_id)
    audio_data = io.BytesIO()

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data.write(chunk["data"])

    return audio_data.getvalue()


@app.route('/')
def index():
    """Serve the main page."""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    return render_template('index.html')


@app.route('/api/load', methods=['POST'])
def load_url():
    """Load and parse a Moltbook URL."""
    data = request.get_json()
    url = data.get('url', '').strip()

    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    session_id = session.get('session_id', str(uuid.uuid4()))
    session['session_id'] = session_id

    scraper = MoltbookScraper()
    content, error = scraper.fetch_page(url)

    if error:
        return jsonify({'error': error}), 400

    # Reset voice manager for new content
    voice_manager = EdgeTTSVoiceManager()

    # Store in session
    session_data = get_session_data(session_id)
    session_data['content'] = content
    session_data['voice_manager'] = voice_manager.to_dict()

    # Return content metadata
    items = []
    for i, (author, text) in enumerate(content):
        voice_id, voice_name = voice_manager.get_voice_for_agent(author)
        items.append({
            'index': i,
            'author': author,
            'text': text,
            'voice_name': voice_name
        })

    # Update voice manager after assignments
    session_data['voice_manager'] = voice_manager.to_dict()

    return jsonify({
        'success': True,
        'item_count': len(content),
        'items': items
    })


@app.route('/api/audio/<int:index>')
def get_audio(index: int):
    """Generate and stream audio for a specific item."""
    session_id = session.get('session_id')

    if not session_id or session_id not in sessions:
        return jsonify({'error': 'Session not found'}), 404

    session_data = sessions[session_id]
    content = session_data.get('content', [])

    if index < 0 or index >= len(content):
        return jsonify({'error': 'Invalid index'}), 404

    author, text = content[index]
    voice_manager = EdgeTTSVoiceManager.from_dict(session_data['voice_manager'])
    voice_id, voice_name = voice_manager.get_voice_for_agent(author)

    # Generate audio with author introduction
    text_with_intro = f"{author} says, {text}"

    # Run async audio generation
    audio_data = asyncio.run(generate_audio(text_with_intro, voice_id))

    return Response(
        audio_data,
        mimetype='audio/mpeg',
        headers={
            'Content-Disposition': f'inline; filename="audio_{index}.mp3"',
            'X-Author': author,
            'X-Voice': voice_name
        }
    )


@app.route('/api/reset', methods=['POST'])
def reset_session():
    """Reset the current session."""
    session_id = session.get('session_id')

    if session_id and session_id in sessions:
        del sessions[session_id]

    session['session_id'] = str(uuid.uuid4())
    return jsonify({'success': True})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
