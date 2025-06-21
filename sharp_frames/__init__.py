"""Sharp Frames - Extract, score, and select the best frames from a video, video directory, or image directory."""

__version__ = "0.1.3"

import subprocess
import sys
import warnings

# Check for FFmpeg and FFprobe availability
def _check_ffmpeg():
    try:
        subprocess.run(
            ["ffmpeg", "-version"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            check=True
        )
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False

def _check_ffprobe():
    try:
        subprocess.run(
            ["ffprobe", "-version"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            check=True
        )
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False

# Check external dependencies
_has_ffmpeg = _check_ffmpeg()
_has_ffprobe = _check_ffprobe()

# Print dependency warnings
if not _has_ffmpeg:
    ffmpeg_warning = (
        "\n⚠️  WARNING: FFmpeg not found in PATH. Video processing will not work.\n"
        "   Install FFmpeg from https://ffmpeg.org/download.html or using your system's package manager.\n"
    )
    print(ffmpeg_warning, file=sys.stderr)
    warnings.warn(
        "FFmpeg not found in PATH. Video processing will not work.",
        ImportWarning
    )

if not _has_ffprobe:
    ffprobe_warning = (
        "\n⚠️  WARNING: FFprobe not found in PATH. Video duration detection will be limited.\n"
        "   FFprobe is typically installed with FFmpeg: https://ffmpeg.org/download.html\n"
    )
    print(ffprobe_warning, file=sys.stderr)
    warnings.warn(
        "FFprobe not found in PATH. Video duration detection will be limited.",
        ImportWarning
    )

from .sharp_frames_processor import SharpFrames, ImageProcessingError
from .selection_methods import (
    select_best_n_frames,
    select_batched_frames,
    select_outlier_removal_frames
) 