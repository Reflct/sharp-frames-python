"""Exact previews backed by the canonical frame-selection algorithms."""

from collections import Counter
from typing import Any, Dict, List, Sequence, Tuple

from .selection_methods import (
    OUTLIER_DEFAULT_SENSITIVITY,
    OUTLIER_DEFAULT_WINDOW_SIZE,
    select_batched_frames_core,
    select_best_n_frames_core,
    select_outlier_removal_frames_core,
)


Frame = Dict[str, Any]


def _select_for_preview(
    frames: Sequence[Frame], method: str, **params: Any
) -> List[Frame]:
    if method in {"best-n", "best_n"}:
        return select_best_n_frames_core(
            frames,
            params.get("n", 300),
            params.get("min_buffer", 3),
            params.get("sharpness_weight", 0.7),
            params.get("distribution_weight", 0.3),
        )
    if method == "batched":
        return select_batched_frames_core(
            frames,
            params.get("batch_size", 5),
            params.get("batch_buffer", 2),
        )
    if method in {"outlier-removal", "outlier_removal"}:
        assessed = select_outlier_removal_frames_core(
            frames,
            params.get("outlier_window_size", OUTLIER_DEFAULT_WINDOW_SIZE),
            params.get("outlier_sensitivity", OUTLIER_DEFAULT_SENSITIVITY),
            params.get("min_neighbors", 3),
            params.get("threshold_divisor", 4.0),
        )
        return [frame for frame in assessed if frame["selected"]]
    raise ValueError(f"Unsupported selection method: {method}")


def get_selection_count(
    frames_with_scores: List[Frame], method: str, **params: Any
) -> int:
    """Return the exact number of frames that execution will select."""
    if not frames_with_scores:
        return 0
    return len(_select_for_preview(frames_with_scores, method, **params))


def get_selection_preview(
    frames_with_scores: List[Frame], method: str, **params: Any
) -> Dict[str, Any]:
    """Return exact selection count, timeline distribution, and score statistics."""
    if not frames_with_scores:
        return _empty_preview()

    positioned_frames = [
        dict(frame, _preview_position=position)
        for position, frame in enumerate(frames_with_scores)
    ]
    selected = _select_for_preview(positioned_frames, method, **params)
    scores = [float(frame.get("sharpnessScore", 0) or 0) for frame in selected]
    return {
        "count": len(selected),
        "distribution": _calculate_timeline_distribution(positioned_frames, selected),
        "statistics": {
            "min_sharpness": min(scores) if scores else 0,
            "max_sharpness": max(scores) if scores else 0,
            "avg_sharpness": sum(scores) / len(scores) if scores else 0,
        },
    }


def _empty_preview() -> Dict[str, Any]:
    return {
        "count": 0,
        "distribution": [],
        "statistics": {
            "min_sharpness": 0,
            "max_sharpness": 0,
            "avg_sharpness": 0,
        },
    }


def _frame_identity(frame: Frame) -> Tuple[Any, ...]:
    return (
        frame.get("_preview_position"),
        frame.get("source_video") or frame.get("sourceVideo"),
        frame.get("source_index"),
        frame.get("id"),
        frame.get("path"),
        frame.get("index"),
    )


def _calculate_timeline_distribution(
    all_frames: List[Frame], selected_frames: List[Frame], num_bins: int = 10
) -> List[int]:
    """Count the exact selected positions in timeline bins."""
    if num_bins <= 0:
        return []
    distribution = [0] * num_bins
    if not all_frames or not selected_frames:
        return distribution

    selected_identities = Counter(_frame_identity(frame) for frame in selected_frames)
    bin_size = len(all_frames) / num_bins
    for position, frame in enumerate(all_frames):
        identity = _frame_identity(frame)
        if not selected_identities[identity]:
            continue
        selected_identities[identity] -= 1
        bin_index = min(int(position / bin_size), num_bins - 1)
        distribution[bin_index] += 1
    return distribution


_preview_cache: Dict[str, Dict[str, Any]] = {}
_cache_max_size = 100


def _calculate_cache_key(
    frames_with_scores: List[Frame], method: str, **params: Any
) -> str:
    """Include every algorithm input so cached previews cannot become stale."""
    frame_state = tuple(
        (
            _frame_identity(frame),
            float(frame.get("sharpnessScore", 0) or 0),
        )
        for frame in frames_with_scores
    )
    parameter_state = tuple(sorted(params.items()))
    return repr((method, frame_state, parameter_state))


def _calculate_cached_preview(
    frames_with_scores: List[Frame], method: str, **params: Any
) -> Dict[str, Any]:
    """Return an exact preview from a bounded in-process cache."""
    key = _calculate_cache_key(frames_with_scores, method, **params)
    cached = _preview_cache.get(key)
    if cached is not None:
        return cached
    result = get_selection_preview(frames_with_scores, method, **params)
    if len(_preview_cache) >= _cache_max_size:
        for stale_key in list(_preview_cache)[: _cache_max_size // 2]:
            del _preview_cache[stale_key]
    _preview_cache[key] = result
    return result
