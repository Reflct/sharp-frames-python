"""
Video directory utility functions for Sharp Frames.

Provides utilities for detecting and processing video files in directories.
"""

import os
import platform
from typing import List, Optional

# Keep media-format support in one place so validation and processing cannot drift.
SUPPORTED_VIDEO_EXTENSIONS = frozenset({
    '.3g2', '.3gp', '.avi', '.flv', '.m2ts', '.m4v', '.mkv', '.mov',
    '.mp4', '.mpeg', '.mpg', '.mts', '.ogv', '.ts', '.vob', '.webm', '.wmv',
})

SUPPORTED_IMAGE_EXTENSIONS = frozenset({
    '.bmp', '.jpeg', '.jpg', '.pbm', '.pgm', '.png', '.ppm', '.tif',
    '.tiff', '.webp',
})


def get_ffmpeg_installation_hint(system_name: Optional[str] = None) -> str:
    """Return platform-appropriate installation guidance for FFmpeg tools."""
    current_system = system_name or platform.system()
    if current_system == 'Windows':
        return (
            "Install a full FFmpeg build from https://ffmpeg.org/download.html "
            "and add its bin directory to PATH."
        )
    if current_system == 'Darwin':
        return (
            "Install FFmpeg and FFprobe with `brew install ffmpeg`, then ensure "
            "Homebrew's bin directory is on your system PATH."
        )
    if current_system == 'Linux':
        return (
            "Install FFmpeg with your package manager (for example, "
            "`sudo apt install ffmpeg`) and ensure it is on your system PATH."
        )
    return (
        "Install a full FFmpeg distribution from https://ffmpeg.org/download.html "
        "and add it to PATH."
    )


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
