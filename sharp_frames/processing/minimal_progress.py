"""
MinimalProgressSharpFrames - Enhanced SharpFrames with progress callbacks.
"""

import os
import subprocess
import shutil
import tempfile
import cv2
import time
import json
import concurrent.futures
import queue
import threading
from typing import Optional, Dict, Any, List
from pathlib import Path
from contextlib import ExitStack

from ..sharp_frames_processor import SharpFrames
from ..ui.constants import ProcessingConfig
from ..ui.utils import managed_subprocess, managed_temp_directory, managed_thread_pool, ErrorContext


class MinimalProgressSharpFrames(SharpFrames):
    """Minimal SharpFrames extension that only intercepts progress without breaking functionality."""
    
    def __init__(self, progress_callback=None, **kwargs):
        self.progress_callback = progress_callback
        # Remove progress_callback from kwargs before passing to parent
        clean_kwargs = {k: v for k, v in kwargs.items() if k != 'progress_callback'}
        super().__init__(**clean_kwargs)
    
    def _update_progress(self, phase: str, current: int, total: int, description: str = ""):
        """Update progress if callback is available."""
        if self.progress_callback:
            self.progress_callback(phase, current, total, description)
    
    def _check_output_dir_overwrite(self):
        """Override to handle output directory checking in UI context without interactive prompts."""
        if not os.path.isdir(self.output_dir):
            # If it doesn't exist, it will be created, no overwrite check needed
            return

        existing_files = os.listdir(self.output_dir)
        if existing_files and not self.force_overwrite:
            # In UI context, we don't prompt - we proceed but warn
            print(f"Warning: Output directory '{self.output_dir}' already contains {len(existing_files)} files.")
            print("Files may be overwritten. Use force overwrite option in configuration to suppress this warning.")
            # Continue without prompting since we're in a UI context
        elif existing_files and self.force_overwrite:
            print(f"Output directory '{self.output_dir}' contains {len(existing_files)} files. Overwriting without confirmation (force overwrite enabled).")
    
    def _build_ffmpeg_command(self, output_pattern: str) -> List[str]:
        """Build the FFmpeg command for frame extraction."""
        # Build the video filters string
        vf_filters = []
        vf_filters.append(f"fps={self.fps}")
        
        # Add scaling filter if width is specified
        if self.width > 0:
            vf_filters.append(f"scale={self.width}:-2")  # -2 maintains aspect ratio and ensures even height
            
        # Join all filters with commas
        vf_string = ",".join(vf_filters)
        
        command = [
            "ffmpeg",
            "-i", self.input_path,
            "-vf", vf_string,
            "-q:v", "1",  # Highest quality
            "-threads", str(ProcessingConfig.MAX_CONCURRENT_WORKERS),
            "-hide_banner",  # Hide verbose info
            "-loglevel", "warning",  # Show errors and warnings
            output_pattern
        ]
        
        return command
    
    def _estimate_total_frames(self, duration: Optional[float]) -> Optional[int]:
        """Estimate total frames to extract based on duration and FPS."""
        if duration:
            return int(duration * self.fps)
        return None
    
    def _setup_stderr_reader(self, process: subprocess.Popen, stderr_queue: queue.Queue) -> threading.Thread:
        """Set up a background thread to read stderr without blocking.
        
        Args:
            process: The subprocess.Popen object for FFmpeg
            stderr_queue: Thread-safe queue to store stderr output lines
            
        Returns:
            threading.Thread: The daemon thread that reads stderr
        """
        def read_stderr():
            try:
                for line in iter(process.stderr.readline, ''):
                    if not line:
                        break
                    stderr_queue.put(line)
            except Exception as e:
                stderr_queue.put(f"Error reading stderr: {str(e)}")

        stderr_thread = threading.Thread(target=read_stderr, daemon=True)
        stderr_thread.start()
        return stderr_thread
    
    def _process_stderr_buffer(self, stderr_queue: queue.Queue, stderr_buffer: List[str]) -> None:
        """Process stderr messages and maintain bounded buffer."""
        while not stderr_queue.empty():
            try:
                line = stderr_queue.get_nowait()
                # Implement bounded buffer for stderr
                if len(stderr_buffer) >= ProcessingConfig.STDERR_BUFFER_SIZE:
                    stderr_buffer.pop(0)  # Remove oldest entry
                stderr_buffer.append(line)
                
                # Only log severe errors, ignore aspect ratio warnings
                if "Cannot store exact aspect ratio" not in line and "[warning]" not in line.lower():
                    print(f"FFmpeg: {line.strip()}")
            except queue.Empty:
                break
    
    def _monitor_extraction_progress(self, process: subprocess.Popen, estimated_total: Optional[int], 
                                   stderr_queue: queue.Queue, stderr_buffer: List[str], start_time: float) -> None:
        """Monitor FFmpeg process and update progress.
        
        Args:
            process: The running FFmpeg subprocess
            estimated_total: Estimated total number of frames (None if unknown)
            stderr_queue: Queue containing stderr output from FFmpeg
            stderr_buffer: List to store bounded stderr history
            start_time: Time when extraction started (for timeout checking)
            
        Raises:
            subprocess.TimeoutExpired: If FFmpeg process exceeds timeout
            KeyboardInterrupt: If user cancels the operation
        """
        last_file_count = 0
        last_stderr_check = 0
        
        while process.poll() is None:
            try:
                # Check file count periodically
                if os.path.exists(self.temp_dir):
                    frame_files = os.listdir(self.temp_dir)
                    file_count = len(frame_files)

                    if file_count > last_file_count:
                        # Update progress in real-time
                        if estimated_total:
                            self._update_progress("extraction", file_count, estimated_total, 
                                                f"Extracted {file_count}/{estimated_total} frames")
                        else:
                            self._update_progress("extraction", file_count, 0, f"Extracted {file_count} frames")
                        last_file_count = file_count

                # Check and collect stderr (limit how often we process to avoid slowdown)
                current_time = time.time()
                if current_time - last_stderr_check > ProcessingConfig.UI_UPDATE_INTERVAL:
                    self._process_stderr_buffer(stderr_queue, stderr_buffer)
                    last_stderr_check = current_time

                # Check for process timeout
                if time.time() - start_time > ProcessingConfig.FFMPEG_TIMEOUT_SECONDS:
                    raise subprocess.TimeoutExpired([], ProcessingConfig.FFMPEG_TIMEOUT_SECONDS)

            except FileNotFoundError:
                # Temp dir might not exist yet briefly at the start
                pass
            except Exception as e:
                print(f"Error during progress monitoring: {str(e)}")
                # Continue monitoring the process itself

            # Small sleep to prevent high CPU usage and allow interrupts
            try:
                time.sleep(ProcessingConfig.PROGRESS_CHECK_INTERVAL)
            except KeyboardInterrupt:
                print("Keyboard interrupt received. Terminating FFmpeg...")
                raise
    
    def _finalize_extraction(self, process: subprocess.Popen, stderr_queue: queue.Queue, 
                           stderr_buffer: List[str]) -> bool:
        """Finalize extraction process and handle results."""
        # Collect any remaining stderr
        self._process_stderr_buffer(stderr_queue, stderr_buffer)
        
        # Check return code
        return_code = process.returncode
        
        # Final progress update
        if os.path.exists(self.temp_dir):
            final_frame_count = len(os.listdir(self.temp_dir))
            self._update_progress("extraction", final_frame_count, final_frame_count, 
                                f"Extraction complete: {final_frame_count} frames")
            print(f"Extraction complete: {final_frame_count} frames extracted")

        # Check result with improved error handling
        if return_code != 0:
            stderr_output = ''.join(stderr_buffer) if stderr_buffer else ""
            error_message = ErrorContext.analyze_ffmpeg_error(return_code, stderr_output, self.input_path)
            raise Exception(error_message)

        return True
    
    def _extract_frames(self, duration: float = None) -> bool:
        """Override to add real-time progress tracking to frame extraction with proper cleanup."""
        output_pattern = os.path.join(self.temp_dir, f"frame_%05d.{self.output_format}")
        
        # Build command and estimate progress
        command = self._build_ffmpeg_command(output_pattern)
        estimated_total_frames = self._estimate_total_frames(duration)
        
        # Print the FFmpeg command for debugging
        print(f"FFmpeg command: {' '.join(command)}")
        
        # Set up initial progress
        if estimated_total_frames:
            print(f"Estimated frames to extract: {estimated_total_frames}")
            self._update_progress("extraction", 0, estimated_total_frames, f"Extracting frames at {self.fps}fps")
        else:
            print("Video duration not found, cannot estimate total frames.")
            self._update_progress("extraction", 0, 0, "Extracting frames (unknown total)")

        # Use context managers for proper resource cleanup
        start_time = time.time()
        stderr_buffer = []  # Bounded buffer for stderr

        try:
            with managed_subprocess(command, ProcessingConfig.FFMPEG_TIMEOUT_SECONDS) as process:
                # Use ExitStack to manage multiple resources
                with ExitStack() as stack:
                    stderr_queue = queue.Queue()
                    
                    # Set up stderr monitoring
                    stderr_thread = self._setup_stderr_reader(process, stderr_queue)
                    
                    # Monitor process and update progress
                    self._monitor_extraction_progress(process, estimated_total_frames, 
                                                    stderr_queue, stderr_buffer, start_time)
                    
                    # Finalize and return result
                    return self._finalize_extraction(process, stderr_queue, stderr_buffer)

        except KeyboardInterrupt:
            print("Keyboard interrupt received during frame extraction.")
            raise
        except Exception as e:
            print(f"Error during frame extraction: {str(e)}")
            raise
    
    def _calculate_sharpness(self, frame_paths: List[str]) -> List[Dict[str, Any]]:
        """Override to add progress tracking to sharpness calculation with proper cleanup."""
        desc = "Calculating sharpness for frames" if self.input_type == "video" else "Calculating sharpness for images"
        self._update_progress("sharpness", 0, len(frame_paths), desc)
        
        frames_data = []
        completed_count = 0
        
        # Use managed thread pool for proper cleanup
        with managed_thread_pool(min(ProcessingConfig.MAX_CONCURRENT_WORKERS, len(frame_paths))) as executor:
            try:
                # Submit tasks
                futures = {}
                for idx, path in enumerate(frame_paths):
                    future = executor.submit(self._process_image, path)
                    futures[future] = {"index": idx, "path": path}

                # Process completed futures with progress updates
                for future in concurrent.futures.as_completed(futures):
                    task_info = futures[future]
                    path = task_info["path"]
                    idx = task_info["index"]
                    frame_id = os.path.basename(path)

                    try:
                        score = future.result()
                        frame_data = {
                            "id": frame_id,
                            "path": path,
                            "index": idx,
                            "sharpnessScore": score
                        }
                        frames_data.append(frame_data)
                    except Exception as e:
                        print(f"Error processing {path}: {str(e)}")

                    completed_count += 1
                    self._update_progress("sharpness", completed_count, len(frame_paths), 
                                        f"Processed {completed_count}/{len(frame_paths)} items")

            except KeyboardInterrupt:
                print("Keyboard interrupt received during sharpness calculation.")
                # executor will be properly cleaned up by context manager
                raise

        # Sort by index like parent method
        frames_data.sort(key=lambda x: x["index"])
        return frames_data
    
    def _analyze_and_select_frames(self, frame_paths: List[str]) -> List[Dict[str, Any]]:
        """Override to add progress tracking to frame selection."""
        print("Calculating sharpness scores...")
        frames_with_scores = self._calculate_sharpness(frame_paths)

        if not frames_with_scores:
            print("No frames/images could be scored.")
            return []

        print(f"Selecting frames/images using {self.selection_method} method...")
        self._update_progress("selection", 0, len(frames_with_scores), f"Starting {self.selection_method} selection")
        
        # Call parent method for the actual selection logic
        # Import here to avoid circular imports
        from ..selection_methods import (
            select_best_n_frames,
            select_batched_frames,
            select_outlier_removal_frames
        )
        
        selected_frames_data = []
        if self.selection_method == "best-n":
            selected_frames_data = select_best_n_frames(
                frames_with_scores,
                self.num_frames,
                self.min_buffer,
                self.BEST_N_SHARPNESS_WEIGHT,
                self.BEST_N_DISTRIBUTION_WEIGHT
            )
        elif self.selection_method == "batched":
            selected_frames_data = select_batched_frames(
                frames_with_scores,
                self.batch_size,
                self.batch_buffer
            )
        elif self.selection_method == "outlier-removal":
            all_frames_data = select_outlier_removal_frames(
                frames_with_scores,
                self.outlier_window_size,
                self.outlier_sensitivity,
                self.OUTLIER_MIN_NEIGHBORS,
                self.OUTLIER_THRESHOLD_DIVISOR
            )
            selected_frames_data = [frame for frame in all_frames_data if frame.get("selected", True)]
        else:
            print(f"Warning: Unknown selection method '{self.selection_method}'. Using best-n instead.")
            selected_frames_data = select_best_n_frames(
                frames_with_scores,
                self.num_frames,
                self.min_buffer,
                self.BEST_N_SHARPNESS_WEIGHT,
                self.BEST_N_DISTRIBUTION_WEIGHT
            )

        self._update_progress("selection", len(selected_frames_data), len(selected_frames_data), 
                            f"Selected {len(selected_frames_data)} frames")

        if not selected_frames_data:
            print("No frames/images were selected based on the criteria.")

        return selected_frames_data
    
    def _save_frames(self, selected_frames: List[Dict[str, Any]], progress_bar=None) -> None:
        """Override to add progress tracking to frame saving."""
        self._update_progress("saving", 0, len(selected_frames), "Starting to save frames")
        
        # Call parent method - but we need to implement it since parent expects a progress_bar parameter
        os.makedirs(self.output_dir, exist_ok=True)
        metadata_list = []

        for idx, frame_data in enumerate(selected_frames):
            src_path = frame_data["path"]
            original_id = frame_data["id"]
            original_index = frame_data["index"]
            sharpness_score = frame_data.get("sharpnessScore", 0)

            filename = self.OUTPUT_FILENAME_FORMAT.format(
                seq=idx + 1,
                ext=self.output_format
            )
            dst_path = os.path.join(self.output_dir, filename)

            try:
                if self.width > 0 and self.input_type == "directory":
                    img = cv2.imread(src_path)
                    if img is None:
                        raise Exception(f"Failed to read image for resizing: {src_path}")
                    
                    height = int(img.shape[0] * (self.width / img.shape[1]))
                    if height % 2 != 0:
                        height += 1
                    
                    resized_img = cv2.resize(img, (self.width, height), interpolation=cv2.INTER_AREA)
                    cv2.imwrite(dst_path, resized_img)
                else:
                    shutil.copy2(src_path, dst_path)
            except Exception as e:
                print(f"Error saving {src_path} to {dst_path}: {e}")
                continue

            metadata_list.append({
                "output_filename": filename,
                "original_id": original_id,
                "original_index": original_index,
                "sharpness_score": sharpness_score
            })

            # Update progress for each saved file
            self._update_progress("saving", idx + 1, len(selected_frames), 
                                f"Saved {idx + 1}/{len(selected_frames)} frames")

        # Save metadata
        metadata_path = os.path.join(self.output_dir, "selected_metadata.json")
        try:
            metadata = {
                "input_path": self.input_path,
                "input_type": self.input_type,
                "total_processed": len(selected_frames),
                "selection_method": self.selection_method,
                "method_parameters": self._get_method_params_for_metadata(),
                "output_format": self.output_format,
                "resize_width": self.width if self.width > 0 else None,
                "selected_items": metadata_list
            }
            
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
                
            print(f"Metadata saved to: {metadata_path}")
        except Exception as e:
            print(f"Warning: Could not save metadata: {str(e)}") 