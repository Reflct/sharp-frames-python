"""
Updated configuration screen for Sharp Frames UI - Two Phase Processing.
Removes selection method configuration (moved to post-extraction SelectionScreen).
"""

import os
from typing import Dict, Any

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import (
    Header, Footer, Button, Input, Select, RadioSet, RadioButton,
    Checkbox, Label, Static
)
from textual.screen import Screen
from textual.binding import Binding

from ..constants import UIElementIds, InputTypes
from ..components.v2_step_handlers import (
    InputTypeStepHandler,
    InputPathStepHandler,
    OutputDirStepHandler,
    FpsStepHandler,
    OutputFormatStepHandler,
    WidthStepHandler,
    ForceOverwriteStepHandler,
    ConfirmStepHandler,
    ValidationHelpers
)


class TwoPhaseConfigurationForm(Screen):
    """Configuration form for Sharp Frames two-phase processing (selection method removed)."""
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+c", "cancel", "Cancel"),
        Binding("f1", "help", "Help", show=True),
    ]
    
    def __init__(self):
        super().__init__()
        self.config_data = {}
        self.current_step = 0
        
        # Updated step list - selection method removed
        self.steps = [
            "input_type",
            "input_path", 
            "output_dir",
            "fps",  # Only shown for video
            "output_format",
            "width",
            "force_overwrite",
            "confirm"
        ]
        
        # Initialize step handlers (excluding selection-related ones)
        self.step_handlers = {}
        self._initialize_step_handlers()
    
    def _initialize_step_handlers(self):
        """Initialize step handlers for the configuration process."""
        # Create step handlers for each configuration step
        self.step_handlers = {
            "input_type": InputTypeStepHandler(),
            "input_path": InputPathStepHandler(),
            "output_dir": OutputDirStepHandler(),
            "fps": FpsStepHandler(),
            "output_format": OutputFormatStepHandler(),
            "width": WidthStepHandler(),
            "force_overwrite": ForceOverwriteStepHandler(),
            "confirm": ConfirmStepHandler()
        }
        
        # Set up validation helpers
        self.validation_helpers = ValidationHelpers()
    
    def compose(self) -> ComposeResult:
        """Create the configuration layout."""
        yield Header()
        
        with Container(id="configuration-container"):
            yield Static("Sharp Frames Configuration", classes="title")
            yield Static("", id="step-title", classes="step-title")
            yield Static("", id="step-description", classes="step-description")
            
            # Dynamic content container for step-specific widgets
            with Container(id="step-content"):
                pass
            
            # Navigation buttons
            with Horizontal(id="navigation-buttons", classes="button-row"):
                yield Button("← Back", id="back-button", variant="default")
                yield Button("Next →", id="next-button", variant="primary")
                yield Button("Cancel", id="cancel-button", variant="error")
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Initialize the form when mounted."""
        self._render_current_step()
        self._update_navigation_buttons()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "next-button":
            self._handle_next()
        elif event.button.id == "back-button":
            self._handle_back()
        elif event.button.id == "cancel-button":
            self.action_cancel()
    
    def _handle_next(self) -> None:
        """Handle next button press."""
        current_step_name = self.steps[self.current_step]
        handler = self.step_handlers[current_step_name]
        
        # Validate current step
        if not handler.validate(self):
            return  # Validation failed, stay on current step
        
        # Save step data
        step_data = handler.get_data(self)
        self.config_data.update(step_data)
        
        if current_step_name == "confirm":
            # Final step - start processing
            self._start_processing()
        else:
            # Move to next step
            self.current_step += 1
            self._render_current_step()
            self._update_navigation_buttons()
    
    def _handle_back(self) -> None:
        """Handle back button press."""
        if self.current_step > 0:
            self.current_step -= 1
            self._render_current_step()
            self._update_navigation_buttons()
    
    def _render_current_step(self) -> None:
        """Render the current configuration step."""
        step_name = self.steps[self.current_step]
        handler = self.step_handlers[step_name]
        
        # Update step title and description
        self.query_one("#step-title").update(handler.get_title())
        self.query_one("#step-description").update(handler.get_description())
        
        # Clear and populate step content
        step_content = self.query_one("#step-content")
        step_content.remove_children()
        
        # Let handler create its widgets
        handler.render(self, step_content)
        
        # Pre-populate with existing data if available
        if step_name in self.config_data:
            handler.set_data(self, self.config_data[step_name])
    
    def _update_navigation_buttons(self) -> None:
        """Update navigation button states."""
        back_button = self.query_one("#back-button")
        next_button = self.query_one("#next-button")
        
        # Back button
        back_button.disabled = (self.current_step == 0)
        
        # Next button label
        if self.current_step == len(self.steps) - 1:  # Last step
            next_button.label = "Start Processing"
        else:
            next_button.label = "Next →"
        
        # Step visibility logic for FPS step
        if self.steps[self.current_step] == "fps":
            # Only show FPS step for video inputs
            input_type = self.config_data.get("input_type")
            if input_type not in ["video", "video_directory"]:
                # Skip FPS step for non-video inputs
                if self.current_step < len(self.steps) - 1:
                    self.current_step += 1
                    self._render_current_step()
                    self._update_navigation_buttons()
                    return
    
    def _start_processing(self) -> None:
        """Start the processing with collected configuration."""
        # Import here to avoid circular imports
        from .processing_v2 import TwoPhaseProcessingScreen
        
        try:
            # Validate final configuration
            if not self._validate_final_config():
                return
            
            # Create and push processing screen
            processing_screen = TwoPhaseProcessingScreen(self.config_data)
            self.app.push_screen(processing_screen)
            
        except Exception as e:
            self.app.log.error(f"Error starting processing: {e}")
            # Show error message to user
            self.query_one("#step-description").update(f"Error starting processing: {str(e)}")
    
    def _validate_final_config(self) -> bool:
        """Perform final validation of the complete configuration."""
        required_fields = ["input_type", "input_path", "output_dir", "output_format"]
        
        for field in required_fields:
            if field not in self.config_data or not self.config_data[field]:
                self.query_one("#step-description").update(f"Missing required field: {field}")
                return False
        
        # Validate input path exists
        if not os.path.exists(self.config_data["input_path"]):
            self.query_one("#step-description").update("Input path does not exist")
            return False
        
        # Set default values for optional fields
        self.config_data.setdefault("fps", 10)
        self.config_data.setdefault("width", 0)
        self.config_data.setdefault("force_overwrite", False)
        
        return True
    
    def action_cancel(self) -> None:
        """Cancel configuration and return to main screen."""
        self.app.pop_screen()
    
    def action_help(self) -> None:
        """Show help information."""
        current_step_name = self.steps[self.current_step]
        handler = self.step_handlers[current_step_name]
        
        help_text = handler.get_help_text() if hasattr(handler, 'get_help_text') else """
# Sharp Frames Configuration Help

This wizard will guide you through configuring Sharp Frames for two-phase processing:

## Phase 1: Extraction & Analysis
- Extract frames from videos or load images from directories
- Calculate sharpness scores for all frames
- Prepare data for interactive selection

## Phase 2: Interactive Selection  
- Choose selection method and parameters interactively
- See real-time preview of how many frames will be selected
- Adjust parameters and see immediate feedback

## Configuration Steps:
1. **Input Type**: Choose video, video directory, or image directory
2. **Input Path**: Select the path to your input
3. **Output Directory**: Choose where to save selected frames  
4. **FPS**: Frame extraction rate (video inputs only)
5. **Output Format**: Image format for saved frames
6. **Width**: Resize width (0 for original size)
7. **Force Overwrite**: Overwrite existing files without asking
8. **Confirm**: Review settings and start processing

The selection method will be chosen interactively after frame analysis is complete.
        """
        
        self.app.push_screen("help", help_text)
    
    def get_current_step_name(self) -> str:
        """Get the name of the current step."""
        return self.steps[self.current_step]
    
    def get_config_data(self) -> Dict[str, Any]:
        """Get current configuration data."""
        return self.config_data.copy()
    
    def set_config_data(self, key: str, value: Any) -> None:
        """Set configuration data for a key."""
        self.config_data[key] = value
    
    def get_step_progress(self) -> tuple:
        """Get current step progress as (current, total)."""
        return (self.current_step + 1, len(self.steps))


# Create alias for backward compatibility
ConfigurationFormV2 = TwoPhaseConfigurationForm