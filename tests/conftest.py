"""
Shared test fixtures for Sharp Frames UI tests.
"""

import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock, patch


@pytest.fixture
def temp_dir():
    """Provide a temporary directory that gets cleaned up."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield tmp_dir


@pytest.fixture
def temp_file():
    """Provide a temporary file that gets cleaned up."""
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        tmp_file.write(b"test content")
        tmp_file.flush()
        yield tmp_file.name
    
    # Clean up
    try:
        os.unlink(tmp_file.name)
    except OSError:
        pass


@pytest.fixture
def sample_video_path():
    """Mock video file path for testing."""
    return "/path/to/sample/video.mp4"


@pytest.fixture
def sample_video_directory():
    """Mock video directory path for testing."""
    return "/path/to/video/directory"


@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return {
        'input_type': 'video',
        'input_path': '/path/to/video.mp4',
        'output_dir': '/path/to/output',
        'fps': 10,
        'selection_method': 'best-n',
        'output_format': 'jpg',
        'width': 800,
        'force_overwrite': False
    }


@pytest.fixture
def sample_video_directory_config():
    """Sample video directory configuration for testing."""
    return {
        'input_type': 'video_directory',
        'input_path': '/path/to/video/directory',
        'output_dir': '/path/to/output',
        'fps': 10,
        'selection_method': 'best-n',
        'output_format': 'jpg',
        'width': 800,
        'force_overwrite': False
    }


@pytest.fixture
def mock_subprocess():
    """Mock subprocess for testing without actual system calls."""
    with patch('subprocess.run') as mock_run, \
         patch('subprocess.Popen') as mock_popen:
        
        # Default successful return
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        mock_popen.return_value = Mock(
            returncode=0,
            poll=Mock(return_value=0),
            wait=Mock(return_value=0),
            terminate=Mock(),
            kill=Mock()
        )
        
        yield {'run': mock_run, 'popen': mock_popen} 