"""
Frame selection component for Sharp Frames.
"""

from typing import List, Dict, Any, Set, Tuple
from tqdm import tqdm
from contextlib import nullcontext

from ..models.frame_data import FrameData


class FrameSelector:
    """Handles frame selection logic with preview capabilities."""
    
    def __init__(self, show_progress: bool = True):
        """
        Initialize FrameSelector.
        
        Args:
            show_progress: Whether to show progress bars (should be False when running in threads)
        """
        self.show_progress = show_progress
        
        # Constants for best-n selection
        self.BEST_N_SHARPNESS_WEIGHT = 0.7
        self.BEST_N_DISTRIBUTION_WEIGHT = 0.3
        
        # Constants for outlier removal
        self.OUTLIER_MIN_NEIGHBORS = 3
        self.OUTLIER_THRESHOLD_DIVISOR = 4
    
    def _get_progress_bar(self, total: int, desc: str):
        """Get a progress bar or null context based on show_progress setting."""
        if self.show_progress:
            return tqdm(total=total, desc=desc, leave=False)
        else:
            return nullcontext()
    
    def _update_progress(self, progress_bar, n=1):
        """Update progress bar if it exists."""
        if progress_bar and hasattr(progress_bar, 'update'):
            progress_bar.update(n)
    
    def preview_selection(self, frames: List[FrameData], method: str, **params) -> int:
        """
        Calculate selection count without modifying data.
        Optimized for speed to enable real-time preview updates.
        
        Args:
            frames: List of FrameData objects
            method: Selection method ('best_n', 'batched', 'outlier_removal')
            **params: Method-specific parameters
            
        Returns:
            Number of frames that would be selected
        """
        if not frames:
            return 0
        
        if method == 'best_n':
            n = params.get('n', 300)
            min_buffer = params.get('min_buffer', 3)
            
            # With min_buffer constraint, we might not be able to select all n frames
            # Quick estimate: if frames are perfectly spaced, we need n + (n-1)*min_buffer positions
            if min_buffer > 0:
                required_positions = n + (n - 1) * min_buffer
                if required_positions > len(frames):
                    # Calculate maximum possible frames with this buffer
                    max_possible = (len(frames) + min_buffer) // (min_buffer + 1)
                    return min(n, max_possible)
            
            return min(n, len(frames))
        
        elif method == 'batched':
            batch_size = params.get('batch_size', 5)
            batch_buffer = params.get('batch_buffer', 2)
            
            # Calculate how many batches we can create with the given parameters
            step_size = batch_size + batch_buffer
            if step_size <= 0:
                return 0
            return (len(frames) + step_size - 1) // step_size if step_size > 0 else 0
        
        elif method == 'outlier_removal':
            outlier_sensitivity = params.get('outlier_sensitivity', 50)
            outlier_window_size = params.get('outlier_window_size', 15)
            
            # Fast preview calculation for outlier removal
            return self._preview_outlier_removal_count(frames, outlier_sensitivity, outlier_window_size)
        
        else:
            raise ValueError(f"Unsupported selection method: {method}")
    
    def select_frames(self, frames: List[FrameData], method: str, **params) -> List[FrameData]:
        """
        Apply selection method and return selected frames.
        
        Args:
            frames: List of FrameData objects  
            method: Selection method ('best_n', 'batched', 'outlier_removal')
            **params: Method-specific parameters
            
        Returns:
            List of selected FrameData objects
        """
        with open("debug_save.log", "a") as f:
            f.write(f"FrameSelector.select_frames called\n")
            f.write(f"  method: {method}\n")
            f.write(f"  params: {params}\n")
            f.write(f"  frames count: {len(frames)}\n")
        
        if not frames:
            with open("debug_save.log", "a") as f:
                f.write("  No frames provided, returning empty list\n")
            return []
        
        if method == 'best_n':
            n = params.get('n', 300)
            min_buffer = params.get('min_buffer', 3)
            with open("debug_save.log", "a") as f:
                f.write(f"  Using best_n method: n={n}, min_buffer={min_buffer}\n")
            result = self._select_best_n_frames(frames, n, min_buffer)
            
        elif method == 'batched':
            batch_size = params.get('batch_size', 5)
            batch_buffer = params.get('batch_buffer', 2)
            with open("debug_save.log", "a") as f:
                f.write(f"  Using batched method: batch_size={batch_size}, batch_buffer={batch_buffer}\n")
            result = self._select_batched_frames(frames, batch_size, batch_buffer)
        
        elif method == 'outlier_removal':
            outlier_sensitivity = params.get('outlier_sensitivity', 50)
            outlier_window_size = params.get('outlier_window_size', 15)
            with open("debug_save.log", "a") as f:
                f.write(f"  Using outlier_removal method: sensitivity={outlier_sensitivity}, window_size={outlier_window_size}\n")
            result = self._select_outlier_removal_frames(frames, outlier_sensitivity, outlier_window_size)
            
        else:
            with open("debug_save.log", "a") as f:
                f.write(f"  ERROR: Unsupported selection method: {method}\n")
            raise ValueError(f"Unsupported selection method: {method}")
        
        with open("debug_save.log", "a") as f:
            f.write(f"  FrameSelector.select_frames returning {len(result)} frames\n")
        
        return result
    
    def _select_best_n_frames(self, frames: List[FrameData], n: int, min_buffer: int) -> List[FrameData]:
        """Select the best N frames based on weighted scoring combining sharpness and distribution."""
        if n <= 0:
            return []
        
        n = min(n, len(frames))
        min_gap = min_buffer
        
        # Convert to dict format for compatibility with existing algorithm
        frames_dict = self._frames_to_dict(frames)
        
        # Calculate weighted scores for all frames
        weighted_scores = self._calculate_weighted_scores(frames_dict)
        
        # Apply the best-n selection algorithm
        selected_frames = []
        selected_indices = set()
        
        with self._get_progress_bar(n, "Selecting frames (best-n)") as progress_bar:
            # Initial segment selection
            selected_frames, selected_indices = self._select_initial_segments(
                frames_dict, weighted_scores, n, min_gap, progress_bar
            )
            
            # Fill remaining slots if needed
            if len(selected_frames) < n:
                self._fill_remaining_slots(
                    frames_dict, weighted_scores, n, min_gap, selected_frames, 
                    selected_indices, progress_bar
                )
        
        # Convert back to FrameData objects
        selected_frame_data = []
        for frame_dict in selected_frames:
            original_frame = frames[frame_dict['index']]
            selected_frame_data.append(original_frame)
        
        # Sort by index to maintain frame order
        return sorted(selected_frame_data, key=lambda f: f.index)
    
    def _select_batched_frames(self, frames: List[FrameData], batch_size: int, batch_buffer: int) -> List[FrameData]:
        """Select frames using legacy batched method - process consecutive groups with gaps."""
        if batch_size <= 0 or not frames:
            return []
        
        selected_frames = []
        step_size = batch_size + batch_buffer
        total_batches = (len(frames) + step_size - 1) // step_size if step_size > 0 else 0
        
        with self._get_progress_bar(total_batches, "Selecting batches") as progress_bar:
            i = 0
            while i < len(frames):
                # Take a batch of consecutive frames
                batch = frames[i:i + batch_size]
                if not batch:
                    break
                
                # Select frame with highest sharpness in this batch
                best_frame = max(batch, key=lambda f: f.sharpness_score)
                selected_frames.append(best_frame)
                
                # Move to next batch position (skip batch_buffer frames)
                i += step_size
                self._update_progress(progress_bar)
        
        return selected_frames
    
    def _select_outlier_removal_frames(self, frames: List[FrameData], outlier_sensitivity: int, outlier_window_size: int) -> List[FrameData]:
        """Select frames by removing outliers using legacy parameters."""
        if not frames:
            return []
        
        selected_frames = []
        all_scores = [frame.sharpness_score for frame in frames]
        
        if not all_scores:
            return frames
        
        global_min = min(all_scores)
        global_max = max(all_scores)
        global_range = global_max - global_min
        
        with self._get_progress_bar(len(frames), "Filtering outliers") as progress_bar:
            for i, frame in enumerate(frames):
                is_outlier = self._is_frame_outlier(
                    i, frames, global_range, outlier_sensitivity, outlier_window_size
                )
                
                if not is_outlier:
                    selected_frames.append(frame)
                
                self._update_progress(progress_bar)
        
        return selected_frames
    
    def _preview_outlier_removal_count(self, frames: List[FrameData], outlier_sensitivity: int, outlier_window_size: int) -> int:
        """Fast preview calculation for outlier removal using legacy parameters."""
        if not frames:
            return 0
        
        # Use more granular heuristic for responsive preview
        # Estimate based on sensitivity: higher sensitivity = more aggressive removal
        # Linear interpolation for smoother changes
        if outlier_sensitivity >= 90:
            removal_rate = 0.40  # Remove ~40% of frames
        elif outlier_sensitivity >= 80:
            removal_rate = 0.30  # Remove ~30% of frames
        elif outlier_sensitivity >= 70:
            removal_rate = 0.25  # Remove ~25% of frames
        elif outlier_sensitivity >= 60:
            removal_rate = 0.20  # Remove ~20% of frames
        elif outlier_sensitivity >= 50:
            removal_rate = 0.15  # Remove ~15% of frames
        elif outlier_sensitivity >= 40:
            removal_rate = 0.10  # Remove ~10% of frames
        elif outlier_sensitivity >= 30:
            removal_rate = 0.07  # Remove ~7% of frames
        elif outlier_sensitivity >= 20:
            removal_rate = 0.05  # Remove ~5% of frames
        elif outlier_sensitivity >= 10:
            removal_rate = 0.03  # Remove ~3% of frames
        else:
            removal_rate = 0.01  # Remove ~1% of frames
        
        estimated_selected = int(len(frames) * (1.0 - removal_rate))
        return max(1, estimated_selected)  # Always select at least 1 frame
    
    def _calculate_weighted_scores(self, frames_dict: List[Dict[str, Any]]) -> List[float]:
        """Calculate weighted scores combining sharpness and distribution."""
        weighted_scores = []
        
        for frame in frames_dict:
            sharpness_score = frame.get('sharpnessScore', 0)
            
            # For initial calculation, use only sharpness score
            # Distribution scoring is applied during selection process
            weighted_score = sharpness_score * self.BEST_N_SHARPNESS_WEIGHT
            weighted_scores.append(weighted_score)
        
        return weighted_scores
    
    def _select_initial_segments(self, frames_dict: List[Dict[str, Any]], weighted_scores: List[float],
                                n: int, min_gap: int, progress_bar) -> Tuple[List[Dict[str, Any]], Set[int]]:
        """First pass: Select best frames from initial segments."""
        selected_frames = []
        selected_indices = set()
        
        if n <= 0 or not frames_dict:
            return selected_frames, selected_indices
        
        # Sort frames by weighted score (highest first)
        sorted_frames = sorted(
            zip(frames_dict, weighted_scores),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Select frames ensuring minimum gap
        for frame_data, _ in sorted_frames:
            if len(selected_frames) >= n:
                break
            
            frame_index = frame_data['index']
            
            if self._is_gap_sufficient(frame_index, selected_indices, min_gap):
                selected_frames.append(frame_data)
                selected_indices.add(frame_index)
                self._update_progress(progress_bar)
        
        return selected_frames, selected_indices
    
    def _fill_remaining_slots(self, frames_dict: List[Dict[str, Any]], weighted_scores: List[float],
                             n: int, min_gap: int, selected_frames: List[Dict[str, Any]],
                             selected_indices: Set[int], progress_bar: tqdm):
        """Fill remaining slots with best available frames."""
        remaining_needed = n - len(selected_frames)
        
        if remaining_needed <= 0:
            return
        
        # Create list of unselected frames with their scores
        unselected_frames = []
        for i, frame_data in enumerate(frames_dict):
            if frame_data['index'] not in selected_indices:
                unselected_frames.append((frame_data, weighted_scores[i]))
        
        # Sort by score
        unselected_frames.sort(key=lambda x: x[1], reverse=True)
        
        # Try to fill remaining slots
        for frame_data, _ in unselected_frames:
            if len(selected_frames) >= n:
                break
            
            frame_index = frame_data['index']
            
            # For remaining slots, use more lenient gap requirement
            relaxed_gap = max(1, min_gap // 2)
            if self._is_gap_sufficient(frame_index, selected_indices, relaxed_gap):
                selected_frames.append(frame_data)
                selected_indices.add(frame_index)
                self._update_progress(progress_bar)
    
    def _is_gap_sufficient(self, frame_index: int, selected_indices: Set[int], min_gap: int) -> bool:
        """Check if a frame index maintains the minimum gap with selected indices."""
        if not selected_indices:
            return True
        
        return all(abs(frame_index - selected_index) >= min_gap 
                  for selected_index in selected_indices)
    
    def _is_frame_outlier(self, index: int, frames: List[FrameData], 
                         global_range: float, sensitivity: int, window_size: int) -> bool:
        """Determine if a frame is an outlier based on its neighbors."""
        if sensitivity <= 0:
            return False
        if sensitivity >= 100:
            return True
        
        # Ensure window size is odd for symmetry
        actual_window_size = window_size if window_size % 2 != 0 else window_size + 1
        half_window = actual_window_size // 2
        
        window_start = max(0, index - half_window)
        window_end = min(len(frames), index + half_window + 1)
        
        neighbor_indices = list(range(window_start, index)) + list(range(index + 1, window_end))
        
        if len(neighbor_indices) < self.OUTLIER_MIN_NEIGHBORS:
            return False
        
        neighbor_scores = [frames[idx].sharpness_score for idx in neighbor_indices]
        window_avg = sum(neighbor_scores) / len(neighbor_scores)
        current_score = frames[index].sharpness_score
        
        if global_range == 0:
            return False
        
        absolute_diff = window_avg - current_score
        percent_of_range = (absolute_diff / global_range) * 100 if global_range > 0 else 0
        
        # Calculate threshold based on sensitivity
        threshold = (100 - sensitivity) / self.OUTLIER_THRESHOLD_DIVISOR
        
        return current_score < window_avg and percent_of_range > threshold
    
    def _frames_to_dict(self, frames: List[FrameData]) -> List[Dict[str, Any]]:
        """Convert FrameData objects to dictionary format for algorithm compatibility."""
        frames_dict = []
        for frame in frames:
            frame_dict = {
                'id': f"frame_{frame.index:05d}",
                'path': frame.path,
                'index': frame.index,
                'sharpnessScore': frame.sharpness_score
            }
            frames_dict.append(frame_dict)
        return frames_dict