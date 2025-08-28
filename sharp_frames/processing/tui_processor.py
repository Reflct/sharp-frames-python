"""
TUI processor orchestrator for Sharp Frames two-phase processing.
"""

import shutil
from typing import Dict, Any, Optional

from ..models.frame_data import ExtractionResult
from .frame_extractor import FrameExtractor
from .sharpness_analyzer import SharpnessAnalyzer
from .frame_selector import FrameSelector
from .frame_saver import FrameSaver


class TUIProcessor:
    """Orchestrates components for two-phase TUI processing."""
    
    def __init__(self):
        """Initialize TUIProcessor with all required components."""
        self.extractor = FrameExtractor()
        self.analyzer = SharpnessAnalyzer()
        self.selector = FrameSelector(show_progress=False)  # Disable progress bars for thread safety
        self.saver = FrameSaver(show_progress=False)  # Disable progress bars for thread safety
        self.current_result: Optional[ExtractionResult] = None
    
    def extract_and_analyze(self, config: Dict[str, Any], progress_callback=None) -> ExtractionResult:
        """
        Phase 1: Extract and analyze frames.
        
        Args:
            config: Configuration dictionary containing input settings
            progress_callback: Optional callback for progress updates (phase, current, total, description)
            
        Returns:
            ExtractionResult with frames and sharpness scores
            
        Raises:
            Exception: If extraction or analysis fails
        """
        try:
            print(f"Phase 1: Extracting and analyzing frames from {config['input_type']}...")
            
            # Report extraction starting
            if progress_callback:
                progress_callback("extraction", 0, 100, "Starting frame extraction...")
            
            # Extract frames
            print("Extracting frames...")
            extraction_result = self.extractor.extract_frames(config, progress_callback)
            
            if not extraction_result.frames:
                print("No frames were extracted.")
                self.current_result = extraction_result
                return extraction_result
            
            print(f"Extracted {len(extraction_result.frames)} frames")
            
            # Report analysis starting
            if progress_callback:
                progress_callback("analysis", 0, len(extraction_result.frames), "Starting sharpness analysis...")
            
            # Calculate sharpness scores
            print("Analyzing frame sharpness...")
            analyzed_result = self.analyzer.calculate_sharpness(extraction_result, progress_callback)
            
            print(f"Analysis complete. Average sharpness: {analyzed_result.average_sharpness:.2f}")
            print(f"Sharpness range: {analyzed_result.sharpness_range[0]:.2f} - {analyzed_result.sharpness_range[1]:.2f}")
            
            # Store result for selection phase
            self.current_result = analyzed_result
            return analyzed_result
            
        except Exception as e:
            print(f"Error during extraction and analysis: {e}")
            # Clean up any temp directories on failure
            if hasattr(self, 'current_result') and self.current_result and self.current_result.temp_dir:
                self.cleanup_temp_directory()
            raise e
    
    def preview_selection(self, method: str, **params) -> int:
        """
        Preview selection without modifying state.
        
        Args:
            method: Selection method ('best_n', 'batched', 'outlier_removal')
            **params: Method-specific parameters
            
        Returns:
            Number of frames that would be selected
            
        Raises:
            RuntimeError: If no extraction result is available
        """
        if not self.current_result:
            raise RuntimeError("No extraction result available. Run extract_and_analyze() first.")
        
        return self.selector.preview_selection(self.current_result.frames, method, **params)
    
    def complete_selection(self, method: str, config: Dict[str, Any], **params) -> bool:
        """
        Phase 2: Select and save frames.
        
        Args:
            method: Selection method ('best_n', 'batched', 'outlier_removal')
            config: Configuration dictionary containing output settings
            **params: Method-specific parameters
            
        Returns:
            True if selection and saving succeeded, False otherwise
            
        Raises:
            RuntimeError: If no extraction result is available
        """
        if not self.current_result:
            raise RuntimeError("No extraction result available. Run extract_and_analyze() first.")
        
        try:
            print(f"Phase 2: Selecting and saving frames using {method} method...")
            
            # Select frames
            selected_frames = self.selector.select_frames(self.current_result.frames, method, **params)
            
            if not selected_frames:
                print("No frames were selected based on the criteria.")
                return False
            
            print(f"Selected {len(selected_frames)} frames")
            
            # Add method information to config for metadata
            selection_config = config.copy()
            selection_config['selection_method'] = method
            selection_config.update(params)
            
            # Save frames
            success = self.saver.save_frames(selected_frames, selection_config)
            
            if success:
                print("Selection and saving completed successfully.")
                # Clean up temp directory after successful save
                self.cleanup_temp_directory()
            else:
                print("Some frames failed to save.")
            
            return success
            
        except Exception as e:
            print(f"Error during selection and saving: {e}")
            return False
    
    def get_current_frame_count(self) -> int:
        """Get the number of frames in current extraction result."""
        if self.current_result:
            return len(self.current_result.frames)
        return 0
    
    def get_current_metadata(self) -> Dict[str, Any]:
        """Get metadata from current extraction result."""
        if self.current_result:
            return self.current_result.metadata.copy()
        return {}
    
    def get_current_input_type(self) -> Optional[str]:
        """Get input type from current extraction result."""
        if self.current_result:
            return self.current_result.input_type
        return None
    
    def get_sharpness_statistics(self) -> Dict[str, float]:
        """Get sharpness statistics for current frames."""
        if not self.current_result or not self.current_result.frames:
            return {}
        
        scores = [frame.sharpness_score for frame in self.current_result.frames]
        return {
            'min': min(scores),
            'max': max(scores),
            'average': sum(scores) / len(scores),
            'count': len(scores)
        }
    
    def get_video_distribution(self) -> Dict[str, int]:
        """Get frame distribution by source video (for video directories)."""
        if not self.current_result or not self.current_result.frames:
            return {}
        
        distribution = {}
        for frame in self.current_result.frames:
            if frame.source_video:
                distribution.setdefault(frame.source_video, 0)
                distribution[frame.source_video] += 1
        
        return distribution
    
    def cleanup_temp_directory(self):
        """Clean up temporary directory if it exists."""
        if self.current_result and self.current_result.temp_dir:
            try:
                shutil.rmtree(self.current_result.temp_dir, ignore_errors=True)
                print(f"Cleaned up temporary directory: {self.current_result.temp_dir}")
                # Clear temp_dir reference to avoid double cleanup
                self.current_result.temp_dir = None
            except Exception as e:
                print(f"Warning: Failed to clean up temp directory: {e}")
    
    def reset_current_result(self):
        """Reset current result (useful for processing multiple inputs)."""
        # Clean up temp directory before reset
        self.cleanup_temp_directory()
        self.current_result = None
    
    def has_current_result(self) -> bool:
        """Check if there is a current extraction result."""
        return self.current_result is not None and len(self.current_result.frames) > 0
    
    def is_ready_for_selection(self) -> bool:
        """Check if processor is ready for frame selection."""
        return (self.current_result is not None and 
                len(self.current_result.frames) > 0 and
                all(frame.sharpness_score > 0 for frame in self.current_result.frames[:5]))  # Check first 5 frames have scores
    
    def get_processing_summary(self) -> Dict[str, Any]:
        """Get summary of current processing state."""
        if not self.current_result:
            return {'status': 'no_data'}
        
        summary = {
            'status': 'ready' if self.is_ready_for_selection() else 'processing',
            'input_type': self.current_result.input_type,
            'total_frames': len(self.current_result.frames),
            'metadata': self.current_result.metadata,
            'has_temp_dir': self.current_result.temp_dir is not None
        }
        
        # Add sharpness statistics if frames have been analyzed
        if self.current_result.frames and any(f.sharpness_score > 0 for f in self.current_result.frames):
            summary['sharpness_stats'] = self.get_sharpness_statistics()
        
        # Add video distribution for video directories
        video_dist = self.get_video_distribution()
        if video_dist:
            summary['video_distribution'] = video_dist
        
        return summary
    
    def validate_selection_parameters(self, method: str, **params) -> tuple[bool, str]:
        """
        Validate selection parameters for a given method.
        
        Args:
            method: Selection method
            **params: Method parameters
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.current_result or not self.current_result.frames:
            return False, "No frames available for selection"
        
        total_frames = len(self.current_result.frames)
        
        if method == 'best_n':
            n = params.get('n', 300)
            if not isinstance(n, int) or n <= 0:
                return False, "Parameter 'n' must be a positive integer"
            if n > total_frames:
                return False, f"Cannot select {n} frames from {total_frames} available frames"
        
        elif method == 'batched':
            batch_size = params.get('batch_size', 5)
            if not isinstance(batch_size, int) or batch_size <= 0:
                return False, "Parameter 'batch_size' must be a positive integer"
            
            batch_buffer = params.get('batch_buffer', 2)
            if not isinstance(batch_buffer, int) or batch_buffer < 0:
                return False, "Parameter 'batch_buffer' must be a non-negative integer"
        
        elif method == 'outlier_removal':
            outlier_sensitivity = params.get('outlier_sensitivity', 50)
            if not isinstance(outlier_sensitivity, int) or not (0 <= outlier_sensitivity <= 100):
                return False, "Parameter 'outlier_sensitivity' must be an integer between 0 and 100"
            
            outlier_window_size = params.get('outlier_window_size', 15)
            if not isinstance(outlier_window_size, int) or outlier_window_size <= 0:
                return False, "Parameter 'outlier_window_size' must be a positive integer"
        
        else:
            return False, f"Unknown selection method: {method}"
        
        return True, ""