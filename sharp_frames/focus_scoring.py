"""Resolution-normalized, noise-resistant focus scoring."""

import cv2
import numpy as np


ANALYSIS_LONG_EDGE = 512
FOCUS_SCORE_METHOD = "normalized_laplacian_tenengrad_v1"
DENOISE_KERNEL = (5, 5)
DENOISE_SIGMA = 1.0
LAPLACIAN_WEIGHT = 0.5
TENENGRAD_WEIGHT = 0.5


def normalize_analysis_image(image: np.ndarray) -> np.ndarray:
    """Return a grayscale image at the canonical analysis resolution."""
    if image is None or image.size == 0:
        raise ValueError("Focus analysis requires a non-empty image")
    if image.ndim == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    height, width = image.shape
    scale = ANALYSIS_LONG_EDGE / max(height, width)
    target_size = (
        max(1, round(width * scale)),
        max(1, round(height * scale)),
    )
    interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
    return cv2.resize(image, target_size, interpolation=interpolation)


def calculate_focus_score(image: np.ndarray) -> float:
    """Combine Laplacian variance and Tenengrad after light denoising."""
    normalized = normalize_analysis_image(image)
    denoised = cv2.GaussianBlur(normalized, DENOISE_KERNEL, DENOISE_SIGMA)

    laplacian_variance = cv2.Laplacian(denoised, cv2.CV_64F).var()
    gradient_x = cv2.Sobel(denoised, cv2.CV_64F, 1, 0, ksize=3)
    gradient_y = cv2.Sobel(denoised, cv2.CV_64F, 0, 1, ksize=3)
    tenengrad = np.mean((gradient_x * gradient_x) + (gradient_y * gradient_y))

    combined_log_score = (
        np.log1p(laplacian_variance) * LAPLACIAN_WEIGHT
        + np.log1p(tenengrad) * TENENGRAD_WEIGHT
    )
    return float(np.expm1(combined_log_score))
