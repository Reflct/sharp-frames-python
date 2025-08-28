"""
Sharpness analysis component for Sharp Frames.
"""

import cv2
import concurrent.futures
import os
import sys
import time
import threading
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
        self._is_windows = os.name == 'nt' or sys.platform.startswith('win')
        self._cancellation_event = threading.Event()
        
        # Windows-specific settings
        if self._is_windows:
            # Reduce thread count on Windows to avoid thread pool issues
            self.max_workers = min(self.max_workers, 4)
            # Add timeouts for Windows operations
            self._operation_timeout = 300  # 5 minutes
            self._progress_timeout = 30    # 30 seconds
    
    def cancel_processing(self):
        """Cancel ongoing sharpness analysis."""
        self._cancellation_event.set()
        
    def calculate_sharpness(self, extraction_result: ExtractionResult, progress_callback=None) -> ExtractionResult:
        """
        Add sharpness scores to frame data, preserving all metadata.
        
        Args:
            extraction_result: Result from frame extraction phase
            progress_callback: Optional callback for progress updates
            
        Returns:
            Updated ExtractionResult with sharpness scores
        """
        if not extraction_result.frames:
            return extraction_result
        
        # Extract frame paths for parallel processing
        frame_paths = [frame.path for frame in extraction_result.frames]
        
        # Report sharpness analysis starting
        if progress_callback:
            desc = "Calculating sharpness for frames" if extraction_result.input_type in ["video", "video_directory"] else "Calculating sharpness for images"
            progress_callback("sharpness", 0, len(frame_paths), desc)
        
        # Use provided callback or create default one for tqdm fallback
        callback = progress_callback or self._create_progress_callback(extraction_result.input_type)
        
        # Calculate sharpness scores in parallel
        sharpness_scores = self._calculate_sharpness_parallel(
            frame_paths, 
            progress_callback=callback
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
        processed_count = 0
        
        # Process in chunks for memory efficiency with large datasets
        for chunk_start in range(0, total_frames, chunk_size):
            chunk_end = min(chunk_start + chunk_size, total_frames)
            chunk_paths = frame_paths[chunk_start:chunk_end]
            
            # Create chunk-aware progress callback that tracks overall progress
            def chunk_progress_callback(phase, chunk_completed, chunk_total, description):
                if progress_callback:
                    overall_completed = processed_count + chunk_completed
                    progress_callback(phase, overall_completed, total_frames, description)
            
            chunk_scores = self._process_chunk_parallel(chunk_paths, chunk_progress_callback)
            scores.extend(chunk_scores)
            processed_count += len(chunk_paths)
        
        return scores
    
    def _process_chunk_parallel(self, frame_paths: List[str], 
                               progress_callback: Optional[Callable] = None) -> List[float]:
        """Process a chunk of frames in parallel with Windows-specific error handling."""
        scores = [0.0] * len(frame_paths)  # Initialize with default scores
        num_workers = min(self.max_workers, len(frame_paths)) if frame_paths else 1
        
        # Track progress across the chunk
        completed_count = 0
        total_frames = len(frame_paths)
        
        futures = {}
        try:
            # Windows-specific executor configuration
            executor_kwargs = {'max_workers': num_workers}
            if self._is_windows:
                # Use context manager with explicit timeout on Windows
                executor_kwargs.update({
                    'thread_name_prefix': 'SharpFrames_',
                })
            
            with concurrent.futures.ThreadPoolExecutor(**executor_kwargs) as executor:
                # Submit tasks
                for idx, path in enumerate(frame_paths):
                    # Check for cancellation before submitting
                    if self._cancellation_event.is_set():
                        print("Sharpness analysis cancelled")
                        return scores
                        
                    future = executor.submit(self._calculate_single_frame_sharpness, path)
                    futures[future] = {"index": idx, "path": path}
                
                # Process completed futures with timeout on Windows
                timeout = self._operation_timeout if self._is_windows else None
                
                try:
                    for future in concurrent.futures.as_completed(futures, timeout=timeout):
                        # Check for cancellation
                        if self._cancellation_event.is_set():
                            print("Sharpness analysis cancelled")
                            # Cancel remaining futures
                            for remaining_future in futures:
                                remaining_future.cancel()
                            return scores
                            
                        task_info = futures[future]
                        idx = task_info["index"]
                        path = task_info["path"]
                        
                        try:
                            # Add timeout for individual result retrieval on Windows
                            result_timeout = 10 if self._is_windows else None
                            score = future.result(timeout=result_timeout)
                            scores[idx] = score
                            
                        except concurrent.futures.TimeoutError:
                            print(f"Warning: Timeout processing {path}")
                            scores[idx] = 0.0
                        except Exception as e:
                            print(f"Warning: Failed to process {path}: {e}")
                            scores[idx] = 0.0  # Use default score for failed frames
                        
                        # Update progress after each frame with timeout protection
                        completed_count += 1
                        if progress_callback:
                            try:
                                progress_callback("sharpness", completed_count, total_frames, 
                                                f"Analyzed {completed_count}/{total_frames} frames")
                            except Exception as e:
                                print(f"Warning: Progress callback failed: {e}")
                                
                except concurrent.futures.TimeoutError:
                    print(f"Warning: Overall processing timeout after {timeout} seconds")
                    # Cancel remaining futures and return partial results
                    for future in futures:
                        future.cancel()
        
        except Exception as e:
            error_msg = f"Error in parallel processing: {e}"
            print(error_msg)
            
            # On Windows, try fallback to sequential processing for small datasets
            if self._is_windows and len(frame_paths) <= 10:
                print("Attempting fallback to sequential processing on Windows...")
                return self._process_chunk_sequential(frame_paths, progress_callback)
            # Return zeros for all frames on complete failure
            return [0.0] * len(frame_paths)
        
        return scores
    
    def _process_chunk_sequential(self, frame_paths: List[str], 
                                 progress_callback: Optional[Callable] = None) -> List[float]:
        """Fallback sequential processing for Windows when threading fails."""
        scores = []
        total_frames = len(frame_paths)
        
        for idx, path in enumerate(frame_paths):
            if self._cancellation_event.is_set():
                print("Sequential processing cancelled")
                break
                
            try:
                score = self._calculate_single_frame_sharpness(path)
                scores.append(score)
            except Exception as e:
                print(f"Warning: Failed to process {path}: {e}")
                scores.append(0.0)
            
            # Update progress
            if progress_callback:
                try:
                    progress_callback("sharpness", idx + 1, total_frames, 
                                    f"Analyzed {idx + 1}/{total_frames} frames (sequential)")
                except Exception as e:
                    print(f"Warning: Progress callback failed: {e}")
        
        # Pad with zeros if processing was cancelled early
        while len(scores) < total_frames:
            scores.append(0.0)
            
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
            # Check for cancellation
            if self._cancellation_event.is_set():
                return 0.0
                
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