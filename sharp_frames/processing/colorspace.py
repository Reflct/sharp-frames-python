"""Color space detection and FFmpeg filter generation for proper color conversion.

This module handles detection of video color spaces (especially iPhone HDR/wide gamut)
and generates appropriate FFmpeg filter chains to convert to sRGB/BT.709.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import Enum
import subprocess
import json
import os


__all__ = [
    'VideoColorInfo',
    'ColorPrimaries',
    'TransferFunction',
    'ColorMatrix',
    'detect_color_space',
    'parse_color_info_from_stream',
    'build_colorspace_filter',
    'get_color_info_description',
    'is_zscale_available',
]


class ColorPrimaries(Enum):
    """Video color primaries (ITU-T H.273)."""
    BT709 = "bt709"           # sRGB/Rec.709
    BT2020 = "bt2020"         # Wide gamut (HDR)
    DISPLAY_P3 = "smpte432"   # Display P3 (Apple)
    UNKNOWN = "unknown"


class TransferFunction(Enum):
    """Transfer characteristics (gamma/EOTF)."""
    BT709 = "bt709"           # SDR
    SRGB = "iec61966-2-1"     # sRGB
    PQ = "smpte2084"          # HDR10/Dolby Vision
    HLG = "arib-std-b67"      # Hybrid Log-Gamma
    UNKNOWN = "unknown"


class ColorMatrix(Enum):
    """Color matrix coefficients."""
    BT709 = "bt709"
    BT2020_NCL = "bt2020nc"   # Non-constant luminance
    BT2020_CL = "bt2020c"     # Constant luminance
    UNKNOWN = "unknown"


@dataclass
class VideoColorInfo:
    """Detected color space information from video."""
    color_primaries: ColorPrimaries
    transfer_function: TransferFunction
    color_matrix: ColorMatrix
    is_hdr: bool
    max_luminance: Optional[float] = None

    @property
    def needs_conversion(self) -> bool:
        """Check if video needs color space conversion to sRGB/BT.709."""
        # Convert if not standard BT.709 SDR
        if self.is_hdr:
            return True
        if self.color_primaries not in [ColorPrimaries.BT709, ColorPrimaries.UNKNOWN]:
            return True
        if self.transfer_function not in [TransferFunction.BT709, TransferFunction.SRGB, TransferFunction.UNKNOWN]:
            return True
        return False

    @property
    def is_wide_gamut_sdr(self) -> bool:
        """Check if this is wide gamut SDR (e.g., Display P3 without HDR)."""
        return (
            self.color_primaries in [ColorPrimaries.DISPLAY_P3, ColorPrimaries.BT2020] and
            not self.is_hdr
        )


def check_zscale_available() -> bool:
    """Check if FFmpeg has zscale filter available (requires libzimg)."""
    ffmpeg_executable = 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg'
    try:
        result = subprocess.run(
            [ffmpeg_executable, '-filters'],
            capture_output=True,
            text=True,
            timeout=10
        )
        return 'zscale' in result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


# Cache the zscale availability check
_zscale_available: Optional[bool] = None


def is_zscale_available() -> bool:
    """Check if zscale is available (cached)."""
    global _zscale_available
    if _zscale_available is None:
        _zscale_available = check_zscale_available()
    return _zscale_available


def detect_color_space(video_path: str) -> VideoColorInfo:
    """
    Detect video color space using ffprobe.

    Args:
        video_path: Path to the video file

    Returns:
        VideoColorInfo with detected or assumed defaults
    """
    ffprobe_executable = 'ffprobe.exe' if os.name == 'nt' else 'ffprobe'

    cmd = [
        ffprobe_executable, '-v', 'quiet',
        '-print_format', 'json',
        '-show_streams', '-select_streams', 'v:0',
        os.path.normpath(video_path)
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return _default_color_info()

        data = json.loads(result.stdout)
        streams = data.get('streams', [])
        if not streams:
            return _default_color_info()

        stream = streams[0]
        return parse_color_info_from_stream(stream)

    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError, OSError):
        return _default_color_info()


def parse_color_info_from_stream(stream: Dict[str, Any]) -> VideoColorInfo:
    """Parse ffprobe stream data into VideoColorInfo.

    This can be used to extract color info from existing ffprobe data
    without making an additional subprocess call.

    Args:
        stream: A video stream dict from ffprobe JSON output

    Returns:
        VideoColorInfo with parsed color space information
    """
    # Extract color metadata
    color_primaries_str = stream.get('color_primaries', 'unknown')
    transfer_str = stream.get('color_transfer', 'unknown')
    color_matrix_str = stream.get('color_space', 'unknown')

    # Map to enums
    primaries = _map_color_primaries(color_primaries_str)
    transfer = _map_transfer_function(transfer_str)
    matrix = _map_color_matrix(color_matrix_str)

    # Determine if HDR based on transfer function
    is_hdr = transfer in [TransferFunction.PQ, TransferFunction.HLG]

    # Try to get max luminance from side data (for HDR content)
    max_luminance = None
    side_data = stream.get('side_data_list', [])
    for data in side_data:
        if data.get('side_data_type') == 'Mastering display metadata':
            max_lum_str = data.get('max_luminance', '')
            if '/' in str(max_lum_str):
                try:
                    num, denom = str(max_lum_str).split('/')
                    max_luminance = float(num) / float(denom)
                except (ValueError, ZeroDivisionError):
                    pass

    return VideoColorInfo(
        color_primaries=primaries,
        transfer_function=transfer,
        color_matrix=matrix,
        is_hdr=is_hdr,
        max_luminance=max_luminance
    )


def _map_color_primaries(value: str) -> ColorPrimaries:
    """Map ffprobe color_primaries to enum."""
    if not value:
        return ColorPrimaries.UNKNOWN
    mapping = {
        'bt709': ColorPrimaries.BT709,
        'bt2020': ColorPrimaries.BT2020,
        'smpte432': ColorPrimaries.DISPLAY_P3,
    }
    return mapping.get(value.lower(), ColorPrimaries.UNKNOWN)


def _map_transfer_function(value: str) -> TransferFunction:
    """Map ffprobe color_transfer to enum."""
    if not value:
        return TransferFunction.UNKNOWN
    mapping = {
        'bt709': TransferFunction.BT709,
        'iec61966-2-1': TransferFunction.SRGB,
        'smpte2084': TransferFunction.PQ,
        'arib-std-b67': TransferFunction.HLG,
    }
    return mapping.get(value.lower(), TransferFunction.UNKNOWN)


def _map_color_matrix(value: str) -> ColorMatrix:
    """Map ffprobe color_space (matrix) to enum."""
    if not value:
        return ColorMatrix.UNKNOWN
    mapping = {
        'bt709': ColorMatrix.BT709,
        'bt2020nc': ColorMatrix.BT2020_NCL,
        'bt2020c': ColorMatrix.BT2020_CL,
    }
    return mapping.get(value.lower(), ColorMatrix.UNKNOWN)


def _default_color_info() -> VideoColorInfo:
    """Return default color info (assume unknown - no conversion)."""
    return VideoColorInfo(
        color_primaries=ColorPrimaries.UNKNOWN,
        transfer_function=TransferFunction.UNKNOWN,
        color_matrix=ColorMatrix.UNKNOWN,
        is_hdr=False
    )


def build_colorspace_filter(color_info: VideoColorInfo) -> Optional[str]:
    """
    Build FFmpeg filter string for color space conversion to sRGB/BT.709.

    Args:
        color_info: Detected color space information

    Returns:
        Filter string to add to -vf, or None if no conversion needed
    """
    if not color_info.needs_conversion:
        return None

    if color_info.is_hdr:
        return _build_hdr_to_sdr_filter(color_info)
    elif color_info.is_wide_gamut_sdr:
        return _build_wide_gamut_to_srgb_filter(color_info)
    else:
        return None


def _build_hdr_to_sdr_filter(color_info: VideoColorInfo) -> str:
    """
    Build HDR to SDR tone mapping filter.

    Uses zscale for high-quality conversion if available,
    otherwise falls back to basic colorspace filter.
    """
    # Determine input transfer function for zscale
    if color_info.transfer_function == TransferFunction.PQ:
        transfer_in = "smpte2084"
    elif color_info.transfer_function == TransferFunction.HLG:
        transfer_in = "arib-std-b67"
    else:
        transfer_in = "smpte2084"  # Default to PQ for unknown HDR

    # Determine input primaries
    if color_info.color_primaries == ColorPrimaries.BT2020:
        primaries_in = "bt2020"
    elif color_info.color_primaries == ColorPrimaries.DISPLAY_P3:
        primaries_in = "smpte432"
    else:
        primaries_in = "bt2020"  # Default to BT.2020 for HDR

    # Determine input matrix
    if color_info.color_matrix in [ColorMatrix.BT2020_NCL, ColorMatrix.BT2020_CL]:
        matrix_in = "bt2020nc"
    else:
        matrix_in = "bt2020nc"  # Default for HDR

    if is_zscale_available():
        # Full HDR to SDR pipeline with tone mapping
        # Explicitly specify input parameters for reliable conversion
        filter_chain = (
            f"zscale=tin={transfer_in}:min={matrix_in}:pin={primaries_in}:"
            f"t=linear:npl=100,"                # Linearize with input specs
            "format=gbrpf32le,"                  # High precision intermediate
            "zscale=p=bt709,"                    # Convert primaries to BT.709
            "tonemap=hable:desat=0,"             # Hable tone mapping (filmic)
            "zscale=t=bt709:m=bt709:r=tv,"       # Apply BT.709 transfer/matrix
            "format=yuv420p"                     # Standard output format
        )
    else:
        # Fallback: basic colorspace conversion (won't tone map properly)
        # This is better than nothing but may clip highlights
        filter_chain = f"colorspace=all=bt709:iall={primaries_in}:fast=0"

    return filter_chain


def _build_wide_gamut_to_srgb_filter(color_info: VideoColorInfo) -> str:
    """
    Build wide gamut SDR (Display P3/BT.2020) to sRGB/BT.709 filter.
    """
    # Determine input color space for the filter
    if color_info.color_primaries == ColorPrimaries.DISPLAY_P3:
        input_primaries = "smpte432"
    elif color_info.color_primaries == ColorPrimaries.BT2020:
        input_primaries = "bt2020"
    else:
        input_primaries = "bt709"  # Assume BT.709 if unknown

    # Use colorspace filter for gamut conversion (no tone mapping needed)
    filter_chain = f"colorspace=all=bt709:iall={input_primaries}:fast=0"

    return filter_chain


def get_color_info_description(color_info: VideoColorInfo) -> str:
    """Get a human-readable description of the color space."""
    parts = []

    if color_info.is_hdr:
        if color_info.transfer_function == TransferFunction.PQ:
            parts.append("HDR10/Dolby Vision (PQ)")
        elif color_info.transfer_function == TransferFunction.HLG:
            parts.append("HLG HDR")
        else:
            parts.append("HDR")
    else:
        parts.append("SDR")

    if color_info.color_primaries == ColorPrimaries.DISPLAY_P3:
        parts.append("Display P3")
    elif color_info.color_primaries == ColorPrimaries.BT2020:
        parts.append("BT.2020")
    elif color_info.color_primaries == ColorPrimaries.BT709:
        parts.append("BT.709")

    return " / ".join(parts) if parts else "Unknown"
