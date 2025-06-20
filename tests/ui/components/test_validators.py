"""
Tests for Sharp Frames UI validators.

These validators are critical for data integrity and user experience.
They're pure functions making them ideal for unit testing.
"""

import os
import pytest
from unittest.mock import patch, Mock

from sharp_frames.ui.components.validators import (
    PathValidator,
    IntRangeValidator,
    ValidationHelpers
)


class TestPathValidator:
    """Test cases for PathValidator."""
    
    def test_empty_path_fails(self):
        """Empty paths should fail validation."""
        validator = PathValidator()
        result = validator.validate("")
        assert not result.is_valid
        assert "cannot be empty" in result.failure_descriptions[0]
        
        result = validator.validate("   ")  # Whitespace only
        assert not result.is_valid
    
    def test_nonexistent_path_fails_when_must_exist(self):
        """Non-existent paths should fail when must_exist=True."""
        validator = PathValidator(must_exist=True)
        result = validator.validate("/definitely/does/not/exist")
        assert not result.is_valid
        assert "does not exist" in result.failure_descriptions[0]
    
    def test_nonexistent_path_passes_when_must_exist_false(self):
        """Non-existent paths should pass when must_exist=False."""
        validator = PathValidator(must_exist=False)
        result = validator.validate("/some/new/path")
        assert result.is_valid
    
    def test_existing_file_validation(self, temp_file):
        """Test validation with actual existing file."""
        # Test file exists and passes general validation
        validator = PathValidator(must_exist=True)
        result = validator.validate(temp_file)
        assert result.is_valid
        
        # Test file passes file-specific validation
        validator = PathValidator(must_exist=True, must_be_file=True)
        result = validator.validate(temp_file)
        assert result.is_valid
        
        # Test file fails directory-specific validation
        validator = PathValidator(must_exist=True, must_be_dir=True)
        result = validator.validate(temp_file)
        assert not result.is_valid
        assert "must be a directory" in result.failure_descriptions[0]
    
    def test_existing_directory_validation(self, temp_dir):
        """Test validation with actual existing directory."""
        # Test directory exists and passes general validation
        validator = PathValidator(must_exist=True)
        result = validator.validate(temp_dir)
        assert result.is_valid
        
        # Test directory passes directory-specific validation
        validator = PathValidator(must_exist=True, must_be_dir=True)
        result = validator.validate(temp_dir)
        assert result.is_valid
        
        # Test directory fails file-specific validation
        validator = PathValidator(must_exist=True, must_be_file=True)
        result = validator.validate(temp_dir)
        assert not result.is_valid
        assert "must be a file" in result.failure_descriptions[0]
    
    def test_path_expansion(self):
        """Test that ~ gets expanded properly."""
        with patch('os.path.expanduser') as mock_expand, \
             patch('pathlib.Path.exists') as mock_exists:
            
            mock_expand.return_value = "/home/user/test"
            mock_exists.return_value = True
            
            validator = PathValidator(must_exist=True)
            result = validator.validate("~/test")
            
            assert result.is_valid
            mock_expand.assert_called_with("~/test")


class TestIntRangeValidator:
    """Test cases for IntRangeValidator."""
    
    def test_empty_value_fails(self):
        """Empty values should fail validation."""
        validator = IntRangeValidator()
        result = validator.validate("")
        assert not result.is_valid
        assert "cannot be empty" in result.failure_descriptions[0]
        
        result = validator.validate("   ")  # Whitespace only
        assert not result.is_valid
    
    def test_non_integer_fails(self):
        """Non-integer values should fail validation."""
        validator = IntRangeValidator()
        
        test_cases = ["abc", "12.5", "12.0", "1.2e3", "not_a_number", "12abc"]
        
        for test_value in test_cases:
            result = validator.validate(test_value)
            assert not result.is_valid, f"'{test_value}' should fail validation"
            assert "valid integer" in result.failure_descriptions[0]
    
    def test_valid_integers_pass(self):
        """Valid integer strings should pass validation."""
        validator = IntRangeValidator()
        
        test_cases = ["0", "42", "-5", "1000", "  123  "]  # Including whitespace
        
        for test_value in test_cases:
            result = validator.validate(test_value)
            assert result.is_valid, f"'{test_value}' should pass validation"
    
    def test_min_value_validation(self):
        """Test minimum value constraints."""
        validator = IntRangeValidator(min_value=10)
        
        # Values below minimum should fail
        assert not validator.validate("5").is_valid
        assert not validator.validate("9").is_valid
        assert "at least 10" in validator.validate("5").failure_descriptions[0]
        
        # Values at or above minimum should pass
        assert validator.validate("10").is_valid
        assert validator.validate("15").is_valid
    
    def test_max_value_validation(self):
        """Test maximum value constraints."""
        validator = IntRangeValidator(max_value=100)
        
        # Values above maximum should fail
        assert not validator.validate("101").is_valid
        assert not validator.validate("200").is_valid
        assert "at most 100" in validator.validate("101").failure_descriptions[0]
        
        # Values at or below maximum should pass
        assert validator.validate("100").is_valid
        assert validator.validate("50").is_valid
    
    def test_range_validation(self):
        """Test validation with both min and max values."""
        validator = IntRangeValidator(min_value=1, max_value=60)
        
        # Test boundary values
        assert not validator.validate("0").is_valid  # Below min
        assert validator.validate("1").is_valid     # At min
        assert validator.validate("30").is_valid    # In range
        assert validator.validate("60").is_valid    # At max
        assert not validator.validate("61").is_valid # Above max


class TestValidationHelpers:
    """Test cases for ValidationHelpers static methods."""
    
    def test_validate_required_field(self):
        """Test required field validation."""
        # Mock Input widget
        mock_widget = Mock()
        mock_widget.value = "some value"
        mock_widget.focus = Mock()
        
        # Valid non-empty field should pass
        result = ValidationHelpers.validate_required_field(mock_widget, "test_field")
        assert result is True
        mock_widget.focus.assert_not_called()
        
        # Empty field should fail and focus
        mock_widget.value = ""
        with patch('builtins.print') as mock_print:
            result = ValidationHelpers.validate_required_field(mock_widget, "test_field")
            assert result is False
            mock_widget.focus.assert_called_once()
            mock_print.assert_called_once()
            assert "test_field cannot be empty" in mock_print.call_args[0][0]
        
        # Whitespace-only field should fail
        mock_widget.value = "   "
        mock_widget.focus.reset_mock()
        result = ValidationHelpers.validate_required_field(mock_widget, "test_field")
        assert result is False
        mock_widget.focus.assert_called_once()
    
    def test_validate_path_exists(self):
        """Test path existence validation."""
        mock_widget = Mock()
        mock_widget.focus = Mock()
        
        # Test with existing path
        with patch('os.path.exists') as mock_exists, \
             patch('os.path.expanduser') as mock_expand:
            
            mock_expand.return_value = "/expanded/path"
            mock_exists.return_value = True
            mock_widget.value = "~/test"
            
            result = ValidationHelpers.validate_path_exists(mock_widget, "test_path")
            assert result is True
            mock_widget.focus.assert_not_called()
            mock_expand.assert_called_with("~/test")
            mock_exists.assert_called_with("/expanded/path")
        
        # Test with non-existent path
        with patch('os.path.exists') as mock_exists, \
             patch('os.path.expanduser') as mock_expand, \
             patch('builtins.print') as mock_print:
            
            mock_expand.return_value = "/expanded/nonexistent"
            mock_exists.return_value = False
            mock_widget.value = "/nonexistent/path"
            
            result = ValidationHelpers.validate_path_exists(mock_widget, "test_path")
            assert result is False
            mock_widget.focus.assert_called_once()
            mock_print.assert_called_once()
            assert "does not exist" in mock_print.call_args[0][0]
        
        # Test with empty path (should pass)
        mock_widget.value = ""
        mock_widget.focus.reset_mock()
        result = ValidationHelpers.validate_path_exists(mock_widget, "test_path")
        assert result is True
        mock_widget.focus.assert_not_called()
    
    def test_validate_numeric_field(self):
        """Test numeric field validation."""
        mock_widget = Mock()
        mock_widget.focus = Mock()
        
        # Valid numeric field should pass
        mock_widget.is_valid = True
        result = ValidationHelpers.validate_numeric_field(mock_widget, "test_field")
        assert result is True
        mock_widget.focus.assert_not_called()
        
        # Invalid numeric field should fail and focus
        mock_widget.is_valid = False
        with patch('builtins.print') as mock_print:
            result = ValidationHelpers.validate_numeric_field(mock_widget, "test_field")
            assert result is False
            mock_widget.focus.assert_called_once()
            mock_print.assert_called_once()
            assert "invalid value" in mock_print.call_args[0][0]
    
    def test_get_int_value(self):
        """Test safe integer value extraction."""
        mock_widget = Mock()
        
        # Test valid integer
        mock_widget.value = "42"
        result = ValidationHelpers.get_int_value(mock_widget)
        assert result == 42
        
        # Test valid integer with whitespace
        mock_widget.value = "  123  "
        result = ValidationHelpers.get_int_value(mock_widget)
        assert result == 123
        
        # Test invalid integer returns default
        mock_widget.value = "not_a_number"
        result = ValidationHelpers.get_int_value(mock_widget, default=99)
        assert result == 99
        
        # Test empty value returns default
        mock_widget.value = ""
        result = ValidationHelpers.get_int_value(mock_widget, default=10)
        assert result == 10
        
        # Test None value returns default
        mock_widget.value = None
        result = ValidationHelpers.get_int_value(mock_widget)
        assert result == 0  # Default parameter default 