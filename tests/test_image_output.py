"""Regression tests for shared image decode/resize/encode behavior."""

import cv2
import numpy as np
import pytest
from PIL import Image

from sharp_frames.image_output import (
    ImageOutputError,
    canonical_image_format,
    image_needs_processing,
    transcode_image,
)


def test_uint16_png_retains_bit_depth_on_resize(tmp_path):
    source = tmp_path / "deep.png"
    image = np.full((8, 8, 3), 32768, dtype=np.uint16)
    assert cv2.imwrite(str(source), image)

    output = tmp_path / "out.png"
    transcode_image(str(source), str(output), width=4)

    decoded = cv2.imread(str(output), cv2.IMREAD_UNCHANGED)
    assert decoded.dtype == np.uint16
    assert int(decoded.max()) > 255


def test_uint16_png_to_jpeg_scales_to_eight_bit_midtone(tmp_path):
    source = tmp_path / "deep.png"
    image = np.full((8, 8, 3), 32768, dtype=np.uint16)
    assert cv2.imwrite(str(source), image)

    output = tmp_path / "out.jpg"
    transcode_image(str(source), str(output))

    decoded = cv2.imread(str(output))
    assert decoded.dtype == np.uint8
    # 32768/65535 ~= 0.5 -> ~128, definitely not saturated white.
    assert 120 <= int(decoded.mean()) <= 136


def test_float_tiff_to_png_is_scaled_not_black(tmp_path):
    source = tmp_path / "linear.tiff"
    image = np.full((8, 8, 3), 0.5, dtype=np.float32)
    assert cv2.imwrite(str(source), image)

    output = tmp_path / "out.png"
    transcode_image(str(source), str(output))

    decoded = cv2.imread(str(output), cv2.IMREAD_UNCHANGED)
    assert decoded.dtype == np.uint8
    assert int(decoded.mean()) > 100


def test_exif_orientation_is_applied_before_resize(tmp_path):
    source = tmp_path / "portrait.jpg"
    # Landscape pixels (tall on disk once orientation 6 is applied).
    array = np.zeros((20, 40, 3), dtype=np.uint8)
    Image.fromarray(array).save(str(source), exif=_exif_orientation(6))

    output = tmp_path / "out.jpg"
    transcode_image(str(source), str(output), width=10)

    decoded = cv2.imread(str(output))
    # Orientation 6 rotates 40x20 landscape into 20x40 portrait, so width 10
    # gives a taller-than-wide result.
    assert decoded.shape[0] > decoded.shape[1]


def test_canonical_format_aliases():
    assert canonical_image_format("a.JPEG") == "jpg"
    assert canonical_image_format("a.tif") == "tiff"
    assert image_needs_processing("a.png", "b.png", width=0) is False
    assert image_needs_processing("a.png", "b.jpg", width=0) is True


def test_missing_source_raises(tmp_path):
    with pytest.raises(ImageOutputError, match="Failed to read"):
        transcode_image(str(tmp_path / "missing.png"), str(tmp_path / "o.png"))


def _exif_orientation(value: int) -> bytes:
    exif = Image.Exif()
    exif[274] = value
    return exif.tobytes()
