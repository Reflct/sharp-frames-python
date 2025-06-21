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
        self._last_action_time = 0
        self._original_signal_handlers = {}
        super().__init__(**kwargs)
    
    def setup_signal_handlers(self):
        """Solution 1: Setup signal handlers for macOS compatibility.
        
        Note: These handlers only affect the main app process, not subprocesses.
        We store original handlers so we can restore them when running subprocesses.
        """
        def signal_handler(signum, frame):
            self.log.info(f"Received signal {signum} in main app, ignoring to prevent premature exit")
            # Don't exit, just log - but only for the main app process
        
        # Handle common signals that might cause issues on macOS
        # Only register signals that exist on the current platform
        signals_to_handle = []
        
        try:
            if hasattr(signal, 'SIGTERM'):
                signals_to_handle.append(signal.SIGTERM)
        except AttributeError:
            pass
        
        try:
            if hasattr(signal, 'SIGHUP'):
                signals_to_handle.append(signal.SIGHUP)
        except AttributeError:
            pass  # Signal not available on this platform (Windows)
        
        try:
            if hasattr(signal, 'SIGPIPE'):
                signals_to_handle.append(signal.SIGPIPE)
        except AttributeError:
            pass  # Signal not available on this platform (Windows)
        
        # Install handlers and store originals
        for sig in signals_to_handle:
            try:
                self._original_signal_handlers[sig] = signal.signal(sig, signal_handler)
            except (ValueError, OSError):
                # Can't handle this signal in this context
                pass
    
    def restore_signal_handlers(self):
        """Restore original signal handlers before running subprocesses."""
        for sig, original_handler in self._original_signal_handlers.items():
            try:
                signal.signal(sig, original_handler)
            except (ValueError, OSError):
                pass
    
    def reinstall_signal_handlers(self):
        """Reinstall app signal handlers after subprocess completion."""
        self.setup_signal_handlers()
    
    def action_cancel(self) -> None:
        """Override cancel action to prevent spurious exits from ANSI sequences."""
        current_time = time.time()
        
        # If we just had escape sequences recently, this is likely spurious
        if current_time - self._last_escape_time < 2.0:  # Within 2 seconds of escape detection
            self.log.info(f"Blocking cancel action - likely triggered by spurious escape sequence (time since escape: {current_time - self._last_escape_time:.2f}s)")
            return
        
        # If we've had multiple recent actions, likely spurious
        if current_time - self._last_action_time < 0.5:  # Multiple actions within 500ms
            self.log.info("Blocking cancel action - too many rapid actions detected")
            return
        
        self._last_action_time = current_time
        
        # For now, block ALL cancel actions to prevent spurious exits
        # This is aggressive but necessary for macOS stability
        self.log.info("Blocking cancel action to prevent spurious app exit")
        return
        
        # When we want to allow legitimate cancels, uncomment this:
        # self.log.info("Processing legitimate cancel action")
        # self.exit("cancelled")
    
    def on_key(self, event: Key) -> None:
        """Solution 4: Handle and filter problematic key events."""
        current_time = time.time()
        
        # Check for escape sequences that are part of ANSI/mouse events
        if event.key == 'escape':
            self.log.info(f"Escape key detected - count: {self._escape_count + 1}, time_since_last: {current_time - self._last_escape_time:.2f}s")
            
            # If this is likely a spurious escape (part of ANSI sequence)
            if current_time - self._last_escape_time < 0.1:  # Less than 100ms
                self.log.info("Filtering out spurious escape sequence")
                event.stop()  # Stop event propagation completely
                return
            
            self._last_escape_time = current_time
            self._escape_count += 1
            
            # Only allow escape if it seems like a genuine user action
            if self._escape_count > 3:  # Too many escapes, likely spurious
                self.log.info("Too many escape sequences detected, filtering")
                event.stop()  # Stop event propagation completely
                return
            
            # For now, block ALL escape keys to prevent spurious exits
            # This is aggressive but necessary for macOS stability
            self.log.info("Blocking escape key to prevent spurious app exit")
            event.stop()  # Stop event propagation completely
            return
        
        # Filter out ANSI escape sequences that corrupt input
        if hasattr(event, 'character') and event.character:
            # Check for ANSI escape sequence patterns
            if re.match(r'[\x1b\x9b][\[\(].*[A-Za-z~]', event.character):
                self.log.info(f"Filtering ANSI escape sequence: {repr(event.character)}")
                event.stop()  # Stop event propagation completely
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