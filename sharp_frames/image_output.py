"""Shared image decoding, resizing, and encoding helpers."""

from pathlib import Path

import cv2
import numpy as np
from PIL import Image


class ImageOutputError(Exception):
    """Raised when an image cannot be decoded or encoded."""


def canonical_image_format(path: str) -> str:
    """Return a canonical image format name for a path."""
    extension = Path(path).suffix.lower().lstrip(".")
    aliases = {"jpeg": "jpg", "tif": "tiff"}
    return aliases.get(extension, extension)


def image_needs_processing(src_path: str, dst_path: str, width: int) -> bool:
    """Return whether an image needs resizing or format conversion."""
    return width > 0 or canonical_image_format(src_path) != canonical_image_format(
        dst_path
    )


def resize_image(image: np.ndarray, width: int) -> np.ndarray:
    """Resize an image to a width while preserving channels and aspect ratio."""
    height = int(image.shape[0] * (width / image.shape[1]))
    if height % 2 != 0:
        height += 1
    return cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA)


def transcode_image(src_path: str, dst_path: str, width: int = 0) -> None:
    """Decode, optionally resize, and encode an image without losing alpha."""
    image = cv2.imread(src_path, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ImageOutputError(f"Failed to read image: {src_path}")
    image = _apply_exif_orientation(image, src_path)

    if width > 0:
        image = resize_image(image, width)

    destination_format = canonical_image_format(dst_path)
    image = _prepare_for_destination(image, destination_format)

    if not cv2.imwrite(dst_path, image):
        raise ImageOutputError(
            f"Failed to encode image as {Path(dst_path).suffix}"
        )


def _apply_exif_orientation(
    image: np.ndarray, source_path: str
) -> np.ndarray:
    """Apply EXIF orientation to decoded pixels before metadata is discarded."""
    try:
        with Image.open(source_path) as source:
            orientation = int(source.getexif().get(274, 1))
    except (OSError, TypeError, ValueError):
        orientation = 1

    if orientation == 2:
        return cv2.flip(image, 1)
    if orientation == 3:
        return cv2.rotate(image, cv2.ROTATE_180)
    if orientation == 4:
        return cv2.flip(image, 0)
    if orientation == 5:
        return cv2.transpose(image)
    if orientation == 6:
        return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    if orientation == 7:
        return cv2.flip(cv2.transpose(image), -1)
    if orientation == 8:
        return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return image


def _prepare_for_destination(
    image: np.ndarray, destination_format: str
) -> np.ndarray:
    """Convert channels and depth to values supported by the encoder."""
    if destination_format == "jpg":
        return _to_uint8(_flatten_alpha_on_white(image))
    if destination_format == "png" and image.dtype.type not in {np.uint8, np.uint16}:
        return _to_uint8(image)
    if destination_format in {"bmp", "webp"} and image.dtype.type is not np.uint8:
        return _to_uint8(image)
    return image


def _to_uint8(image: np.ndarray) -> np.ndarray:
    """Scale image data to the eight-bit range required by JPEG."""
    if image.dtype == np.uint8:
        return image
    if image.dtype == np.bool_:
        return image.astype(np.uint8) * 255
    if np.issubdtype(image.dtype, np.integer):
        info = np.iinfo(image.dtype)
        scaled = (
            (image.astype(np.float32) - float(info.min))
            * (255.0 / float(info.max - info.min))
        )
        return np.clip(scaled, 0, 255).round().astype(np.uint8)

    finite = np.nan_to_num(image.astype(np.float32), nan=0.0)
    if finite.size and finite.min() >= 0 and finite.max() <= 1:
        finite = finite * 255.0
    return np.clip(finite, 0, 255).round().astype(np.uint8)


def _flatten_alpha_on_white(image: np.ndarray) -> np.ndarray:
    """Composite alpha-bearing images on white for JPEG output."""
    if image.ndim != 3 or image.shape[2] not in {2, 4}:
        return image

    color = image[..., :-1]
    alpha = image[..., -1:]
    if np.issubdtype(image.dtype, np.integer):
        maximum = float(np.iinfo(image.dtype).max)
    else:
        maximum = 1.0

    alpha_fraction = alpha.astype(np.float32) / maximum
    composited = (
        color.astype(np.float32) * alpha_fraction
        + maximum * (1.0 - alpha_fraction)
    )
    return np.clip(composited, 0, maximum).astype(image.dtype)
