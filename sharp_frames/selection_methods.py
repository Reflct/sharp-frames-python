"""Canonical frame-selection algorithms shared by the CLI and TUI."""

from collections import OrderedDict
from math import expm1, log1p
from statistics import median
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from tqdm import tqdm


Frame = Dict[str, Any]
PositionedFrame = Tuple[int, Frame]

OUTLIER_DEFAULT_WINDOW_SIZE = 15
OUTLIER_DEFAULT_SENSITIVITY = 60
OUTLIER_MIN_WINDOW_SIZE = 5
OUTLIER_MIN_RELATIVE_DROP = 0.005
OUTLIER_MAX_RELATIVE_DROP = 0.08
OUTLIER_MIN_ROBUST_THRESHOLD = 1.5


def _source_key(frame: Frame) -> Optional[str]:
    """Return a stable source identifier, if the frame belongs to a video."""
    return frame.get("source_video") or frame.get("sourceVideo")


def _group_by_source(frames: Sequence[Frame]) -> List[List[PositionedFrame]]:
    """Group video frames without allowing selection windows to cross sources."""
    groups: "OrderedDict[Optional[str], List[PositionedFrame]]" = OrderedDict()
    for position, frame in enumerate(frames):
        groups.setdefault(_source_key(frame), []).append((position, frame))
    return list(groups.values())


def _selection_capacity(frame_count: int, min_buffer: int) -> int:
    """Maximum selections when ``min_buffer`` frames must remain between picks."""
    if frame_count <= 0:
        return 0
    minimum_distance = max(0, min_buffer) + 1
    return ((frame_count - 1) // minimum_distance) + 1


def _allocate_fair_quotas(capacities: Sequence[int], requested: int) -> List[int]:
    """Allocate picks round-robin so no source can monopolize Best-N."""
    quotas = [0] * len(capacities)
    remaining = min(max(0, requested), sum(capacities))
    while remaining:
        allocated_this_round = False
        for group_index, capacity in enumerate(capacities):
            if remaining == 0:
                break
            if quotas[group_index] >= capacity:
                continue
            quotas[group_index] += 1
            remaining -= 1
            allocated_this_round = True
        if not allocated_this_round:
            break
    return quotas


def _normalise_scores(group: Sequence[PositionedFrame]) -> List[float]:
    scores = [float(frame.get("sharpnessScore", 0) or 0) for _, frame in group]
    low = min(scores)
    high = max(scores)
    if high == low:
        return [1.0] * len(scores)
    score_range = high - low
    return [(score - low) / score_range for score in scores]


def _normalise_weights(sharpness_weight: float, distribution_weight: float) -> Tuple[float, float]:
    sharpness = max(0.0, float(sharpness_weight))
    distribution = max(0.0, float(distribution_weight))
    total = sharpness + distribution
    if total == 0:
        return 0.7, 0.3
    return sharpness / total, distribution / total


def _segment_bounds(slot: int, quota: int, frame_count: int) -> Tuple[int, int]:
    start = (slot * frame_count) // quota
    end = max(start, (((slot + 1) * frame_count) // quota) - 1)
    return start, min(end, frame_count - 1)


def _select_best_from_group(
    group: Sequence[PositionedFrame],
    quota: int,
    min_buffer: int,
    sharpness_weight: float,
    distribution_weight: float,
) -> List[PositionedFrame]:
    """Pick the sharpest well-positioned frame from each feasible timeline segment."""
    if quota <= 0 or not group:
        return []

    frame_count = len(group)
    quota = min(quota, _selection_capacity(frame_count, min_buffer))
    minimum_distance = max(0, min_buffer) + 1
    sharpness_scores = _normalise_scores(group)
    sharpness_weight, distribution_weight = _normalise_weights(
        sharpness_weight, distribution_weight
    )

    selected: List[PositionedFrame] = []
    previous_position: Optional[int] = None
    for slot in range(quota):
        segment_start, segment_end = _segment_bounds(slot, quota, frame_count)
        remaining_slots = quota - slot - 1
        feasible_start = 0 if previous_position is None else previous_position + minimum_distance
        feasible_end = frame_count - 1 - (remaining_slots * minimum_distance)

        candidate_start = max(segment_start, feasible_start)
        candidate_end = min(segment_end, feasible_end)
        if candidate_start > candidate_end:
            candidate_start, candidate_end = feasible_start, feasible_end

        ideal_position = (segment_start + segment_end) / 2
        distribution_scale = max(1.0, (segment_end - segment_start + 1) / 2)

        def composite_score(position: int) -> Tuple[float, float, int]:
            distribution_score = max(
                0.0, 1.0 - (abs(position - ideal_position) / distribution_scale)
            )
            total_score = (
                sharpness_scores[position] * sharpness_weight
                + distribution_score * distribution_weight
            )
            raw_sharpness = float(group[position][1].get("sharpnessScore", 0) or 0)
            return total_score, raw_sharpness, -position

        best_position = max(range(candidate_start, candidate_end + 1), key=composite_score)
        selected.append(group[best_position])
        previous_position = best_position

    return selected


def select_best_n_frames_core(
    frames: Sequence[Frame],
    num_frames: int,
    min_buffer: int,
    sharpness_weight: float = 0.7,
    distribution_weight: float = 0.3,
) -> List[Frame]:
    """Pure Best-N implementation used by every application surface."""
    if not frames or num_frames <= 0:
        return []

    groups = _group_by_source(frames)
    capacities = [_selection_capacity(len(group), min_buffer) for group in groups]
    quotas = _allocate_fair_quotas(capacities, num_frames)
    selected: List[PositionedFrame] = []
    for group, quota in zip(groups, quotas):
        selected.extend(
            _select_best_from_group(
                group,
                quota,
                min_buffer,
                sharpness_weight,
                distribution_weight,
            )
        )
    return [frame for _, frame in sorted(selected, key=lambda item: item[0])]


def select_batched_frames_core(
    frames: Sequence[Frame], batch_size: int, batch_buffer: int
) -> List[Frame]:
    """Select the sharpest frame per source-local batch."""
    if not frames or batch_size <= 0:
        return []
    step_size = batch_size + max(0, batch_buffer)
    selected: List[PositionedFrame] = []
    for group in _group_by_source(frames):
        for start in range(0, len(group), step_size):
            batch = group[start : start + batch_size]
            if batch:
                selected.append(
                    max(
                        batch,
                        key=lambda item: (
                            float(item[1].get("sharpnessScore", 0) or 0),
                            -item[0],
                        ),
                    )
                )
    return [frame for _, frame in sorted(selected, key=lambda item: item[0])]


def _outlier_positions(
    group: Sequence[PositionedFrame],
    window_size: int,
    sensitivity: int,
    min_neighbors: int,
    threshold_divisor: float,
) -> Set[int]:
    if sensitivity <= 0 or not group:
        return set()

    raw_scores = [
        max(0.0, float(frame.get("sharpnessScore", 0) or 0))
        for _, frame in group
    ]
    scores = [log1p(score) for score in raw_scores]
    dip_magnitudes = [0.0] * len(scores)
    relative_drops = [0.0] * len(scores)
    for position in range(1, len(scores) - 1):
        # A local dip must sit below both adjacent frames. Using the lower
        # neighbor as the baseline prevents one unusually sharp neighbor from
        # making an otherwise ordinary frame look like an outlier.
        expected_score = min(scores[position - 1], scores[position + 1])
        dip_magnitudes[position] = max(0.0, expected_score - scores[position])
        expected_raw_score = expm1(expected_score)
        if expected_raw_score > 0:
            relative_drops[position] = max(
                0.0,
                (expected_raw_score - raw_scores[position]) / expected_raw_score,
            )

    actual_window_size = max(OUTLIER_MIN_WINDOW_SIZE, window_size)
    if actual_window_size % 2 == 0:
        actual_window_size += 1
    half_window = actual_window_size // 2
    maximum_threshold = threshold_divisor if threshold_divisor > 0 else 4.0
    sensitivity_ratio = min(100, sensitivity) / 100
    robust_threshold = OUTLIER_MIN_ROBUST_THRESHOLD + (
        (maximum_threshold - OUTLIER_MIN_ROBUST_THRESHOLD)
        * (1 - sensitivity_ratio)
    )
    minimum_relative_drop = OUTLIER_MAX_RELATIVE_DROP - (
        (OUTLIER_MAX_RELATIVE_DROP - OUTLIER_MIN_RELATIVE_DROP)
        * sensitivity_ratio
    )
    outliers: Set[int] = set()

    for position, dip_magnitude in enumerate(dip_magnitudes):
        if position == 0 or position == len(scores) - 1:
            continue
        window_start = max(0, position - half_window)
        window_end = min(len(group), position + half_window + 1)
        neighbor_dips = (
            dip_magnitudes[window_start:position]
            + dip_magnitudes[position + 1 : window_end]
        )
        required_neighbors = max(2, min_neighbors)
        if len(neighbor_dips) < required_neighbors:
            continue
        neighbor_median = median(neighbor_dips)
        absolute_deviations = [
            abs(neighbor_dip - neighbor_median) for neighbor_dip in neighbor_dips
        ]
        median_absolute_deviation = median(absolute_deviations)
        robust_scale = median_absolute_deviation * 1.4826
        if robust_scale == 0:
            robust_scale = max(abs(neighbor_median) * 0.01, 1e-9)

        excess_dip = dip_magnitude - neighbor_median
        robust_excess = excess_dip / robust_scale
        if (
            excess_dip > 0
            and relative_drops[position] >= minimum_relative_drop
            and robust_excess > robust_threshold
        ):
            outliers.add(position)
    return outliers


def select_outlier_removal_frames_core(
    frames: Sequence[Frame],
    window_size: int,
    sensitivity: int,
    min_neighbors: int = 3,
    threshold_divisor: float = 4.0,
) -> List[Frame]:
    """Return copies of all frames with an exact source-local ``selected`` flag."""
    result = [dict(frame, selected=True) for frame in frames]
    for group in _group_by_source(frames):
        for group_position in _outlier_positions(
            group, window_size, sensitivity, min_neighbors, threshold_divisor
        ):
            input_position = group[group_position][0]
            result[input_position]["selected"] = False
    return result


def select_best_n_frames(
    frames: List[Frame],
    num_frames: int,
    min_buffer: int,
    sharpness_weight: float,
    distribution_weight: float,
) -> List[Frame]:
    """Select Best-N frames and display CLI progress."""
    selected = select_best_n_frames_core(
        frames, num_frames, min_buffer, sharpness_weight, distribution_weight
    )
    with tqdm(total=len(selected), desc="Selecting frames (best-n)") as progress_bar:
        progress_bar.update(len(selected))
    return selected


def select_batched_frames(
    frames: List[Frame], batch_size: int, batch_buffer: int
) -> List[Frame]:
    """Select batched frames and display CLI progress."""
    selected = select_batched_frames_core(frames, batch_size, batch_buffer)
    with tqdm(total=len(selected), desc="Selecting batches") as progress_bar:
        progress_bar.update(len(selected))
    print(f"Batch selection: Selected {len(selected)} frames")
    return selected


def select_outlier_removal_frames(
    frames: List[Frame],
    window_size: int,
    sensitivity: int,
    min_neighbors: int,
    threshold_divisor: float,
) -> List[Frame]:
    """Flag local low-sharpness outliers and display CLI progress."""
    result = select_outlier_removal_frames_core(
        frames, window_size, sensitivity, min_neighbors, threshold_divisor
    )
    with tqdm(total=len(result), desc="Analyzing for outliers") as progress_bar:
        progress_bar.update(len(result))
    selected_count = sum(frame["selected"] for frame in result)
    print(
        f"Outlier detection: Marked {len(result) - selected_count} outliers. "
        f"Keeping {selected_count} frames."
    )
    return result


# Compatibility hooks used by the legacy minimal-progress UI. They now delegate to
# the same canonical Best-N implementation, so that UI no longer has separate rules.
def _select_initial_segments(
    frames: List[Frame], n: int, min_gap: int, progress_bar: Any
) -> Tuple[List[Frame], Set[int]]:
    selected = select_best_n_frames_core(frames, n, min_gap, 0.7, 0.3)
    if progress_bar is not None:
        progress_bar.update(len(selected))
    return selected, {frame["index"] for frame in selected}


def _fill_remaining_slots(
    frames: List[Frame],
    n: int,
    min_gap: int,
    selected_frames: List[Frame],
    selected_indices: Set[int],
    progress_bar: Any,
    sharpness_weight: float,
    distribution_weight: float,
) -> None:
    """Compatibility no-op; the canonical first pass fills every feasible slot."""
    return None


def _is_gap_sufficient(frame_index: int, selected_indices: Set[int], min_buffer: int) -> bool:
    """Compatibility helper using intervening-frame buffer semantics."""
    minimum_distance = max(0, min_buffer) + 1
    return all(abs(frame_index - selected) >= minimum_distance for selected in selected_indices)
