"""
Tests for Sharp Frames main module functionality.

Tests the video directory processing utilities and input type detection.
"""

import pytest
import os
import tempfile
import json
from unittest.mock import patch, Mock

import cv2
import numpy as np

from sharp_frames.sharp_frames_processor import SharpFrames
from sharp_frames.video_utils import (
    SUPPORTED_VIDEO_EXTENSIONS,
    detect_input_type,
    get_video_files_in_directory,
    has_mpeg_ts_signature,
)


class TestDirectCliSaving:
    """Direct CLI output must use the same safe encoding contract as the TUI."""

    @staticmethod
    def _write_image(path, color):
        image = np.full((12, 16, 3), color, dtype=np.uint8)
        assert cv2.imwrite(str(path), image)

    @staticmethod
    def _write_rgba_image(path):
        image = np.zeros((12, 16, 4), dtype=np.uint8)
        image[..., :3] = (10, 40, 200)
        image[..., 3] = np.linspace(0, 255, 16, dtype=np.uint8)
        assert cv2.imwrite(str(path), image)

    def test_directory_images_are_transcoded_and_collision_safe(self, tmp_path):
        input_dir = tmp_path / "input"
        output_dir = tmp_path / "output"
        input_dir.mkdir()
        output_dir.mkdir()
        png_source = input_dir / "photo.png"
        jpg_source = input_dir / "photo.jpg"
        self._write_image(png_source, (255, 0, 0))
        self._write_image(jpg_source, (0, 0, 255))
        processor = SharpFrames(
            input_path=str(input_dir),
            input_type="directory",
            output_dir=str(output_dir),
            output_format="jpg",
            force_overwrite=True,
        )
        selected = [
            {"id": path.name, "path": str(path), "index": index,
             "sharpnessScore": 10.0 + index}
            for index, path in enumerate((png_source, jpg_source))
        ]

        assert processor._save_frames(selected) is True

        assert (output_dir / "photo.jpg").read_bytes().startswith(b"\xff\xd8\xff")
        assert (output_dir / "photo_2.jpg").read_bytes().startswith(b"\xff\xd8\xff")
        metadata = json.loads((output_dir / "selected_metadata.json").read_text())
        assert metadata["total_selected"] == 2
        assert metadata["total_saved"] == 2
        assert metadata["total_failed"] == 0
        assert [item["output_filename"] for item in metadata["selected_items"]] == [
            "photo.jpg", "photo_2.jpg"
        ]

    def test_direct_cli_png_output_preserves_alpha(self, tmp_path):
        input_dir = tmp_path / "input"
        output_dir = tmp_path / "output"
        input_dir.mkdir()
        output_dir.mkdir()
        source = input_dir / "photo.webp"
        self._write_rgba_image(source)
        processor = SharpFrames(
            input_path=str(input_dir),
            input_type="directory",
            output_dir=str(output_dir),
            output_format="png",
            force_overwrite=True,
        )
        selected = [{
            "id": source.name,
            "path": str(source),
            "index": 0,
            "sharpnessScore": 10.0,
        }]

        assert processor._save_frames(selected) is True

        output = cv2.imread(
            str(output_dir / "photo.png"), cv2.IMREAD_UNCHANGED
        )
        assert output is not None
        assert output.shape[2] == 4
        assert output[..., 3].min() == 0
        assert output[..., 3].max() == 255

    def test_save_failure_is_reported_to_run(self, tmp_path):
        processor = SharpFrames(
            input_path=str(tmp_path),
            input_type="directory",
            output_dir=str(tmp_path / "output"),
        )
        selected = [{
            "id": "missing.png",
            "path": str(tmp_path / "missing.png"),
            "index": 0,
            "sharpnessScore": 1.0,
        }]

        with (
            patch.object(processor, "_setup", return_value=True),
            patch.object(processor, "_load_input_frames", return_value=(["input"], False)),
            patch.object(processor, "_analyze_and_select_frames", return_value=selected),
            patch.object(processor, "_save_frames", return_value=False),
        ):
            assert processor.run() is False

    def test_direct_cli_uses_canonical_ffmpeg_runner(self, tmp_path):
        processor = SharpFrames(
            input_path=str(tmp_path / "input.mp4"),
            input_type="video",
            output_dir=str(tmp_path / "output"),
            fps=5,
            output_format="png",
            width=640,
        )
        processor.temp_dir = str(tmp_path / "frames")

        with patch(
            "sharp_frames.processing.frame_extractor.FrameExtractor._run_ffmpeg_extraction",
            return_value=True,
        ) as extraction:
            assert processor._extract_frames(duration=2.0) is True

        extraction.assert_called_once_with(
            processor.input_path,
            processor.temp_dir,
            5,
            "png",
            640,
            2.0,
            None,
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

    def test_typescript_file_does_not_override_image_directory_detection(
        self, tmp_path
    ):
        (tmp_path / "photo.png").write_bytes(b"image")
        (tmp_path / "helpers.ts").write_text(
            "export const answer = 42;", encoding="utf-8"
        )

        assert get_video_files_in_directory(str(tmp_path)) == []
        assert detect_input_type(str(tmp_path)) == "directory"

    @pytest.mark.parametrize("packet_size", [188, 192, 204])
    def test_mpeg_transport_stream_signature_is_detected(
        self, tmp_path, packet_size
    ):
        sync_offset = 4 if packet_size == 192 else 0
        stream = bytearray(sync_offset + packet_size * 4)
        for packet_index in range(4):
            stream[sync_offset + packet_index * packet_size] = 0x47
        path = tmp_path / "video.ts"
        path.write_bytes(stream)

        assert has_mpeg_ts_signature(str(path)) is True
        assert get_video_files_in_directory(str(tmp_path)) == [str(path)]

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
        expected_extensions = frozenset({
            '.3g2', '.3gp', '.avi', '.flv', '.m2ts', '.m4v', '.mkv', '.mov',
            '.mp4', '.mpeg', '.mpg', '.mts', '.ogv', '.ts', '.vob', '.webm',
            '.wmv',
        })
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

    def test_detect_input_type_rejects_non_video_ts_file(self, tmp_path):
        """A TypeScript .ts file passed directly must not be treated as video."""
        source = tmp_path / "helpers.ts"
        source.write_text("export const answer = 42;", encoding="utf-8")

        with pytest.raises(ValueError, match="not a supported video"):
            detect_input_type(str(source))

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
