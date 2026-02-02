#!/usr/bin/env python3
"""
MoltReader - A Cross-Platform Text-to-Speech Reader for Moltbook Posts

This program reads Moltbook posts and comments aloud using edge-tts (Microsoft's
neural text-to-speech). Each poster/commenter is assigned a unique voice (chosen
randomly) that persists throughout the reading session.

Requirements:
    - Python 3.7+
    - edge-tts: pip install edge-tts
    - playwright: pip install playwright && playwright install chromium
    - beautifulsoup4: pip install beautifulsoup4
    - pygame: pip install pygame (for audio playback)

Usage:
    python moltreader.py

License: MIT (Open Source)
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import random
import re
import asyncio
import tempfile
import os
from typing import Dict, List, Tuple, Optional

# Third-party imports (need to be installed)
try:
    from bs4 import BeautifulSoup
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
    import edge_tts
    import pygame
except ImportError as e:
    print("Please install required packages:")
    print("  pip install beautifulsoup4 playwright edge-tts pygame")
    print("  playwright install chromium")
    raise e


class EdgeTTSVoiceManager:
    """
    Manages Microsoft Edge text-to-speech voices.

    Uses edge-tts library to access high-quality neural voices.
    Works cross-platform (macOS, Windows, Linux).
    """

    # Curated list of high-quality English neural voices from edge-tts
    # These are verified to work as of 2024
    # Format: (voice_name, friendly_name, gender)
    ENGLISH_VOICES = [
        # US voices
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
        # UK voices
        ("en-GB-SoniaNeural", "Sonia", "female"),
        ("en-GB-RyanNeural", "Ryan", "male"),
        ("en-GB-LibbyNeural", "Libby", "female"),
        ("en-GB-MaisieNeural", "Maisie", "female"),
        ("en-GB-ThomasNeural", "Thomas", "male"),
        # Australian voices
        ("en-AU-NatashaNeural", "Natasha", "female"),
        # Canadian voices
        ("en-CA-ClaraNeural", "Clara", "female"),
        ("en-CA-LiamNeural", "Liam", "male"),
        # Other English variants
        ("en-IE-EmilyNeural", "Emily", "female"),
        ("en-IE-ConnorNeural", "Connor", "male"),
        ("en-NZ-MollyNeural", "Molly", "female"),
        ("en-NZ-MitchellNeural", "Mitchell", "male"),
    ]

    def __init__(self):
        # Dictionary mapping agent names to their assigned voices
        self.agent_voices: Dict[str, Tuple[str, str]] = {}

        # Available voices (voice_id, friendly_name)
        self.available_voices = [(v[0], v[1]) for v in self.ENGLISH_VOICES]

        # Keep track of which voices have been assigned
        self.assigned_voices: List[str] = []

    def get_voice_for_agent(self, agent_name: str) -> Tuple[str, str]:
        """
        Get or assign a voice for a given agent (poster/commenter).

        If the agent already has a voice assigned, return that voice.
        Otherwise, assign a new random voice (preferring unassigned voices).

        Args:
            agent_name: The name/identifier of the poster or commenter.

        Returns:
            Tuple of (voice_id, friendly_name) to use for this agent.
        """
        # Check if agent already has a voice assigned
        if agent_name in self.agent_voices:
            return self.agent_voices[agent_name]

        # Find voices that haven't been assigned yet
        unassigned = [v for v in self.available_voices if v[0] not in self.assigned_voices]

        if unassigned:
            # Pick a random unassigned voice
            voice = random.choice(unassigned)
        else:
            # All voices used - pick a random one (allowing reuse)
            voice = random.choice(self.available_voices)

        # Remember the assignment
        self.agent_voices[agent_name] = voice
        self.assigned_voices.append(voice[0])

        return voice

    def reset(self):
        """Reset all voice assignments for a new reading session."""
        self.agent_voices.clear()
        self.assigned_voices.clear()


class MoltbookScraper:
    """
    Scrapes Moltbook pages to extract posts and comments.

    Uses Playwright headless browser to render JavaScript content.

    Moltbook HTML structure (as of 2024):
    - Main post: Contains h1 title, author link (href="/u/..."), and .prose content
    - Comments: Located after h2 "Comments", each in div.py-2 with author link and .prose content
    """

    def fetch_page(self, url: str) -> Tuple[List[Tuple[str, str]], Optional[str]]:
        """
        Fetch and parse a Moltbook page using headless browser.

        Uses Playwright to render JavaScript and get fully loaded content.

        Args:
            url: The URL of the Moltbook post.

        Returns:
            Tuple of:
            - List of (agent_name, text_content) tuples in reading order
            - Error message if any, or None on success
        """
        try:
            # Validate URL is from moltbook.com
            if 'moltbook.com' not in url:
                return [], "URL must be from moltbook.com"

            # Use Playwright to fetch and render the page
            html_content = self._fetch_with_playwright(url)

            # Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')

            # Extract posts and comments
            content_items = self._extract_content(soup)

            if not content_items:
                return [], "No posts or comments found on this page"

            return content_items, None

        except PlaywrightTimeout:
            return [], "Page load timed out. Please try again."
        except Exception as e:
            return [], f"Error fetching page: {str(e)}"

    def _fetch_with_playwright(self, url: str) -> str:
        """
        Fetch a page using Playwright headless browser.

        Waits for the page to fully render before extracting HTML.

        Args:
            url: The URL to fetch.

        Returns:
            The fully rendered HTML content.
        """
        with sync_playwright() as p:
            # Launch headless Chromium browser
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Navigate to the URL
            page.goto(url, wait_until='networkidle', timeout=30000)

            # Wait for the main post content to appear
            # This ensures JavaScript has rendered the content
            page.wait_for_selector('h1.text-xl', timeout=15000)

            # Also wait for comments to load
            try:
                page.wait_for_selector('h2:has-text("Comments")', timeout=10000)
            except PlaywrightTimeout:
                pass  # Comments section might not exist, continue anyway

            # Get the fully rendered HTML
            html_content = page.content()

            browser.close()

            return html_content

    def _extract_content(self, soup: BeautifulSoup) -> List[Tuple[str, str]]:
        """
        Extract post and comment content from Moltbook HTML.

        Args:
            soup: BeautifulSoup parsed HTML.

        Returns:
            List of (author_name, content_text) tuples.
        """
        content_items = []

        # Find the main post
        main_post = self._find_main_post(soup)
        if main_post:
            content_items.append(main_post)

        # Find all comments
        comments = self._find_comments(soup)
        content_items.extend(comments)

        return content_items

    def _find_main_post(self, soup: BeautifulSoup) -> Optional[Tuple[str, str]]:
        """
        Find the main post on the page.

        Moltbook structure:
        - Post title in <h1> with class containing "text-xl"
        - Author in <a href="/u/username">
        - Content in <div class="prose prose-invert ...">
        """
        # Find the main post title
        title_elem = soup.select_one('h1.text-xl')
        if not title_elem:
            return None

        # Get the title text
        title = title_elem.get_text(strip=True)

        # Find the post container (parent elements of the title)
        post_container = title_elem.find_parent('div', class_=lambda c: c and 'flex-1' in c)
        if not post_container:
            # Try to find by going up to the rounded-lg container
            post_container = title_elem.find_parent('div', class_=lambda c: c and 'rounded-lg' in c)

        if not post_container:
            return None

        # Extract author from the "Posted by u/username" link
        author = "Author"
        author_link = post_container.select_one('a[href^="/u/"]')

        # If not found in post_container, search in parent elements
        if not author_link:
            parent = post_container.parent
            if parent:
                author_link = parent.select_one('a[href^="/u/"]')

        # If still not found, look near the title element
        if not author_link:
            parent_of_title = title_elem.parent
            if parent_of_title:
                author_link = parent_of_title.select_one('a[href^="/u/"]')

        # If still not found, search the whole page for the first user link before comments
        if not author_link:
            # Find comments header to know where to stop
            comments_header = soup.find('h2', string=lambda s: s and 'Comments' in s)
            all_user_links = soup.select('a[href^="/u/"]')
            for link in all_user_links:
                # Use the first user link found (which should be the post author)
                # Stop if we've reached the comments section
                if comments_header and link.find_parent() == comments_header.find_parent():
                    break
                author_link = link
                break

        if author_link:
            author = author_link.get_text(strip=True)
            # Remove "u/" prefix if present for cleaner speech
            if author.startswith('u/'):
                author = author[2:]

        # Extract content from prose div
        prose_div = post_container.select_one('div.prose')
        if prose_div:
            content = self._extract_prose_text(prose_div)
        else:
            content = ""

        # Combine title and content for reading
        full_text = f"{title}. {content}" if content else title

        return (author, full_text)

    def _find_comments(self, soup: BeautifulSoup) -> List[Tuple[str, str]]:
        """
        Find all comments on the page.

        Moltbook structure:
        - Comments section starts after <h2> containing "Comments"
        - Each comment is in a <div class="py-2">
        - Author in <a href="/u/username" class="...font-medium...">
        - Content in <div class="prose prose-invert ...">
        """
        comments = []

        # Find the comments section header
        comments_header = soup.find('h2', string=lambda s: s and 'Comments' in s)
        if not comments_header:
            # Try finding by class pattern
            comments_header = soup.find('h2', class_=lambda c: c and 'text-lg' in c and 'font-bold' in c)

        if not comments_header:
            return comments

        # Find the comments container (sibling or parent's next element)
        comments_container = comments_header.find_next_sibling('div')
        if not comments_container:
            # Try parent's structure
            parent = comments_header.parent
            if parent:
                comments_container = parent.select_one('div.rounded-lg')

        if not comments_container:
            return comments

        # Find all individual comments (div.py-2 contains each comment)
        comment_divs = comments_container.select('div.py-2')

        for comment_div in comment_divs:
            # Extract author
            author = "Commenter"
            author_link = comment_div.select_one('a[href^="/u/"]')
            if author_link:
                author = author_link.get_text(strip=True)
                # Remove "u/" prefix for cleaner speech
                if author.startswith('u/'):
                    author = author[2:]

            # Extract content from prose div
            prose_div = comment_div.select_one('div.prose')
            if prose_div:
                content = self._extract_prose_text(prose_div)
                if content:
                    comments.append((author, content))

        return comments

    def _extract_prose_text(self, prose_element) -> str:
        """
        Extract clean text from a Moltbook prose div.

        Handles paragraphs, emphasis, code blocks, and lists.
        """
        if not prose_element:
            return ""

        # Collect text from all paragraph and list elements
        text_parts = []

        # Get all text-containing elements
        for elem in prose_element.find_all(['p', 'li', 'pre', 'code', 'em', 'strong'], recursive=True):
            # Skip nested elements we'll process at their parent level
            if elem.parent.name in ['p', 'li']:
                continue

            text = elem.get_text(separator=' ', strip=True)
            if text:
                text_parts.append(text)

        # If no structured elements found, get all text
        if not text_parts:
            text = prose_element.get_text(separator=' ', strip=True)
            text_parts = [text] if text else []

        # Join with proper spacing
        full_text = ' '.join(text_parts)

        # Clean up whitespace
        full_text = re.sub(r'\s+', ' ', full_text)

        return full_text.strip()


class TextToSpeechEngine:
    """
    Manages text-to-speech playback using edge-tts and pygame.

    Uses Microsoft's neural TTS voices for high-quality speech.
    Supports play, pause, and stop functionality.
    Runs speech in a background thread to keep UI responsive.
    """

    def __init__(self, voice_manager: EdgeTTSVoiceManager):
        self.voice_manager = voice_manager

        # Initialize pygame mixer for audio playback
        pygame.mixer.init()

        # Current playback state
        self.is_playing = False
        self.is_paused = False

        # Queue of content items to read
        self.content_queue: List[Tuple[str, str]] = []
        self.current_index = 0

        # Threading components
        self.speech_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.skip_requested = False

        # Temp file for current audio
        self.current_audio_file: Optional[str] = None

        # Callbacks for status and text updates
        self.status_callback = None
        self.text_callback = None

    def set_content(self, content_items: List[Tuple[str, str]]):
        """
        Set the content to be read.

        Args:
            content_items: List of (author, text) tuples.
        """
        self.content_queue = content_items
        self.current_index = 0

    def play(self):
        """Start or resume playback."""
        if self.is_paused:
            # Resume from pause
            self.is_paused = False
            pygame.mixer.music.unpause()
            self.pause_event.set()
            return

        if self.is_playing:
            return  # Already playing

        if not self.content_queue:
            return  # Nothing to play

        # Start fresh playback
        self.is_playing = True
        self.is_paused = False
        self.stop_event.clear()
        self.pause_event.set()

        # Start speech in background thread
        self.speech_thread = threading.Thread(target=self._speech_loop, daemon=True)
        self.speech_thread.start()

    def pause(self):
        """Pause playback."""
        if self.is_playing and not self.is_paused:
            self.is_paused = True
            self.pause_event.clear()
            pygame.mixer.music.pause()

    def stop(self):
        """Stop playback and reset to beginning."""
        self.stop_event.set()
        self.pause_event.set()  # Unblock if paused

        # Stop audio playback
        pygame.mixer.music.stop()

        # Reset state
        self.is_playing = False
        self.is_paused = False
        self.current_index = 0

        # Clean up temp file
        self._cleanup_audio_file()

        # Reset voice assignments for fresh start
        self.voice_manager.reset()

    def skip(self):
        """Skip to the next item in the queue."""
        if not self.is_playing:
            return

        # Set skip flag so speech loop knows to continue to next item
        self.skip_requested = True

        # Stop current audio playback
        pygame.mixer.music.stop()

        # Ensure we're not paused
        if self.is_paused:
            self.is_paused = False
            self.pause_event.set()

    def _cleanup_audio_file(self):
        """Remove temporary audio file if it exists."""
        if self.current_audio_file and os.path.exists(self.current_audio_file):
            try:
                os.remove(self.current_audio_file)
            except:
                pass
            self.current_audio_file = None

    def _speech_loop(self):
        """
        Main speech loop - runs in background thread.

        Iterates through content queue and speaks each item.
        """
        while self.current_index < len(self.content_queue):
            # Check for stop signal
            if self.stop_event.is_set():
                break

            # Check for pause - block until unpaused
            self.pause_event.wait()

            if self.stop_event.is_set():
                break

            # Get current item
            author, text = self.content_queue[self.current_index]

            # Get voice for this author
            voice_id, voice_name = self.voice_manager.get_voice_for_agent(author)

            # Update status (speaker info) and text display separately
            if self.status_callback:
                progress = f"[{self.current_index + 1}/{len(self.content_queue)}]"
                self.status_callback(f"{progress} {author} (voice: {voice_name})")
            if self.text_callback:
                self.text_callback(text)

            # Speak the text with author introduction
            text_with_intro = f"{author} says, {text}"
            success = self._speak(text_with_intro, voice_id)

            # Check if skip was requested (speech was interrupted but we should continue)
            if self.skip_requested:
                self.skip_requested = False
                self.current_index += 1
                continue

            if not success or self.stop_event.is_set():
                break

            # Move to next item (only if not paused mid-speech)
            if not self.is_paused:
                self.current_index += 1

        # Playback finished
        self.is_playing = False
        self._cleanup_audio_file()
        if self.status_callback and not self.stop_event.is_set():
            self.status_callback("Finished reading")

    def _speak(self, text: str, voice_id: str) -> bool:
        """
        Speak text using edge-tts and pygame.

        Args:
            text: The text to speak.
            voice_id: The edge-tts voice ID to use.

        Returns:
            True if speech completed successfully, False if interrupted.
        """
        try:
            # Clean up previous audio file
            self._cleanup_audio_file()

            # Create temp file for audio
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
                self.current_audio_file = f.name

            # Generate speech using edge-tts (async, so we run in event loop)
            asyncio.run(self._generate_speech(text, voice_id, self.current_audio_file))

            # Check if stopped during generation
            if self.stop_event.is_set():
                return False

            # Play the audio
            pygame.mixer.music.load(self.current_audio_file)
            pygame.mixer.music.play()

            # Wait for playback to complete
            while pygame.mixer.music.get_busy():
                if self.stop_event.is_set():
                    pygame.mixer.music.stop()
                    return False
                if self.is_paused:
                    # Wait while paused
                    self.pause_event.wait()
                    if self.stop_event.is_set():
                        return False
                pygame.time.wait(100)

            return True

        except Exception as e:
            print(f"Speech error: {e}")
            return False

    async def _generate_speech(self, text: str, voice_id: str, output_file: str):
        """
        Generate speech audio using edge-tts.

        Args:
            text: The text to convert to speech.
            voice_id: The edge-tts voice ID.
            output_file: Path to save the audio file.
        """
        communicate = edge_tts.Communicate(text, voice_id)
        await communicate.save(output_file)


class MoltReaderApp:
    """
    Main application class for MoltReader.

    Creates the GUI and coordinates all components:
    - URL input field
    - Audio controls (Play, Pause, Skip, Stop, Quit)
    - Status display
    """

    def __init__(self):
        # Initialize components
        self.voice_manager = EdgeTTSVoiceManager()
        self.scraper = MoltbookScraper()
        self.tts_engine = TextToSpeechEngine(self.voice_manager)

        # Set up TTS callbacks for status and text display
        self.tts_engine.status_callback = self._update_status
        self.tts_engine.text_callback = self._update_current_text

        # Create main window
        self.root = tk.Tk()
        self.root.title("MoltReader - Moltbook Text-to-Speech")
        self.root.geometry("600x450")
        self.root.minsize(500, 400)

        # Configure grid weights for resizing
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(3, weight=1)  # Text area gets most space

        # Build UI
        self._create_widgets()

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_quit)

    def _create_widgets(self):
        """Create all UI widgets."""
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.columnconfigure(1, weight=1)

        # --- URL Input Section ---
        url_frame = ttk.LabelFrame(main_frame, text="Moltbook URL", padding="5")
        url_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        url_frame.columnconfigure(0, weight=1)

        # URL entry field
        self.url_var = tk.StringVar()
        self.url_entry = ttk.Entry(url_frame, textvariable=self.url_var, font=('TkDefaultFont', 12))
        self.url_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        # Load button
        self.load_btn = ttk.Button(url_frame, text="Load", command=self._on_load)
        self.load_btn.grid(row=0, column=1)

        # Default URL
        self.url_entry.insert(0, "https://www.moltbook.com/post/39a5bb00-3de9-4b0a-bfa2-314dc643fdb3")

        # --- Audio Controls Section ---
        controls_frame = ttk.LabelFrame(main_frame, text="Audio Controls", padding="10")
        controls_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        # Center the buttons
        controls_frame.columnconfigure(0, weight=1)
        controls_frame.columnconfigure(6, weight=1)

        # Play button
        self.play_btn = ttk.Button(
            controls_frame,
            text="▶ Play",
            command=self._on_play,
            width=10
        )
        self.play_btn.grid(row=0, column=1, padx=5)

        # Pause button
        self.pause_btn = ttk.Button(
            controls_frame,
            text="⏸ Pause",
            command=self._on_pause,
            width=10
        )
        self.pause_btn.grid(row=0, column=2, padx=5)

        # Skip button
        self.skip_btn = ttk.Button(
            controls_frame,
            text="⏭ Skip",
            command=self._on_skip,
            width=10
        )
        self.skip_btn.grid(row=0, column=3, padx=5)

        # Stop button
        self.stop_btn = ttk.Button(
            controls_frame,
            text="⏹ Stop",
            command=self._on_stop,
            width=10
        )
        self.stop_btn.grid(row=0, column=4, padx=5)

        # Quit button
        self.quit_btn = ttk.Button(
            controls_frame,
            text="✕ Quit",
            command=self._on_quit,
            width=10
        )
        self.quit_btn.grid(row=0, column=5, padx=5)

        # --- Status Section (compact, for speaker/voice info) ---
        status_frame = ttk.LabelFrame(main_frame, text="Now Playing", padding="5")
        status_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        status_frame.columnconfigure(0, weight=1)

        # Status label (single line for speaker info)
        self.status_var = tk.StringVar(value="Ready. Paste a Moltbook URL and click Load.")
        self.status_label = ttk.Label(
            status_frame,
            textvariable=self.status_var,
            font=('TkDefaultFont', 11),
            wraplength=550
        )
        self.status_label.grid(row=0, column=0, sticky="ew")

        # --- Current Text Section (larger, for post/comment content) ---
        text_frame = ttk.LabelFrame(main_frame, text="Current Text", padding="5")
        text_frame.grid(row=3, column=0, columnspan=2, sticky="nsew")
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(3, weight=1)

        # Text display area
        self.current_text = tk.Text(
            text_frame,
            height=10,
            state='disabled',
            font=('TkDefaultFont', 11),
            wrap='word'
        )
        self.current_text.grid(row=0, column=0, sticky="nsew")

        # Scrollbar for text
        scrollbar = ttk.Scrollbar(text_frame, orient='vertical', command=self.current_text.yview)
        scrollbar.grid(row=0, column=1, sticky='ns')
        self.current_text.configure(yscrollcommand=scrollbar.set)

    def _on_load(self):
        """Handle Load button click - fetch and parse the Moltbook page."""
        url = self.url_var.get().strip()

        if not url:
            messagebox.showwarning("No URL", "Please enter a Moltbook URL.")
            return

        self._update_status(f"Loading: {url}")

        # Fetch in background to keep UI responsive
        def fetch_thread():
            content, error = self.scraper.fetch_page(url)

            # Update UI from main thread
            self.root.after(0, lambda: self._on_fetch_complete(content, error))

        threading.Thread(target=fetch_thread, daemon=True).start()

    def _on_fetch_complete(self, content: List[Tuple[str, str]], error: Optional[str]):
        """Handle completion of page fetch."""
        if error:
            self._update_status(f"Error: {error}")
            messagebox.showerror("Load Error", error)
            return

        # Set content in TTS engine
        self.tts_engine.set_content(content)
        self.voice_manager.reset()

        # Show summary in status
        self._update_status(f"Loaded {len(content)} items. Click Play to start.")

        # Show first item preview in text area
        if content:
            author, text = content[0]
            self._update_current_text(f"[First item by {author}]\n\n{text}")

    def _on_play(self):
        """Handle Play button click."""
        if not self.tts_engine.content_queue:
            messagebox.showwarning("No Content", "Please load a Moltbook page first.")
            return

        self.tts_engine.play()
        self._update_status("Playing...")

    def _on_pause(self):
        """Handle Pause button click."""
        if self.tts_engine.is_playing:
            if self.tts_engine.is_paused:
                self.tts_engine.play()  # Resume
                self._update_status("Resumed")
            else:
                self.tts_engine.pause()
                self._update_status("Paused")

    def _on_stop(self):
        """Handle Stop button click - stop and reset to beginning."""
        self.tts_engine.stop()
        self._update_status("Stopped. Ready to play from beginning.")
        self._update_current_text("")  # Clear the text display

    def _on_skip(self):
        """Handle Skip button click - skip to next item."""
        if self.tts_engine.is_playing:
            self.tts_engine.skip()
            self._update_status("Skipping...")

    def _on_quit(self):
        """Handle Quit button or window close."""
        self.tts_engine.stop()
        pygame.mixer.quit()
        self.root.destroy()

    def _update_status(self, message: str):
        """
        Update the status label (speaker/voice info).

        Args:
            message: Status message to display.
        """
        self.status_var.set(message)

    def _update_current_text(self, text: str):
        """
        Update the current text display area.

        Args:
            text: The post/comment text being read.
        """
        self.current_text.configure(state='normal')
        self.current_text.delete(1.0, tk.END)
        self.current_text.insert(tk.END, text)
        self.current_text.configure(state='disabled')
        self.current_text.see("1.0")  # Scroll to top

    def run(self):
        """Start the application main loop."""
        self.root.mainloop()


def main():
    """Entry point for MoltReader application."""
    print("Starting MoltReader...")
    print(f"Available voices: {len(EdgeTTSVoiceManager().available_voices)} neural voices")

    app = MoltReaderApp()
    app.run()


if __name__ == "__main__":
    main()
