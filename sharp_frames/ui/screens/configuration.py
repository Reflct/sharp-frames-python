"""
Configuration screen for Sharp Frames UI.
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
from textual.events import Key

from ..utils import sanitize_path_input

from ..constants import UIElementIds, InputTypes
from ..components.step_handlers import (
    InputTypeStepHandler,
    InputPathStepHandler,
    OutputDirStepHandler,
    FpsStepHandler,
    OutputFormatStepHandler,
    WidthStepHandler,
    ForceOverwriteStepHandler,
    ConfirmStepHandler
)
from ..components.validators import ValidationHelpers


class ConfigurationForm(Screen):
    """Configuration form for Sharp Frames processing (selection method removed)."""
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+c", "cancel", "Cancel"),
        Binding("f1", "help", "Help", show=True),
        Binding("enter", "next_step", "Next", show=False),
    ]
    
    def __init__(self):
        super().__init__()
        self.config_data = {}
        self.current_step = 0
        
        # Individual step list - each control on its own step
        self.steps = [
            "input_type",
            "input_path", 
            "output_dir",
            "fps",
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
        """Create the wizard layout - same style as legacy."""
        yield Header()
        ascii_title = """
███████[#2575E6]╗[/#2575E6]██[#2575E6]╗[/#2575E6]  ██[#2575E6]╗[/#2575E6] █████[#2575E6]╗[/#2575E6] ██████[#2575E6]╗[/#2575E6] ██████[#2575E6]╗[/#2575E6]     ███████[#2575E6]╗[/#2575E6]██████[#2575E6]╗[/#2575E6]  █████[#2575E6]╗[/#2575E6] ███[#2575E6]╗[/#2575E6]   ███[#2575E6]╗[/#2575E6]███████[#2575E6]╗[/#2575E6]███████[#2575E6]╗[/#2575E6]
██[#2575E6]╔[/#2575E6][#2575E6]════╝[/#2575E6]██[#2575E6]║[/#2575E6]  ██[#2575E6]║[/#2575E6]██[#2575E6]╔══[/#2575E6]██[#2575E6]╗[/#2575E6]██[#2575E6]╔══[/#2575E6]██[#2575E6]╗[/#2575E6]██[#2575E6]╔══[/#2575E6]██[#2575E6]╗[/#2575E6]    ██[#2575E6]╔[/#2575E6][#2575E6]════╝[/#2575E6]██[#2575E6]╔══[/#2575E6]██[#2575E6]╗[/#2575E6]██[#2575E6]╔══[/#2575E6]██[#2575E6]╗[/#2575E6]████[#2575E6]╗[/#2575E6] ████[#2575E6]║[/#2575E6]██[#2575E6]╔[/#2575E6][#2575E6]════╝[/#2575E6]██[#2575E6]╔[/#2575E6][#2575E6]════╝[/#2575E6]
███████[#2575E6]╗[/#2575E6]███████[#2575E6]║[/#2575E6]███████[#2575E6]║[/#2575E6]██████[#2575E6]╔╝[/#2575E6]██████[#2575E6]╔╝[/#2575E6]    █████[#2575E6]╗[/#2575E6]  ██████[#2575E6]╔╝[/#2575E6]███████[#2575E6]║[/#2575E6]██[#2575E6]╔[/#2575E6]████[#2575E6]╔[/#2575E6]██[#2575E6]║[/#2575E6]█████[#2575E6]╗[/#2575E6]  ███████[#2575E6]╗[/#2575E6]
[#2575E6]╚[/#2575E6][#2575E6]════[/#2575E6]██[#2575E6]║[/#2575E6]██[#2575E6]╔══[/#2575E6]██[#2575E6]║[/#2575E6]██[#2575E6]╔══[/#2575E6]██[#2575E6]║[/#2575E6]██[#2575E6]╔══[/#2575E6]██[#2575E6]╗[/#2575E6]██[#2575E6]╔═══╝[/#2575E6]     ██[#2575E6]╔══╝[/#2575E6]  ██[#2575E6]╔══[/#2575E6]██[#2575E6]╗[/#2575E6]██[#2575E6]╔══[/#2575E6]██[#2575E6]║[/#2575E6]██[#2575E6]║╚[/#2575E6]██[#2575E6]╔╝[/#2575E6]██[#2575E6]║[/#2575E6]██[#2575E6]╔══╝[/#2575E6]  [#2575E6]╚[/#2575E6][#2575E6]════[/#2575E6]██[#2575E6]║[/#2575E6]
███████[#2575E6]║[/#2575E6]██[#2575E6]║[/#2575E6]  ██[#2575E6]║[/#2575E6]██[#2575E6]║[/#2575E6]  ██[#2575E6]║[/#2575E6]██[#2575E6]║[/#2575E6]  ██[#2575E6]║[/#2575E6]██[#2575E6]║[/#2575E6]         ██[#2575E6]║[/#2575E6]     ██[#2575E6]║[/#2575E6]  ██[#2575E6]║[/#2575E6]██[#2575E6]║[/#2575E6]  ██[#2575E6]║[/#2575E6]██[#2575E6]║[/#2575E6] [#2575E6]╚═╝[/#2575E6] ██[#2575E6]║[/#2575E6]███████[#2575E6]╗[/#2575E6]███████[#2575E6]║[/#2575E6]
[#2575E6]╚══════╝╚═╝[/#2575E6]  [#2575E6]╚═╝╚═╝[/#2575E6]  [#2575E6]╚═╝╚═╝[/#2575E6]  [#2575E6]╚═╝╚═╝[/#2575E6]         [#2575E6]╚═╝[/#2575E6]     [#2575E6]╚═╝[/#2575E6]  [#2575E6]╚═╝╚═╝[/#2575E6]  [#2575E6]╚═╝╚═╝[/#2575E6]     [#2575E6]╚═╝╚══════╝╚══════╝[/#2575E6]
        """
        yield Static(ascii_title, classes="title")
        yield Static("", id="step-info", classes="step-info")
        yield Static("", id="step-description", classes="step-description")
        
        with Container(id="main-container"):
            yield Container(id="step-container")
        
        with Horizontal(classes="buttons"):
            yield Button("Back", variant="default", id="back-btn", disabled=True)
            yield Button("Next", variant="primary", id="next-btn")
            yield Button("Cancel", variant="default", id="cancel-btn")
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Set up the wizard when mounted."""
        self.show_current_step()
    
    def reset_to_first_step(self) -> None:
        """Reset the configuration form to the first step."""
        self.current_step = 0
        self.config_data = {}  # Clear previous configuration
        self.show_current_step()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events - same pattern as legacy."""
        if event.button.id == UIElementIds.NEXT_BTN:
            self._next_step()
        elif event.button.id == UIElementIds.BACK_BTN:
            self._back_step()
        elif event.button.id == UIElementIds.CANCEL_BTN:
            self.action_cancel()
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in Input fields - progress to next step."""
        self._next_step()
    
    def on_radio_set_changed(self, event) -> None:
        """Handle RadioSet selection change - allow Enter to progress."""
        # Don't auto-progress on selection change, just allow Enter to work
        pass
    
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes and sanitize file paths."""
        input_id = event.input.id
        
        # Path inputs that need sanitization
        path_inputs = ['input-path', 'output-dir-input']
        
        if input_id in path_inputs:
            current_value = event.value
            sanitized_value = sanitize_path_input(current_value)
            
            # Only update if sanitization changed the value
            if sanitized_value != current_value:
                event.input.value = sanitized_value
    
    def show_current_step(self) -> None:
        """Display the current step of the wizard - same pattern as legacy."""
        step_container = self.query_one("#step-container")
        # Clear all children from the container using legacy pattern
        for child in list(step_container.children):
            child.remove()
        
        step = self.steps[self.current_step]
        visible_steps = [s for s in self.steps if self._should_show_step(s)]
        step_number = visible_steps.index(step) + 1 if step in visible_steps else 1
        total_visible = len(visible_steps)
        
        # Update step info - same format as legacy
        step_info = self.query_one("#step-info")
        step_title = self.step_handlers[step].get_title()
        step_description = self.step_handlers[step].get_description()
        step_info.update(f"Step {step_number} of {total_visible}: {step_title}\n{step_description}")
        
        # Update navigation buttons - same logic as legacy
        back_btn = self.query_one("#back-btn")
        next_btn = self.query_one("#next-btn")
        
        back_btn.disabled = (self.current_step == 0)
        
        if step == "confirm":
            next_btn.label = "Start Processing"
            next_btn.variant = "success"
        else:
            next_btn.label = "Next"
            next_btn.variant = "primary"
        
        # Render step content using handler
        if step in self.step_handlers:
            self.step_handlers[step].render(self, step_container)
        else:
            # Fallback for unknown steps
            step_container.mount(Label(f"Unknown step: {step}", classes="error-message"))
        
        # Set focus to the appropriate widget for this step
        self.set_timer(0.1, self._focus_step_widget)
    
    def _focus_step_widget(self) -> None:
        """Set focus to the main widget for the current step."""
        step = self.steps[self.current_step]
        step_container = self.query_one("#step-container")
        
        try:
            # Focus based on step type
            if step == "input_type":
                # Focus the RadioSet
                radio_set = step_container.query_one("#input-type-selection")
                radio_set.focus()
            elif step in ["input_path", "output_dir", "fps", "width"]:
                # Focus the Input field
                input_field = step_container.query_one("Input")
                input_field.focus()
            elif step == "output_format":
                # Focus the Select field
                select_field = step_container.query_one("Select")
                select_field.focus()
            elif step == "force_overwrite":
                # Focus the Checkbox field
                checkbox_field = step_container.query_one("Checkbox")
                checkbox_field.focus()
            else:
                # Default: focus the first focusable widget in the step
                focusable_widgets = step_container.query("Input, Select, RadioSet, Checkbox")
                if focusable_widgets:
                    focusable_widgets[0].focus()
        except Exception:
            # If focusing fails, don't crash - just continue
            pass
    
    def _should_show_step(self, step: str) -> bool:
        """Check if a step should be shown based on current configuration."""
        # Show/hide steps based on input type
        if step in ["fps", "output_format"] and self.config_data.get("input_type") not in ["video", "video_directory"]:
            return False
        return True
    
    def _next_step(self) -> None:
        """Move to the next step if current step is valid - same logic as legacy."""
        # Save current step data
        if not self._save_current_step():
            return  # Validation failed, stay on current step
        
        # Skip steps that shouldn't be shown
        next_step = self.current_step + 1
        while next_step < len(self.steps) and not self._should_show_step(self.steps[next_step]):
            next_step += 1
        
        if next_step < len(self.steps):
            self.current_step = next_step
            self.show_current_step()
        else:
            # Last step - process the configuration (go to processing screen)
            self.action_process()
    
    def _back_step(self) -> None:
        """Move to the previous step - same logic as legacy."""
        # Skip steps that shouldn't be shown
        prev_step = self.current_step - 1
        while prev_step >= 0 and not self._should_show_step(self.steps[prev_step]):
            prev_step -= 1
        
        if prev_step >= 0:
            self.current_step = prev_step
            self.show_current_step()
    
    def _save_current_step(self) -> bool:
        """Save the current step data and validate - same pattern as legacy."""
        step = self.steps[self.current_step]
        handler = self.step_handlers.get(step)
        
        if not handler:
            return True
        
        try:
            self._clear_error()
            
            # Validate step
            if not handler.validate(self):
                return False
            
            # Get data from step
            step_data = handler.get_data(self)
            self.config_data.update(step_data)
            
            return True
            
        except Exception as e:
            self._show_error(f"Error: {str(e)}")
            return False
    
    def _clear_error(self) -> None:
        """Clear any error messages - same as legacy."""
        try:
            error_widget = self.query_one(".error-message")
            error_widget.remove()
        except:
            pass  # No error message to remove
    
    def _show_error(self, message: str) -> None:
        """Show error message - same as legacy."""
        try:
            step_container = self.query_one("#step-container")
            error_label = Label(message, classes="error-message")
            step_container.mount(error_label)
        except Exception as e:
            print(f"Failed to show error message: {e}")
    
    def action_next_step(self) -> None:
        """Move to next step when Enter is pressed."""
        # Don't progress if an Input widget has focus - let it handle Enter
        focused = self.app.focused
        if focused and focused.__class__.__name__ == "Input":
            return  # Let the Input widget handle Enter
        
        # For RadioSet and RadioButton, Enter selects the option but we also want to progress
        # Check if we're on a step with RadioSet/RadioButton
        if focused and focused.__class__.__name__ in ["RadioSet", "RadioButton"]:
            # Still progress to next step
            self._next_step()
            return
        
        # Otherwise, progress to next step
        self._next_step()
    
    def action_cancel(self) -> None:
        """Cancel the configuration and exit - same as legacy."""
        self.app.pop_screen()
    
    def action_process(self) -> None:
        """Start processing with the collected configuration - transition to processing."""
        # Import here to avoid circular imports
        from .processing import ProcessingScreen
        
        # Push the processing screen with our configuration
        processing_screen = ProcessingScreen(self.config_data)
        self.app.push_screen(processing_screen)
    
    def action_help(self) -> None:
        """Show help information - same as legacy."""
        help_text = """
# Sharp Frames Configuration Help

**Interactive Mode**: This mode separates frame extraction from selection, allowing you to:
1. Extract and analyze all frames first
2. Interactively select frames with real-time preview
3. Adjust selection criteria without re-processing

## Configuration Steps

**Input Type**: Choose between single video, video directory, or image directory.

**Input Path**: Specify the path to your video file(s) or image directory.

**Output Directory**: Where selected frames will be saved.

**FPS** (video only): Frames per second to extract from video.

**Output Format**: Image format for saved frames (JPG or PNG).

**Width**: Optional resizing width (maintains aspect ratio).

**Force Overwrite**: Overwrite existing files without confirmation.

## Selection Process

After configuration, frames will be extracted and analyzed. You'll then see an interactive selection screen where you can:
- Choose selection method (Best N, Batched, Outlier Removal)
- Adjust parameters with real-time preview
- See exactly how many frames will be selected

Press F1 on any screen for context-specific help.
        """
        self.app.push_screen("help", help_text)
    
    def get_current_step_name(self) -> str:
        """Get the name of the current step."""
        return self.steps[self.current_step]


