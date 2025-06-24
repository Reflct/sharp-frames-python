"""
Step handlers for configuration wizard.

This module contains specialized classes for handling different steps
of the configuration wizard, breaking down the large ConfigurationForm
into smaller, focused components.
"""

from typing import Dict, Any
from textual.containers import Container
from textual.widgets import Label, Input, Select, RadioSet, RadioButton, Checkbox, Static

from ..constants import UIElementIds, InputTypes
from .validators import (
    IntRangeValidator, 
    VideoFileValidator, 
    VideoDirectoryValidator, 
    ImageDirectoryValidator,
    OutputDirectoryValidator
)
from ..utils.path_sanitizer import PathSanitizer


class BaseStepHandler:
    """Base class for configuration step handlers."""
    
    def __init__(self, config_data: Dict[str, Any]):
        self.config_data = config_data
    
    def create_step(self, container: Container) -> None:
        """Create the step UI. Must be implemented by subclasses."""
        raise NotImplementedError
    
    def validate_step(self) -> bool:
        """Validate the current step. Override if needed."""
        return True
    
    def save_step_data(self, container: Container) -> bool:
        """Save data from the step. Override if needed."""
        return True


class InputTypeStepHandler(BaseStepHandler):
    """Handler for input type selection step."""
    
    def create_step(self, container: Container) -> None:
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
        
        # Add description label
        description_label = Label("Extract and select the sharpest frames of a single video", 
                                classes="hint", id="input-type-description")
        container.mount(description_label)
        
        # Set current value if exists
        if "input_type" in self.config_data:
            current_type = self.config_data["input_type"]
            video_radio.value = current_type == InputTypes.VIDEO
            video_dir_radio.value = current_type == InputTypes.VIDEO_DIRECTORY
            dir_radio.value = current_type == InputTypes.DIRECTORY
            
            # Update description based on current selection
            if current_type == InputTypes.VIDEO:
                description_label.update("Extract and select the sharpest frames of a single video")
            elif current_type == InputTypes.VIDEO_DIRECTORY:
                description_label.update("Extract and select the sharpest frames of all videos in a folder")
            elif current_type == InputTypes.DIRECTORY:
                description_label.update("Select the sharpest images from a folder")


class InputPathStepHandler(BaseStepHandler):
    """Handler for input path selection step."""
    
    def create_step(self, container: Container) -> None:
        """Create the input path step."""
        input_type = self.config_data.get("input_type", InputTypes.VIDEO)
        
        # Create appropriate validator based on input type
        if input_type == InputTypes.VIDEO:
            container.mount(Label("Enter the path to your video file:", classes="question"))
            placeholder = "e.g., /path/to/video.mp4"
            validator = VideoFileValidator(must_exist=True)
        elif input_type == InputTypes.VIDEO_DIRECTORY:
            container.mount(Label("Enter the path to your video directory:", classes="question"))
            placeholder = "e.g., /path/to/videos/"
            validator = VideoDirectoryValidator(must_exist=True)
        else:
            container.mount(Label("Enter the path to your image directory:", classes="question"))
            placeholder = "e.g., /path/to/images/"
            validator = ImageDirectoryValidator(must_exist=True)
        
        input_widget = Input(
            placeholder=placeholder,
            id=UIElementIds.INPUT_PATH_FIELD,
            value=self.config_data.get("input_path", ""),
            validators=[validator]
        )
        container.mount(input_widget)
        
        # Add helpful text about automatic cleaning
        helper_label = Label("Quotes will be automatically removed", classes="hint")
        container.mount(helper_label)
        
        input_widget.focus()
    



class OutputDirStepHandler(BaseStepHandler):
    """Handler for output directory selection step."""
    
    def create_step(self, container: Container) -> None:
        """Create the output directory step."""
        container.mount(Label("Where should the selected frames be saved?", classes="question"))
        input_widget = Input(
            placeholder="e.g., /path/to/output",
            id="output-dir-field",
            value=self.config_data.get("output_dir", ""),
            validators=[OutputDirectoryValidator(create_if_missing=True)]
        )
        container.mount(input_widget)
        
        # Add helpful text about automatic cleaning
        helper_label = Label("Quotes will be automatically removed", classes="hint")
        container.mount(helper_label)
        
        input_widget.focus()
    



class FpsStepHandler(BaseStepHandler):
    """Handler for FPS selection step."""
    
    def create_step(self, container: Container) -> None:
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


class SelectionMethodStepHandler(BaseStepHandler):
    """Handler for selection method step."""
    
    def create_step(self, container: Container) -> None:
        """Create the selection method step."""
        container.mount(Label("Which frame selection method would you like to use?", classes="question"))
        select_widget = Select([
            ("Best N frames - Choose a specific number of frames", "best-n"),
            ("Batched selection - Best frame from each batch", "batched"),
            ("Outlier removal - Remove the blurriest frames", "outlier-removal")
        ], value=self.config_data.get("selection_method", "best-n"), id="selection-method-field")
        container.mount(select_widget)
        
        # Add description label
        current_method = self.config_data.get("selection_method", "best-n")
        description_text = self._get_method_description(current_method)
        description_label = Label(description_text, classes="hint", id="selection-method-description")
        container.mount(description_label)
    
    def _get_method_description(self, method: str) -> str:
        """Get description text for a selection method."""
        descriptions = {
            "best-n": "Selects the N sharpest frames from the entire video with minimum spacing between frames",
            "batched": "Divides frames into batches and selects the sharpest frame from each batch for even distribution",
            "outlier-removal": "Analyzes frame sharpness and removes unusually blurry frames to keep the clearest ones"
        }
        return descriptions.get(method, "")


class MethodParamsStepHandler(BaseStepHandler):
    """Handler for method-specific parameters step."""
    
    def create_step(self, container: Container) -> None:
        """Create the method-specific parameters step."""
        method = self.config_data.get("selection_method", "best-n")
        
        if method == "best-n":
            self._create_best_n_params(container)
        elif method == "batched":
            self._create_batched_params(container)
        elif method == "outlier-removal":
            self._create_outlier_params(container)
    
    def _create_best_n_params(self, container: Container) -> None:
        """Create best-n method parameters."""
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
    
    def _create_batched_params(self, container: Container) -> None:
        """Create batched method parameters."""
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
    
    def _create_outlier_params(self, container: Container) -> None:
        """Create outlier removal method parameters."""
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


class OutputFormatStepHandler(BaseStepHandler):
    """Handler for output format step."""
    
    def create_step(self, container: Container) -> None:
        """Create the output format step."""
        container.mount(Label("What format should the output images be saved in?", classes="question"))
        select_widget = Select([
            ("JPEG (smaller file size)", "jpg"),
            ("PNG (better quality)", "png")
        ], value=self.config_data.get("output_format", "jpg"), id="output-format-field")
        container.mount(select_widget)


class WidthStepHandler(BaseStepHandler):
    """Handler for width/resize step."""
    
    def create_step(self, container: Container) -> None:
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


class ForceOverwriteStepHandler(BaseStepHandler):
    """Handler for force overwrite step."""
    
    def create_step(self, container: Container) -> None:
        """Create the force overwrite step."""
        container.mount(Label("Should existing files be overwritten without confirmation?", classes="question"))
        checkbox = Checkbox(
            "Yes, overwrite existing files",
            value=self.config_data.get("force_overwrite", False),
            id="force-overwrite-field"
        )
        container.mount(checkbox)


class ConfirmStepHandler(BaseStepHandler):
    """Handler for confirmation step."""
    
    def create_step(self, container: Container) -> None:
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
        if input_type != InputTypes.DIRECTORY:
            lines.append(f"Output Format: {self.config_data.get('output_format', 'jpg').upper()}")
            
            width = self.config_data.get('width', 0)
            if width > 0:
                lines.append(f"Resize Width: {width}px")
            else:
                lines.append("Resize: No resizing")
        else:
            lines.append("Output Format: Preserve original formats")
            lines.append("Resize: Preserve original dimensions")
        
        overwrite = self.config_data.get('force_overwrite', False)
        lines.append(f"Force Overwrite: {'Yes' if overwrite else 'No'}")
        
        return "\n".join(lines) 