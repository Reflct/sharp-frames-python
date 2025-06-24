"""
Validation components for Sharp Frames UI.
"""

import os
from typing import Optional, Set, List
from pathlib import Path

from textual.widgets import Input
from textual.validation import ValidationResult, Validator
from ..utils.path_sanitizer import PathSanitizer


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
        
        # Sanitize the path input
        sanitized_path, changes = PathSanitizer.sanitize(value)
        
        # Store sanitized path for retrieval
        self._last_sanitized = sanitized_path
        self._last_changes = changes
        
        if not sanitized_path:
            return self.failure("Path cannot be empty")
        
        path = Path(os.path.expanduser(sanitized_path))
        
        if self.must_exist:
            if not path.exists():
                return self.failure("Path does not exist")
            
            if self.must_be_file and not path.is_file():
                return self.failure("Path must be a file")
            
            if self.must_be_dir and not path.is_dir():
                return self.failure("Path must be a directory")
        
        return self.success()
    
    def get_sanitized_value(self) -> str:
        """Get the last sanitized path value."""
        return getattr(self, '_last_sanitized', '')
    
    def get_sanitization_changes(self) -> list:
        """Get the list of changes made during sanitization."""
        return getattr(self, '_last_changes', [])


class VideoFileValidator(Validator):
    """Validator specifically for video files with format checking."""
    
    # Common video file extensions
    SUPPORTED_VIDEO_EXTENSIONS = {
        '.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', 
        '.m4v', '.3gp', '.ogv', '.ts', '.mts', '.m2ts'
    }
    
    def __init__(self, must_exist: bool = True):
        self.must_exist = must_exist
        super().__init__()
    
    def validate(self, value: str) -> ValidationResult:
        if not value.strip():
            return self.failure("Please enter a video file path (e.g., /path/to/video.mp4)")
        
        # Sanitize the path input
        sanitized_path, changes = PathSanitizer.sanitize(value)
        
        # Store sanitized path for retrieval
        self._last_sanitized = sanitized_path
        self._last_changes = changes
        
        if not sanitized_path:
            return self.failure("Please enter a video file path (e.g., /path/to/video.mp4)")
        
        path = Path(os.path.expanduser(sanitized_path))
        
        # Check file extension first (even if file doesn't exist yet)
        if path.suffix.lower() not in self.SUPPORTED_VIDEO_EXTENSIONS:
            supported_formats = ', '.join(sorted(self.SUPPORTED_VIDEO_EXTENSIONS))
            return self.failure(f"Please select a video file. Supported formats: {supported_formats}")
        
        if self.must_exist:
            if not path.exists():
                return self.failure(f"Video file not found: {path}")
            
            if not path.is_file():
                return self.failure("Path must be a video file, not a directory")
            
            # Check if file is readable and not empty
            try:
                file_size = path.stat().st_size
                if file_size == 0:
                    return self.failure("Video file is empty")
                elif file_size < 1024:  # Less than 1KB is suspicious
                    return self.failure(f"Video file is very small ({file_size} bytes) - may be corrupted")
            except (OSError, PermissionError):
                return self.failure("Cannot access video file - check permissions")
        
        return self.success()
    
    def get_sanitized_value(self) -> str:
        """Get the last sanitized path value."""
        return getattr(self, '_last_sanitized', '')
    
    def get_sanitization_changes(self) -> list:
        """Get the list of changes made during sanitization."""
        return getattr(self, '_last_changes', [])


class VideoDirectoryValidator(Validator):
    """Validator for directories containing video files."""
    
    def __init__(self, must_exist: bool = True, min_videos: int = 1):
        self.must_exist = must_exist
        self.min_videos = min_videos
        super().__init__()
    
    def validate(self, value: str) -> ValidationResult:
        if not value.strip():
            return self.failure("Please enter a directory path containing video files")
        
        # Sanitize the path input
        sanitized_path, changes = PathSanitizer.sanitize(value)
        
        # Store sanitized path for retrieval
        self._last_sanitized = sanitized_path
        self._last_changes = changes
        
        if not sanitized_path:
            return self.failure("Please enter a directory path containing video files")
        
        path = Path(os.path.expanduser(sanitized_path))
        
        if self.must_exist:
            if not path.exists():
                return self.failure(f"Directory not found: {path}")
            
            if not path.is_dir():
                return self.failure("Path must be a directory, not a file")
            
            # Check for video files in directory
            try:
                video_files = self._find_video_files(path)
                if len(video_files) < self.min_videos:
                    if len(video_files) == 0:
                        return self.failure("No video files found in directory. Please select a directory containing video files.")
                    else:
                        return self.failure(f"Found only {len(video_files)} video file(s), need at least {self.min_videos}")
                
            except (OSError, PermissionError):
                return self.failure("Cannot access directory - check permissions")
        
        return self.success()
    
    def _find_video_files(self, directory: Path) -> List[Path]:
        """Find video files in the given directory."""
        video_extensions = VideoFileValidator.SUPPORTED_VIDEO_EXTENSIONS
        video_files = []
        
        try:
            for file_path in directory.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in video_extensions:
                    video_files.append(file_path)
        except (OSError, PermissionError):
            pass
        
        return video_files
    
    def get_sanitized_value(self) -> str:
        """Get the last sanitized path value."""
        return getattr(self, '_last_sanitized', '')
    
    def get_sanitization_changes(self) -> list:
        """Get the list of changes made during sanitization."""
        return getattr(self, '_last_changes', [])


class ImageDirectoryValidator(Validator):
    """Validator for directories containing image files."""
    
    # Common image file extensions
    SUPPORTED_IMAGE_EXTENSIONS = {
        '.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', 
        '.webp', '.gif', '.ppm', '.pgm', '.pbm'
    }
    
    def __init__(self, must_exist: bool = True, min_images: int = 1):
        self.must_exist = must_exist
        self.min_images = min_images
        super().__init__()
    
    def validate(self, value: str) -> ValidationResult:
        if not value.strip():
            return self.failure("Please enter a directory path containing image files")
        
        # Sanitize the path input
        sanitized_path, changes = PathSanitizer.sanitize(value)
        
        # Store sanitized path for retrieval
        self._last_sanitized = sanitized_path
        self._last_changes = changes
        
        if not sanitized_path:
            return self.failure("Please enter a directory path containing image files")
        
        path = Path(os.path.expanduser(sanitized_path))
        
        if self.must_exist:
            if not path.exists():
                return self.failure(f"Directory not found: {path}")
            
            if not path.is_dir():
                return self.failure("Path must be a directory, not a file")
            
            # Check for image files in directory
            try:
                image_files = self._find_image_files(path)
                if len(image_files) < self.min_images:
                    if len(image_files) == 0:
                        supported_formats = ', '.join(sorted(self.SUPPORTED_IMAGE_EXTENSIONS))
                        return self.failure(f"No image files found in directory. Supported formats: {supported_formats}")
                    else:
                        return self.failure(f"Found only {len(image_files)} image file(s), need at least {self.min_images}")
                
            except (OSError, PermissionError):
                return self.failure("Cannot access directory - check permissions")
        
        return self.success()
    
    def _find_image_files(self, directory: Path) -> List[Path]:
        """Find image files in the given directory."""
        image_files = []
        
        try:
            for file_path in directory.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in self.SUPPORTED_IMAGE_EXTENSIONS:
                    image_files.append(file_path)
        except (OSError, PermissionError):
            pass
        
        return image_files
    
    def get_sanitized_value(self) -> str:
        """Get the last sanitized path value."""
        return getattr(self, '_last_sanitized', '')
    
    def get_sanitization_changes(self) -> list:
        """Get the list of changes made during sanitization."""
        return getattr(self, '_last_changes', [])


class OutputDirectoryValidator(Validator):
    """Validator for output directories with creation capability."""
    
    def __init__(self, create_if_missing: bool = True):
        self.create_if_missing = create_if_missing
        super().__init__()
    
    def validate(self, value: str) -> ValidationResult:
        if not value.strip():
            return self.failure("Please enter an output directory path")
        
        # Sanitize the path input
        sanitized_path, changes = PathSanitizer.sanitize(value)
        
        # Store sanitized path for retrieval
        self._last_sanitized = sanitized_path
        self._last_changes = changes
        
        if not sanitized_path:
            return self.failure("Please enter an output directory path")
        
        path = Path(os.path.expanduser(sanitized_path))
        
        # Check if path exists
        if path.exists():
            if not path.is_dir():
                return self.failure("Output path exists but is not a directory")
            
            # Check if directory is writable
            try:
                # Try creating a temporary file to test write permissions
                test_file = path / ".write_test"
                test_file.touch()
                test_file.unlink()  # Clean up
            except (OSError, PermissionError):
                return self.failure("No write permission for output directory")
        else:
            # Directory doesn't exist
            if self.create_if_missing:
                # Check if parent directory exists and is writable
                parent = path.parent
                if not parent.exists():
                    return self.failure(f"Parent directory does not exist: {parent}")
                
                if not parent.is_dir():
                    return self.failure(f"Parent path is not a directory: {parent}")
                
                try:
                    # Test write permission on parent directory
                    test_file = parent / ".write_test"
                    test_file.touch()
                    test_file.unlink()  # Clean up
                except (OSError, PermissionError):
                    return self.failure(f"No write permission to create directory in: {parent}")
            else:
                return self.failure("Output directory does not exist")
        
        return self.success()
    
    def get_sanitized_value(self) -> str:
        """Get the last sanitized path value."""
        return getattr(self, '_last_sanitized', '')
    
    def get_sanitization_changes(self) -> list:
        """Get the list of changes made during sanitization."""
        return getattr(self, '_last_changes', [])


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


class ValidationHelpers:
    """Helper methods for common validation patterns."""
    
    @staticmethod
    def validate_required_field(widget: Input, field_name: str) -> bool:
        """Validate that a required field is not empty."""
        value = widget.value.strip()
        if not value:
            widget.focus()
            print(f"Validation failed: {field_name} cannot be empty")
            return False
        return True
    
    @staticmethod
    def validate_path_exists(widget: Input, field_name: str) -> bool:
        """Validate that a path exists."""
        path = widget.value.strip()
        if path and not os.path.exists(os.path.expanduser(path)):
            widget.focus()
            print(f"Validation failed: {field_name} path does not exist: {path}")
            return False
        return True
    
    @staticmethod
    def validate_numeric_field(widget: Input, field_name: str) -> bool:
        """Validate that a numeric field has valid input."""
        if not widget.is_valid:
            widget.focus()
            print(f"Validation failed: {field_name} has invalid value")
            return False
        return True
    
    @staticmethod
    def get_int_value(widget: Input, default: int = 0) -> int:
        """Safely get integer value from input widget."""
        try:
            return int(widget.value.strip())
        except (ValueError, AttributeError):
            return default
    
    @staticmethod
    def create_input_validator(input_type: str, must_exist: bool = True):
        """Factory method to create appropriate validator based on input type."""
        if input_type == "video":
            return VideoFileValidator(must_exist=must_exist)
        elif input_type == "video_directory":
            return VideoDirectoryValidator(must_exist=must_exist)
        elif input_type == "directory":
            return ImageDirectoryValidator(must_exist=must_exist)
        else:
            return PathValidator(must_exist=must_exist) 