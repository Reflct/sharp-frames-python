"""
Validation components for Sharp Frames UI.
"""

import os
from typing import Optional
from pathlib import Path

from textual.widgets import Input
from textual.validation import ValidationResult, Validator


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