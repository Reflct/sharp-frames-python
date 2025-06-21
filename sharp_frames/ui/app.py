"""
Main Sharp Frames Textual application.
"""

from textual.app import App

from .screens import ConfigurationForm
from .styles import SHARP_FRAMES_CSS


class SharpFramesApp(App):
    """Main Sharp Frames Textual application."""
    
    CSS = SHARP_FRAMES_CSS
    TITLE = "Sharp Frames - by Reflct.app"
    
    def on_mount(self) -> None:
        """Start with the configuration form."""
        self.theme = "flexoki"
        self.push_screen(ConfigurationForm()) 