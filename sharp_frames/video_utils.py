"""
Video directory utility functions for Sharp Frames.

Provides utilities for detecting and processing video files in directories.
"""

import os
import platform
import re
from typing import List, Optional

# Keep media-format support in one place so validation and processing cannot drift.
SUPPORTED_VIDEO_EXTENSIONS = frozenset({
    '.3g2', '.3gp', '.avi', '.flv', '.m2ts', '.m4v', '.mkv', '.mov',
    '.mp4', '.mpeg', '.mpg', '.mts', '.ogv', '.ts', '.vob', '.webm', '.wmv',
})
AMBIGUOUS_VIDEO_EXTENSIONS = frozenset({'.ts'})
_MPEG_TS_PACKET_SIZES = (188, 192, 204)
_MPEG_TS_REQUIRED_SYNC_BYTES = 4

SUPPORTED_IMAGE_EXTENSIONS = frozenset({
    '.bmp', '.jpeg', '.jpg', '.pbm', '.pgm', '.png', '.ppm', '.tif',
    '.tiff', '.webp',
})

_NATURAL_NUMBER = re.compile(r"(\d+)")


def natural_path_key(path: str) -> tuple:
    """Return a deterministic, case-insensitive key for numbered filenames."""
    name = os.path.basename(os.fspath(path))
    parts = tuple(
        (1, int(part)) if part.isdigit() else (0, part.casefold())
        for part in _NATURAL_NUMBER.split(name)
        if part
    )
    return parts, name.casefold(), name


def get_ffmpeg_installation_hint(system_name: Optional[str] = None) -> str:
    """Return platform-appropriate installation guidance for FFmpeg tools."""
    current_system = system_name or platform.system()
    if current_system == 'Windows':
        return (
            "Install FFmpeg using a full build from https://ffmpeg.org/download.html "
            "and add its bin directory to PATH (the system PATH)."
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


def has_mpeg_ts_signature(path: str) -> bool:
    """Return whether a file begins with a recognizable MPEG-TS packet layout."""
    read_size = max(_MPEG_TS_PACKET_SIZES) * (_MPEG_TS_REQUIRED_SYNC_BYTES + 1)
    try:
        with open(path, "rb") as stream:
            data = stream.read(read_size)
    except (OSError, PermissionError):
        return False

    for packet_size in _MPEG_TS_PACKET_SIZES:
        required_span = packet_size * (_MPEG_TS_REQUIRED_SYNC_BYTES - 1)
        if len(data) <= required_span:
            continue
        max_offset = min(packet_size, len(data) - required_span)
        for offset in range(max_offset):
            if all(
                data[offset + packet_size * packet_index] == 0x47
                for packet_index in range(_MPEG_TS_REQUIRED_SYNC_BYTES)
            ):
                return True
    return False


def is_video_file(path: str) -> bool:
    """Return whether an existing file is a supported video candidate."""
    if not os.path.isfile(path):
        return False
    extension = os.path.splitext(os.fspath(path))[1].lower()
    if extension not in SUPPORTED_VIDEO_EXTENSIONS:
        return False
    if extension in AMBIGUOUS_VIDEO_EXTENSIONS:
        return has_mpeg_ts_signature(path)
    return True


def get_video_files_in_directory(directory_path: str) -> List[str]:
    """Get all video files in a directory."""
    video_files = []
    if not os.path.isdir(directory_path):
        return video_files

    for filename in os.listdir(directory_path):
        file_path = os.path.join(directory_path, filename)
        if is_video_file(file_path):
            video_files.append(file_path)

    return sorted(video_files, key=natural_path_key)


def detect_input_type(input_path: str) -> str:
    """Detect the input type based on the path contents."""
    if os.path.isfile(input_path):
        if is_video_file(input_path):
            return "video"
        raise ValueError(f"Input file is not a supported video: {input_path}")
    elif os.path.isdir(input_path):
        # Check what's in the directory
        video_files = get_video_files_in_directory(input_path)
        if video_files:
            return "video_directory"
        else:
            return "directory"  # Assume image directory
    else:
        raise ValueError(f"Input path is neither a file nor a directory: {input_path}")
