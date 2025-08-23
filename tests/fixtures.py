"""
Test fixtures for Sharp Frames TUI components.
"""

import os
import tempfile
import pytest
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch
from PIL import Image
from dataclasses import dataclass
from typing import List, Dict, Any, Optional


@dataclass
class MockFrameData:
    """Mock frame data for testing."""
    path: str
    index: int
    sharpness_score: float
    source_video: Optional[str] = None
    source_index: Optional[int] = None
    output_name: Optional[str] = None


@pytest.fixture
def sample_frames_data():
    """Generate sample frame data with known sharpness scores."""
    frames = []
    for i in range(100):
        # Create varied sharpness scores for testing selection algorithms
        if i < 20:
            score = 50.0 + i  # Low scores (50-69)
        elif i < 80:
            score = 100.0 + i  # Medium scores (100-179) 
        else:
            score = 200.0 + i  # High scores (200-219)
            
        frames.append(MockFrameData(
            path=f"/tmp/frame_{i:05d}.jpg",
            index=i,
            sharpness_score=score,
            output_name=f"{i+1:05d}"
        ))
    return frames


@pytest.fixture
def sample_video_directory_frames():
    """Generate sample frame data from video directory with video attribution."""
    frames = []
    frame_index = 0
    
    # Simulate 3 videos with different frame counts
    video_frame_counts = [30, 40, 30]
    
    for video_num, frame_count in enumerate(video_frame_counts, 1):
        video_dir = f"video_{video_num:03d}"
        
        for video_frame_idx in range(frame_count):
            score = 100.0 + np.random.uniform(0, 50)  # Random scores 100-150
            
            frames.append(MockFrameData(
                path=f"/tmp/{video_dir}/frame_{video_frame_idx:05d}.jpg",
                index=frame_index,
                sharpness_score=score,
                source_video=video_dir,
                source_index=video_frame_idx,
                output_name=f"video{video_num:02d}_{frame_index+1:05d}"
            ))
            frame_index += 1
            
    return frames


@pytest.fixture
def mock_extraction_result():
    """Mock ExtractionResult for testing."""
    from sharp_frames.models.frame_data import ExtractionResult
    
    return ExtractionResult(
        frames=[],
        metadata={"fps": 30, "duration": 10.0, "source_type": "video"},
        temp_dir="/tmp/sharp_frames_test",
        input_type="video"
    )


@pytest.fixture
def test_images_directory(tmp_path):
    """Create a temporary directory with test images."""
    image_dir = tmp_path / "test_images"
    image_dir.mkdir()
    
    # Create test images with different sizes for variety
    image_files = []
    for i in range(10):
        # Create a simple test image
        img = Image.new('RGB', (100, 100), color=(i*25, i*25, i*25))
        img_path = image_dir / f"test_image_{i:03d}.jpg"
        img.save(img_path)
        image_files.append(str(img_path))
        
    return str(image_dir), image_files


@pytest.fixture
def test_video_file(tmp_path):
    """Create a mock video file path for testing."""
    video_path = tmp_path / "test_video.mp4"
    video_path.touch()  # Create empty file
    return str(video_path)


@pytest.fixture
def test_video_directory(tmp_path):
    """Create a directory structure simulating multiple video files."""
    video_dir = tmp_path / "video_directory"
    video_dir.mkdir()
    
    video_files = []
    for i in range(3):
        video_file = video_dir / f"video_{i+1:03d}.mp4"
        video_file.touch()
        video_files.append(str(video_file))
        
    return str(video_dir), video_files


@pytest.fixture
def mock_temp_directory_structure(tmp_path):
    """Create a temporary directory structure mimicking video extraction."""
    temp_dir = tmp_path / "sharp_frames_temp"
    temp_dir.mkdir()
    
    # Create subdirectories for different videos
    video_dirs = []
    for video_num in range(1, 4):  # 3 videos
        video_dir = temp_dir / f"video_{video_num:03d}"
        video_dir.mkdir()
        
        # Create frame files in each video directory
        frame_files = []
        frame_count = 20 + video_num * 5  # Different frame counts per video
        for frame_idx in range(frame_count):
            frame_file = video_dir / f"frame_{frame_idx:05d}.jpg"
            frame_file.touch()
            frame_files.append(str(frame_file))
            
        video_dirs.append({
            'dir': str(video_dir),
            'frames': frame_files
        })
        
    return str(temp_dir), video_dirs


@pytest.fixture
def sample_config_video():
    """Sample configuration for video input testing."""
    return {
        'input_type': 'video',
        'input_path': '/path/to/test_video.mp4',
        'output_dir': '/path/to/output',
        'fps': 10,
        'output_format': 'jpg',
        'width': 800,
        'force_overwrite': False
    }


@pytest.fixture
def sample_config_directory():
    """Sample configuration for image directory input testing."""
    return {
        'input_type': 'directory',
        'input_path': '/path/to/image_directory',
        'output_dir': '/path/to/output',
        'output_format': 'jpg',
        'width': 800,
        'force_overwrite': False
    }


@pytest.fixture
def sample_config_video_directory():
    """Sample configuration for video directory input testing."""
    return {
        'input_type': 'video_directory',
        'input_path': '/path/to/video_directory',
        'output_dir': '/path/to/output',
        'fps': 10,
        'output_format': 'jpg',
        'width': 800,
        'force_overwrite': False
    }


@pytest.fixture
def mock_sharpness_scores():
    """Generate predictable sharpness scores for testing selection algorithms."""
    # Create scores that will test edge cases:
    # - Some very high scores (outliers)
    # - Normal distribution in middle
    # - Some very low scores
    scores = []
    
    # Low scores (10 frames): 10-30
    for i in range(10):
        scores.append(10.0 + i * 2)
        
    # Medium scores (80 frames): 50-150  
    for i in range(80):
        scores.append(50.0 + i * 1.25)
        
    # High scores (10 frames): 200-300
    for i in range(10):
        scores.append(200.0 + i * 10)
        
    return scores


@pytest.fixture
def expected_selection_outcomes():
    """Expected outcomes for different selection methods with test data."""
    return {
        'best_n': {
            'n=10': 10,  # Should select 10 highest scoring frames
            'n=50': 50,  # Should select 50 highest scoring frames  
            'n=150': 100, # Should cap at total available frames
        },
        'batched': {
            'batch_count=5': 5,   # 5 batches from 100 frames = 5 selected
            'batch_count=10': 10, # 10 batches = 10 selected
            'batch_count=150': 100, # More batches than frames = 100 selected
        },
        'outlier_removal': {
            'factor=1.5': 90,  # Should remove ~10 outlier frames
            'factor=2.0': 95,  # Should remove ~5 outlier frames
            'factor=0.5': 70,  # Should remove ~30 frames (more aggressive)
        }
    }


@pytest.fixture
def mock_ffmpeg_success():
    """Mock successful FFmpeg calls."""
    with patch('subprocess.run') as mock_run, \
         patch('subprocess.Popen') as mock_popen:
        
        mock_run.return_value = Mock(
            returncode=0, 
            stdout="", 
            stderr="",
            check=True
        )
        
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.poll.return_value = 0
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process
        
        yield {'run': mock_run, 'popen': mock_popen, 'process': mock_process}


@pytest.fixture
def mock_ffmpeg_failure():
    """Mock failed FFmpeg calls."""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="FFmpeg error: file not found"
        )
        yield mock_run