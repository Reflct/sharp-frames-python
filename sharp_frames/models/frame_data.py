"""
Data structures for frame information and processing results.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional


@dataclass
class FrameData:
    """Immutable data structure for frame information."""
    path: str
    index: int  # Global index across all frames
    sharpness_score: float
    source_video: Optional[str] = None  # e.g., "video_001"
    source_index: Optional[int] = None  # Index within that video
    output_name: Optional[str] = None  # For preserving naming
    
    def __post_init__(self):
        """Validate frame data after initialization."""
        if self.index < 0:
            raise ValueError("Frame index must be non-negative")
        if self.sharpness_score < 0:
            raise ValueError("Sharpness score must be non-negative")


@dataclass
class ExtractionResult:
    """Result of frame extraction/loading phase."""
    frames: List[FrameData]
    metadata: Dict[str, Any]  # fps, duration, source_type, etc.
    temp_dir: Optional[str] = None  # For cleanup
    input_type: str = "video"  # video, directory, video_directory
    
    def __post_init__(self):
        """Validate extraction result after initialization."""
        if not isinstance(self.frames, list):
            raise TypeError("frames must be a list")
        if not isinstance(self.metadata, dict):
            raise TypeError("metadata must be a dictionary")
        if self.input_type not in ["video", "directory", "video_directory"]:
            raise ValueError(f"Invalid input_type: {self.input_type}")
    
    @property
    def total_frames(self) -> int:
        """Get total number of frames."""
        return len(self.frames)
    
    @property
    def average_sharpness(self) -> float:
        """Calculate average sharpness score across all frames."""
        if not self.frames:
            return 0.0
        return sum(frame.sharpness_score for frame in self.frames) / len(self.frames)
    
    @property
    def sharpness_range(self) -> tuple:
        """Get min and max sharpness scores."""
        if not self.frames:
            return (0.0, 0.0)
        scores = [frame.sharpness_score for frame in self.frames]
        return (min(scores), max(scores))