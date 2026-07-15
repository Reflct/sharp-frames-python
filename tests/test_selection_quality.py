"""Regression probes for the deferred selection-quality roadmap."""

from pathlib import Path

import cv2
import numpy as np

from sharp_frames.processing.frame_extractor import FrameExtractor
from sharp_frames.processing.sharpness_analyzer import SharpnessAnalyzer
from sharp_frames.selection_methods import select_outlier_removal_frames_core
from sharp_frames.sharp_frames_processor import SharpFrames
from sharp_frames.video_utils import get_video_files_in_directory


def _write_image(path: Path, image: np.ndarray) -> str:
    assert cv2.imwrite(str(path), image)
    return str(path)


def test_focus_score_is_comparable_across_source_resolutions(tmp_path):
    analyzer = SharpnessAnalyzer(max_workers=1)
    scores = []

    for resolution in (256, 1024):
        edge = np.zeros((resolution, resolution), dtype=np.uint8)
        edge[:, resolution // 2 :] = 255
        path = _write_image(tmp_path / f"edge_{resolution}.png", edge)
        scores.append(analyzer._calculate_single_frame_sharpness(path))

    assert max(scores) / min(scores) < 1.5


def test_focus_score_materially_separates_fine_detail_from_mild_blur(tmp_path):
    analyzer = SharpnessAnalyzer(max_workers=1)
    rng = np.random.default_rng(7)
    texture = rng.normal(127, 45, (1080, 1920)).clip(0, 255).astype(np.uint8)
    sharp = cv2.GaussianBlur(texture, (0, 0), 0.7)
    mildly_blurred = cv2.GaussianBlur(sharp, (0, 0), 2.0)

    sharp_score = analyzer._calculate_single_frame_sharpness(
        _write_image(tmp_path / "fine-detail-sharp.png", sharp)
    )
    blurred_score = analyzer._calculate_single_frame_sharpness(
        _write_image(tmp_path / "fine-detail-blurred.png", mildly_blurred)
    )

    assert sharp_score > blurred_score * 1.4


def test_focus_score_does_not_prefer_noisy_blur_over_clean_edge(tmp_path):
    analyzer = SharpnessAnalyzer(max_workers=1)
    sharp = np.zeros((512, 512), dtype=np.uint8)
    sharp[:, 256:] = 255
    blurred = cv2.GaussianBlur(sharp, (0, 0), 8)
    noise = np.random.default_rng(42).normal(0, 20, blurred.shape)
    noisy_blur = np.clip(blurred.astype(float) + noise, 0, 255).astype(np.uint8)

    sharp_score = analyzer._calculate_single_frame_sharpness(
        _write_image(tmp_path / "sharp.png", sharp)
    )
    noisy_blur_score = analyzer._calculate_single_frame_sharpness(
        _write_image(tmp_path / "noisy_blur.png", noisy_blur)
    )

    assert sharp_score > noisy_blur_score


def test_modern_and_direct_cli_use_the_same_focus_score(tmp_path):
    image = np.zeros((360, 640), dtype=np.uint8)
    image[:, 320:] = 255
    path = _write_image(tmp_path / "edge.png", image)

    modern_score = SharpnessAnalyzer(max_workers=1)._calculate_single_frame_sharpness(
        path
    )
    direct_cli_score = SharpFrames._process_image(path)

    assert direct_cli_score == modern_score


def test_image_and_video_directories_use_natural_casefolded_order(tmp_path):
    image_dir = tmp_path / "images"
    video_dir = tmp_path / "videos"
    image_dir.mkdir()
    video_dir.mkdir()

    for name in ("frame10.png", "Frame2.png", "frame1.png"):
        (image_dir / name).touch()
    for name in ("clip10.mp4", "Clip2.mp4", "clip1.mp4"):
        (video_dir / name).touch()

    image_names = [
        Path(path).name for path in FrameExtractor()._filter_image_files(str(image_dir))
    ]
    video_names = [
        Path(path).name for path in get_video_files_in_directory(str(video_dir))
    ]

    assert image_names == ["frame1.png", "Frame2.png", "frame10.png"]
    assert video_names == ["clip1.mp4", "Clip2.mp4", "clip10.mp4"]


def test_robust_outliers_ignore_one_extreme_high_score():
    scores = [100.0] * 15
    scores[7] = 1.0
    scores[14] = 1_000_000_000.0
    frames = [
        {"index": index, "sharpnessScore": score}
        for index, score in enumerate(scores)
    ]

    assessed = select_outlier_removal_frames_core(
        frames,
        window_size=15,
        sensitivity=50,
        min_neighbors=3,
        threshold_divisor=4.0,
    )

    assert assessed[7]["selected"] is False
    assert assessed[14]["selected"] is True


def test_labeled_blur_probe_tracks_rejection_precision_and_recall():
    blurry_positions = {7, 15, 23}
    scores = [100.0] * 31
    for position in blurry_positions:
        scores[position] = 10.0
    scores[-1] = 1_000_000_000.0
    frames = [
        {"index": index, "sharpnessScore": score}
        for index, score in enumerate(scores)
    ]

    assessed = select_outlier_removal_frames_core(
        frames,
        window_size=7,
        sensitivity=50,
        min_neighbors=3,
        threshold_divisor=4.0,
    )
    rejected = {
        position
        for position, frame in enumerate(assessed)
        if not frame["selected"]
    }
    true_rejections = rejected & blurry_positions
    precision = len(true_rejections) / len(rejected)
    recall = len(true_rejections) / len(blurry_positions)

    assert precision == 1.0
    assert recall == 1.0


def test_default_outlier_detection_requires_a_meaningful_relative_drop():
    scores = [100.0] * 15
    scores[5] = 90.0
    scores[9] = 75.0
    frames = [
        {"index": index, "sharpnessScore": score}
        for index, score in enumerate(scores)
    ]

    assessed = select_outlier_removal_frames_core(
        frames,
        window_size=15,
        sensitivity=60,
    )

    assert assessed[5]["selected"] is True
    assert assessed[9]["selected"] is False


def test_log_scaled_outlier_detection_is_consistent_across_score_magnitudes():
    def rejected_dip(baseline, dip):
        scores = [baseline] * 15
        scores[7] = dip
        frames = [
            {"index": index, "sharpnessScore": score}
            for index, score in enumerate(scores)
        ]
        return not select_outlier_removal_frames_core(
            frames,
            window_size=15,
            sensitivity=60,
        )[7]["selected"]

    assert rejected_dip(10.0, 7.0) is True
    assert rejected_dip(1_000.0, 700.0) is True
