"""
Tests for FrameExtractor component.
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from sharp_frames.processing.frame_extractor import FrameExtractor
from sharp_frames.models.frame_data import ExtractionResult, FrameData
from tests.fixtures import (
    test_images_directory, 
    test_video_file, 
    test_video_directory,
    sample_config_video,
    sample_config_directory, 
    sample_config_video_directory,
    mock_ffmpeg_success,
    mock_ffmpeg_failure
)


class TestFrameExtractor:
    """Test cases for FrameExtractor component."""
    
    def setup_method(self):
        """Set up test environment."""
        self.extractor = FrameExtractor()
    
    def test_init(self):
        """Test FrameExtractor initialization."""
        assert self.extractor is not None
        assert hasattr(self.extractor, 'extract_frames')
    
    def test_extract_frames_video_type(self, sample_config_video, mock_ffmpeg_success):
        """Test frame extraction from video file."""
        config = sample_config_video.copy()
        config['input_type'] = 'video'
        
        with patch.object(self.extractor, '_extract_video_frames') as mock_extract:
            mock_result = ExtractionResult(
                frames=[],
                metadata={'fps': 30, 'duration': 10.0},
                input_type='video'
            )
            mock_extract.return_value = mock_result
            
            result = self.extractor.extract_frames(config)
            
            mock_extract.assert_called_once_with(config)
            assert result.input_type == 'video'
    
    def test_extract_frames_directory_type(self, sample_config_directory):
        """Test frame loading from image directory."""
        config = sample_config_directory.copy()
        config['input_type'] = 'directory'
        
        with patch.object(self.extractor, '_load_images') as mock_load:
            mock_result = ExtractionResult(
                frames=[],
                metadata={'source_type': 'directory'},
                input_type='directory'
            )
            mock_load.return_value = mock_result
            
            result = self.extractor.extract_frames(config)
            
            mock_load.assert_called_once_with(config['input_path'])
            assert result.input_type == 'directory'
    
    def test_extract_frames_video_directory_type(self, sample_config_video_directory, mock_ffmpeg_success):
        """Test frame extraction from video directory."""
        config = sample_config_video_directory.copy()
        config['input_type'] = 'video_directory'
        
        with patch.object(self.extractor, '_extract_video_directory_frames') as mock_extract:
            mock_result = ExtractionResult(
                frames=[],
                metadata={'video_count': 3},
                input_type='video_directory'
            )
            mock_extract.return_value = mock_result
            
            result = self.extractor.extract_frames(config)
            
            mock_extract.assert_called_once_with(config)
            assert result.input_type == 'video_directory'
    
    def test_extract_frames_invalid_type(self, sample_config_video):
        """Test error handling for invalid input type."""
        config = sample_config_video.copy()
        config['input_type'] = 'invalid_type'
        
        with pytest.raises(ValueError, match="Unsupported input type"):
            self.extractor.extract_frames(config)
    
    def test_load_images_success(self, test_images_directory):
        """Test successful image directory loading."""
        image_dir, image_files = test_images_directory
        
        result = self.extractor._load_images(image_dir)
        
        assert isinstance(result, ExtractionResult)
        assert result.input_type == 'directory'
        assert len(result.frames) == 10  # Should have loaded all 10 test images
        assert result.temp_dir is None  # No temp directory for image loading
        
        # Verify frame data structure
        for i, frame in enumerate(result.frames):
            assert isinstance(frame, FrameData)
            assert frame.index == i
            assert frame.path in image_files
            assert frame.sharpness_score == 0.0  # Not calculated yet
            assert frame.source_video is None
            assert frame.output_name is not None
    
    def test_load_images_empty_directory(self, tmp_path):
        """Test loading from empty image directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        
        result = self.extractor._load_images(str(empty_dir))
        
        assert isinstance(result, ExtractionResult)
        assert len(result.frames) == 0
        assert result.input_type == 'directory'
    
    def test_load_images_nonexistent_directory(self):
        """Test error handling for non-existent directory."""
        with pytest.raises(FileNotFoundError):
            self.extractor._load_images("/nonexistent/directory")
    
    def test_extract_video_frames_success(self, sample_config_video, mock_ffmpeg_success):
        """Test successful video frame extraction."""
        config = sample_config_video.copy()
        
        with patch('tempfile.mkdtemp', return_value='/tmp/test_frames'), \
             patch('os.listdir', return_value=['frame_00001.jpg', 'frame_00002.jpg']), \
             patch('os.path.isfile', return_value=True):
            
            result = self.extractor._extract_video_frames(config)
            
            assert isinstance(result, ExtractionResult)
            assert result.input_type == 'video'
            assert result.temp_dir == '/tmp/test_frames'
            assert len(result.frames) == 2
            
            # Verify FFmpeg was called
            mock_ffmpeg_success['run'].assert_called_once()
    
    def test_extract_video_frames_ffmpeg_failure(self, sample_config_video, mock_ffmpeg_failure):
        """Test handling of FFmpeg extraction failure."""
        config = sample_config_video.copy()
        
        with patch('tempfile.mkdtemp', return_value='/tmp/test_frames'):
            with pytest.raises(RuntimeError, match="Frame extraction failed"):
                self.extractor._extract_video_frames(config)
    
    def test_extract_video_directory_frames_success(self, sample_config_video_directory, test_video_directory, mock_ffmpeg_success):
        """Test successful video directory frame extraction with video attribution."""
        config = sample_config_video_directory.copy()
        video_dir, video_files = test_video_directory
        config['input_path'] = video_dir
        
        with patch('tempfile.mkdtemp', return_value='/tmp/test_frames'), \
             patch.object(self.extractor, '_extract_single_video') as mock_extract:
            
            # Mock single video extraction to return frames with video attribution
            def mock_single_video_extract(video_path, video_index, temp_dir, config):
                video_name = f"video_{video_index+1:03d}"
                frames = []
                for i in range(5):  # 5 frames per video
                    frame = FrameData(
                        path=f"{temp_dir}/{video_name}/frame_{i:05d}.jpg",
                        index=video_index * 5 + i,
                        sharpness_score=0.0,
                        source_video=video_name,
                        source_index=i,
                        output_name=f"video{video_index+1:02d}_{i+1:05d}"
                    )
                    frames.append(frame)
                return frames
                
            mock_extract.side_effect = mock_single_video_extract
            
            result = self.extractor._extract_video_directory_frames(config)
            
            assert isinstance(result, ExtractionResult)
            assert result.input_type == 'video_directory'
            assert result.temp_dir == '/tmp/test_frames'
            assert len(result.frames) == 15  # 3 videos * 5 frames each
            
            # Verify video attribution is preserved
            for i, frame in enumerate(result.frames):
                video_index = i // 5
                assert frame.source_video == f"video_{video_index+1:03d}"
                assert frame.output_name.startswith(f"video{video_index+1:02d}_")
    
    def test_extract_video_directory_empty(self, tmp_path, sample_config_video_directory):
        """Test extraction from empty video directory."""
        empty_dir = tmp_path / "empty_videos"
        empty_dir.mkdir()
        
        config = sample_config_video_directory.copy()
        config['input_path'] = str(empty_dir)
        
        result = self.extractor._extract_video_directory_frames(config)
        
        assert isinstance(result, ExtractionResult)
        assert len(result.frames) == 0
        assert result.input_type == 'video_directory'
    
    def test_create_frame_data_simple(self):
        """Test frame data creation without video attribution."""
        frame_data = self.extractor._create_frame_data("/path/frame_001.jpg", 5, 125.5)
        
        assert frame_data.path == "/path/frame_001.jpg"
        assert frame_data.index == 5
        assert frame_data.sharpness_score == 125.5
        assert frame_data.source_video is None
        assert frame_data.output_name == "000006"  # index + 1, zero-padded
    
    def test_create_frame_data_with_video_attribution(self):
        """Test frame data creation with video directory attribution."""
        path = "/tmp/video_001/frame_00005.jpg"
        frame_data = self.extractor._create_frame_data_with_video_attribution(
            path, 25, 150.0, "video_001", 5
        )
        
        assert frame_data.path == path
        assert frame_data.index == 25
        assert frame_data.sharpness_score == 150.0
        assert frame_data.source_video == "video_001"
        assert frame_data.source_index == 5
        assert frame_data.output_name == "video01_00026"  # index + 1
    
    def test_temp_directory_management(self):
        """Test temporary directory creation and tracking."""
        with patch('tempfile.mkdtemp', return_value='/tmp/sharp_frames_12345') as mock_mkdtemp:
            temp_dir = self.extractor._create_temp_directory()
            
            mock_mkdtemp.assert_called_once()
            assert temp_dir == '/tmp/sharp_frames_12345'
    
    def test_get_supported_image_extensions(self):
        """Test supported image format detection."""
        supported = self.extractor._get_supported_image_extensions()
        
        assert '.jpg' in supported
        assert '.jpeg' in supported
        assert '.png' in supported
        assert '.bmp' in supported
        assert '.tiff' in supported
    
    def test_filter_image_files(self, test_images_directory):
        """Test filtering of image files from directory listing."""
        image_dir, image_files = test_images_directory
        
        # Add some non-image files
        non_image = Path(image_dir) / "readme.txt"
        non_image.touch()
        
        filtered_files = self.extractor._filter_image_files(image_dir)
        
        # Should only include image files
        assert len(filtered_files) == 10
        for file_path in filtered_files:
            assert file_path.endswith('.jpg')
        
        # Should not include non-image files
        assert str(non_image) not in filtered_files