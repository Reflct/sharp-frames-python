"""
Configuration screen for Sharp Frames UI.
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
from ..components import IntRangeValidator, ValidationHelpers


class ConfigurationForm(Screen):
    """Main configuration form for Sharp Frames."""
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+c", "cancel", "Cancel"),
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
    
    def compose(self) -> ComposeResult:
        """Create the wizard layout."""
        yield Header()
        ascii_title = """
 ███████ ██   ██  █████  ██████  ██████     ███████ ██████   █████  ███    ███ ███████ ███████ 
 ██      ██   ██ ██   ██ ██   ██ ██   ██    ██      ██   ██ ██   ██ ████  ████ ██      ██      
 ███████ ███████ ███████ ██████  ██████     █████   ██████  ███████ ██ ████ ██ █████   ███████ 
      ██ ██   ██ ██   ██ ██   ██ ██         ██      ██   ██ ██   ██ ██  ██  ██ ██           ██ 
 ███████ ██   ██ ██   ██ ██   ██ ██         ██      ██   ██ ██   ██ ██      ██ ███████ ███████ 
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
        step_number = self.current_step + 1
        total_steps = len([s for s in self.steps if self._should_show_step(s)])
        
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
        
        # Create the step content
        if step == "input_type":
            self._create_input_type_step(step_container)
        elif step == "input_path":
            self._create_input_path_step(step_container)
        elif step == "output_dir":
            self._create_output_dir_step(step_container)
        elif step == "fps":
            self._create_fps_step(step_container)
        elif step == "selection_method":
            self._create_selection_method_step(step_container)
        elif step == "method_params":
            self._create_method_params_step(step_container)
        elif step == "output_format":
            self._create_output_format_step(step_container)
        elif step == "width":
            self._create_width_step(step_container)
        elif step == "force_overwrite":
            self._create_force_overwrite_step(step_container)
        elif step == "confirm":
            self._create_confirm_step(step_container)
    
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
    
    def _create_input_type_step(self, container) -> None:
        """Create the input type selection step."""
        container.mount(Label("What type of input do you want to process?", classes="question"))
        
        # Create radio buttons and mount them
        radio_set = RadioSet(id=UIElementIds.INPUT_TYPE_RADIO)
        video_radio = RadioButton("Video file", value=True, id=UIElementIds.VIDEO_OPTION)
        video_dir_radio = RadioButton("Video directory", id=UIElementIds.VIDEO_DIRECTORY_OPTION)
        dir_radio = RadioButton("Image directory", id=UIElementIds.DIRECTORY_OPTION)
        
        # Mount radio set first, then add children
        container.mount(radio_set)
        radio_set.mount(video_radio)
        radio_set.mount(video_dir_radio)
        radio_set.mount(dir_radio)
        
        # Set current value if exists
        if "input_type" in self.config_data:
            current_type = self.config_data["input_type"]
            video_radio.value = current_type == InputTypes.VIDEO
            video_dir_radio.value = current_type == InputTypes.VIDEO_DIRECTORY
            dir_radio.value = current_type == InputTypes.DIRECTORY
    
    def _create_input_path_step(self, container) -> None:
        """Create the input path step."""
        input_type = self.config_data.get("input_type", InputTypes.VIDEO)
        if input_type == InputTypes.VIDEO:
            container.mount(Label("Enter the path to your video file:", classes="question"))
            placeholder = "e.g., /path/to/video.mp4"
        elif input_type == InputTypes.VIDEO_DIRECTORY:
            container.mount(Label("Enter the path to your video directory:", classes="question"))
            placeholder = "e.g., /path/to/videos/"
        else:
            container.mount(Label("Enter the path to your image directory:", classes="question"))
            placeholder = "e.g., /path/to/images/"
        
        input_widget = Input(
            placeholder=placeholder,
            id=UIElementIds.INPUT_PATH_FIELD,
            value=self.config_data.get("input_path", "")
        )
        container.mount(input_widget)
        input_widget.focus()
    
    def _create_output_dir_step(self, container) -> None:
        """Create the output directory step."""
        container.mount(Label("Where should the selected frames be saved?", classes="question"))
        input_widget = Input(
            placeholder="e.g., /path/to/output",
            id="output-dir-field",
            value=self.config_data.get("output_dir", "")
        )
        container.mount(input_widget)
        input_widget.focus()
    
    def _create_fps_step(self, container) -> None:
        """Create the FPS selection step."""
        input_type = self.config_data.get("input_type", InputTypes.VIDEO)
        if input_type == InputTypes.VIDEO_DIRECTORY:
            question_text = "How many frames per second should be extracted from each video?"
        else:
            question_text = "How many frames per second should be extracted from the video?"
            
        container.mount(Label(question_text, classes="question"))
        input_widget = Input(
            value=str(self.config_data.get("fps", 10)),
            validators=[IntRangeValidator(min_value=1, max_value=60)],
            id="fps-field"
        )
        container.mount(input_widget)
        container.mount(Label("(Recommended: 5-15 fps)", classes="hint"))
        input_widget.focus()
    
    def _create_selection_method_step(self, container) -> None:
        """Create the selection method step."""
        container.mount(Label("Which frame selection method would you like to use?", classes="question"))
        select_widget = Select([
            ("Best N frames - Select the sharpest frames", "best-n"),
            ("Batched selection - Best frame from each batch", "batched"),
            ("Outlier removal - Remove blurry frames", "outlier-removal")
        ], value=self.config_data.get("selection_method", "best-n"), id="selection-method-field")
        container.mount(select_widget)
    
    def _create_method_params_step(self, container) -> None:
        """Create the method-specific parameters step."""
        method = self.config_data.get("selection_method", "best-n")
        
        if method == "best-n":
            container.mount(Label("Best-N Method Configuration:", classes="question"))
            container.mount(Label("Number of frames to select:"))
            input1 = Input(
                value=str(self.config_data.get("num_frames", 300)),
                validators=[IntRangeValidator(min_value=1)],
                id="param1"
            )
            container.mount(input1)
            container.mount(Label("Minimum distance between frames:"))
            input2 = Input(
                value=str(self.config_data.get("min_buffer", 3)),
                validators=[IntRangeValidator(min_value=0)],
                id="param2"
            )
            container.mount(input2)
            input1.focus()
            
        elif method == "batched":
            container.mount(Label("Batched Method Configuration:", classes="question"))
            container.mount(Label("Batch size (frames per batch):"))
            input1 = Input(
                value=str(self.config_data.get("batch_size", 5)),
                validators=[IntRangeValidator(min_value=1)],
                id="param1"
            )
            container.mount(input1)
            container.mount(Label("Frames to skip between batches:"))
            input2 = Input(
                value=str(self.config_data.get("batch_buffer", 2)),
                validators=[IntRangeValidator(min_value=0)],
                id="param2"
            )
            container.mount(input2)
            input1.focus()
            
        elif method == "outlier-removal":
            container.mount(Label("Outlier Removal Configuration:", classes="question"))
            container.mount(Label("Window size for comparison:"))
            input1 = Input(
                value=str(self.config_data.get("outlier_window_size", 15)),
                validators=[IntRangeValidator(min_value=3, max_value=30)],
                id="param1"
            )
            container.mount(input1)
            container.mount(Label("Sensitivity (0-100, higher = more aggressive):"))
            input2 = Input(
                value=str(self.config_data.get("outlier_sensitivity", 50)),
                validators=[IntRangeValidator(min_value=0, max_value=100)],
                id="param2"
            )
            container.mount(input2)
            input1.focus()
    
    def _create_output_format_step(self, container) -> None:
        """Create the output format step."""
        container.mount(Label("What format should the output images be saved in?", classes="question"))
        select_widget = Select([
            ("JPEG (smaller file size)", "jpg"),
            ("PNG (better quality)", "png")
        ], value=self.config_data.get("output_format", "jpg"), id="output-format-field")
        container.mount(select_widget)
    
    def _create_width_step(self, container) -> None:
        """Create the width step."""
        container.mount(Label("Do you want to resize the output images?", classes="question"))
        input_widget = Input(
            value=str(self.config_data.get("width", 0)),
            validators=[IntRangeValidator(min_value=0)],
            id="width-field"
        )
        container.mount(input_widget)
        container.mount(Label("(Enter 0 for no resizing, or width in pixels)", classes="hint"))
        input_widget.focus()
    
    def _create_force_overwrite_step(self, container) -> None:
        """Create the force overwrite step."""
        container.mount(Label("Should existing files be overwritten without confirmation?", classes="question"))
        checkbox = Checkbox(
            "Yes, overwrite existing files",
            value=self.config_data.get("force_overwrite", False),
            id="force-overwrite-field"
        )
        container.mount(checkbox)
    
    def _create_confirm_step(self, container) -> None:
        """Create the confirmation step."""
        container.mount(Label("Review your configuration:", classes="question"))
        
        # Show summary
        summary_text = self._build_config_summary()
        container.mount(Static(summary_text, classes="summary"))
        container.mount(Label("Press 'Process' to start, or 'Back' to make changes.", classes="hint"))
    
    def _build_config_summary(self) -> str:
        """Build a summary of the current configuration."""
        lines = []
        
        input_type = self.config_data.get("input_type", InputTypes.VIDEO)
        lines.append(f"Input Type: {input_type.title()}")
        lines.append(f"Input Path: {self.config_data.get('input_path', 'Not set')}")
        lines.append(f"Output Directory: {self.config_data.get('output_dir', 'Not set')}")
        
        if input_type in [InputTypes.VIDEO, InputTypes.VIDEO_DIRECTORY]:
            fps_label = "FPS (per video)" if input_type == InputTypes.VIDEO_DIRECTORY else "FPS"
            lines.append(f"{fps_label}: {self.config_data.get('fps', 10)}")
        
        method = self.config_data.get("selection_method", "best-n")
        lines.append(f"Selection Method: {method}")
        
        if method == "best-n":
            lines.append(f"  Number of frames: {self.config_data.get('num_frames', 300)}")
            lines.append(f"  Minimum buffer: {self.config_data.get('min_buffer', 3)}")
        elif method == "batched":
            lines.append(f"  Batch size: {self.config_data.get('batch_size', 5)}")
            lines.append(f"  Batch buffer: {self.config_data.get('batch_buffer', 2)}")
        elif method == "outlier-removal":
            lines.append(f"  Window size: {self.config_data.get('outlier_window_size', 15)}")
            lines.append(f"  Sensitivity: {self.config_data.get('outlier_sensitivity', 50)}")
        
        # Only show output format and resize options for non-directory modes
        input_type = self.config_data.get("input_type", InputTypes.VIDEO)
        if input_type != InputTypes.DIRECTORY:
            lines.append(f"Output Format: {self.config_data.get('output_format', 'jpg').upper()}")
            
            width = self.config_data.get('width', 0)
            if width > 0:
                lines.append(f"Resize Width: {width}px")
            else:
                lines.append("Resize Width: No resizing")
        else:
            lines.append("Output Format: Preserve original formats")
            lines.append("Resize Width: Preserve original dimensions")
        
        overwrite = self.config_data.get('force_overwrite', False)
        lines.append(f"Force Overwrite: {'Yes' if overwrite else 'No'}")
        
        return "\n".join(lines)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel-btn":
            self.action_cancel()
        elif event.button.id == "next-btn":
            self._next_step()
        elif event.button.id == "back-btn":
            self._back_step()
    

    
    def _next_step(self) -> None:
        """Move to the next step in the wizard."""
        # Save current step data
        if not self._save_current_step():
            return  # Validation failed
        
        # Find next step to show
        self.current_step += 1
        while (self.current_step < len(self.steps) and 
               not self._should_show_step(self.steps[self.current_step])):
            self.current_step += 1
        
        if self.current_step >= len(self.steps):
            # Process the configuration
            self.action_process()
        else:
            self.show_current_step()
    
    def _back_step(self) -> None:
        """Move to the previous step in the wizard."""
        if self.current_step > 0:
            self.current_step -= 1
            while (self.current_step > 0 and 
                   not self._should_show_step(self.steps[self.current_step])):
                self.current_step -= 1
            self.show_current_step()
    
    def _save_current_step(self) -> bool:
        """Save the current step's data and validate it."""
        step = self.steps[self.current_step]
        step_container = self.query_one("#step-container")
        
        try:
            if step == "input_type":
                if self.query_one("#video-option").value:
                    self.config_data["input_type"] = InputTypes.VIDEO
                elif self.query_one("#video-directory-option").value:
                    self.config_data["input_type"] = InputTypes.VIDEO_DIRECTORY
                else:
                    self.config_data["input_type"] = InputTypes.DIRECTORY
                    
            elif step == "input_path":
                input_widget = self.query_one(f"#{UIElementIds.INPUT_PATH_FIELD}", Input)
                value = input_widget.value.strip()
                
                # Clear any existing errors
                self._clear_error(step_container)
                
                if not value:
                    input_type = self.config_data.get("input_type", InputTypes.VIDEO)
                    if input_type == InputTypes.VIDEO:
                        self._show_error(step_container, "Please enter your video file path")
                    elif input_type == InputTypes.VIDEO_DIRECTORY:
                        self._show_error(step_container, "Please enter your video directory path")
                    else:
                        self._show_error(step_container, "Please enter your image directory path")
                    return False
                
                # Validate path exists (but don't show error for non-existent paths in this simple validation)
                self.config_data["input_path"] = value
                
            elif step == "output_dir":
                input_widget = self.query_one(f"#{UIElementIds.OUTPUT_DIR_FIELD}", Input)
                value = input_widget.value.strip()
                
                # Clear any existing errors
                self._clear_error(step_container)
                
                if not value:
                    self._show_error(step_container, "Please enter your output directory path")
                    return False
                
                self.config_data["output_dir"] = value
                
            elif step == "fps":
                input_widget = self.query_one(f"#{UIElementIds.FPS_FIELD}", Input)
                value = input_widget.value.strip()
                
                # Clear any existing errors
                self._clear_error(step_container)
                
                if not value:
                    self._show_error(step_container, "Please enter FPS value")
                    return False
                
                try:
                    fps_value = int(value)
                    if fps_value < 1 or fps_value > 60:
                        self._show_error(step_container, "FPS must be between 1 and 60")
                        return False
                    self.config_data["fps"] = fps_value
                except ValueError:
                    self._show_error(step_container, "FPS must be a valid number")
                    return False
                
            elif step == "selection_method":
                select_widget = self.query_one("#selection-method-field", Select)
                self.config_data["selection_method"] = select_widget.value
                
            elif step == "method_params":
                method = self.config_data.get("selection_method")
                param1 = self.query_one("#param1", Input)
                param2 = self.query_one("#param2", Input)
                
                # Clear any existing errors
                self._clear_error(step_container)
                
                value1 = param1.value.strip()
                value2 = param2.value.strip()
                
                if not value1 or not value2:
                    self._show_error(step_container, "Please fill in all parameter fields")
                    return False
                
                try:
                    if method == "best-n":
                        num_frames = int(value1)
                        min_buffer = int(value2)
                        if num_frames < 1:
                            self._show_error(step_container, "Number of frames must be at least 1")
                            return False
                        if min_buffer < 0:
                            self._show_error(step_container, "Minimum buffer must be 0 or greater")
                            return False
                        self.config_data["num_frames"] = num_frames
                        self.config_data["min_buffer"] = min_buffer
                    elif method == "batched":
                        batch_size = int(value1)
                        batch_buffer = int(value2)
                        if batch_size < 1:
                            self._show_error(step_container, "Batch size must be at least 1")
                            return False
                        if batch_buffer < 0:
                            self._show_error(step_container, "Batch buffer must be 0 or greater")
                            return False
                        self.config_data["batch_size"] = batch_size
                        self.config_data["batch_buffer"] = batch_buffer
                    elif method == "outlier-removal":
                        window_size = int(value1)
                        sensitivity = int(value2)
                        if window_size < 3:
                            self._show_error(step_container, "Window size must be at least 3")
                            return False
                        if sensitivity < 0 or sensitivity > 100:
                            self._show_error(step_container, "Sensitivity must be between 0 and 100")
                            return False
                        self.config_data["outlier_window_size"] = window_size
                        self.config_data["outlier_sensitivity"] = sensitivity
                except ValueError:
                    self._show_error(step_container, "All parameters must be valid numbers")
                    return False
                    
            elif step == "output_format":
                select_widget = self.query_one("#output-format-field", Select)
                self.config_data["output_format"] = select_widget.value
                
            elif step == "width":
                input_widget = self.query_one("#width-field", Input)
                value = input_widget.value.strip()
                
                # Clear any existing errors
                self._clear_error(step_container)
                
                if not value:
                    self._show_error(step_container, "Please enter width value (0 for no resizing)")
                    return False
                
                try:
                    width_value = int(value)
                    if width_value < 0:
                        self._show_error(step_container, "Width must be 0 or greater")
                        return False
                    self.config_data["width"] = width_value
                except ValueError:
                    self._show_error(step_container, "Width must be a valid number")
                    return False
                
            elif step == "force_overwrite":
                checkbox = self.query_one("#force-overwrite-field", Checkbox)
                self.config_data["force_overwrite"] = checkbox.value
                
            return True
            
        except Exception:
            return False
    
    def action_cancel(self) -> None:
        """Cancel the configuration."""
        self.app.exit(result="cancelled")
    

    

    

    
    def action_process(self) -> None:
        """Process the configuration and start Sharp Frames."""
        # Import here to avoid circular imports
        from .processing import ProcessingScreen
        
        # Use the collected config data
        config = self._prepare_final_config()
        
        # Switch to processing screen
        self.app.push_screen(ProcessingScreen(config))
    
    def _prepare_final_config(self) -> Dict[str, Any]:
        """Prepare the final configuration for processing."""
        input_type = self.config_data.get("input_type", InputTypes.VIDEO)
        
        config = {
            "input_path": self.config_data.get("input_path"),
            "input_type": input_type,
            "output_dir": self.config_data.get("output_dir"),
            "force_overwrite": self.config_data.get("force_overwrite", False),
        }
        
        # Set output format and width based on input type
        if input_type == InputTypes.DIRECTORY:
            # For image directory mode, preserve original formats and dimensions
            # Use jpg as placeholder (not used for directory input since we preserve originals)
            config["output_format"] = "jpg"
            config["width"] = 0
        else:
            # For video modes, use user-selected format and width
            config["output_format"] = self.config_data.get("output_format", "jpg")
            config["width"] = self.config_data.get("width", 0)
        
        # Add video-specific config
        if config["input_type"] in [InputTypes.VIDEO, InputTypes.VIDEO_DIRECTORY]:
            config["fps"] = self.config_data.get("fps", 10)
        else:
            config["fps"] = 0
        
        # Add selection method config
        selection_method = self.config_data.get("selection_method", "best-n")
        config["selection_method"] = selection_method
        
        # Set default values for all methods (required by SharpFrames)
        config["num_frames"] = 300
        config["min_buffer"] = 3
        config["batch_size"] = 5
        config["batch_buffer"] = 2
        config["outlier_window_size"] = 15
        config["outlier_sensitivity"] = 50
        
        # Override with method-specific values
        if selection_method == "best-n":
            config["num_frames"] = self.config_data.get("num_frames", 300)
            config["min_buffer"] = self.config_data.get("min_buffer", 3)
        elif selection_method == "batched":
            config["batch_size"] = self.config_data.get("batch_size", 5)
            config["batch_buffer"] = self.config_data.get("batch_buffer", 2)
        elif selection_method == "outlier-removal":
            config["outlier_window_size"] = self.config_data.get("outlier_window_size", 15)
            config["outlier_sensitivity"] = self.config_data.get("outlier_sensitivity", 50)
        
        return config 