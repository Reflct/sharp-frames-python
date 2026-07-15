"""Frame selection component for Sharp Frames."""

from typing import Any, Dict, List

from ..models.frame_data import FrameData
from ..selection_methods import (
    OUTLIER_DEFAULT_SENSITIVITY,
    OUTLIER_DEFAULT_WINDOW_SIZE,
    select_batched_frames_core,
    select_best_n_frames_core,
    select_outlier_removal_frames_core,
)


class FrameSelector:
    """Apply the canonical selection algorithms to :class:`FrameData` objects."""

    BEST_N_SHARPNESS_WEIGHT = 0.7
    BEST_N_DISTRIBUTION_WEIGHT = 0.3
    OUTLIER_MIN_NEIGHBORS = 3
    OUTLIER_THRESHOLD_DIVISOR = 4.0

    def __init__(self, show_progress: bool = True):
        self.show_progress = show_progress

    def preview_selection(self, frames: List[FrameData], method: str, **params: Any) -> int:
        """Return the exact count produced by selection with the supplied parameters."""
        return len(self.select_frames(frames, method, **params))

    def select_frames(
        self, frames: List[FrameData], method: str, **params: Any
    ) -> List[FrameData]:
        """Apply a public selection method while preserving original frame objects."""
        if not frames:
            return []

        if method in {"best_n", "best-n"}:
            return self._select_best_n_frames(
                frames,
                params.get("n", 300),
                params.get("min_buffer", 3),
            )
        if method == "batched":
            return self._select_batched_frames(
                frames,
                params.get("batch_size", 5),
                params.get("batch_buffer", 2),
            )
        if method in {"outlier_removal", "outlier-removal"}:
            return self._select_outlier_removal_frames(
                frames,
                params.get("outlier_sensitivity", OUTLIER_DEFAULT_SENSITIVITY),
                params.get("outlier_window_size", OUTLIER_DEFAULT_WINDOW_SIZE),
            )
        raise ValueError(f"Unsupported selection method: {method}")

    def _select_best_n_frames(
        self, frames: List[FrameData], n: int, min_buffer: int
    ) -> List[FrameData]:
        frame_dicts = self._frames_to_dict(frames)
        selected = select_best_n_frames_core(
            frame_dicts,
            n,
            min_buffer,
            self.BEST_N_SHARPNESS_WEIGHT,
            self.BEST_N_DISTRIBUTION_WEIGHT,
        )
        return self._restore_frame_objects(frames, selected)

    def _select_batched_frames(
        self, frames: List[FrameData], batch_size: int, batch_buffer: int
    ) -> List[FrameData]:
        selected = select_batched_frames_core(
            self._frames_to_dict(frames), batch_size, batch_buffer
        )
        return self._restore_frame_objects(frames, selected)

    def _select_outlier_removal_frames(
        self,
        frames: List[FrameData],
        outlier_sensitivity: int,
        outlier_window_size: int,
    ) -> List[FrameData]:
        assessed = select_outlier_removal_frames_core(
            self._frames_to_dict(frames),
            outlier_window_size,
            outlier_sensitivity,
            self.OUTLIER_MIN_NEIGHBORS,
            self.OUTLIER_THRESHOLD_DIVISOR,
        )
        selected = [frame for frame in assessed if frame["selected"]]
        return self._restore_frame_objects(frames, selected)

    @staticmethod
    def _restore_frame_objects(
        frames: List[FrameData], selected: List[Dict[str, Any]]
    ) -> List[FrameData]:
        return [frames[frame["_selection_position"]] for frame in selected]

    @staticmethod
    def _frames_to_dict(frames: List[FrameData]) -> List[Dict[str, Any]]:
        return [
            {
                "id": f"frame_{frame.index:05d}",
                "path": frame.path,
                "index": frame.index,
                "sharpnessScore": frame.sharpness_score,
                "source_video": frame.source_video,
                "source_index": frame.source_index,
                "_selection_position": position,
            }
            for position, frame in enumerate(frames)
        ]
