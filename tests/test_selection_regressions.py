"""Regression tests for the canonical frame-selection contract."""

from collections import Counter
from typing import Optional

from sharp_frames.models.frame_data import FrameData
from sharp_frames.processing.frame_selector import FrameSelector
from sharp_frames.selection_methods import (
    select_batched_frames,
    select_best_n_frames,
    select_outlier_removal_frames,
    select_outlier_removal_frames_core,
)
from sharp_frames.selection_preview import get_selection_count
from sharp_frames.sharp_frames_processor import SharpFrames


def _frame(
    index: int,
    score: float,
    source: Optional[str] = None,
    source_index: Optional[int] = None,
) -> FrameData:
    return FrameData(
        path=f"/tmp/{source or 'frames'}/frame_{index:05d}.jpg",
        index=index,
        sharpness_score=score,
        source_video=source,
        source_index=index if source_index is None else source_index,
    )


def _as_dict(frame: FrameData) -> dict:
    return {
        "id": f"frame_{frame.index:05d}",
        "path": frame.path,
        "index": frame.index,
        "sharpnessScore": frame.sharpness_score,
        "source_video": frame.source_video,
        "source_index": frame.source_index,
    }


def _selected_dicts(frames: list[dict]) -> list[dict]:
    return [frame for frame in frames if frame.get("selected", True)]


def test_best_n_balances_normalized_sharpness_and_timeline_in_both_apis():
    frames = [_frame(index, 10_000 - index * 100) for index in range(20)]
    frame_dicts = [_as_dict(frame) for frame in frames]

    selected_objects = FrameSelector(show_progress=False).select_frames(
        frames, "best_n", n=5, min_buffer=0
    )
    selected_dicts = select_best_n_frames(frame_dicts, 5, 0, 0.7, 0.3)

    object_indices = [frame.index for frame in selected_objects]
    assert object_indices == [frame["index"] for frame in selected_dicts]
    assert all(any(start <= index < start + 4 for index in object_indices) for start in range(0, 20, 4))


def test_best_n_weights_control_normalized_sharpness_distribution_tradeoff():
    frames = [_frame(index, score) for index, score in enumerate([100, 1, 99, 1, 1])]
    frame_dicts = [_as_dict(frame) for frame in frames]

    sharpness_only = select_best_n_frames(frame_dicts, 1, 0, 1.0, 0.0)
    distribution_only = select_best_n_frames(frame_dicts, 1, 0, 0.0, 1.0)

    assert sharpness_only[0]["index"] == 0
    assert distribution_only[0]["index"] == 2


def test_min_buffer_means_intervening_frames_and_previews_are_exact():
    frames = [_frame(index, 100 - index) for index in range(7)]
    frame_dicts = [_as_dict(frame) for frame in frames]
    selector = FrameSelector(show_progress=False)

    selected = selector.select_frames(frames, "best_n", n=3, min_buffer=3)

    assert len(selected) == 2
    assert all(right.index - left.index >= 4 for left, right in zip(selected, selected[1:]))
    assert selector.preview_selection(frames, "best_n", n=3, min_buffer=3) == len(selected)
    assert get_selection_count(frame_dicts, "best-n", n=3, min_buffer=3) == len(selected)


def test_outlier_endpoints_and_preview_match_across_apis():
    scores = [100, 100, 100, 1, 100, 100, 100]
    frames = [_frame(index, score) for index, score in enumerate(scores)]
    frame_dicts = [_as_dict(frame) for frame in frames]
    selector = FrameSelector(show_progress=False)

    at_zero = selector.select_frames(
        frames, "outlier_removal", outlier_sensitivity=0, outlier_window_size=7
    )
    at_hundred = selector.select_frames(
        frames, "outlier_removal", outlier_sensitivity=100, outlier_window_size=7
    )
    legacy_at_hundred = _selected_dicts(
        select_outlier_removal_frames(frame_dicts, 7, 100, 3, 4)
    )

    assert len(at_zero) == len(frames)
    assert [frame.index for frame in at_hundred] == [0, 1, 2, 4, 5, 6]
    assert [frame.index for frame in at_hundred] == [frame["index"] for frame in legacy_at_hundred]
    assert selector.preview_selection(
        frames, "outlier_removal", outlier_sensitivity=100, outlier_window_size=7
    ) == len(at_hundred)
    assert get_selection_count(
        frame_dicts, "outlier-removal", outlier_sensitivity=100, outlier_window_size=7
    ) == len(at_hundred)


def test_maximum_outlier_sensitivity_keeps_identical_frames():
    frames = [_frame(index, 100) for index in range(20)]

    selected = FrameSelector(show_progress=False).select_frames(
        frames, "outlier_removal", outlier_sensitivity=100, outlier_window_size=7
    )

    assert len(selected) == len(frames)


def test_outlier_window_without_neighbors_never_divides_by_zero():
    frame_dicts = [
        _as_dict(_frame(0, 1.0)),
        _as_dict(_frame(1, 100.0)),
    ]

    assessed = select_outlier_removal_frames_core(
        frame_dicts,
        window_size=1,
        sensitivity=100,
        min_neighbors=0,
        threshold_divisor=4.0,
    )

    assert all(frame["selected"] for frame in assessed)


def test_best_n_allocates_fairly_across_video_sources():
    frames = [
        *[_frame(index, 1_000 - index, "video_a", index) for index in range(10)],
        *[_frame(index + 10, 10 - index, "video_b", index) for index in range(10)],
    ]
    frame_dicts = [_as_dict(frame) for frame in frames]

    selected = FrameSelector(show_progress=False).select_frames(
        frames, "best_n", n=4, min_buffer=0
    )
    selected_dicts = select_best_n_frames(frame_dicts, 4, 0, 0.7, 0.3)

    assert Counter(frame.source_video for frame in selected) == {"video_a": 2, "video_b": 2}
    assert [frame.index for frame in selected] == [frame["index"] for frame in selected_dicts]


def test_batched_selection_restarts_at_each_video_boundary():
    frames = [
        *[_frame(index, index, "video_a", index) for index in range(6)],
        *[_frame(index + 6, index, "video_b", index) for index in range(6)],
    ]
    frame_dicts = [_as_dict(frame) for frame in frames]

    selected = FrameSelector(show_progress=False).select_frames(
        frames, "batched", batch_size=4, batch_buffer=0
    )
    selected_dicts = select_batched_frames(frame_dicts, 4, 0)

    assert Counter(frame.source_video for frame in selected) == {"video_a": 2, "video_b": 2}
    assert [frame.index for frame in selected] == [frame["index"] for frame in selected_dicts]
    assert get_selection_count(frame_dicts, "batched", batch_size=4, batch_buffer=0) == 4


def test_outlier_windows_do_not_cross_video_boundaries():
    frames = [
        *[_frame(index, score, "video_a", index) for index, score in enumerate([100, 100, 1])],
        *[_frame(index + 3, score, "video_b", index) for index, score in enumerate([100, 100, 100])],
    ]
    frame_dicts = [_as_dict(frame) for frame in frames]

    selected = FrameSelector(show_progress=False).select_frames(
        frames, "outlier_removal", outlier_sensitivity=100, outlier_window_size=7
    )
    selected_dicts = _selected_dicts(
        select_outlier_removal_frames(frame_dicts, 7, 100, 3, 4)
    )

    assert len(selected) == 6
    assert [frame.index for frame in selected] == [frame["index"] for frame in selected_dicts]
    assert get_selection_count(
        frame_dicts, "outlier-removal", outlier_sensitivity=100, outlier_window_size=7
    ) == 6


def test_legacy_video_directory_analysis_records_source_boundaries(tmp_path):
    processor = SharpFrames(
        input_path=str(tmp_path),
        input_type="video_directory",
        output_dir=str(tmp_path / "output"),
    )
    processor._process_image = lambda path: 100.0
    paths = [
        str(tmp_path / "video_001" / "frame_00001.jpg"),
        str(tmp_path / "video_001" / "frame_00002.jpg"),
        str(tmp_path / "video_002" / "frame_00001.jpg"),
    ]

    frames = processor._calculate_sharpness(paths)

    assert [frame["source_video"] for frame in frames] == [
        "video_001",
        "video_001",
        "video_002",
    ]
    assert [frame["source_index"] for frame in frames] == [0, 1, 0]
