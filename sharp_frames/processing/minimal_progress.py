"""
MinimalProgressSharpFrames - UI-safe SharpFrames that avoids tqdm multiprocessing issues.
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
    """UI-safe SharpFrames extension that avoids tqdm multiprocessing issues in Textual UI context."""
    
    def __init__(self, progress_callback=None, app_instance=None, **kwargs):
        self.progress_callback = progress_callback
        self.app_instance = app_instance
        # Remove UI-specific kwargs before passing to parent
        clean_kwargs = {k: v for k, v in kwargs.items() if k not in ['progress_callback', 'app_instance']}
        super().__init__(**clean_kwargs)
    
    def _update_progress(self, phase: str, current: int, total: int, description: str = ""):
        """Update progress via callback if available."""
        if self.progress_callback:
            self.progress_callback(phase, current, total, description)
    
    def _check_output_dir_overwrite(self):
        """Override to handle output directory checking in UI context without interactive prompts."""
        if not os.path.isdir(self.output_dir):
            return

        existing_files = os.listdir(self.output_dir)
        
        if existing_files and not self.force_overwrite:
            print(f"Warning: Output directory '{self.output_dir}' already contains {len(existing_files)} files.")
            print("Files may be overwritten. Use force overwrite option in configuration to suppress this warning.")
        elif existing_files and self.force_overwrite:
            print(f"Output directory '{self.output_dir}' contains {len(existing_files)} files. Overwriting without confirmation (force overwrite enabled).")
    
    def _check_dependencies(self, check_ffmpeg: bool = True) -> bool:
        """Override dependency check to ensure proper OpenCV detection."""
        try:
            if check_ffmpeg:
                # Check for FFmpeg
                try:
                    subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
                except (subprocess.SubprocessError, FileNotFoundError):
                    print("Error: FFmpeg is not installed or not in PATH. Required for video input.")
                    return False

                # Check for FFprobe (warning only if missing)
                try:
                    subprocess.run(["ffprobe", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
                except (subprocess.SubprocessError, FileNotFoundError):
                    print("Warning: FFprobe is not installed or not in PATH. Video duration cannot be determined.")

            # Always check for OpenCV (needed for sharpness calculation)
            try:
                import cv2
            except ImportError:
                print("Error: OpenCV (cv2) is not installed. Please install it (e.g., pip install opencv-python).")
                return False

        except Exception as e:
            print(f"Error checking dependencies: {str(e)}")
            return False
            
        return True
    
    def _build_ffmpeg_command(self, output_pattern: str, color_info=None) -> List[str]:
        """Build the FFmpeg command for frame extraction with color space conversion."""
        from .colorspace import build_colorspace_filter

        # Build the video filters string - order matters!
        vf_filters = []

        # 1. Color space conversion FIRST (before any other processing)
        if color_info is not None:
            colorspace_filter = build_colorspace_filter(color_info)
            if colorspace_filter:
                vf_filters.append(colorspace_filter)

        # 2. FPS filter
        vf_filters.append(f"fps={self.fps}")

        # 3. Scaling filter (after color conversion)
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
            error_message = f"FFmpeg failed with exit code {return_code}."
            if stderr_output:
                error_message += f" FFmpeg stderr: {stderr_output}"
            raise Exception(error_message)

        return True
    
    def _extract_frames(self, duration: float = None, color_info=None) -> bool:
        """Override to add real-time progress tracking to frame extraction with proper cleanup."""
        output_pattern = os.path.join(self.temp_dir, f"frame_%05d.{self.output_format}")

        # Build command and estimate progress
        command = self._build_ffmpeg_command(output_pattern, color_info)
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
            # Pass app_instance to managed_subprocess for signal handling
            with managed_subprocess(command, ProcessingConfig.FFMPEG_TIMEOUT_SECONDS, self.app_instance) as process:
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
        """Override to add progress tracking and avoid tqdm multiprocessing issues."""
        print("Calculating sharpness scores...")
        self._update_progress("sharpness", 0, len(frame_paths), "Starting sharpness calculation")
        
        # Use parent's sharpness calculation
        frames_with_scores = self._calculate_sharpness(frame_paths)

        if not frames_with_scores:
            print("No frames/images could be scored.")
            return []

        print(f"Selecting frames/images using {self.selection_method} method...")
        self._update_progress("selection", 0, len(frames_with_scores), f"Starting {self.selection_method} selection")
        
        # Call selection methods but avoid tqdm multiprocessing issues
        selected_frames_data = []
        try:
            if self.selection_method == "best-n":
                # Use UI-safe implementation to avoid tqdm multiprocessing issues
                selected_frames_data = self._select_best_n_frames_ui_safe(
                    frames_with_scores,
                    self.num_frames,
                    self.min_buffer,
                    self.BEST_N_SHARPNESS_WEIGHT,
                    self.BEST_N_DISTRIBUTION_WEIGHT
                )
            elif self.selection_method == "batched":
                from ..selection_methods import select_batched_frames
                selected_frames_data = select_batched_frames(
                    frames_with_scores,
                    self.batch_size,
                    self.batch_buffer
                )
            elif self.selection_method == "outlier-removal":
                from ..selection_methods import select_outlier_removal_frames
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
                selected_frames_data = self._select_best_n_frames_ui_safe(
                    frames_with_scores,
                    self.num_frames,
                    self.min_buffer,
                    self.BEST_N_SHARPNESS_WEIGHT,
                    self.BEST_N_DISTRIBUTION_WEIGHT
                )
        except Exception as e:
            print(f"Error during frame selection: {e}")
            return []

        self._update_progress("selection", len(selected_frames_data), len(selected_frames_data), 
                            f"Selected {len(selected_frames_data)} frames")

        if not selected_frames_data:
            print("No frames/images were selected based on the criteria.")

        return selected_frames_data
    
    def _select_best_n_frames_ui_safe(self, frames: List[Dict[str, Any]], num_frames: int, min_buffer: int,
                                      sharpness_weight: float, distribution_weight: float) -> List[Dict[str, Any]]:
        """UI-safe version of select_best_n_frames that avoids tqdm multiprocessing issues."""
        from ..selection_methods import _select_initial_segments, _fill_remaining_slots
        
        if not frames:
            return []

        n = min(num_frames, len(frames))
        min_gap = min_buffer

        # Create a simple progress tracker that updates our UI progress
        class UIProgressTracker:
            def __init__(self, total, parent):
                self.total = total
                self.current = 0
                self.parent = parent
            
            def update(self, increment=1):
                self.current += increment
                self.parent._update_progress("selection", self.current, self.total, 
                                           f"Selected {self.current}/{self.total} frames")

        progress_tracker = UIProgressTracker(n, self)

        # Use the original selection logic but with our UI-safe progress tracker
        selected_frames, selected_indices = _select_initial_segments(
            frames, n, min_gap, progress_tracker
        )

        if len(selected_frames) < n:
            _fill_remaining_slots(
                frames, n, min_gap, selected_frames, selected_indices, progress_tracker,
                sharpness_weight, distribution_weight
            )

        return sorted(selected_frames, key=lambda f: f["index"])
    
    def _save_frames(self, selected_frames: List[Dict[str, Any]], progress_bar=None) -> None:
        """Override to add progress tracking and avoid tqdm."""
        if not selected_frames:
            return

        total_frames = len(selected_frames)
        self._update_progress("saving", 0, total_frames, "Starting to save frames")
        
        # Call parent method but pass None to avoid tqdm
        super()._save_frames(selected_frames, None)
        
        # Final progress update
        self._update_progress("saving", total_frames, total_frames, f"Saved {total_frames} frames")

    def run(self):
        """Override the parent run() method to avoid tqdm usage in UI context."""
        cleanup_temp_dir = False

        try:
            # Setup Phase
            self._update_progress("setup", 0, 1, "Setting up processing")
            if not self._setup():
                print("Setup failed. Exiting.")
                return False
            self._update_progress("setup", 1, 1, "Setup complete")

            # Load Input Frames Phase
            self._update_progress("loading", 0, 1, "Loading input frames")
            frame_paths, cleanup_temp_dir = self._load_input_frames()
            if not frame_paths and self.input_type == "directory":
                print("No images found or loaded. Exiting gracefully.")
                return True
            elif not frame_paths and self.input_type in ["video", "video_directory"]:
                print("No frames extracted from video(s). Exiting.")
                return False
            self._update_progress("loading", 1, 1, f"Loaded {len(frame_paths)} frames")

            # Analyze and Select Phase
            self._update_progress("analysis", 0, 1, "Starting analysis and selection")
            selected_frames_data = self._analyze_and_select_frames(frame_paths)
            if not selected_frames_data:
                print("Frame analysis or selection yielded no results. Exiting.")
                return True
            self._update_progress("analysis", 1, 1, f"Selected {len(selected_frames_data)} frames")

            # Save Phase - Use our UI-safe save method instead of tqdm
            print(f"Saving {len(selected_frames_data)} selected frames/images...")
            self._save_frames(selected_frames_data, None)

            print(f"Successfully processed. Selected items saved to: {self.output_dir}")
            self._update_progress("complete", 1, 1, "Processing complete")
            return True

        except KeyboardInterrupt:
            print("Process cancelled by user. Cleaning up...")
            return False
        except Exception as e:
            print(f"Error during processing: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            # Clean up temporary directory only if it was created (video input)
            if cleanup_temp_dir and self.temp_dir and os.path.exists(self.temp_dir):
                print("Cleaning up temporary directory...")
                try:
                    shutil.rmtree(self.temp_dir)
                    print(f"Cleaned up temporary directory: {self.temp_dir}")
                except Exception as e:
                    print(f"Warning: Could not clean up temporary directory: {str(e)}") 