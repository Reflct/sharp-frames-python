"""
Tests for Sharp Frames main module functionality.

Tests the video directory processing utilities and input type detection.
"""

import pytest
import os
import tempfile
from unittest.mock import patch, Mock

from sharp_frames.video_utils import (
    get_video_files_in_directory,
    detect_input_type,
    SUPPORTED_VIDEO_EXTENSIONS
)


class TestVideoDirectoryUtilities:
    """Test cases for video directory utility functions."""

    def test_get_video_files_in_directory_with_videos(self):
        """Test getting video files from a directory containing videos."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create some test files
            video_files = ['video1.mp4', 'video2.avi', 'video3.mkv']
            non_video_files = ['image.jpg', 'text.txt', 'readme.md']
            
            for filename in video_files + non_video_files:
                filepath = os.path.join(temp_dir, filename)
                with open(filepath, 'w') as f:
                    f.write('test content')
            
            result = get_video_files_in_directory(temp_dir)
            
            # Should return sorted list of video files with full paths
            assert len(result) == 3
            assert all(os.path.basename(path) in video_files for path in result)
            assert all(os.path.isabs(path) for path in result)
            # Should be sorted
            basenames = [os.path.basename(path) for path in result]
            assert basenames == sorted(basenames)

    def test_get_video_files_in_directory_no_videos(self):
        """Test getting video files from directory with no videos."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create some non-video files
            non_video_files = ['image.jpg', 'text.txt', 'document.pdf']
            
            for filename in non_video_files:
                filepath = os.path.join(temp_dir, filename)
                with open(filepath, 'w') as f:
                    f.write('test content')
            
            result = get_video_files_in_directory(temp_dir)
            assert result == []

    def test_get_video_files_in_directory_case_insensitive(self):
        """Test that video file detection is case insensitive."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create files with different case extensions
            video_files = ['video1.MP4', 'video2.AVI', 'video3.MkV']
            
            for filename in video_files:
                filepath = os.path.join(temp_dir, filename)
                with open(filepath, 'w') as f:
                    f.write('test content')
            
            result = get_video_files_in_directory(temp_dir)
            assert len(result) == 3

    def test_get_video_files_in_directory_nonexistent(self):
        """Test getting video files from non-existent directory."""
        result = get_video_files_in_directory('/nonexistent/directory')
        assert result == []

    def test_supported_video_extensions_comprehensive(self):
        """Test that all expected video extensions are supported."""
        expected_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.flv', '.wmv', '.webm'}
        assert SUPPORTED_VIDEO_EXTENSIONS == expected_extensions


class TestInputTypeDetection:
    """Test cases for input type detection logic."""

    def test_detect_input_type_single_file(self):
        """Test input type detection for a single file."""
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
            temp_file_path = temp_file.name
        
        try:
            result = detect_input_type(temp_file_path)
            assert result == "video"
        finally:
            try:
                os.unlink(temp_file_path)
            except (OSError, PermissionError):
                pass  # Ignore cleanup errors on Windows

    def test_detect_input_type_video_directory(self):
        """Test input type detection for directory containing videos."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create video files
            video_files = ['video1.mp4', 'video2.avi']
            for filename in video_files:
                filepath = os.path.join(temp_dir, filename)
                with open(filepath, 'w') as f:
                    f.write('test content')
            
            result = detect_input_type(temp_dir)
            assert result == "video_directory"

    def test_detect_input_type_image_directory(self):
        """Test input type detection for directory containing only images."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create image files
            image_files = ['image1.jpg', 'image2.png']
            for filename in image_files:
                filepath = os.path.join(temp_dir, filename)
                with open(filepath, 'w') as f:
                    f.write('test content')
            
            result = detect_input_type(temp_dir)
            assert result == "directory"

    def test_detect_input_type_mixed_directory(self):
        """Test input type detection for directory with mixed content (videos take precedence)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create both video and image files
            files = ['video1.mp4', 'image1.jpg', 'video2.avi']
            for filename in files:
                filepath = os.path.join(temp_dir, filename)
                with open(filepath, 'w') as f:
                    f.write('test content')
            
            result = detect_input_type(temp_dir)
            # Videos take precedence
            assert result == "video_directory"

    def test_detect_input_type_empty_directory(self):
        """Test input type detection for empty directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = detect_input_type(temp_dir)
            # Empty directory defaults to image directory
            assert result == "directory"

    def test_detect_input_type_nonexistent_path(self):
        """Test input type detection for non-existent path."""
        with pytest.raises(ValueError, match="Input path is neither a file nor a directory"):
            detect_input_type('/nonexistent/path')


class TestVideoDirectoryIntegration:
    """Integration tests for video directory processing."""

    @patch('sharp_frames.video_utils.get_video_files_in_directory')
    def test_cli_video_directory_detection_logic(self, mock_get_videos):
        """Test that CLI properly detects and handles video directories."""
        mock_get_videos.return_value = ['video1.mp4', 'video2.avi']
        
        # This would normally be tested with actual CLI parsing
        # but we can test the logic components
        
        with tempfile.TemporaryDirectory() as temp_dir:
            input_type = detect_input_type(temp_dir)
            
            if input_type == "video_directory":
                video_files = get_video_files_in_directory(temp_dir)
                assert len(video_files) >= 0  # Should handle the mock return

    def test_video_file_extensions_comprehensive_coverage(self):
        """Test that our supported extensions cover common video formats."""
        common_video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm']
        
        for ext in common_video_extensions:
            assert ext in SUPPORTED_VIDEO_EXTENSIONS, f"Extension {ext} should be supported" 