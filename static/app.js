/**
 * MoltReader Web App - Frontend JavaScript
 */

class MoltReaderApp {
    constructor() {
        // DOM Elements
        this.urlInput = document.getElementById('url-input');
        this.loadBtn = document.getElementById('load-btn');
        this.playBtn = document.getElementById('play-btn');
        this.pauseBtn = document.getElementById('pause-btn');
        this.skipBtn = document.getElementById('skip-btn');
        this.stopBtn = document.getElementById('stop-btn');
        this.statusEl = document.getElementById('status');
        this.currentTextEl = document.getElementById('current-text');
        this.progressFill = document.getElementById('progress-fill');
        this.progressText = document.getElementById('progress-text');
        this.audioPlayer = document.getElementById('audio-player');

        // State
        this.items = [];
        this.currentIndex = 0;
        this.isPlaying = false;
        this.isPaused = false;

        // Bind event handlers
        this.loadBtn.addEventListener('click', () => this.loadUrl());
        this.playBtn.addEventListener('click', () => this.play());
        this.pauseBtn.addEventListener('click', () => this.togglePause());
        this.skipBtn.addEventListener('click', () => this.skip());
        this.stopBtn.addEventListener('click', () => this.stop());

        // Audio events
        this.audioPlayer.addEventListener('ended', () => this.onAudioEnded());
        this.audioPlayer.addEventListener('error', (e) => this.onAudioError(e));

        // Enter key to load
        this.urlInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.loadUrl();
        });
    }

    setStatus(message) {
        this.statusEl.textContent = message;
    }

    setCurrentText(text) {
        this.currentTextEl.textContent = text;
    }

    updateProgress() {
        const total = this.items.length;
        const current = this.currentIndex + 1;
        const percent = total > 0 ? (current / total) * 100 : 0;

        this.progressFill.style.width = `${percent}%`;
        this.progressText.textContent = `${current} / ${total}`;
    }

    enableControls(enabled) {
        this.playBtn.disabled = !enabled;
        this.pauseBtn.disabled = !enabled;
        this.skipBtn.disabled = !enabled;
        this.stopBtn.disabled = !enabled;
    }

    async loadUrl() {
        const url = this.urlInput.value.trim();
        if (!url) {
            this.setStatus('Please enter a Moltbook URL.');
            return;
        }

        // Stop any current playback
        this.stop();

        this.setStatus('Loading page...');
        this.loadBtn.disabled = true;
        this.loadBtn.classList.add('loading');

        try {
            const response = await fetch('/api/load', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to load page');
            }

            this.items = data.items;
            this.currentIndex = 0;

            this.setStatus(`Loaded ${data.item_count} items. Click Play to start.`);
            this.updateProgress();
            this.enableControls(true);

            // Show preview of first item
            if (this.items.length > 0) {
                const first = this.items[0];
                this.setCurrentText(`[First item by ${first.author}]\n\n${first.text}`);
            }

        } catch (error) {
            this.setStatus(`Error: ${error.message}`);
        } finally {
            this.loadBtn.disabled = false;
            this.loadBtn.classList.remove('loading');
        }
    }

    play() {
        if (this.items.length === 0) {
            this.setStatus('Please load a Moltbook page first.');
            return;
        }

        if (this.isPaused) {
            // Resume from pause
            this.isPaused = false;
            this.audioPlayer.play();
            this.pauseBtn.textContent = 'Pause';
            this.setStatus(`Playing: ${this.items[this.currentIndex].author}`);
            return;
        }

        if (this.isPlaying) {
            return;
        }

        this.isPlaying = true;
        this.playCurrentItem();
    }

    playCurrentItem() {
        if (this.currentIndex >= this.items.length) {
            this.onPlaybackComplete();
            return;
        }

        const item = this.items[this.currentIndex];
        this.setStatus(`[${this.currentIndex + 1}/${this.items.length}] ${item.author} (voice: ${item.voice_name})`);
        this.setCurrentText(item.text);
        this.updateProgress();

        // Load and play audio
        this.audioPlayer.src = `/api/audio/${this.currentIndex}`;
        this.audioPlayer.play().catch(e => {
            console.error('Playback error:', e);
            this.setStatus(`Error playing audio: ${e.message}`);
        });
    }

    togglePause() {
        if (!this.isPlaying) return;

        if (this.isPaused) {
            // Resume
            this.isPaused = false;
            this.audioPlayer.play();
            this.pauseBtn.textContent = 'Pause';
            this.setStatus(`Playing: ${this.items[this.currentIndex].author}`);
        } else {
            // Pause
            this.isPaused = true;
            this.audioPlayer.pause();
            this.pauseBtn.textContent = 'Resume';
            this.setStatus('Paused');
        }
    }

    skip() {
        if (!this.isPlaying || this.items.length === 0) return;

        this.audioPlayer.pause();
        this.currentIndex++;

        if (this.currentIndex >= this.items.length) {
            this.onPlaybackComplete();
        } else {
            this.isPaused = false;
            this.pauseBtn.textContent = 'Pause';
            this.playCurrentItem();
        }
    }

    stop() {
        this.audioPlayer.pause();
        this.audioPlayer.currentTime = 0;
        this.audioPlayer.src = '';

        this.isPlaying = false;
        this.isPaused = false;
        this.currentIndex = 0;

        this.pauseBtn.textContent = 'Pause';
        this.setStatus('Stopped. Ready to play from beginning.');
        this.setCurrentText('');

        if (this.items.length > 0) {
            this.progressFill.style.width = '0%';
            this.progressText.textContent = `0 / ${this.items.length}`;
        }
    }

    onAudioEnded() {
        if (!this.isPlaying || this.isPaused) return;

        this.currentIndex++;

        if (this.currentIndex >= this.items.length) {
            this.onPlaybackComplete();
        } else {
            this.playCurrentItem();
        }
    }

    onAudioError(e) {
        // Ignore errors when not playing (e.g., when stop() clears the source)
        if (!this.isPlaying) return;

        console.error('Audio error:', e);
        this.setStatus('Error loading audio. Trying next item...');

        // Try to continue with next item
        setTimeout(() => {
            if (this.isPlaying) {
                this.currentIndex++;
                if (this.currentIndex < this.items.length) {
                    this.playCurrentItem();
                } else {
                    this.onPlaybackComplete();
                }
            }
        }, 1000);
    }

    onPlaybackComplete() {
        this.isPlaying = false;
        this.isPaused = false;
        this.currentIndex = 0;
        this.pauseBtn.textContent = 'Pause';
        this.setStatus('Finished reading all items.');
        this.progressFill.style.width = '100%';
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.app = new MoltReaderApp();
});
