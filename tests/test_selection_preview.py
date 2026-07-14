"""Tests for exact selection previews."""

import time

import pytest

from sharp_frames.selection_methods import (
    select_batched_frames_core,
    select_best_n_frames_core,
    select_outlier_removal_frames_core,
)
from sharp_frames.selection_preview import (
    _calculate_cached_preview,
    _preview_cache,
    get_selection_count,
    get_selection_preview,
)


def make_frames(scores, source=None, index_offset=0):
    return [
        {
            "id": f"{source or 'frames'}_{position:05d}",
            "path": f"/tmp/{source or 'frames'}/frame_{position:05d}.jpg",
            "index": index_offset + position,
            "sharpnessScore": score,
            "source_video": source,
            "source_index": position if source else None,
        }
        for position, score in enumerate(scores)
    ]


def test_best_n_count_includes_exact_buffer_capacity():
    frames = make_frames(range(100))

    assert get_selection_count(frames, "best-n", n=50, min_buffer=0) == 50
    assert get_selection_count(frames, "best-n", n=50, min_buffer=3) == 25
    assert get_selection_count(frames, "best-n", n=0, min_buffer=3) == 0


def test_batched_count_is_one_pick_per_batch():
    frames = make_frames(range(100))

    assert get_selection_count(frames, "batched", batch_size=5, batch_buffer=10) == 7
    assert get_selection_count(frames, "batched", batch_size=10, batch_buffer=0) == 10
    assert get_selection_count(frames, "batched", batch_size=1, batch_buffer=9) == 10


@pytest.mark.parametrize(
    ("method", "params", "select"),
    [
        (
            "best-n",
            {"n": 8, "min_buffer": 2},
            lambda frames: select_best_n_frames_core(frames, 8, 2),
        ),
        (
            "batched",
            {"batch_size": 4, "batch_buffer": 2},
            lambda frames: select_batched_frames_core(frames, 4, 2),
        ),
        (
            "outlier-removal",
            {"outlier_sensitivity": 75, "outlier_window_size": 7},
            lambda frames: [
                frame
                for frame in select_outlier_removal_frames_core(frames, 7, 75)
                if frame["selected"]
            ],
        ),
    ],
)
def test_count_matches_canonical_execution(method, params, select):
    frames = make_frames([100, 100, 10, 100, 80, 120, 100] * 5)

    assert get_selection_count(frames, method, **params) == len(select(frames))


def test_detailed_preview_uses_exact_selected_scores_and_positions():
    frames = make_frames([10, 90, 20, 80, 30, 70, 40, 60, 50, 100])
    selected = select_best_n_frames_core(frames, 3, 0)

    preview = get_selection_preview(frames, "best-n", n=3, min_buffer=0)
    selected_scores = [frame["sharpnessScore"] for frame in selected]

    assert preview["count"] == len(selected)
    assert sum(preview["distribution"]) == len(selected)
    assert preview["statistics"] == {
        "min_sharpness": min(selected_scores),
        "max_sharpness": max(selected_scores),
        "avg_sharpness": sum(selected_scores) / len(selected_scores),
    }


def test_distribution_tracks_duplicate_frame_metadata_by_input_position():
    duplicate = {
        "id": "duplicate",
        "path": "/tmp/duplicate.jpg",
        "index": 0,
        "sharpnessScore": 100,
    }
    frames = [duplicate.copy() for _ in range(20)]

    preview = get_selection_preview(frames, "best-n", n=2, min_buffer=0)

    assert sum(preview["distribution"][:5]) == 1
    assert sum(preview["distribution"][5:]) == 1


def test_outlier_preview_uses_actual_scores_and_window_size():
    frames = make_frames([100, 100, 100, 1, 100, 100, 100])

    small_window = get_selection_count(
        frames,
        "outlier-removal",
        outlier_sensitivity=100,
        outlier_window_size=3,
    )
    large_window = get_selection_count(
        frames,
        "outlier-removal",
        outlier_sensitivity=100,
        outlier_window_size=7,
    )

    assert small_window == 7
    assert large_window == 6


def test_video_source_boundaries_are_reflected_in_preview():
    frames = [
        *make_frames(range(6), source="video_a"),
        *make_frames(range(6), source="video_b", index_offset=6),
    ]

    assert get_selection_count(
        frames, "batched", batch_size=4, batch_buffer=0
    ) == 4


def test_empty_and_invalid_inputs():
    assert get_selection_count([], "best-n", n=10) == 0
    assert get_selection_preview([], "best-n", n=10)["count"] == 0
    with pytest.raises(ValueError, match="Unsupported selection method"):
        get_selection_count(make_frames([100]), "invalid")


def test_preview_cache_includes_middle_scores():
    _preview_cache.clear()
    frames = make_frames([100, 100, 1, 100, 100, 100, 100])
    first = _calculate_cached_preview(
        frames,
        "outlier-removal",
        outlier_sensitivity=100,
        outlier_window_size=7,
    )
    frames[2]["sharpnessScore"] = 100
    second = _calculate_cached_preview(
        frames,
        "outlier-removal",
        outlier_sensitivity=100,
        outlier_window_size=7,
    )

    assert first["count"] == 6
    assert second["count"] == 7


def test_best_n_count_remains_responsive_for_large_inputs():
    frames = make_frames([50 + index * 0.01 for index in range(10_000)])

    start = time.perf_counter()
    count = get_selection_count(frames, "best-n", n=1_000, min_buffer=0)
    elapsed = time.perf_counter() - start

    assert count == 1_000
    assert elapsed < 0.1
