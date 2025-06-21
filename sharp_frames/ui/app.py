"""
Main Sharp Frames Textual application.
"""

import signal
import os
from textual.app import App

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
    
    async def on_load(self) -> None:
        """Solution 3: Handle app loading with better error handling."""
        try:
            await super().on_load()
        except Exception as e:
            self.log(f"Error during app load: {e}")
            self.notify(f"Error: {e}", severity="error")
    
    def on_mount(self) -> None:
        """Start with the configuration form and setup signal handlers."""
        # Solution 1: Setup signal handlers
        self.setup_signal_handlers()
        
        # Solution 3: Add exception handling to mount
        try:
            self.theme = "flexoki"
            self.push_screen(ConfigurationForm())
        except Exception as e:
            self.log(f"Error during mount: {e}")
            self.notify(f"Mount error: {e}", severity="error") 