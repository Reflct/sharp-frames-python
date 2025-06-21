"""
Main Sharp Frames Textual application.
"""

import signal
import os
import time
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
            self.log(f"Received signal {signum}")
            # Don't exit immediately, let textual handle cleanup
            return
            
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGHUP, signal_handler)
        signal.signal(signal.SIGPIPE, signal_handler)
    
    def on_key(self, event: Key) -> None:
        """Filter out spurious escape sequences on macOS."""
        if event.key == "escape":
            current_time = time.time()
            
            # Check if this might be a spurious escape sequence
            if current_time - self._last_escape_time < 1.0:  # Multiple escapes within 1 second
                self._escape_count += 1
            else:
                self._escape_count = 1
            
            self._last_escape_time = current_time
            
            # Log the escape event for debugging
            self.log(f"Escape key detected - count: {self._escape_count}, time_since_last: {current_time - self._last_escape_time:.2f}s")
            
            # If we're getting rapid escape sequences, likely spurious - ignore them
            if self._escape_count > 1:
                self.log("Ignoring spurious escape sequence")
                event.prevent_default()
                return
        
        # Let the event continue normally
        super().on_key(event)
    
    def on_mount(self) -> None:
        """Start with the configuration form and setup signal handlers."""
        # Solution 1: Setup signal handlers
        self.setup_signal_handlers()
        
        # Solution 3: Add exception handling to mount
        try:
            self.theme = "flexoki"
            self.push_screen(ConfigurationForm())
            self.log("App mounted successfully - monitoring for spurious escape sequences")
        except Exception as e:
            self.log(f"Error during mount: {e}")
            self.notify(f"Mount error: {e}", severity="error") 