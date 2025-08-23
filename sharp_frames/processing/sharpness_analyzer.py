"""
Sharpness analysis component for Sharp Frames.
"""

import cv2
import concurrent.futures
from multiprocessing import cpu_count
from typing import List, Callable, Optional
from tqdm import tqdm

from ..models.frame_data import FrameData, ExtractionResult


class ImageProcessingError(Exception):
    """Custom exception for image processing errors."""
    pass


class SharpnessAnalyzer:
    """Calculates sharpness scores for frames using parallel processing."""
    
    def __init__(self, max_workers: Optional[int] = None):
        """
        Initialize SharpnessAnalyzer.
        
        Args:
            max_workers: Maximum number of worker threads. If None, uses cpu_count().
        """
        self.max_workers = max_workers or cpu_count()
        
    def calculate_sharpness(self, extraction_result: ExtractionResult) -> ExtractionResult:
        """
        Add sharpness scores to frame data, preserving all metadata.
        
        Args:
            extraction_result: Result from frame extraction phase
            
        Returns:
            Updated ExtractionResult with sharpness scores
        """
        if not extraction_result.frames:
            return extraction_result
        
        # Extract frame paths for parallel processing
        frame_paths = [frame.path for frame in extraction_result.frames]
        
        # Calculate sharpness scores in parallel
        sharpness_scores = self._calculate_sharpness_parallel(
            frame_paths, 
            progress_callback=self._create_progress_callback(extraction_result.input_type)
        )
        
        # Update frame data with sharpness scores
        updated_frames = []
        for frame, score in zip(extraction_result.frames, sharpness_scores):
            updated_frame = self._update_frame_with_sharpness(frame, score)
            updated_frames.append(updated_frame)
        
        # Create updated extraction result
        return ExtractionResult(
            frames=updated_frames,
            metadata=extraction_result.metadata,
            temp_dir=extraction_result.temp_dir,
            input_type=extraction_result.input_type
        )
    
    def _calculate_sharpness_parallel(self, frame_paths: List[str], 
                                     progress_callback: Optional[Callable] = None,
                                     chunk_size: int = 100) -> List[float]:
        """
        Calculate sharpness scores for multiple frames using parallel processing.
        
        Args:
            frame_paths: List of frame file paths
            progress_callback: Optional callback for progress updates
            chunk_size: Size of processing chunks for memory efficiency
            
        Returns:
            List of sharpness scores corresponding to frame_paths
        """
        scores = []
        total_frames = len(frame_paths)
        
        # Process in chunks for memory efficiency with large datasets
        for chunk_start in range(0, total_frames, chunk_size):
            chunk_end = min(chunk_start + chunk_size, total_frames)
            chunk_paths = frame_paths[chunk_start:chunk_end]
            
            chunk_scores = self._process_chunk_parallel(chunk_paths, progress_callback)
            scores.extend(chunk_scores)
        
        return scores
    
    def _process_chunk_parallel(self, frame_paths: List[str], 
                               progress_callback: Optional[Callable] = None) -> List[float]:
        """Process a chunk of frames in parallel."""
        scores = [0.0] * len(frame_paths)  # Initialize with default scores
        num_workers = min(self.max_workers, len(frame_paths)) if frame_paths else 1
        
        futures = {}
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
                # Submit tasks
                for idx, path in enumerate(frame_paths):
                    future = executor.submit(self._calculate_single_frame_sharpness, path)
                    futures[future] = {"index": idx, "path": path}
                
                # Process completed futures
                for future in concurrent.futures.as_completed(futures):
                    task_info = futures[future]
                    idx = task_info["index"]
                    path = task_info["path"]
                    
                    try:
                        score = future.result()
                        scores[idx] = score
                        
                        if progress_callback:
                            progress_callback(1, len(frame_paths))
                            
                    except Exception as e:
                        print(f"Warning: Failed to process {path}: {e}")
                        scores[idx] = 0.0  # Use default score for failed frames
                        
                        if progress_callback:
                            progress_callback(1, len(frame_paths))
        
        except Exception as e:
            print(f"Error in parallel processing: {e}")
            # Return zeros for all frames on complete failure
            return [0.0] * len(frame_paths)
        
        return scores
    
    def _calculate_single_frame_sharpness(self, frame_path: str) -> float:
        """
        Calculate sharpness score for a single frame using Laplacian variance.
        
        Args:
            frame_path: Path to the frame image file
            
        Returns:
            Sharpness score (Laplacian variance)
            
        Raises:
            ImageProcessingError: If frame processing fails
        """
        try:
            # Read image in grayscale
            img_gray = cv2.imread(frame_path, cv2.IMREAD_GRAYSCALE)
            if img_gray is None:
                raise ImageProcessingError(f"Failed to read image: {frame_path}")
            
            # Calculate Laplacian variance on resized image for efficiency
            height, width = img_gray.shape
            img_half = cv2.resize(img_gray, (width // 2, height // 2), interpolation=cv2.INTER_AREA)
            
            score = self._calculate_laplacian_variance(img_half)
            return float(score)
            
        except cv2.error as e:
            raise ImageProcessingError(f"OpenCV error processing {frame_path}: {str(e)}") from e
        except Exception as e:
            raise ImageProcessingError(f"Error processing {frame_path}: {str(e)}") from e
    
    def _calculate_laplacian_variance(self, image) -> float:
        """
        Calculate Laplacian variance for sharpness measurement.
        
        Args:
            image: Grayscale image array
            
        Returns:
            Laplacian variance (sharpness score)
        """
        laplacian = cv2.Laplacian(image, cv2.CV_64F)
        return float(laplacian.var())
    
    def _update_frame_with_sharpness(self, frame: FrameData, sharpness_score: float) -> FrameData:
        """
        Create updated FrameData with sharpness score.
        
        Args:
            frame: Original frame data
            sharpness_score: Calculated sharpness score
            
        Returns:
            New FrameData with updated sharpness score
        """
        return FrameData(
            path=frame.path,
            index=frame.index,
            sharpness_score=sharpness_score,
            source_video=frame.source_video,
            source_index=frame.source_index,
            output_name=frame.output_name
        )
    
    def _create_progress_callback(self, input_type: str) -> Callable:
        """Create progress callback with appropriate description."""
        desc = "Calculating sharpness for frames" if input_type in ["video", "video_directory"] else "Calculating sharpness for images"
        
        # Use closure to maintain progress bar state
        progress_state = {"progress_bar": None, "completed": 0}
        
        def progress_callback(increment: int, total: int):
            # Initialize progress bar on first call
            if progress_state["progress_bar"] is None:
                progress_state["progress_bar"] = tqdm(total=total, desc=desc)
            
            # Update progress
            progress_state["progress_bar"].update(increment)
            progress_state["completed"] += increment
            
            # Close progress bar when complete
            if progress_state["completed"] >= total:
                progress_state["progress_bar"].close()
        
        return progress_callback
    
    def _progress_callback(self, current: int, total: int):
        """Default progress callback - can be overridden for custom progress tracking."""
        pass