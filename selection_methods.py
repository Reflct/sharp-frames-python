# selection_methods.py

from typing import List, Dict, Any, Tuple, Set
from tqdm import tqdm

# === Helper Functions ===

def _is_gap_sufficient(frame_index: int, selected_indices: Set[int], min_gap: int) -> bool:
    """Check if a frame index maintains the minimum gap with selected indices."""
    if not selected_indices:
        return True # No selected indices yet, any gap is sufficient
    return all(abs(frame_index - selected_index) >= min_gap for selected_index in selected_indices)

def _calculate_distribution_score(frame_index: int, total_frames: int,
                                  selected_indices: Set[int], min_gap: int,
                                  distribution_weight: float) -> float:
    """Calculate a score representing how well a frame is distributed among others."""
    # Calculate distance from nearest selected frame (capped by min_gap)
    nearest_selected_distance = min_gap # Default to max distance if no selected indices yet
    if selected_indices: # Avoid calculation if set is empty
        nearest_selected_distance = min(abs(frame_index - sel_idx) for sel_idx in selected_indices)

    # Normalize distance score: 1 if gap >= min_gap, 0 if gap == 0
    distance_score = min(1.0, nearest_selected_distance / min_gap) if min_gap > 0 else 1.0

    # Calculate ideal position score
    num_selected_or_one = max(len(selected_indices), 1)
    if total_frames <= 0 or num_selected_or_one <= 0:
        position_score = 1.0 # Avoid division by zero if total_frames or num_selected is 0
    else:
        segment_size = total_frames / num_selected_or_one
        if segment_size <= 0:
            position_score = 1.0 # Avoid division by zero if segment_size is 0
        else:
            ideal_position = round(frame_index / segment_size) * segment_size
            dist_from_ideal = abs(frame_index - ideal_position)
            # Normalize: 1 at ideal pos, 0 at midpoint between ideal positions (segment_size / 2 away)
            position_score = max(0.0, 1.0 - (dist_from_ideal / (segment_size / 2))) if segment_size > 0 else 1.0

    # Combine scores using weights (sharpness weight is implicitly 1.0 - distribution_weight)
    return (distance_score * distribution_weight) + (position_score * (1.0 - distribution_weight))

# === Best-N Selection ===

def _select_initial_segments(frames: List[Dict[str, Any]], n: int, min_gap: int,
                             progress_bar: tqdm) -> Tuple[List[Dict[str, Any]], Set[int]]:
    """First pass of best-n: Select best frame from initial segments."""
    selected_frames = []
    selected_indices = set()
    if n <= 0 or not frames: return selected_frames, selected_indices # Handle edge cases

    # Prevent division by zero if n is zero
    if n == 0: return selected_frames, selected_indices
    
    segment_size = max(1, len(frames) // n)
    num_segments = (len(frames) + segment_size - 1) // segment_size # Ensure all frames are covered

    for i in range(num_segments):
        if len(selected_frames) >= n:
            break

        segment_start = i * segment_size
        segment_end = min(segment_start + segment_size, len(frames))
        segment = frames[segment_start:segment_end]

        if not segment: continue # Skip empty segments

        # Find valid frames in the segment respecting the minimum gap
        valid_frames = [
            frame for frame in segment
            if _is_gap_sufficient(frame["index"], selected_indices, min_gap)
        ]

        if valid_frames:
            best_frame = max(valid_frames, key=lambda f: f.get("sharpnessScore", 0))
            selected_frames.append(best_frame)
            selected_indices.add(best_frame["index"])
            progress_bar.update(1)

    return selected_frames, selected_indices

def _fill_remaining_slots(frames: List[Dict[str, Any]], n: int, min_gap: int,
                          selected_frames: List[Dict[str, Any]], selected_indices: Set[int],
                          progress_bar: tqdm, sharpness_weight: float, distribution_weight: float):
    """Second pass of best-n: Fill remaining slots using composite score."""
    current_selected_indices = set(selected_indices) # Use the indices passed in

    while len(selected_frames) < n:
        best_candidate = None
        best_composite_score = -1

        potential_candidates = [f for f in frames if f["index"] not in current_selected_indices]

        if not potential_candidates:
             break # No more frames left to consider

        for frame in potential_candidates:
            frame_index = frame["index"]

            if not _is_gap_sufficient(frame_index, current_selected_indices, min_gap):
                continue

            distribution_score = _calculate_distribution_score(
                frame_index, len(frames), current_selected_indices, min_gap, distribution_weight
            )
            sharpness_score = frame.get("sharpnessScore", 0)

            composite_score = (
                (sharpness_score * sharpness_weight) +
                (distribution_score * distribution_weight)
            )

            if composite_score > best_composite_score:
                best_composite_score = composite_score
                best_candidate = frame

        if best_candidate:
            selected_frames.append(best_candidate)
            current_selected_indices.add(best_candidate["index"])
            progress_bar.update(1)
        else:
            break # No more valid frames could be found in this pass

def select_best_n_frames(frames: List[Dict[str, Any]], num_frames: int, min_buffer: int,
                         sharpness_weight: float, distribution_weight: float) -> List[Dict[str, Any]]:
    """Select the best N frames based on sharpness and distribution."""
    if not frames:
        return []

    n = min(num_frames, len(frames))
    min_gap = min_buffer

    with tqdm(total=n, desc="Selecting frames (best-n)") as progress_bar:
        selected_frames, selected_indices = _select_initial_segments(
            frames, n, min_gap, progress_bar
        )

        if len(selected_frames) < n:
            _fill_remaining_slots(
                frames, n, min_gap, selected_frames, selected_indices, progress_bar,
                sharpness_weight, distribution_weight
            )

    progress_bar.n = len(selected_frames)
    return sorted(selected_frames, key=lambda f: f["index"])

# === Batched Selection ===

def select_batched_frames(frames: List[Dict[str, Any]], batch_size: int, batch_buffer: int) -> List[Dict[str, Any]]:
    """Select frames using batch selection method"""
    if not frames or batch_size <= 0:
        return []

    selected_frames = []
    step_size = batch_size + batch_buffer
    total_batches = (len(frames) + step_size - 1) // step_size if step_size > 0 else 0

    with tqdm(total=total_batches, desc="Selecting batches") as progress_bar:
        i = 0
        while i < len(frames):
            batch = frames[i : i + batch_size]
            if not batch:
                break

            best_frame = max(batch, key=lambda f: f.get("sharpnessScore", 0))
            selected_frames.append(best_frame)

            i += step_size
            progress_bar.update(1)

    print(f"Batch selection: Selected {len(selected_frames)} frames")
    return selected_frames

# === Outlier Removal Selection ===

def _is_frame_outlier(index: int, frames: List[Dict[str, Any]],
                        global_range: float, sensitivity: int,
                        window_size: int, min_neighbors: int, threshold_divisor: float) -> bool:
    """Determine if a frame at a given index is an outlier based on its neighbors."""
    if sensitivity <= 0:
         return False # Sensitivity 0 means nothing is an outlier
    if sensitivity >= 100:
         return True # Sensitivity 100 means everything potentially is (handled by caller range check)

    # Ensure window size is odd for symmetry, adjust if even
    actual_window_size = window_size if window_size % 2 != 0 else window_size + 1
    half_window = actual_window_size // 2

    window_start = max(0, index - half_window)
    window_end = min(len(frames), index + half_window + 1)

    neighbor_indices = list(range(window_start, index)) + list(range(index + 1, window_end))

    if len(neighbor_indices) < min_neighbors:
        return False

    neighbor_scores = [frames[idx].get("sharpnessScore", 0) for idx in neighbor_indices]
    window_avg = sum(neighbor_scores) / len(neighbor_scores)
    current_score = frames[index].get("sharpnessScore", 0)

    if global_range == 0:
        return False

    absolute_diff = window_avg - current_score
    percent_of_range = (absolute_diff / global_range) * 100 if global_range > 0 else 0

    # Sensitivity 0 = threshold 25, 50 = threshold 12.5, 100 = threshold 0
    threshold = (100 - sensitivity) / threshold_divisor

    is_outlier = (current_score < window_avg and percent_of_range > threshold)
    return is_outlier

def select_outlier_removal_frames(frames: List[Dict[str, Any]], window_size: int, sensitivity: int,
                                  min_neighbors: int, threshold_divisor: float) -> List[Dict[str, Any]]:
    """Flags frames considered outliers based on local sharpness comparison."""
    if not frames:
        return []

    # Create a list of frame data including the 'selected' flag
    result_frames = [frame.copy() for frame in frames]
    for frame_data in result_frames:
        frame_data["selected"] = True # Start with all selected

    all_scores = [frame.get("sharpnessScore", 0) for frame in frames]
    if not all_scores: return []

    global_min = min(all_scores)
    global_max = max(all_scores)
    global_range = global_max - global_min

    if global_range == 0 or sensitivity >= 100 or sensitivity <= 0:
         if sensitivity >= 100: print("Outlier sensitivity >= 100, selecting all frames.")
         elif sensitivity <= 0: print("Outlier sensitivity <= 0, selecting all frames.")
         else: print("All frames have identical scores, skipping outlier analysis.")
         return result_frames # Return all frames marked as selected

    num_outliers = 0
    with tqdm(total=len(frames), desc="Analyzing for outliers") as progress_bar:
        for i in range(len(frames)):
            if _is_frame_outlier(i, frames, global_range, sensitivity,
                                window_size, min_neighbors, threshold_divisor):
                result_frames[i]["selected"] = False
                num_outliers += 1
            progress_bar.update(1)

    selected_count = len(frames) - num_outliers
    print(f"Outlier removal: Marked {num_outliers} outliers. Keeping {selected_count} frames.")

    # Return the list containing *all* original frames, each with its 'selected' status
    # The caller will filter based on this status.
    return result_frames 