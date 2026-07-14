"""Tests for the colorspace detection and conversion module."""

import pytest
from unittest.mock import patch, MagicMock

from sharp_frames.processing.colorspace import (
    VideoColorInfo,
    ColorPrimaries,
    TransferFunction,
    ColorMatrix,
    detect_color_space,
    parse_color_info_from_stream,
    build_colorspace_filter,
    get_color_info_description,
    is_zscale_available,
    _default_color_info,
)


class TestVideoColorInfo:
    """Tests for VideoColorInfo dataclass."""

    def test_bt709_sdr_no_conversion_needed(self):
        """Standard BT.709 SDR should not need conversion."""
        info = VideoColorInfo(
            color_primaries=ColorPrimaries.BT709,
            transfer_function=TransferFunction.BT709,
            color_matrix=ColorMatrix.BT709,
            is_hdr=False
        )
        assert info.needs_conversion is False
        assert info.is_wide_gamut_sdr is False

    def test_unknown_no_conversion_needed(self):
        """Unknown color space should not trigger conversion (safe default)."""
        info = VideoColorInfo(
            color_primaries=ColorPrimaries.UNKNOWN,
            transfer_function=TransferFunction.UNKNOWN,
            color_matrix=ColorMatrix.UNKNOWN,
            is_hdr=False
        )
        assert info.needs_conversion is False

    def test_display_p3_needs_conversion(self):
        """Display P3 SDR should need conversion."""
        info = VideoColorInfo(
            color_primaries=ColorPrimaries.DISPLAY_P3,
            transfer_function=TransferFunction.BT709,
            color_matrix=ColorMatrix.BT709,
            is_hdr=False
        )
        assert info.needs_conversion is True
        assert info.is_wide_gamut_sdr is True

    def test_bt2020_sdr_needs_conversion(self):
        """BT.2020 SDR should need conversion."""
        info = VideoColorInfo(
            color_primaries=ColorPrimaries.BT2020,
            transfer_function=TransferFunction.BT709,
            color_matrix=ColorMatrix.BT709,
            is_hdr=False
        )
        assert info.needs_conversion is True
        assert info.is_wide_gamut_sdr is True

    def test_hdr_pq_needs_conversion(self):
        """HDR with PQ transfer (HDR10/Dolby Vision) should need conversion."""
        info = VideoColorInfo(
            color_primaries=ColorPrimaries.BT2020,
            transfer_function=TransferFunction.PQ,
            color_matrix=ColorMatrix.BT2020_NCL,
            is_hdr=True
        )
        assert info.needs_conversion is True
        assert info.is_wide_gamut_sdr is False  # It's HDR, not SDR

    def test_hdr_hlg_needs_conversion(self):
        """HDR with HLG transfer should need conversion."""
        info = VideoColorInfo(
            color_primaries=ColorPrimaries.BT2020,
            transfer_function=TransferFunction.HLG,
            color_matrix=ColorMatrix.BT2020_NCL,
            is_hdr=True
        )
        assert info.needs_conversion is True


class TestParseColorInfoFromStream:
    """Tests for parse_color_info_from_stream function."""

    def test_parse_bt709_stream(self):
        """Parse BT.709 stream data."""
        stream = {
            'color_primaries': 'bt709',
            'color_transfer': 'bt709',
            'color_space': 'bt709'
        }
        info = parse_color_info_from_stream(stream)
        assert info.color_primaries == ColorPrimaries.BT709
        assert info.transfer_function == TransferFunction.BT709
        assert info.color_matrix == ColorMatrix.BT709
        assert info.is_hdr is False

    def test_parse_display_p3_stream(self):
        """Parse Display P3 stream data (iPhone SDR)."""
        stream = {
            'color_primaries': 'smpte432',
            'color_transfer': 'bt709',
            'color_space': 'bt709'
        }
        info = parse_color_info_from_stream(stream)
        assert info.color_primaries == ColorPrimaries.DISPLAY_P3
        assert info.is_hdr is False

    def test_parse_hdr10_stream(self):
        """Parse HDR10 stream data."""
        stream = {
            'color_primaries': 'bt2020',
            'color_transfer': 'smpte2084',
            'color_space': 'bt2020nc'
        }
        info = parse_color_info_from_stream(stream)
        assert info.color_primaries == ColorPrimaries.BT2020
        assert info.transfer_function == TransferFunction.PQ
        assert info.color_matrix == ColorMatrix.BT2020_NCL
        assert info.is_hdr is True

    def test_parse_hlg_stream(self):
        """Parse HLG HDR stream data."""
        stream = {
            'color_primaries': 'bt2020',
            'color_transfer': 'arib-std-b67',
            'color_space': 'bt2020nc'
        }
        info = parse_color_info_from_stream(stream)
        assert info.transfer_function == TransferFunction.HLG
        assert info.is_hdr is True

    def test_parse_empty_stream(self):
        """Parse stream with missing color data."""
        stream = {}
        info = parse_color_info_from_stream(stream)
        assert info.color_primaries == ColorPrimaries.UNKNOWN
        assert info.transfer_function == TransferFunction.UNKNOWN
        assert info.color_matrix == ColorMatrix.UNKNOWN
        assert info.is_hdr is False

    def test_parse_stream_with_max_luminance(self):
        """Parse HDR stream with mastering display metadata."""
        stream = {
            'color_primaries': 'bt2020',
            'color_transfer': 'smpte2084',
            'color_space': 'bt2020nc',
            'side_data_list': [
                {
                    'side_data_type': 'Mastering display metadata',
                    'max_luminance': '10000000/10000'
                }
            ]
        }
        info = parse_color_info_from_stream(stream)
        assert info.max_luminance == 1000.0


class TestBuildColorspaceFilter:
    """Tests for build_colorspace_filter function."""

    def test_no_filter_for_bt709(self):
        """No filter needed for standard BT.709."""
        info = VideoColorInfo(
            color_primaries=ColorPrimaries.BT709,
            transfer_function=TransferFunction.BT709,
            color_matrix=ColorMatrix.BT709,
            is_hdr=False
        )
        assert build_colorspace_filter(info) is None

    def test_no_filter_for_unknown(self):
        """No filter for unknown color space (safe default)."""
        info = VideoColorInfo(
            color_primaries=ColorPrimaries.UNKNOWN,
            transfer_function=TransferFunction.UNKNOWN,
            color_matrix=ColorMatrix.UNKNOWN,
            is_hdr=False
        )
        assert build_colorspace_filter(info) is None

    def test_filter_for_display_p3(self):
        """Filter generated for Display P3."""
        info = VideoColorInfo(
            color_primaries=ColorPrimaries.DISPLAY_P3,
            transfer_function=TransferFunction.BT709,
            color_matrix=ColorMatrix.BT709,
            is_hdr=False
        )
        filter_str = build_colorspace_filter(info)
        assert filter_str is not None
        assert 'colorspace' in filter_str
        assert 'bt709' in filter_str
        assert 'smpte432' in filter_str

    @patch('sharp_frames.processing.colorspace.is_zscale_available', return_value=True)
    def test_hdr_filter_with_zscale(self, mock_zscale):
        """HDR filter uses zscale when available."""
        info = VideoColorInfo(
            color_primaries=ColorPrimaries.BT2020,
            transfer_function=TransferFunction.PQ,
            color_matrix=ColorMatrix.BT2020_NCL,
            is_hdr=True
        )
        filter_str = build_colorspace_filter(info)
        assert filter_str is not None
        assert 'zscale' in filter_str
        assert 'tonemap' in filter_str
        assert 'hable' in filter_str
        # Check that input parameters are specified
        assert 'tin=' in filter_str
        assert 'pin=' in filter_str

    @patch('sharp_frames.processing.colorspace.is_zscale_available', return_value=False)
    def test_hdr_filter_fallback_without_zscale(self, mock_zscale):
        """HDR filter falls back to colorspace when zscale unavailable."""
        info = VideoColorInfo(
            color_primaries=ColorPrimaries.BT2020,
            transfer_function=TransferFunction.PQ,
            color_matrix=ColorMatrix.BT2020_NCL,
            is_hdr=True
        )
        filter_str = build_colorspace_filter(info)
        assert filter_str is not None
        assert 'colorspace' in filter_str
        assert 'zscale' not in filter_str


class TestGetColorInfoDescription:
    """Tests for get_color_info_description function."""

    def test_sdr_bt709_description(self):
        """Description for standard SDR."""
        info = VideoColorInfo(
            color_primaries=ColorPrimaries.BT709,
            transfer_function=TransferFunction.BT709,
            color_matrix=ColorMatrix.BT709,
            is_hdr=False
        )
        desc = get_color_info_description(info)
        assert 'SDR' in desc
        assert 'BT.709' in desc

    def test_display_p3_description(self):
        """Description for Display P3."""
        info = VideoColorInfo(
            color_primaries=ColorPrimaries.DISPLAY_P3,
            transfer_function=TransferFunction.BT709,
            color_matrix=ColorMatrix.BT709,
            is_hdr=False
        )
        desc = get_color_info_description(info)
        assert 'SDR' in desc
        assert 'Display P3' in desc

    def test_hdr_pq_description(self):
        """Description for HDR10/Dolby Vision."""
        info = VideoColorInfo(
            color_primaries=ColorPrimaries.BT2020,
            transfer_function=TransferFunction.PQ,
            color_matrix=ColorMatrix.BT2020_NCL,
            is_hdr=True
        )
        desc = get_color_info_description(info)
        assert 'HDR10' in desc or 'Dolby Vision' in desc
        assert 'BT.2020' in desc

    def test_hlg_description(self):
        """Description for HLG HDR."""
        info = VideoColorInfo(
            color_primaries=ColorPrimaries.BT2020,
            transfer_function=TransferFunction.HLG,
            color_matrix=ColorMatrix.BT2020_NCL,
            is_hdr=True
        )
        desc = get_color_info_description(info)
        assert 'HLG' in desc


class TestDetectColorSpace:
    """Tests for detect_color_space function with mocked ffprobe."""

    @patch('subprocess.run')
    def test_detect_bt709(self, mock_run):
        """Detect BT.709 from ffprobe output."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"streams": [{"codec_type": "video", "color_primaries": "bt709", "color_transfer": "bt709", "color_space": "bt709"}]}'
        )
        info = detect_color_space('/fake/video.mp4')
        assert info.color_primaries == ColorPrimaries.BT709
        assert info.is_hdr is False

    @patch('subprocess.run')
    def test_detect_hdr(self, mock_run):
        """Detect HDR from ffprobe output."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"streams": [{"codec_type": "video", "color_primaries": "bt2020", "color_transfer": "smpte2084", "color_space": "bt2020nc"}]}'
        )
        info = detect_color_space('/fake/video.mp4')
        assert info.color_primaries == ColorPrimaries.BT2020
        assert info.transfer_function == TransferFunction.PQ
        assert info.is_hdr is True

    @patch('subprocess.run')
    def test_detect_failure_returns_default(self, mock_run):
        """Return default color info when ffprobe fails."""
        mock_run.return_value = MagicMock(returncode=1, stdout='')
        info = detect_color_space('/fake/video.mp4')
        assert info.color_primaries == ColorPrimaries.UNKNOWN
        assert info.is_hdr is False

    @patch('subprocess.run')
    def test_detect_timeout_returns_default(self, mock_run):
        """Return default color info on timeout."""
        from subprocess import TimeoutExpired
        mock_run.side_effect = TimeoutExpired('ffprobe', 30)
        info = detect_color_space('/fake/video.mp4')
        assert info.color_primaries == ColorPrimaries.UNKNOWN


class TestIsZscaleAvailable:
    """Tests for zscale availability check."""

    @patch('subprocess.run')
    def test_zscale_available(self, mock_run):
        """Detect zscale when available."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='... zscale ... other filters ...'
        )
        # Clear the cache
        import sharp_frames.processing.colorspace as cs
        cs._zscale_available = None

        assert is_zscale_available() is True

    @patch('subprocess.run')
    def test_zscale_not_available(self, mock_run):
        """Detect when zscale is not available."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='scale colorspace other_filter'
        )
        # Clear the cache
        import sharp_frames.processing.colorspace as cs
        cs._zscale_available = None

        assert is_zscale_available() is False
