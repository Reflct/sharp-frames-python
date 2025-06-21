"""
Main Sharp Frames Textual application.
"""

import signal
import os
import time
import re
from textual.app import App
from textual.events import Key

from .screens import ConfigurationForm
from .styles import SHARP_FRAMES_CSS


class SharpFramesApp(App):
    """Main Sharp Frames Textual application."""
    
    CSS = SHARP_FRAMES_CSS
    TITLE = "Sharp Frames - by Reflct.app"
    
    def __init__(self, **kwargs):
        """Initialize app with macOS compatibility fixes."""
        # Solution 2: Force specific terminal driver for macOS
        if os.name == 'posix':  # macOS/Linux
            os.environ['TEXTUAL_DRIVER'] = 'linux'
        
        # Track spurious escape sequences
        self._last_escape_time = 0
        self._escape_count = 0
        super().__init__(**kwargs)
    
    def setup_signal_handlers(self):
        """Solution 1: Setup signal handlers for macOS compatibility."""
        def signal_handler(signum, frame):
            self.log.info(f"Received signal {signum}, ignoring to prevent premature exit")
            # Don't exit, just log
        
        # Handle common signals that might cause issues on macOS
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGHUP, signal_handler)
        signal.signal(signal.SIGPIPE, signal_handler)
    
    def on_key(self, event: Key) -> None:
        """Solution 4: Handle and filter problematic key events."""
        current_time = time.time()
        
        # Check for escape sequences that are part of ANSI/mouse events
        if event.key == 'escape':
            self.log.info(f"Escape key detected - count: {self._escape_count + 1}, time_since_last: {current_time - self._last_escape_time:.2f}s")
            
            # If this is likely a spurious escape (part of ANSI sequence)
            if current_time - self._last_escape_time < 0.1:  # Less than 100ms
                self.log.info("Filtering out spurious escape sequence")
                event.prevent_default()
                return
            
            self._last_escape_time = current_time
            self._escape_count += 1
            
            # Only allow escape if it seems like a genuine user action
            if self._escape_count > 3:  # Too many escapes, likely spurious
                self.log.info("Too many escape sequences detected, filtering")
                event.prevent_default()
                return
        
        # Filter out ANSI escape sequences that corrupt input
        if hasattr(event, 'character') and event.character:
            # Check for ANSI escape sequence patterns
            if re.match(r'[\x1b\x9b][\[\(].*[A-Za-z~]', event.character):
                self.log.info(f"Filtering ANSI escape sequence: {repr(event.character)}")
                event.prevent_default()
                return
    
    def on_mount(self) -> None:
        """Start with the configuration form and setup signal handlers."""
        try:
            self.setup_signal_handlers()
            self.theme = "flexoki"
            self.push_screen(ConfigurationForm())
            self.log.info("App mounted successfully - monitoring for spurious escape sequences")
        except Exception as e:
            self.log.error(f"Error during mount: {e}")
            self.notify(f"Error starting app: {e}", severity="error") 