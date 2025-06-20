"""
Constants for the Sharp Frames UI components.
"""


class WorkerNames:
    """Constants for worker names."""
    FRAME_PROCESSOR = "frame_processor"


class UIElementIds:
    """Constants for UI element IDs."""
    # Form field IDs
    INPUT_TYPE_RADIO = "input-type-radio"
    VIDEO_OPTION = "video-option"
    DIRECTORY_OPTION = "directory-option"
    INPUT_PATH_FIELD = "input-path-field"
    OUTPUT_DIR_FIELD = "output-dir-field"
    FPS_FIELD = "fps-field"
    SELECTION_METHOD_FIELD = "selection-method-field"
    OUTPUT_FORMAT_FIELD = "output-format-field"
    WIDTH_FIELD = "width-field"
    FORCE_OVERWRITE_FIELD = "force-overwrite-field"
    PARAM1 = "param1"
    PARAM2 = "param2"
    
    # Button IDs
    BACK_BTN = "back-btn"
    NEXT_BTN = "next-btn"
    CANCEL_BTN = "cancel-btn"
    CANCEL_PROCESSING = "cancel-processing"
    
    # Display element IDs
    STEP_INFO = "step-info"
    STEP_CONTAINER = "step-container"
    MAIN_CONTAINER = "main-container"
    STATUS_TEXT = "status-text"
    PHASE_TEXT = "phase-text"
    PROGRESS_BAR = "progress-bar"
    PROCESSING_CONTAINER = "processing-container"


class ProcessingPhases:
    """Constants for processing phases."""
    DEPENDENCIES = "dependencies"
    EXTRACTION = "extraction"
    LOADING = "loading"
    SHARPNESS = "sharpness"
    SELECTION = "selection"
    SAVING = "saving"


class SelectionMethods:
    """Constants for selection methods."""
    BEST_N = "best-n"
    BATCHED = "batched"
    OUTLIER_REMOVAL = "outlier-removal"


class InputTypes:
    """Constants for input types."""
    VIDEO = "video"
    DIRECTORY = "directory"


class OutputFormats:
    """Constants for output formats."""
    JPG = "jpg"
    PNG = "png"


class ProcessingConfig:
    """Configuration constants for processing operations."""
    FFMPEG_TIMEOUT_SECONDS = 3600  # 1 hour timeout for FFmpeg
    PROGRESS_CHECK_INTERVAL = 0.1  # Check progress every 100ms
    MAX_CONCURRENT_WORKERS = 4  # Default to 4 workers, can be dynamically set
    STDERR_BUFFER_SIZE = 1000  # Maximum stderr lines to keep
    UI_UPDATE_INTERVAL = 1.0  # Update UI every second during stderr processing 