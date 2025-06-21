"""
Refactored configuration screen for Sharp Frames UI.

This version uses step handlers to break down the large ConfigurationForm
into smaller, focused components for better maintainability.
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
from ..components import (
    InputTypeStepHandler,
    InputPathStepHandler,
    OutputDirStepHandler,
    FpsStepHandler,
    SelectionMethodStepHandler,
    MethodParamsStepHandler,
    OutputFormatStepHandler,
    WidthStepHandler,
    ForceOverwriteStepHandler,
    ConfirmStepHandler,
    ValidationHelpers
)


class ConfigurationForm(Screen):
    """Main configuration form for Sharp Frames using step handlers."""
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+c", "cancel", "Cancel"),
        Binding("f1", "help", "Help", show=True),
    ]
    
    def __init__(self):
        super().__init__()
        self.config_data = {}
        self.current_step = 0
        self.steps = [
            "input_type",
            "input_path", 
            "output_dir",
            "fps",  # Only shown for video
            "selection_method",
            "method_params",  # Dynamic based on selection method
            "output_format",
            "width",
            "force_overwrite",
            "confirm"
        ]
        
        # Initialize step handlers
        self.step_handlers = {}
        self._initialize_step_handlers()
    
    def _initialize_step_handlers(self) -> None:
        """Initialize step handlers with current config data."""
        self.step_handlers = {
            "input_type": InputTypeStepHandler(self.config_data),
            "input_path": InputPathStepHandler(self.config_data),
            "output_dir": OutputDirStepHandler(self.config_data),
            "fps": FpsStepHandler(self.config_data),
            "selection_method": SelectionMethodStepHandler(self.config_data),
            "method_params": MethodParamsStepHandler(self.config_data),
            "output_format": OutputFormatStepHandler(self.config_data),
            "width": WidthStepHandler(self.config_data),
            "force_overwrite": ForceOverwriteStepHandler(self.config_data),
            "confirm": ConfirmStepHandler(self.config_data)
        }
    
    def compose(self) -> ComposeResult:
        """Create the wizard layout."""
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
    
    def show_current_step(self) -> None:
        """Display the current step of the wizard."""
        step_container = self.query_one("#step-container")
        # Clear all children from the container
        for child in list(step_container.children):
            child.remove()
        
        step = self.steps[self.current_step]
        visible_steps = [s for s in self.steps if self._should_show_step(s)]
        step_number = visible_steps.index(step) + 1 if step in visible_steps else 1
        total_steps = len(visible_steps)
        
        # Update step info
        step_info = self.query_one(f"#{UIElementIds.STEP_INFO}")
        step_info.update(f"Step {step_number} of {total_steps}")
        
        # Update button states
        back_btn = self.query_one(f"#{UIElementIds.BACK_BTN}")
        next_btn = self.query_one(f"#{UIElementIds.NEXT_BTN}")
        
        back_btn.disabled = self.current_step == 0
        
        if step == "confirm":
            next_btn.label = "Process"
            next_btn.variant = "success"
        else:
            next_btn.label = "Next"
            next_btn.variant = "primary"
        
        # Refresh step handlers with current config
        self._initialize_step_handlers()
        
        # Create the step content using appropriate handler
        if step in self.step_handlers:
            self.step_handlers[step].create_step(step_container)
        else:
            # Fallback for unknown steps
            step_container.mount(Label(f"Unknown step: {step}", classes="error-message"))
    
    def _should_show_step(self, step: str) -> bool:
        """Check if a step should be shown based on current configuration."""
        if step == "fps":
            return self.config_data.get("input_type") in [InputTypes.VIDEO, InputTypes.VIDEO_DIRECTORY]
        if step == "method_params":
            return self.config_data.get("selection_method") in ["best-n", "batched", "outlier-removal"]
        if step == "output_format":
            return self.config_data.get("input_type") != InputTypes.DIRECTORY
        if step == "width":
            return self.config_data.get("input_type") != InputTypes.DIRECTORY
        return True
    
    def _show_error(self, container, message: str, error_id: str = "error-message") -> None:
        """Show an error message in the container."""
        # Remove existing error if present
        try:
            existing_error = container.query_one(f"#{error_id}")
            existing_error.remove()
        except:
            pass
        
        # Add new error message
        error_label = Label(message, classes="error-message", id=error_id)
        container.mount(error_label)
    
    def _clear_error(self, container, error_id: str = "error-message") -> None:
        """Clear error message from the container."""
        try:
            error = container.query_one(f"#{error_id}")
            error.remove()
        except:
            pass
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == UIElementIds.NEXT_BTN:
            self._next_step()
        elif event.button.id == UIElementIds.BACK_BTN:
            self._back_step()
        elif event.button.id == UIElementIds.CANCEL_BTN:
            self.action_cancel()
    
    def _next_step(self) -> None:
        """Move to the next step if current step is valid."""
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
            # Last step - process the configuration
            self.action_process()
    
    def _back_step(self) -> None:
        """Move to the previous step."""
        # Skip steps that shouldn't be shown
        prev_step = self.current_step - 1
        while prev_step >= 0 and not self._should_show_step(self.steps[prev_step]):
            prev_step -= 1
        
        if prev_step >= 0:
            self.current_step = prev_step
            self.show_current_step()
    
    def _save_current_step(self) -> bool:
        """Save the current step data and validate."""
        step = self.steps[self.current_step]
        step_container = self.query_one("#step-container")
        
        try:
            self._clear_error(step_container)
            
            if step == "input_type":
                return self._save_input_type_step(step_container)
            elif step == "input_path":
                return self._save_input_path_step(step_container)
            elif step == "output_dir":
                return self._save_output_dir_step(step_container)
            elif step == "fps":
                return self._save_fps_step(step_container)
            elif step == "selection_method":
                return self._save_selection_method_step(step_container)
            elif step == "method_params":
                return self._save_method_params_step(step_container)
            elif step == "output_format":
                return self._save_output_format_step(step_container)
            elif step == "width":
                return self._save_width_step(step_container)
            elif step == "force_overwrite":
                return self._save_force_overwrite_step(step_container)
            elif step == "confirm":
                return True  # No validation needed for confirm step
                
        except Exception as e:
            self._show_error(step_container, f"Error: {str(e)}")
            return False
        
        return True
    
    def _save_input_type_step(self, container) -> bool:
        """Save input type selection."""
        try:
            radio_set = container.query_one(f"#{UIElementIds.INPUT_TYPE_RADIO}")
            if radio_set.pressed_button:
                if radio_set.pressed_button.id == UIElementIds.VIDEO_OPTION:
                    self.config_data["input_type"] = InputTypes.VIDEO
                elif radio_set.pressed_button.id == UIElementIds.VIDEO_DIRECTORY_OPTION:
                    self.config_data["input_type"] = InputTypes.VIDEO_DIRECTORY
                elif radio_set.pressed_button.id == UIElementIds.DIRECTORY_OPTION:
                    self.config_data["input_type"] = InputTypes.DIRECTORY
                return True
            else:
                self._show_error(container, "Please select an input type")
                return False
        except Exception:
            self._show_error(container, "Error reading input type selection")
            return False
    
    def _save_input_path_step(self, container) -> bool:
        """Save input path with validation."""
        try:
            input_widget = container.query_one(f"#{UIElementIds.INPUT_PATH_FIELD}")
            
            if not ValidationHelpers.validate_required_field(input_widget, "Input path"):
                self._show_error(container, "Input path is required")
                return False
            
            if not input_widget.is_valid:
                self._show_error(container, "Please enter a valid input path")
                return False
            
            self.config_data["input_path"] = input_widget.value.strip()
            return True
        except Exception as e:
            self._show_error(container, f"Error validating input path: {str(e)}")
            return False
    
    def _save_output_dir_step(self, container) -> bool:
        """Save output directory with validation."""
        try:
            input_widget = container.query_one("#output-dir-field")
            
            if not ValidationHelpers.validate_required_field(input_widget, "Output directory"):
                self._show_error(container, "Output directory is required")
                return False
            
            if not input_widget.is_valid:
                self._show_error(container, "Please enter a valid output directory")
                return False
            
            self.config_data["output_dir"] = input_widget.value.strip()
            return True
        except Exception as e:
            self._show_error(container, f"Error validating output directory: {str(e)}")
            return False
    
    def _save_fps_step(self, container) -> bool:
        """Save FPS setting with validation."""
        try:
            input_widget = container.query_one("#fps-field")
            
            if not ValidationHelpers.validate_numeric_field(input_widget, "FPS"):
                self._show_error(container, "Please enter a valid FPS value")
                return False
            
            fps_value = ValidationHelpers.get_int_value(input_widget, 10)
            if fps_value < 1 or fps_value > 60:
                self._show_error(container, "FPS must be between 1 and 60")
                return False
                
            self.config_data["fps"] = fps_value
            return True
        except Exception as e:
            self._show_error(container, f"Error saving FPS: {str(e)}")
            return False
    
    def _save_selection_method_step(self, container) -> bool:
        """Save selection method."""
        try:
            select_widget = container.query_one("#selection-method-field")
            self.config_data["selection_method"] = select_widget.value
            return True
        except Exception as e:
            self._show_error(container, f"Error saving selection method: {str(e)}")
            return False
    
    def _save_method_params_step(self, container) -> bool:
        """Save method-specific parameters."""
        try:
            method = self.config_data.get("selection_method", "best-n")
            
            param1_widget = container.query_one("#param1")
            param2_widget = container.query_one("#param2")
            
            if not ValidationHelpers.validate_numeric_field(param1_widget, "Parameter 1"):
                self._show_error(container, "Please enter valid parameters")
                return False
                
            if not ValidationHelpers.validate_numeric_field(param2_widget, "Parameter 2"):
                self._show_error(container, "Please enter valid parameters")
                return False
            
            param1_value = ValidationHelpers.get_int_value(param1_widget)
            param2_value = ValidationHelpers.get_int_value(param2_widget)
            
            if method == "best-n":
                self.config_data["num_frames"] = param1_value
                self.config_data["min_buffer"] = param2_value
            elif method == "batched":
                self.config_data["batch_size"] = param1_value
                self.config_data["batch_buffer"] = param2_value
            elif method == "outlier-removal":
                self.config_data["outlier_window_size"] = param1_value
                self.config_data["outlier_sensitivity"] = param2_value
            
            return True
        except Exception as e:
            self._show_error(container, f"Error saving method parameters: {str(e)}")
            return False
    
    def _save_output_format_step(self, container) -> bool:
        """Save output format."""
        try:
            select_widget = container.query_one("#output-format-field")
            self.config_data["output_format"] = select_widget.value
            return True
        except Exception as e:
            self._show_error(container, f"Error saving output format: {str(e)}")
            return False
    
    def _save_width_step(self, container) -> bool:
        """Save width setting."""
        try:
            input_widget = container.query_one("#width-field")
            
            if not ValidationHelpers.validate_numeric_field(input_widget, "Width"):
                self._show_error(container, "Please enter a valid width value")
                return False
            
            width_value = ValidationHelpers.get_int_value(input_widget, 0)
            if width_value < 0:
                self._show_error(container, "Width cannot be negative")
                return False
                
            self.config_data["width"] = width_value
            return True
        except Exception as e:
            self._show_error(container, f"Error saving width: {str(e)}")
            return False
    
    def _save_force_overwrite_step(self, container) -> bool:
        """Save force overwrite setting."""
        try:
            checkbox = container.query_one("#force-overwrite-field")
            self.config_data["force_overwrite"] = checkbox.value
            return True
        except Exception as e:
            self._show_error(container, f"Error saving overwrite setting: {str(e)}")
            return False
    
    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """Handle radio button changes."""
        if event.radio_set.id == UIElementIds.INPUT_TYPE_RADIO:
            # Update description based on selection
            try:
                description_label = self.query_one("#input-type-description")
                if event.pressed.id == UIElementIds.VIDEO_OPTION:
                    description_label.update("Extract and select the sharpest frames of a single video")
                elif event.pressed.id == UIElementIds.VIDEO_DIRECTORY_OPTION:
                    description_label.update("Extract and select the sharpest frames of all videos in a folder")
                elif event.pressed.id == UIElementIds.DIRECTORY_OPTION:
                    description_label.update("Select the sharpest images from a folder")
            except:
                pass  # Description label might not exist yet
    
    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle select widget changes."""
        if event.select.id == "selection-method-field":
            # Update method description
            try:
                description_label = self.query_one("#selection-method-description")
                handler = self.step_handlers.get("selection_method")
                if handler and hasattr(handler, '_get_method_description'):
                    description_text = handler._get_method_description(event.value)
                    description_label.update(description_text)
            except:
                pass  # Description label might not exist yet
    
    def action_cancel(self) -> None:
        """Cancel the configuration and exit."""
        # Use the app's cancel action instead of direct exit
        # This allows the app to filter spurious cancel actions
        if hasattr(self.app, 'action_cancel'):
            self.app.action_cancel()
        else:
            # Fallback if app doesn't have custom cancel handling
            self.app.exit("cancelled")
    
    def action_help(self) -> None:
        """Show help information."""
        step = self.steps[self.current_step]
        help_texts = {
            "input_type": "Choose whether to process a single video file, multiple videos in a directory, or a directory of images.",
            "input_path": "Enter the full path to your input file or directory. Use drag-and-drop if supported.",
            "fps": "Higher FPS extracts more frames but takes longer. 5-15 FPS is usually sufficient.",
            "selection_method": "Best-N selects specific count, Batched ensures even distribution, Outlier-removal keeps all except blurry frames.",
            "output_format": "JPEG produces smaller files, PNG preserves quality better."
        }
        
        help_text = help_texts.get(step, "No help available for this step.")
        # For now, just show in footer - could be expanded to a help modal
        self.notify(f"Help: {help_text}", severity="information")
    
    def action_process(self) -> None:
        """Start processing with the current configuration."""
        from .processing import ProcessingScreen
        
        final_config = self._prepare_final_config()
        self.app.push_screen(ProcessingScreen(final_config))
    
    def _prepare_final_config(self) -> Dict[str, Any]:
        """Prepare the final configuration for processing."""
        final_config = dict(self.config_data)
        
        # Remove any None values
        final_config = {k: v for k, v in final_config.items() if v is not None}
        
        return final_config 