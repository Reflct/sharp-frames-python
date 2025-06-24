"""
Main Sharp Frames Textual application.
"""

import signal
import os
import time
import re
from textual.app import App
from textual.events import Key, Paste
from textual.widgets import Input

from .screens import ConfigurationForm
from .styles import SHARP_FRAMES_CSS
from .utils import sanitize_path_input


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
        # Check if we're in a screen that wants to handle its own cancellation
        current_screen = self.screen_stack[-1] if self.screen_stack else None
        
        # If the current screen has its own action_cancel method, delegate to it
        if current_screen and hasattr(current_screen, 'action_cancel') and callable(getattr(current_screen, 'action_cancel')):
            # Only delegate to ProcessingScreen - ConfigurationForm handles its own cancellation directly
            if 'ProcessingScreen' in str(type(current_screen)):
                self.log.info("Delegating cancel action to ProcessingScreen")
                current_screen.action_cancel()
                return
        
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
        
        # Allow legitimate cancel actions
        self.log.info("Processing legitimate cancel action")
        self.exit("cancelled")
    
    def on_key(self, event: Key) -> None:
        """Solution 4: Handle and filter problematic key events."""
        current_time = time.time()
        
        # Allow Ctrl+C to pass through if it's legitimate
        if event.key == 'ctrl+c':
            self.log.info("Ctrl+C detected - allowing through for cancellation")
            return  # Let it propagate normally
        
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
            
            # Allow legitimate escape keys to pass through
            self.log.info("Allowing legitimate escape key through")
            return  # Let it propagate normally
        
        # Filter out ANSI escape sequences that corrupt input
        if hasattr(event, 'character') and event.character:
            # Check for ANSI escape sequence patterns
            if re.match(r'[\x1b\x9b][\[\(].*[A-Za-z~]', event.character):
                self.log.info(f"Filtering ANSI escape sequence: {repr(event.character)}")
                event.stop()  # Stop event propagation completely
                return
    
    def on_paste(self, event: Paste) -> None:
        """Handle paste events, including drag-and-drop file paths."""
        pasted_text = event.text.strip()
        
        # Skip empty pastes
        if not pasted_text:
            return
        
        # Try to detect if this looks like a file path
        if self._is_file_path(pasted_text):
            self.log.info(f"Detected potential file path in paste: {pasted_text}")
            
            # Sanitize the path using our existing infrastructure
            sanitized_path = sanitize_path_input(pasted_text)
            
            if sanitized_path and self._route_file_path(sanitized_path):
                # Successfully routed to input field, prevent default paste
                event.stop()
                return
        
        # Let normal paste behavior continue for non-file content
        self.log.info(f"Normal paste event: {pasted_text[:50]}..." if len(pasted_text) > 50 else f"Normal paste event: {pasted_text}")
    
    def _is_file_path(self, text: str) -> bool:
        """Simple heuristic to detect if pasted text is likely a file path."""
        # Skip if too long (likely not a single file path)
        if len(text) > 500:
            return False
        
        # Skip if contains multiple lines (likely not a single file path)
        if '\n' in text or '\r' in text:
            return False
        
        # Common file path patterns
        path_patterns = [
            r'^[A-Za-z]:[\\\/]',  # Windows drive letters
            r'^[\\\/]',           # Unix-style absolute paths
            r'^~[\\\/]',          # Home directory paths
            r'^\.',               # Relative paths starting with .
        ]
        
        # Check for path-like patterns
        for pattern in path_patterns:
            if re.match(pattern, text):
                return True
        
        # Check for common file extensions
        common_extensions = [
            '.mp4', '.avi', '.mov', '.mkv', '.webm', '.m4v',  # Video
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp',  # Images
        ]
        
        text_lower = text.lower()
        for ext in common_extensions:
            if text_lower.endswith(ext):
                return True
        
        # Check if it's an existing path
        try:
            # Expand user path and check existence
            expanded_path = os.path.expanduser(text)
            if os.path.exists(expanded_path):
                return True
        except (OSError, ValueError):
            pass
        
        return False
    
    def _route_file_path(self, file_path: str) -> bool:
        """Route detected file path to appropriate input field based on current context."""
        try:
            # Get current screen
            current_screen = self.screen_stack[-1] if self.screen_stack else None
            
            # Only handle ConfigurationForm for now
            if not isinstance(current_screen, ConfigurationForm):
                self.log.info("Not on configuration screen, skipping file path routing")
                return False
            
            # Determine target input based on current step
            target_input_id = self._get_target_input_for_step(current_screen, file_path)
            
            if target_input_id:
                # Find and update the target input
                try:
                    input_widget = current_screen.query_one(f"#{target_input_id}", Input)
                    input_widget.value = file_path
                    input_widget.focus()
                    
                    self.log.info(f"Successfully routed file path to {target_input_id}: {file_path}")
                    return True
                    
                except Exception as e:
                    self.log.warning(f"Could not find or update input {target_input_id}: {e}")
            
        except Exception as e:
            self.log.error(f"Error routing file path: {e}")
        
        return False
    
    def _get_target_input_for_step(self, config_screen: ConfigurationForm, file_path: str) -> str:
        """Determine which input field should receive the file path based on current step."""
        current_step = config_screen.steps[config_screen.current_step]
        
        # Check what type of path this is
        is_directory = os.path.isdir(file_path) if os.path.exists(file_path) else file_path.endswith(('/', '\\'))
        is_video = any(file_path.lower().endswith(ext) for ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.m4v'])
        is_image = any(file_path.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'])
        
        # Import UIElementIds here to avoid circular imports
        from .constants import UIElementIds
        
        # Route based on current step and file type
        if current_step == "input_path":
            # Input path step - route based on file type and current input type selection
            input_type = config_screen.config_data.get("input_type")
            if input_type == "video" and (is_video or is_directory):
                return UIElementIds.INPUT_PATH_FIELD
            elif input_type == "video_directory" and is_directory:
                return UIElementIds.INPUT_PATH_FIELD
            elif input_type == "image_directory" and is_directory:
                return UIElementIds.INPUT_PATH_FIELD
            elif not input_type:  # No input type selected yet, accept any
                return UIElementIds.INPUT_PATH_FIELD
        
        elif current_step == "output_dir":
            # Output directory step - only accept directories
            if is_directory or not os.path.exists(file_path):  # Accept non-existent paths as potential output dirs
                return UIElementIds.OUTPUT_DIR_FIELD
        
        # For other steps, be more conservative
        elif current_step == "input_type":
            # If on input type selection, accept file paths to help determine type
            return UIElementIds.INPUT_PATH_FIELD if any([is_video, is_image, is_directory]) else None
        
        self.log.info(f"No appropriate input found for step {current_step}, file type: directory={is_directory}, video={is_video}, image={is_image}")
        return None
    
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