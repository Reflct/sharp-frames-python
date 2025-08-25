"""
Frame saving component for Sharp Frames.
"""

import os
import shutil
import json
import cv2
from typing import List, Dict, Any, Optional
from tqdm import tqdm
from contextlib import nullcontext

from ..models.frame_data import FrameData


class ImageProcessingError(Exception):
    """Custom exception for image processing errors."""
    pass


class FrameSaver:
    """Handles saving selected frames to disk with proper naming conventions."""
    
    def __init__(self, show_progress: bool = True):
        """Initialize FrameSaver.
        
        Args:
            show_progress: Whether to show progress bars (should be False when running in threads)
        """
        self.DEFAULT_OUTPUT_FORMAT = "jpg"
        self.show_progress = show_progress
    
    def _get_progress_bar(self, total: int, desc: str):
        """Get a progress bar or null context based on show_progress setting."""
        if self.show_progress:
            return tqdm(total=total, desc=desc)
        else:
            return nullcontext()
    
    def _update_progress(self, progress_bar, n=1):
        """Update progress bar if it exists."""
        if progress_bar and hasattr(progress_bar, 'update'):
            progress_bar.update(n)
    
    def save_frames(self, selected_frames: List[FrameData], config: Dict[str, Any]) -> bool:
        """
        Save frames with proper naming based on input type.
        
        Args:
            selected_frames: List of selected FrameData objects
            config: Configuration dictionary containing output settings
            
        Returns:
            True if all frames saved successfully, False otherwise
        """
        with open("debug_save.log", "a") as f:
            f.write(f"FrameSaver.save_frames called\n")
            f.write(f"  selected_frames count: {len(selected_frames)}\n")
            f.write(f"  config: {config}\n")
        
        if not selected_frames:
            with open("debug_save.log", "a") as f:
                f.write("  No frames to save, returning True\n")
            print("No frames to save.")
            return True
        
        output_dir = config['output_dir']
        output_format = config.get('output_format', self.DEFAULT_OUTPUT_FORMAT)
        width = config.get('width', 0)
        input_type = config.get('input_type', 'video')
        input_path = config.get('input_path', '')
        force_overwrite = config.get('force_overwrite', False)
        
        with open("debug_save.log", "a") as f:
            f.write(f"  output_dir: {output_dir}\n")
            f.write(f"  output_format: {output_format}\n")
            f.write(f"  width: {width}\n")
            f.write(f"  input_type: {input_type}\n")
            f.write(f"  force_overwrite: {force_overwrite}\n")
        
        # Ensure output directory exists
        with open("debug_save.log", "a") as f:
            f.write(f"  Creating output directory: {output_dir}\n")
        try:
            os.makedirs(output_dir, exist_ok=True)
            with open("debug_save.log", "a") as f:
                f.write(f"  Output directory created/exists\n")
        except Exception as e:
            with open("debug_save.log", "a") as f:
                f.write(f"  ERROR creating output directory: {e}\n")
            return False
        
        # Check for overwrite if needed
        if not force_overwrite:
            self._check_output_directory_overwrite(output_dir)
        
        success_count = 0
        metadata_list = []
        
        with self._get_progress_bar(len(selected_frames), "Saving frames") as progress_bar:
            for i, frame in enumerate(selected_frames):
                try:
                    # Determine output filename based on input type and frame data
                    filename = self._get_output_filename(frame, i, input_type, output_format)
                    dst_path = os.path.join(output_dir, filename)
                    
                    # Save the frame (with optional resizing)
                    if self._save_single_frame(frame.path, dst_path, width, input_type):
                        success_count += 1
                        
                        # Add to metadata
                        metadata_list.append({
                            "output_filename": filename,
                            "original_path": frame.path,
                            "original_index": frame.index,
                            "sharpness_score": frame.sharpness_score,
                            "source_video": frame.source_video,
                            "source_index": frame.source_index
                        })
                    else:
                        print(f"Failed to save frame: {frame.path}")
                    
                except Exception as e:
                    print(f"Error saving frame {frame.path}: {e}")
                    continue
                
                self._update_progress(progress_bar)
        
        # Save metadata
        self._save_metadata(output_dir, metadata_list, config, selected_frames)
        
        print(f"Successfully saved {success_count}/{len(selected_frames)} frames to {output_dir}")
        return success_count == len(selected_frames)
    
    def _get_output_filename(self, frame: FrameData, sequence_index: int, 
                           input_type: str, output_format: str) -> str:
        """
        Get output filename based on input type and frame data.
        
        Args:
            frame: FrameData object
            sequence_index: Sequential index in selected frames list
            input_type: Type of input ('video', 'directory', 'video_directory')
            output_format: Output file format
            
        Returns:
            Output filename
        """
        if input_type == 'directory':
            # For image directories, use original filename
            if frame.output_name:
                return f"{frame.output_name}.{output_format}"
            else:
                # Fallback to sequential naming
                return f"image_{sequence_index + 1:05d}.{output_format}"
        
        elif input_type == 'video_directory':
            # For video directories, preserve video attribution in naming
            if frame.output_name and frame.output_name.startswith('video'):
                # Use existing video attribution: video01_00001, video02_00005, etc.
                return f"{frame.output_name}.{output_format}"
            elif frame.source_video:
                # Create video attribution from source_video: "video_001" -> "video01_XXXXX"
                video_num = frame.source_video.split('_')[1] if '_' in frame.source_video else "01"
                return f"video{video_num}_{sequence_index + 1:05d}.{output_format}"
            else:
                # Fallback to sequential naming
                return f"frame_{sequence_index + 1:05d}.{output_format}"
        
        else:  # video
            # For single videos, use sequential naming
            return f"frame_{sequence_index + 1:05d}.{output_format}"
    
    def _save_single_frame(self, src_path: str, dst_path: str, width: int, input_type: str) -> bool:
        """
        Save a single frame with optional resizing.
        
        Args:
            src_path: Source file path
            dst_path: Destination file path
            width: Resize width (0 for no resizing)
            input_type: Type of input (affects resizing behavior)
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Handle resizing for directory input (video frames already resized during extraction)
            if width > 0 and input_type == 'directory':
                # Load and resize image
                img = cv2.imread(src_path)
                if img is None:
                    raise ImageProcessingError(f"Failed to read image for resizing: {src_path}")
                
                # Calculate height to maintain aspect ratio
                height = int(img.shape[0] * (width / img.shape[1]))
                # Ensure height is even for video compatibility
                if height % 2 != 0:
                    height += 1
                
                # Resize and save
                resized_img = cv2.resize(img, (width, height), interpolation=cv2.INTER_AREA)
                return cv2.imwrite(dst_path, resized_img)
            else:
                # Normal copy for non-resized frames or video frames
                shutil.copy2(src_path, dst_path)
                return True
                
        except Exception as e:
            print(f"Error saving {src_path} to {dst_path}: {e}")
            return False
    
    def _save_metadata(self, output_dir: str, metadata_list: List[Dict[str, Any]], 
                      config: Dict[str, Any], selected_frames: List[FrameData]):
        """
        Save metadata about selected frames.
        
        Args:
            output_dir: Output directory
            metadata_list: List of frame metadata
            config: Configuration dictionary
            selected_frames: List of selected frames
        """
        metadata_path = os.path.join(output_dir, "selected_metadata.json")
        
        try:
            # Create comprehensive metadata
            metadata = {
                "input_path": config.get('input_path', ''),
                "input_type": config.get('input_type', 'video'),
                "output_directory": output_dir,
                "total_selected": len(selected_frames),
                "output_format": config.get('output_format', self.DEFAULT_OUTPUT_FORMAT),
                "resize_width": config.get('width', 0) if config.get('width', 0) > 0 else None,
                "processing_timestamp": self._get_current_timestamp(),
                "selection_summary": self._create_selection_summary(selected_frames),
                "selected_frames": metadata_list
            }
            
            # Add method-specific parameters if available
            if 'selection_method' in config:
                metadata['selection_method'] = config['selection_method']
                metadata.update(self._get_method_params_for_metadata(config))
            
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
                
            print(f"Metadata saved to {metadata_path}")
            
        except Exception as e:
            print(f"Warning: Failed to save metadata: {e}")
    
    def _create_selection_summary(self, selected_frames: List[FrameData]) -> Dict[str, Any]:
        """Create summary statistics for selected frames."""
        if not selected_frames:
            return {}
        
        sharpness_scores = [frame.sharpness_score for frame in selected_frames]
        
        # Group by source video for video directory processing
        video_groups = {}
        for frame in selected_frames:
            if frame.source_video:
                video_groups.setdefault(frame.source_video, 0)
                video_groups[frame.source_video] += 1
        
        summary = {
            "total_frames": len(selected_frames),
            "sharpness_stats": {
                "min": min(sharpness_scores),
                "max": max(sharpness_scores),
                "average": sum(sharpness_scores) / len(sharpness_scores),
            },
            "frame_indices": {
                "first": min(frame.index for frame in selected_frames),
                "last": max(frame.index for frame in selected_frames),
            }
        }
        
        # Add video distribution if applicable
        if video_groups:
            summary["video_distribution"] = video_groups
        
        return summary
    
    def _get_method_params_for_metadata(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Get method-specific parameters for metadata."""
        params = {}
        selection_method = config.get('selection_method', '')
        
        if selection_method == 'best_n':
            params.update({
                "num_frames_requested": config.get('n', 300),
                "min_buffer": config.get('min_buffer', 3)
            })
        elif selection_method == 'batched':
            params.update({
                "batch_size": config.get('batch_size', 5),
                "batch_buffer": config.get('batch_buffer', 2)
            })
        elif selection_method == 'outlier_removal':
            params.update({
                "outlier_sensitivity": config.get('outlier_sensitivity', 50),
                "outlier_window_size": config.get('outlier_window_size', 15)
            })
        
        return params
    
    def _get_current_timestamp(self) -> str:
        """Get current timestamp for metadata."""
        import datetime
        return datetime.datetime.now().isoformat()
    
    def _check_output_directory_overwrite(self, output_dir: str):
        """Check if output directory contains files and warn user."""
        if not os.path.exists(output_dir):
            return  # Directory doesn't exist, no overwrite concern
        
        try:
            existing_files = [f for f in os.listdir(output_dir) 
                            if os.path.isfile(os.path.join(output_dir, f))]
            
            if existing_files:
                # In non-interactive mode (TUI/thread context), just warn without prompting
                if not self.show_progress:  # show_progress=False indicates non-interactive context
                    print(f"Warning: Output directory '{output_dir}' contains {len(existing_files)} files that may be overwritten.")
                    return
                
                # Interactive mode - prompt user
                print(f"Warning: Output directory '{output_dir}' contains {len(existing_files)} files.")
                print("Existing files may be overwritten.")
                
                while True:
                    response = input("Continue anyway? (y/n): ").strip().lower()
                    if response in ['y', 'yes']:
                        print("Continuing with existing output directory...")
                        break
                    elif response in ['n', 'no']:
                        print("Operation cancelled. Please specify a different output directory or use --force-overwrite.")
                        raise SystemExit(1)
                    else:
                        print("Please enter 'y' or 'n'.")
        
        except OSError as e:
            print(f"Warning: Could not check output directory: {e}")
    
    def cleanup_temp_directory(self, temp_dir: Optional[str]):
        """Clean up temporary directory if it exists."""
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                print(f"Cleaned up temporary directory: {temp_dir}")
            except OSError as e:
                print(f"Warning: Could not clean up temporary directory {temp_dir}: {e}")