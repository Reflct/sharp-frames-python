#!/usr/bin/env python3
"""
Textual-based user interface for Sharp Frames interactive mode.
Provides a form-based alternative to the terminal prompts.
"""

import os
from typing import Optional, Dict, Any, List
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import (
    Header, Footer, Button, Input, Select, RadioSet, RadioButton,
    Checkbox, Label, Static, ProgressBar
)
from textual.screen import Screen
from textual.binding import Binding
from textual.validation import Function, ValidationResult, Validator

from .sharp_frames_processor import SharpFrames


class PathValidator(Validator):
    """Validator for file and directory paths."""
    
    def __init__(self, must_exist: bool = True, must_be_file: bool = False, must_be_dir: bool = False):
        self.must_exist = must_exist
        self.must_be_file = must_be_file
        self.must_be_dir = must_be_dir
        super().__init__()
    
    def validate(self, value: str) -> ValidationResult:
        if not value.strip():
            return self.failure("Path cannot be empty")
        
        path = Path(os.path.expanduser(value.strip()))
        
        if self.must_exist:
            if not path.exists():
                return self.failure("Path does not exist")
            
            if self.must_be_file and not path.is_file():
                return self.failure("Path must be a file")
            
            if self.must_be_dir and not path.is_dir():
                return self.failure("Path must be a directory")
        
        return self.success()


class IntRangeValidator(Validator):
    """Validator for integer inputs with optional min/max bounds."""
    
    def __init__(self, min_value: Optional[int] = None, max_value: Optional[int] = None):
        self.min_value = min_value
        self.max_value = max_value
        super().__init__()
    
    def validate(self, value: str) -> ValidationResult:
        if not value.strip():
            return self.failure("Value cannot be empty")
        
        try:
            int_value = int(value.strip())
        except ValueError:
            return self.failure("Must be a valid integer")
        
        if self.min_value is not None and int_value < self.min_value:
            return self.failure(f"Value must be at least {self.min_value}")
        
        if self.max_value is not None and int_value > self.max_value:
            return self.failure(f"Value must be at most {self.max_value}")
        
        return self.success()


class ConfigurationForm(Screen):
    """Main configuration form for Sharp Frames."""
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+c", "cancel", "Cancel"),
        Binding("enter", "next_step", "Next"),
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
        yield Static("Sharp Frames - Configuration Wizard", classes="title")
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
        step_info = self.query_one("#step-info")
        step_info.update(f"Step {step_number} of {total_steps}")
        
        # Update button states
        back_btn = self.query_one("#back-btn")
        next_btn = self.query_one("#next-btn")
        
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
            return self.config_data.get("input_type") == "video"
        if step == "method_params":
            return self.config_data.get("selection_method") in ["best-n", "batched", "outlier-removal"]
        return True
    
    def _create_input_type_step(self, container) -> None:
        """Create the input type selection step."""
        container.mount(Label("What type of input do you want to process?", classes="question"))
        
        # Create radio buttons and mount them
        radio_set = RadioSet(id="input-type-radio")
        video_radio = RadioButton("Video file", value=True, id="video-option")
        dir_radio = RadioButton("Image directory", id="directory-option")
        
        # Mount radio set first, then add children
        container.mount(radio_set)
        radio_set.mount(video_radio)
        radio_set.mount(dir_radio)
        
        # Set current value if exists
        if "input_type" in self.config_data:
            if self.config_data["input_type"] == "directory":
                dir_radio.value = True
                video_radio.value = False
    
    def _create_input_path_step(self, container) -> None:
        """Create the input path step."""
        input_type = self.config_data.get("input_type", "video")
        if input_type == "video":
            container.mount(Label("Enter the path to your video file:", classes="question"))
            placeholder = "e.g., /path/to/video.mp4"
        else:
            container.mount(Label("Enter the path to your image directory:", classes="question"))
            placeholder = "e.g., /path/to/images/"
        
        input_widget = Input(
            placeholder=placeholder,
            id="input-path-field",
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
        container.mount(Label("How many frames per second should be extracted from the video?", classes="question"))
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
        
        input_type = self.config_data.get("input_type", "video")
        lines.append(f"Input Type: {input_type.title()}")
        lines.append(f"Input Path: {self.config_data.get('input_path', 'Not set')}")
        lines.append(f"Output Directory: {self.config_data.get('output_dir', 'Not set')}")
        
        if input_type == "video":
            lines.append(f"FPS: {self.config_data.get('fps', 10)}")
        
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
        
        lines.append(f"Output Format: {self.config_data.get('output_format', 'jpg').upper()}")
        
        width = self.config_data.get('width', 0)
        if width > 0:
            lines.append(f"Resize Width: {width}px")
        else:
            lines.append("Resize Width: No resizing")
        
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
        
        try:
            if step == "input_type":
                if self.query_one("#video-option").value:
                    self.config_data["input_type"] = "video"
                else:
                    self.config_data["input_type"] = "directory"
                    
            elif step == "input_path":
                input_widget = self.query_one("#input-path-field", Input)
                path = input_widget.value.strip()
                if not path:
                    return False
                if not os.path.exists(os.path.expanduser(path)):
                    return False
                self.config_data["input_path"] = path
                
            elif step == "output_dir":
                input_widget = self.query_one("#output-dir-field", Input)
                path = input_widget.value.strip()
                if not path:
                    return False
                self.config_data["output_dir"] = path
                
            elif step == "fps":
                input_widget = self.query_one("#fps-field", Input)
                if not input_widget.is_valid:
                    return False
                self.config_data["fps"] = int(input_widget.value)
                
            elif step == "selection_method":
                select_widget = self.query_one("#selection-method-field", Select)
                self.config_data["selection_method"] = select_widget.value
                
            elif step == "method_params":
                method = self.config_data.get("selection_method")
                param1 = self.query_one("#param1", Input)
                param2 = self.query_one("#param2", Input)
                
                if not param1.is_valid or not param2.is_valid:
                    return False
                
                if method == "best-n":
                    self.config_data["num_frames"] = int(param1.value)
                    self.config_data["min_buffer"] = int(param2.value)
                elif method == "batched":
                    self.config_data["batch_size"] = int(param1.value)
                    self.config_data["batch_buffer"] = int(param2.value)
                elif method == "outlier-removal":
                    self.config_data["outlier_window_size"] = int(param1.value)
                    self.config_data["outlier_sensitivity"] = int(param2.value)
                    
            elif step == "output_format":
                select_widget = self.query_one("#output-format-field", Select)
                self.config_data["output_format"] = select_widget.value
                
            elif step == "width":
                input_widget = self.query_one("#width-field", Input)
                if not input_widget.is_valid:
                    return False
                self.config_data["width"] = int(input_widget.value)
                
            elif step == "force_overwrite":
                checkbox = self.query_one("#force-overwrite-field", Checkbox)
                self.config_data["force_overwrite"] = checkbox.value
                
            return True
            
        except Exception:
            return False
    
    def action_cancel(self) -> None:
        """Cancel the configuration."""
        self.app.exit(result="cancelled")
    
    def action_next_step(self) -> None:
        """Action for Enter key - same as clicking Next button."""
        self._next_step()
    
    def action_process(self) -> None:
        """Process the configuration and start Sharp Frames."""
        # Use the collected config data
        config = self._prepare_final_config()
        
        # Switch to processing screen
        self.app.push_screen(ProcessingScreen(config))
    
    def _prepare_final_config(self) -> Dict[str, Any]:
        """Prepare the final configuration for processing."""
        config = {
            "input_path": self.config_data.get("input_path"),
            "input_type": self.config_data.get("input_type", "video"),
            "output_dir": self.config_data.get("output_dir"),
            "output_format": self.config_data.get("output_format", "jpg"),
            "width": self.config_data.get("width", 0),
            "force_overwrite": self.config_data.get("force_overwrite", False),
        }
        
        # Add video-specific config
        if config["input_type"] == "video":
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
    
    def _validate_form(self) -> bool:
        """Validate all form inputs."""
        # Check required fields
        input_path = self.query_one("#input-path").value.strip()
        output_dir = self.query_one("#output-dir").value.strip()
        
        if not input_path:
            self.query_one("#input-path").focus()
            return False
            
        if not output_dir:
            self.query_one("#output-dir").focus()
            return False
        
        # Check if input path exists
        if not os.path.exists(os.path.expanduser(input_path)):
            self.query_one("#input-path").focus()
            return False
        
        # Get all input widgets and check their validation (for numeric fields)
        inputs = self.query(Input)
        for input_widget in inputs:
            if input_widget.id in ["fps", "num-frames", "min-buffer", "batch-size", 
                                  "batch-buffer", "outlier-window-size", "outlier-sensitivity", "width"]:
                if not input_widget.is_valid:
                    input_widget.focus()
                    return False
        return True
    
    def _collect_configuration(self) -> Dict[str, Any]:
        """Collect all configuration values from the form."""
        # Determine input type
        input_type_radio = self.query_one("#input-type")
        is_video = self.query_one("#video-radio").value
        
        # Get basic configuration
        config = {
            "input_path": self.query_one("#input-path").value.strip(),
            "input_type": "video" if is_video else "directory",
            "output_dir": self.query_one("#output-dir").value.strip(),
            "output_format": self.query_one("#output-format").value,
            "width": int(self.query_one("#width").value or "0"),
            "force_overwrite": self.query_one("#force-overwrite").value,
        }
        
        # Add video-specific config
        if is_video:
            config["fps"] = int(self.query_one("#fps").value or "10")
        else:
            config["fps"] = 0
        
        # Add selection method config
        selection_method = self.query_one("#selection-method").value
        config["selection_method"] = selection_method
        
        if selection_method == "best-n":
            config["num_frames"] = int(self.query_one("#num-frames").value or "300")
            config["min_buffer"] = int(self.query_one("#min-buffer").value or "3")
        elif selection_method == "batched":
            config["batch_size"] = int(self.query_one("#batch-size").value or "5")
            config["batch_buffer"] = int(self.query_one("#batch-buffer").value or "2")
        elif selection_method == "outlier-removal":
            config["outlier_window_size"] = int(self.query_one("#outlier-window-size").value or "15")
            config["outlier_sensitivity"] = int(self.query_one("#outlier-sensitivity").value or "50")
        
        return config


class ProcessingScreen(Screen):
    """Screen shown during processing."""
    
    BINDINGS = [
        Binding("ctrl+c", "cancel", "Cancel Processing"),
    ]
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__()
        self.config = config
        self.processor = None
        self.processing_cancelled = False
        self.current_phase = ""
        self.phase_progress = 0
        self.total_phases = 5  # dependencies, extraction/loading, sharpness, selection, saving
        self.processing_complete = False
    
    def compose(self) -> ComposeResult:
        """Create the processing layout."""
        yield Header()
        
        with Container(id="processing-container"):
            yield Static("Processing...", classes="title")
            yield Static("", id="status-text")
            yield Static("", id="phase-text")
            yield ProgressBar(id="progress-bar", show_eta=False)
            yield Button("Cancel", variant="default", id="cancel-processing")
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Start processing when mounted."""
        self.start_processing()
    
    def start_processing(self) -> None:
        """Start the Sharp Frames processing asynchronously."""
        try:
            status_text = self.query_one("#status-text")
            progress_bar = self.query_one("#progress-bar")
            phase_text = self.query_one("#phase-text")
            
            # Validate configuration before starting
            config_issues = self._validate_config()
            if config_issues:
                status_text.update("❌ Configuration Error")
                phase_text.update(f"Config issue: {config_issues}")
                self.query_one("#cancel-processing").label = "Close"
                return
            
            # Immediately show that processing has started
            status_text.update("🔄 Initializing Sharp Frames processor...")
            phase_text.update("Phase 1/5: Starting...")
            progress_bar.update(progress=0)  # Start at 0%
            
            # Start the processing in a background worker
            self.run_worker(self._process_frames, exclusive=True, thread=True, name="frame_processor")
            
        except Exception as e:
            self.query_one("#status-text").update(f"❌ Error starting processing: {str(e)}")
            self.query_one("#cancel-processing").label = "Close"
    
    def _validate_config(self) -> str:
        """Validate configuration and return error message if invalid."""
        config = self.config
        
        # Check required fields
        if not config.get('input_path'):
            return "Missing input path"
        
        if not config.get('output_dir'):
            return "Missing output directory"
        
        # Check if input path exists
        input_path = config.get('input_path')
        if not os.path.exists(input_path):
            return f"Input path does not exist: {input_path}"
        
        # Check input type consistency
        input_type = config.get('input_type')
        if input_type == 'video' and not os.path.isfile(input_path):
            return f"Video input must be a file: {input_path}"
        
        if input_type == 'directory' and not os.path.isdir(input_path):
            return f"Directory input must be a directory: {input_path}"
        
        # For video files, check if FFmpeg is available
        if input_type == 'video':
            try:
                import subprocess
                result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=5)
                if result.returncode != 0:
                    return "FFmpeg not working properly. Please reinstall FFmpeg."
            except subprocess.TimeoutExpired:
                return "FFmpeg check timed out. Please check FFmpeg installation."
            except FileNotFoundError:
                return "FFmpeg not found. Please install FFmpeg and add it to your system PATH."
            except Exception as e:
                return f"Error checking FFmpeg: {str(e)}"
        
        return ""  # No issues found
    
    def _progress_callback(self, phase: str, current: int, total: int, description: str = ""):
        """Callback function to update progress from the processor."""
        if self.processing_cancelled or self.processing_complete:
            return
        
        self.current_phase = phase
        
        # Calculate overall progress across all phases
        phase_mapping = {
            "dependencies": 0,
            "extraction": 1, 
            "loading": 1,  # Same as extraction phase
            "sharpness": 2,
            "selection": 3,
            "saving": 4
        }
        
        current_phase_num = phase_mapping.get(phase, 0)
        
        # Calculate progress within current phase (0-20% per phase)
        phase_progress = 0
        if total > 0:
            phase_progress = (current / total) * 20  # Each phase is 20%
        
        # Calculate total progress (current phase * 20% + progress within phase)
        total_progress = (current_phase_num * 20) + phase_progress
        total_progress = min(100, max(0, total_progress))  # Clamp between 0-100
        
        # Schedule UI update on main thread
        self.app.call_from_thread(self._update_progress_ui, phase, current, total, total_progress, description)
    
    def _update_progress_ui(self, phase: str, current: int, total: int, total_progress: float, description: str):
        """Update the UI with progress information."""
        try:
            # Don't update UI if processing is complete or cancelled
            if self.processing_complete or self.processing_cancelled:
                return
                
            status_text = self.query_one("#status-text")
            phase_text = self.query_one("#phase-text")
            progress_bar = self.query_one("#progress-bar")
            
            # Update phase information
            phase_names = {
                "dependencies": "Checking Dependencies",
                "extraction": "Extracting Frames",
                "loading": "Loading Images", 
                "sharpness": "Calculating Sharpness",
                "selection": "Selecting Frames",
                "saving": "Saving Results"
            }
            
            phase_name = phase_names.get(phase, phase.title())
            phase_num = ["dependencies", "extraction", "loading", "sharpness", "selection", "saving"].index(phase) + 1
            
            if phase == "loading":
                phase_num = 2  # Loading is phase 2, same as extraction conceptually
            
            status_text.update(f"🔄 {phase_name}...")
            
            if total > 0:
                phase_text.update(f"Phase {phase_num}/5: {description} ({current}/{total})")
            else:
                phase_text.update(f"Phase {phase_num}/5: {description}")
            
            # Update progress bar
            progress_bar.update(progress=total_progress)
            
        except Exception as e:
            # Fail silently if UI update fails to avoid breaking processing
            pass
    
    def _process_frames(self) -> bool:
        """Worker function that runs the actual processing."""
        try:
            # Create a custom SharpFrames processor with progress callback
            processor_config = self.config.copy()
            processor_config['progress_callback'] = self._progress_callback
            
            # Update UI with config info for debugging
            self.app.call_from_thread(self._update_debug_info, f"Creating processor...")
            
            try:
                # Remove progress_callback from config to avoid duplicate argument
                clean_config = {k: v for k, v in processor_config.items() if k != 'progress_callback'}
                self.processor = MinimalProgressSharpFrames(progress_callback=self._progress_callback, **clean_config)
                self.app.call_from_thread(self._update_debug_info, f"Using progress-enabled SharpFrames processor")
            except Exception as init_error:
                self.app.call_from_thread(self._update_debug_info, f"Failed to create processor: {str(init_error)}")
                raise init_error
            
            # Run the processing
            self.app.call_from_thread(self._update_debug_info, f"Starting processing...")
            
            success = self.processor.run()
            
            if not success:
                self.app.call_from_thread(self._update_debug_info, "Processor run() returned False - check terminal for errors")
            
            return success
            
        except KeyboardInterrupt:
            self.app.call_from_thread(self._update_debug_info, "Processing cancelled by user")
            self.processing_cancelled = True
            return False
        except Exception as e:
            # Update UI with error information
            error_msg = f"Exception: {str(e)}"
            self.app.call_from_thread(self._update_debug_info, error_msg)
            # Re-raise the exception to be caught by worker error handler
            raise e
    
    def _update_debug_info(self, message: str):
        """Update UI with debug information."""
        try:
            phase_text = self.query_one("#phase-text")
            phase_text.update(f"Debug: {message}")
        except:
            pass  # Fail silently if UI update fails
    

    
    def on_worker_state_changed(self, event) -> None:
        """Handle worker state changes."""
        if event.worker.name == "frame_processor":
            status_text = self.query_one("#status-text")
            progress_bar = self.query_one("#progress-bar")
            phase_text = self.query_one("#phase-text")
            
            if event.worker.is_running:
                # Keep current progress display while running
                pass
            elif event.worker.is_finished:
                # Mark processing as complete to stop progress updates
                self.processing_complete = True
                
                if event.worker.result:
                    status_text.update("✅ Processing completed successfully!")
                    phase_text.update("All phases complete!")
                    progress_bar.display = False  # Hide the progress bar when complete
                else:
                    if self.processing_cancelled:
                        status_text.update("⚠️ Processing cancelled by user.")
                        phase_text.update("Processing was cancelled.")
                    else:
                        # Worker finished but returned False - this means processing failed
                        status_text.update("❌ Processing failed - see details below.")
                        
                        # Show a more helpful error message
                        input_path = self.config.get('input_path', '')
                        if input_path and not os.path.exists(input_path):
                            phase_text.update(f"Input file not found: {input_path}")
                        elif self.config.get('input_type') == 'video':
                            phase_text.update("Video processing failed. Check: 1) FFmpeg installed 2) Valid video file 3) File permissions")
                        else:
                            phase_text.update(f"Processing failed. Input: {input_path}")
                        
                        # Also try to run a quick FFmpeg check for video files
                        if self.config.get('input_type') == 'video':
                            try:
                                import subprocess
                                result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=5)
                                if result.returncode != 0:
                                    phase_text.update("FFmpeg not found or not working. Install FFmpeg and add to PATH.")
                            except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
                                phase_text.update("FFmpeg not found. Install FFmpeg and add to PATH for video processing.")
                    progress_bar.update(progress=0)  # Show failed state without animation
                
                # Change button to close
                self.query_one("#cancel-processing").label = "Close"
            elif event.worker.is_cancelled:
                # Mark processing as complete to stop progress updates
                self.processing_complete = True
                status_text.update("⚠️ Processing cancelled.")
                phase_text.update("Processing was cancelled.")
                progress_bar.update(progress=0)  # Show cancelled state without animation
                self.query_one("#cancel-processing").label = "Close"
    
    def on_worker_state_error(self, event) -> None:
        """Handle worker errors."""
        if event.worker.name == "frame_processor":
            # Mark processing as complete to stop progress updates
            self.processing_complete = True
            
            # Get detailed error information
            error_msg = "Unknown error"
            if event.error:
                error_msg = str(event.error)
                # If it's an exception, also get the traceback
                if hasattr(event.error, '__traceback__'):
                    import traceback
                    error_details = ''.join(traceback.format_exception(type(event.error), event.error, event.error.__traceback__))
                    print(f"Detailed error:\n{error_details}")
            
            self.query_one("#status-text").update(f"❌ Error: {error_msg}")
            self.query_one("#phase-text").update("Processing failed due to error.")
            self.query_one("#progress-bar").update(progress=0)  # Show error state without animation
            self.query_one("#cancel-processing").label = "Close"
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel-processing":
            if event.button.label == "Cancel":
                self.action_cancel()
            else:
                # Close button
                self.app.exit(result="completed")
    
    def action_cancel(self) -> None:
        """Cancel processing."""
        self.processing_cancelled = True
        
        # Cancel the worker if it's running
        workers = self.workers
        for worker in workers:
            if worker.name == "frame_processor" and not worker.is_finished:
                worker.cancel()
                break
        
        # If no worker was cancelled, just exit
        if not any(w.name == "frame_processor" for w in workers):
            self.app.exit(result="cancelled")


class MinimalProgressSharpFrames(SharpFrames):
    """Minimal SharpFrames extension that only intercepts progress without breaking functionality."""
    
    def __init__(self, progress_callback=None, **kwargs):
        self.progress_callback = progress_callback
        # Remove progress_callback from kwargs before passing to parent
        clean_kwargs = {k: v for k, v in kwargs.items() if k != 'progress_callback'}
        super().__init__(**clean_kwargs)
    
    def _update_progress(self, phase: str, current: int, total: int, description: str = ""):
        """Update progress if callback is available."""
        if self.progress_callback:
            self.progress_callback(phase, current, total, description)
    
    def _extract_frames(self, duration: float = None) -> bool:
        """Override to add real-time progress tracking to frame extraction."""
        output_pattern = os.path.join(self.temp_dir, f"frame_%05d.{self.output_format}")
        
        # Set a timeout threshold for the process in case it hangs
        process_timeout_seconds = 3600  # 1 hour timeout for FFmpeg process
        
        # Build the video filters string
        vf_filters = []
        vf_filters.append(f"fps={self.fps}")
        
        # Add scaling filter if width is specified
        if self.width > 0:
            vf_filters.append(f"scale={self.width}:-2")  # -2 maintains aspect ratio and ensures even height
            
        # Join all filters with commas
        vf_string = ",".join(vf_filters)
        
        command = [
            "ffmpeg",
            "-i", self.input_path,
            "-vf", vf_string,
            "-q:v", "1",  # Highest quality
            "-threads", str(cpu_count()),
            "-hide_banner",  # Hide verbose info
            "-loglevel", "warning",  # Show errors and warnings
            output_pattern
        ]
        
        # Print the FFmpeg command for debugging
        print(f"FFmpeg command: {' '.join(command)}")
        
        # Estimate total frames if duration is available
        estimated_total_frames = None
        if duration:
            estimated_total_frames = int(duration * self.fps)
            print(f"Estimated frames to extract: {estimated_total_frames}")
            self._update_progress("extraction", 0, estimated_total_frames, f"Extracting frames at {self.fps}fps")
        else:
            # If no duration, we can't estimate total, so progress will be indeterminate
            print("Video duration not found, cannot estimate total frames.")
            self._update_progress("extraction", 0, 0, "Extracting frames (unknown total)")

        # Start FFmpeg with real-time progress monitoring
        import queue
        import threading
        
        process = None
        start_time = time.time()
        stderr_queue = queue.Queue()
        stderr_chunks = []
        last_file_count = 0
        last_stderr_check = 0

        try:
            # Start FFmpeg process
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Thread to read stderr without blocking
            def read_stderr():
                try:
                    for line in iter(process.stderr.readline, ''):
                        stderr_queue.put(line)
                        if not line:
                            break
                except Exception as e:
                    stderr_queue.put(f"Error reading stderr: {str(e)}")

            stderr_thread = threading.Thread(target=read_stderr, daemon=True)
            stderr_thread.start()

            # Monitor process completion and update progress based on file count
            while process.poll() is None:
                # Check file count periodically
                try:
                    frame_files = os.listdir(self.temp_dir)
                    file_count = len(frame_files)

                    if file_count > last_file_count:
                        # Update progress in real-time
                        if estimated_total_frames:
                            self._update_progress("extraction", file_count, estimated_total_frames, 
                                                f"Extracted {file_count}/{estimated_total_frames} frames")
                        else:
                            self._update_progress("extraction", file_count, 0, f"Extracted {file_count} frames")
                        last_file_count = file_count

                    # Check and collect stderr (limit how often we process to avoid slowdown)
                    current_time = time.time()
                    if current_time - last_stderr_check > 1.0:  # Check every second
                        while not stderr_queue.empty():
                            line = stderr_queue.get_nowait()
                            stderr_chunks.append(line)
                            # Only log severe errors, ignore aspect ratio warnings
                            if "Cannot store exact aspect ratio" not in line and "[warning]" not in line.lower():
                                print(f"FFmpeg: {line.strip()}")
                        last_stderr_check = current_time

                    # Check for process timeout
                    if time.time() - start_time > process_timeout_seconds:
                        raise subprocess.TimeoutExpired(command, process_timeout_seconds)

                except FileNotFoundError:
                     # Temp dir might not exist yet briefly at the start
                     pass
                except Exception as e:
                    print(f"Error during progress monitoring: {str(e)}")
                    # Continue monitoring the process itself

                # Small sleep to prevent high CPU usage and allow interrupts
                try:
                    time.sleep(0.1)  # Check more frequently for better responsiveness
                except KeyboardInterrupt:
                    print("Keyboard interrupt received. Terminating FFmpeg...")
                    if process:
                        process.terminate()
                    raise

            # Collect any remaining stderr
            while not stderr_queue.empty():
                stderr_chunks.append(stderr_queue.get_nowait())
            
            # Process finished, check return code
            return_code = process.returncode
            
            # Final progress update
            final_frame_count = len(os.listdir(self.temp_dir))
            self._update_progress("extraction", final_frame_count, final_frame_count, 
                                f"Extraction complete: {final_frame_count} frames")

            print(f"Extraction complete: {final_frame_count} frames extracted")

            # Check result
            if return_code != 0:
                error_message = f"FFmpeg failed with exit code {return_code}."
                if stderr_chunks:
                    error_message += f"FFmpeg stderr: {''.join(stderr_chunks)}"
                raise Exception(error_message)

            return True

        except KeyboardInterrupt:
            print("Keyboard interrupt received during frame extraction.")
            if process:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
            raise
        except Exception as e:
            print(f"Error during frame extraction: {str(e)}")
            if process:
                process.terminate()
            raise
    
    def _calculate_sharpness(self, frame_paths: List[str]) -> List[Dict[str, Any]]:
        """Override to add progress tracking to sharpness calculation."""
        desc = "Calculating sharpness for frames" if self.input_type == "video" else "Calculating sharpness for images"
        self._update_progress("sharpness", 0, len(frame_paths), desc)
        
        # Use the parent implementation but track progress
        frames_data = []
        
        # Use ThreadPoolExecutor for parallel processing (same as parent)
        num_workers = min(cpu_count(), len(frame_paths)) if len(frame_paths) > 0 else 1
        completed_count = 0
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            # Submit tasks
            futures = {}
            for idx, path in enumerate(frame_paths):
                future = executor.submit(self._process_image, path)
                futures[future] = {"index": idx, "path": path}

            # Process completed futures with progress updates
            for future in concurrent.futures.as_completed(futures):
                task_info = futures[future]
                path = task_info["path"]
                idx = task_info["index"]
                frame_id = os.path.basename(path)

                try:
                    score = future.result()
                    frame_data = {
                        "id": frame_id,
                        "path": path,
                        "index": idx,
                        "sharpnessScore": score
                    }
                    frames_data.append(frame_data)
                except Exception as e:
                    print(f"Error processing {path}: {str(e)}")

                completed_count += 1
                self._update_progress("sharpness", completed_count, len(frame_paths), 
                                    f"Processed {completed_count}/{len(frame_paths)} items")

        # Sort by index like parent method
        frames_data.sort(key=lambda x: x["index"])
        return frames_data
    
    def _analyze_and_select_frames(self, frame_paths: List[str]) -> List[Dict[str, Any]]:
        """Override to add progress tracking to frame selection."""
        print("Calculating sharpness scores...")
        frames_with_scores = self._calculate_sharpness(frame_paths)

        if not frames_with_scores:
            print("No frames/images could be scored.")
            return []

        print(f"Selecting frames/images using {self.selection_method} method...")
        self._update_progress("selection", 0, len(frames_with_scores), f"Starting {self.selection_method} selection")
        
        # Call parent method for the actual selection logic
        # Import here to avoid circular imports
        from .selection_methods import (
            select_best_n_frames,
            select_batched_frames,
            select_outlier_removal_frames
        )
        
        selected_frames_data = []
        if self.selection_method == "best-n":
            selected_frames_data = select_best_n_frames(
                frames_with_scores,
                self.num_frames,
                self.min_buffer,
                self.BEST_N_SHARPNESS_WEIGHT,
                self.BEST_N_DISTRIBUTION_WEIGHT
            )
        elif self.selection_method == "batched":
            selected_frames_data = select_batched_frames(
                frames_with_scores,
                self.batch_size,
                self.batch_buffer
            )
        elif self.selection_method == "outlier-removal":
            all_frames_data = select_outlier_removal_frames(
                frames_with_scores,
                self.outlier_window_size,
                self.outlier_sensitivity,
                self.OUTLIER_MIN_NEIGHBORS,
                self.OUTLIER_THRESHOLD_DIVISOR
            )
            selected_frames_data = [frame for frame in all_frames_data if frame.get("selected", True)]
        else:
            print(f"Warning: Unknown selection method '{self.selection_method}'. Using best-n instead.")
            selected_frames_data = select_best_n_frames(
                frames_with_scores,
                self.num_frames,
                self.min_buffer,
                self.BEST_N_SHARPNESS_WEIGHT,
                self.BEST_N_DISTRIBUTION_WEIGHT
            )

        self._update_progress("selection", len(selected_frames_data), len(selected_frames_data), 
                            f"Selected {len(selected_frames_data)} frames")

        if not selected_frames_data:
            print("No frames/images were selected based on the criteria.")

        return selected_frames_data
    
    def _save_frames(self, selected_frames: List[Dict[str, Any]], progress_bar=None) -> None:
        """Override to add progress tracking to frame saving."""
        self._update_progress("saving", 0, len(selected_frames), "Starting to save frames")
        
        # Call parent method - but we need to implement it since parent expects a progress_bar parameter
        os.makedirs(self.output_dir, exist_ok=True)
        metadata_list = []

        for idx, frame_data in enumerate(selected_frames):
            src_path = frame_data["path"]
            original_id = frame_data["id"]
            original_index = frame_data["index"]
            sharpness_score = frame_data.get("sharpnessScore", 0)

            filename = self.OUTPUT_FILENAME_FORMAT.format(
                seq=idx + 1,
                ext=self.output_format
            )
            dst_path = os.path.join(self.output_dir, filename)

            try:
                if self.width > 0 and self.input_type == "directory":
                    img = cv2.imread(src_path)
                    if img is None:
                        raise Exception(f"Failed to read image for resizing: {src_path}")
                    
                    height = int(img.shape[0] * (self.width / img.shape[1]))
                    if height % 2 != 0:
                        height += 1
                    
                    resized_img = cv2.resize(img, (self.width, height), interpolation=cv2.INTER_AREA)
                    cv2.imwrite(dst_path, resized_img)
                else:
                    shutil.copy2(src_path, dst_path)
            except Exception as e:
                print(f"Error saving {src_path} to {dst_path}: {e}")
                continue

            metadata_list.append({
                "output_filename": filename,
                "original_id": original_id,
                "original_index": original_index,
                "sharpness_score": sharpness_score
            })

            # Update progress for each saved file
            self._update_progress("saving", idx + 1, len(selected_frames), 
                                f"Saved {idx + 1}/{len(selected_frames)} frames")

        # Save metadata
        metadata_path = os.path.join(self.output_dir, "selected_metadata.json")
        try:
            metadata = {
                "input_path": self.input_path,
                "input_type": self.input_type,
                "total_processed": len(selected_frames),
                "selection_method": self.selection_method,
                "method_parameters": self._get_method_params_for_metadata(),
                "output_format": self.output_format,
                "resize_width": self.width if self.width > 0 else None,
                "selected_items": metadata_list
            }
            
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
                
            print(f"Metadata saved to: {metadata_path}")
        except Exception as e:
            print(f"Warning: Could not save metadata: {str(e)}")


# Add missing imports
import subprocess
import shutil
import tempfile
import cv2
import time
import json
import concurrent.futures
import queue
import threading
from multiprocessing import cpu_count

# Import the original SharpFrames and selection methods
from .sharp_frames_processor import SharpFrames, ImageProcessingError


class SharpFramesApp(App):
    """Main Sharp Frames Textual application."""
    
    CSS = """
    Screen {
        layout: vertical;
    }
    
    Header {
        dock: top;
    }
    
    Footer {
        dock: bottom;
    }
    
    .title {
        text-align: center;
        text-style: bold;
        margin: 0;
        color: $accent;
    }
    
    .step-info {
        text-align: center;
        margin: 0;
        color: $text-muted;
    }
    
    .question {
        text-style: bold;
        margin: 1 0 0 0;
        color: $primary;
    }
    
    .hint {
        margin: 0;
        color: $text-muted;
        text-style: italic;
    }
    
    .summary {
        margin: 1 0;
        padding: 1;
        border: solid $primary;
        background: $surface;
    }
    
    .buttons {
        margin: 0 0 1 0;
        align: center middle;
        height: 3;
    }
    
    Button {
        margin: 0 1;
    }
    
    #main-container {
        padding: 1;
        height: 1fr;
        min-height: 0;
    }
    
    #step-container {
        height: 1fr;
        padding: 0 1;
        min-height: 0;
        overflow: auto;
    }
    
    #processing-container {
        padding: 1;
        text-align: center;
    }
    
    #phase-text {
        margin: 0 0 2 0;
        color: $text-muted;
        text-style: italic;
    }
    
    Input {
        margin: 0;
    }
    
    Select {
        margin: 0;
    }
    
    RadioSet {
        margin: 0;
    }
    
    Checkbox {
        margin: 0;
    }
    
    Label {
        margin: 0;
    }
    """
    
    def on_mount(self) -> None:
        """Start with the configuration form."""
        self.push_screen(ConfigurationForm())


def run_textual_interface() -> bool:
    """Run the Textual interface and return success status."""
    try:
        app = SharpFramesApp()
        result = app.run()
        return result != "cancelled"
    except Exception as e:
        print(f"Error running Textual interface: {e}")
        return False


if __name__ == "__main__":
    run_textual_interface() 