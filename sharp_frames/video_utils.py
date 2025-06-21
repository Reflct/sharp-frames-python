"""
Video directory utility functions for Sharp Frames.

Provides utilities for detecting and processing video files in directories.
"""

import os
from typing import List

# Supported video extensions for video directory processing
SUPPORTED_VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mkv', '.mov', '.flv', '.wmv', '.webm'}


def get_video_files_in_directory(directory_path: str) -> List[str]:
    """Get all video files in a directory."""
    video_files = []
    if not os.path.isdir(directory_path):
        return video_files
    
    for filename in os.listdir(directory_path):
        file_path = os.path.join(directory_path, filename)
        if os.path.isfile(file_path):
            _, ext = os.path.splitext(filename.lower())
            if ext in SUPPORTED_VIDEO_EXTENSIONS:
                video_files.append(file_path)
    
    return sorted(video_files)


def detect_input_type(input_path: str) -> str:
    """Detect the input type based on the path contents."""
    if os.path.isfile(input_path):
        return "video"
    elif os.path.isdir(input_path):
        # Check what's in the directory
        video_files = get_video_files_in_directory(input_path)
        if video_files:
            return "video_directory"
        else:
            return "directory"  # Assume image directory
    else:
        raise ValueError(f"Input path is neither a file nor a directory: {input_path}") 