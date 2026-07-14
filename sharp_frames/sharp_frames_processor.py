# Core processing logic for Sharp Frames
import subprocess
import os
import sys
import json
import shutil
import tempfile
import cv2
import time
from typing import List, Dict, Any, Tuple, Set
# Simplify imports to avoid multiprocessing issues on Windows
from multiprocessing import cpu_count
import concurrent.futures # Add concurrent.futures import

# Add tqdm for progress visualization (mandatory dependency)
from tqdm import tqdm

# Import selection strategy functions
from .selection_methods import (
    select_best_n_frames,
    select_batched_frames,
    select_outlier_removal_frames
)

# Import video directory utilities
from .video_utils import get_video_files_in_directory

# Define a custom exception for image processing errors
class ImageProcessingError(Exception):
    pass

class SharpFrames:
    def __init__(self,
                 # --- Core Parameters ---
                 input_path: str,
                 input_type: str,
                 output_dir: str,
                 fps: int = 10,
                 output_format: str = "jpg",
                 force_overwrite: bool = False,
                 selection_method: str = "best-n",

                 # --- Parameters for 'best-n' selection ---
                 num_frames: int = 300,
                 min_buffer: int = 3,

                 # --- Parameters for 'batched' selection ---
                 batch_size: int = 5,
                 batch_buffer: int = 0,

                 # --- Parameters for 'outlier-removal' selection ---
                 outlier_window_size: int = 15,
                 outlier_sensitivity: int = 50,
                 
                 # --- Parameters for image resizing ---
                 width: int = 0):

        # --- Constants ---
        # Filename format for output files
        self.OUTPUT_FILENAME_FORMAT = "frame_{seq:05d}.{ext}"
        # Supported image extensions for directory input
        self.SUPPORTED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png'}
        # Weights for composite score calculation in 'best-n' selection
        self.BEST_N_SHARPNESS_WEIGHT = 0.7
        self.BEST_N_DISTRIBUTION_WEIGHT = 0.3
        # Parameters for 'outlier-removal' calculation
        self.OUTLIER_MIN_NEIGHBORS = 3
        self.OUTLIER_THRESHOLD_DIVISOR = 4

        # --- Instance Variables ---
        self.input_path = input_path
        self.input_type = input_type
        self.output_dir = output_dir
        self.fps = fps
        self.num_frames = num_frames
        self.min_buffer = min_buffer
        self.output_format = output_format
        self.temp_dir = None
        self.force_overwrite = force_overwrite
        
        # New properties for selection methods
        self.selection_method = selection_method
        self.batch_size = batch_size
        self.batch_buffer = batch_buffer
        self.outlier_window_size = outlier_window_size
        self.outlier_sensitivity = outlier_sensitivity
        
        # New property for image resizing
        # Ensure width is non-negative (treat negative values as 0)
        self.width = max(0, width)
        if width < 0:
            print(f"Warning: Negative width value ({width}) treated as 0 (no resizing)")
        
    def _setup(self) -> bool:
        """Perform initial setup checks and directory creation."""
        print(f"Processing {self.input_type}: {self.input_path}")
        # Check common dependencies (OpenCV) first
        if not self._check_dependencies(check_ffmpeg=False):
            return False

        os.makedirs(self.output_dir, exist_ok=True)
        try:
            self._check_output_dir_overwrite()
        except SystemExit: # Catch SystemExit raised by _check_output_dir_overwrite
             return False # Indicate setup failure

        # Check video-specific dependencies if needed
        if self.input_type in ["video", "video_directory"]:
            if not self._check_dependencies(check_ffmpeg=True):
                 return False # Check_dependencies already prints error
        return True

    def _load_input_frames(self) -> Tuple[List[str], bool]:
        """Load frame paths from video or directory. Returns (frame_paths, cleanup_temp_dir)."""
        frame_paths = []
        cleanup_temp_dir = False

        if self.input_type == "video":
            # Create temporary directory for extracted frames
            self.temp_dir = tempfile.mkdtemp()
            cleanup_temp_dir = True # Ensure cleanup only if temp dir was created
            print(f"Created temporary directory: {self.temp_dir}")

            print("Extracting video information...")
            video_info = self._get_video_info()
            duration = self._extract_duration(video_info)
            if duration:
                print(f"Video duration: {self._format_duration(duration)}")

            # Extract color space from existing video_info (no extra ffprobe call)
            from .processing.colorspace import get_color_info_description
            color_info = self._extract_color_info_from_video_info(video_info)
            if color_info.needs_conversion:
                print(f"Detected color space: {get_color_info_description(color_info)}")
                print("Will convert to sRGB/BT.709")

            print(f"Extracting frames at {self.fps} fps...")
            # Extract frames relies on self.temp_dir being set
            self._extract_frames(duration, color_info)

            # Get paths from temp directory
            frame_paths = self._get_frame_paths()
            frame_count = len(frame_paths)
            print(f"Extracted {frame_count} frames")

        elif self.input_type == "video_directory":
            # Process all videos in directory
            frame_paths = self._load_frames_from_video_directory()
            frame_count = len(frame_paths)
            cleanup_temp_dir = True  # We create temp directories for video extraction
            if frame_count == 0:
                print("No frames could be extracted from videos in directory.")
                return [], cleanup_temp_dir

        elif self.input_type == "directory":
            # Scan input directory for images
            frame_paths = self._get_image_paths_from_dir()
            frame_count = len(frame_paths)
            if frame_count == 0:
                 print("No images found to process.")
                 # Return empty list, indicating nothing to process further
                 return [], False

        else:
             # Should not happen if validation in main/interactive is correct
             raise ValueError(f"Invalid input_type: {self.input_type}")

        return frame_paths, cleanup_temp_dir

    def _analyze_and_select_frames(self, frame_paths: List[str]) -> List[Dict[str, Any]]:
        """Calculate sharpness, select frames based on method, and return selected data."""
        print("Calculating sharpness scores...")
        frames_with_scores = self._calculate_sharpness(frame_paths)

        if not frames_with_scores:
            print("No frames/images could be scored.")
            return [] # Return empty list

        print(f"Selecting frames/images using {self.selection_method} method...")
        selected_frames_data = [] # Initialize
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
            # Outlier removal returns all frames with a 'selected' flag
            all_frames_data = select_outlier_removal_frames(
                frames_with_scores,
                self.outlier_window_size,
                self.outlier_sensitivity,
                self.OUTLIER_MIN_NEIGHBORS,
                self.OUTLIER_THRESHOLD_DIVISOR
            )
            # Filter here based on the 'selected' flag
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

        if not selected_frames_data:
             print("No frames/images were selected based on the criteria.")
             # Return empty list

        return selected_frames_data

    def run(self):
        """Execute the full pipeline for either video or directory input."""
        cleanup_temp_dir = False # Flag to control temp dir cleanup

        try:
            # --- Setup Phase ---
            if not self._setup():
                 print("Setup failed. Exiting.")
                 return False

            # --- Load Input Frames Phase ---
            frame_paths, cleanup_temp_dir = self._load_input_frames()
            if not frame_paths and self.input_type == "directory":
                 print("No images found or loaded. Exiting gracefully.")
                 return True # Not an error, just nothing to process
            elif not frame_paths and self.input_type in ["video", "video_directory"]:
                 print("No frames extracted from video(s). Exiting.")
                 # This might indicate an issue with extraction or an empty video
                 return False # Consider this potentially an error state

            # --- Analyze and Select Phase ---
            selected_frames_data = self._analyze_and_select_frames(frame_paths)
            if not selected_frames_data:
                 print("Frame analysis or selection yielded no results. Exiting.")
                 return True # Not necessarily an error, could be criteria didn't match

            # --- Save Phase ---
            print(f"Saving {len(selected_frames_data)} selected frames/images...")
            with tqdm(total=len(selected_frames_data), desc="Saving selected items") as progress_bar:
                self._save_frames(selected_frames_data, progress_bar)

            print(f"Successfully processed. Selected items saved to: {self.output_dir}")
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

    def _load_frames_from_video_directory(self) -> List[str]:
        """Process all videos in directory and return aggregated frame paths."""
        video_files = get_video_files_in_directory(self.input_path)
        
        if not video_files:
            print(f"No video files found in directory: {self.input_path}")
            return []

        print(f"Processing {len(video_files)} video file(s)...")
        
        # Create main temporary directory for all video extractions
        self.temp_dir = tempfile.mkdtemp()
        all_frame_paths = []
        
        for i, video_path in enumerate(video_files, 1):
            print(f"\nProcessing video {i}/{len(video_files)}: {os.path.basename(video_path)}")
            
            # Create subdirectory for this video
            video_temp_dir = os.path.join(self.temp_dir, f"video_{i:03d}")
            os.makedirs(video_temp_dir, exist_ok=True)
            
            # Temporarily set paths for single video processing
            original_input_path = self.input_path
            original_temp_dir = self.temp_dir
            
            try:
                self.input_path = video_path
                self.temp_dir = video_temp_dir
                
                # Extract video info and frames for this video
                print("Extracting video information...")
                video_info = None
                color_info = None
                try:
                    video_info = self._get_video_info()
                    duration = self._extract_duration(video_info)
                    if duration:
                        print(f"Video duration: {self._format_duration(duration)}")
                    # Extract color space from existing video_info (no extra ffprobe call)
                    color_info = self._extract_color_info_from_video_info(video_info)
                except Exception as e:
                    print(f"Warning: Could not extract video info for {os.path.basename(video_path)}: {e}")
                    duration = None
                    # Fallback to separate color detection if video_info failed
                    from .processing.colorspace import detect_color_space
                    color_info = detect_color_space(video_path)

                print(f"Extracting frames at {self.fps} fps...")
                if self._extract_frames(duration, color_info):
                    # Get frame paths from this video
                    video_frame_paths = self._get_frame_paths()
                    print(f"Extracted {len(video_frame_paths)} frames from {os.path.basename(video_path)}")
                    
                    # Add to aggregated list with updated indices
                    for frame_path in video_frame_paths:
                        all_frame_paths.append(frame_path)
                else:
                    print(f"Warning: Failed to extract frames from {os.path.basename(video_path)}")
                    
            except Exception as e:
                print(f"Error processing video {os.path.basename(video_path)}: {e}")
                continue
            finally:
                # Restore original paths
                self.input_path = original_input_path
                self.temp_dir = original_temp_dir
        
        print(f"\nTotal frames extracted from all videos: {len(all_frame_paths)}")
        return all_frame_paths

    def _check_output_dir_overwrite(self):
        """Checks output directory and handles overwrite confirmation."""
        if not os.path.isdir(self.output_dir):
            # If it doesn't exist, it will be created, no overwrite check needed
            return

        existing_files = os.listdir(self.output_dir)
        if existing_files and not self.force_overwrite:
            print(f"Warning: Output directory '{self.output_dir}' already contains {len(existing_files)} files.")
            print("This may cause existing files to be overwritten.")
            while True:
                response = input("Continue anyway? (y/n): ").strip().lower()
                if response in ['y', 'yes']:
                    print("Continuing with existing output directory...")
                    break
                elif response in ['n', 'no']:
                    print("Operation cancelled. Please specify a different output directory or use --force-overwrite.")
                    raise SystemExit(1) # Use SystemExit for controlled exit
                else:
                    print("Please enter 'y' or 'n'.")
        elif existing_files and self.force_overwrite:
            print(f"Output directory '{self.output_dir}' contains {len(existing_files)} files. Overwriting without confirmation (--force-overwrite).")

    def _check_dependencies(self, check_ffmpeg: bool = True) -> bool:
        """Check if required dependencies are installed"""
        # Determine number of checks for progress bar
        num_checks = 3 if check_ffmpeg else 1

        try:
            with tqdm(total=num_checks, desc="Checking dependencies") as progress_bar:
                if check_ffmpeg:
                    # Check for FFmpeg
                    try:
                        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
                        progress_bar.update(1)
                    except (subprocess.SubprocessError, FileNotFoundError):
                        print("Error: FFmpeg is not installed or not in PATH. Required for video input.")
                        return False

                    # Check for FFprobe
                    try:
                        subprocess.run(["ffprobe", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
                        progress_bar.update(1)
                    except (subprocess.SubprocessError, FileNotFoundError):
                        # This is only a warning as duration extraction is a nice-to-have
                        print("Warning: FFprobe is not installed or not in PATH. Video duration cannot be determined.")

                # Always check for OpenCV (needed for sharpness calculation)
                # A simple check if cv2 was imported successfully is enough here
                if 'cv2' not in sys.modules:
                     print("Error: OpenCV (cv2) is not installed. Please install it (e.g., pip install opencv-python).")
                     return False
                progress_bar.update(1) # Update progress for OpenCV check

        except Exception as e:
            print(f"Error checking dependencies: {str(e)}")
            return False
            
        return True
    
    def _format_duration(self, seconds: float) -> str:
        """Format seconds as HH:MM:SS"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:05.2f}"
    
    def _extract_duration(self, video_info: Dict[str, Any]) -> float:
        """Extract duration from video info"""
        try:
            if 'format' in video_info and 'duration' in video_info['format']:
                return float(video_info['format']['duration'])
            elif 'streams' in video_info:
                for stream in video_info['streams']:
                    if 'duration' in stream:
                        return float(stream['duration'])
        except (KeyError, ValueError, TypeError) as e:
            print(f"Warning: Unable to extract duration: {str(e)}")
        return None
    
    def _get_video_info(self) -> Dict[str, Any]:
        """Get video metadata using FFmpeg including color space info."""
        # Try using ffprobe for more detailed info including color metadata
        probe_command = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,avg_frame_rate,duration,color_primaries,color_transfer,color_space",
            "-of", "json",
            self.input_path
        ]

        try:
            probe_result = subprocess.run(
                probe_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                text=True
            )

            video_info = json.loads(probe_result.stdout)
            return video_info
        except subprocess.CalledProcessError:
            # Fallback if ffprobe fails
            return {"error": "Failed to get video info"}

    def _extract_color_info_from_video_info(self, video_info: Dict[str, Any]):
        """Extract color space info from existing video_info (avoids extra ffprobe call)."""
        from .processing.colorspace import parse_color_info_from_stream, VideoColorInfo, ColorPrimaries, TransferFunction, ColorMatrix

        streams = video_info.get('streams', [])
        if streams:
            return parse_color_info_from_stream(streams[0])

        # No stream found, return default
        return VideoColorInfo(
            color_primaries=ColorPrimaries.UNKNOWN,
            transfer_function=TransferFunction.UNKNOWN,
            color_matrix=ColorMatrix.UNKNOWN,
            is_hdr=False
        )
    
    def _extract_frames(self, duration: float = None, color_info=None) -> bool:
        """Extract frames from video using FFmpeg with color space conversion."""
        from .processing.colorspace import build_colorspace_filter

        output_pattern = os.path.join(self.temp_dir, f"frame_%05d.{self.output_format}")

        # Set a timeout threshold for the process in case it hangs
        process_timeout_seconds = 3600 # 1 hour timeout for FFmpeg process

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
            "-threads", str(cpu_count()),
            "-hide_banner", # Hide verbose info
            "-loglevel", "warning", # Show errors and warnings
            output_pattern
        ]
        
        # Print the FFmpeg command for debugging
        print(f"FFmpeg command: {' '.join(command)}")
        
        # Estimate total frames if duration is available
        estimated_total_frames = None
        if duration:
            estimated_total_frames = int(duration * self.fps)
            print(f"Estimated frames to extract: {estimated_total_frames}")
        else:
            # If no duration, we can't estimate total, so progress will be indeterminate
            print("Video duration not found, cannot estimate total frames.")

        # Setup progress monitoring
        progress_desc = "Extracting frames"
        # Use total=estimated_total_frames if available, else indeterminate
        progress_bar = tqdm(total=estimated_total_frames, desc=progress_desc, unit="frame")
        
        process = None
        stderr_chunks = []
        try:
            # Start the FFmpeg process
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE, # Pipe stdout to avoid printing to console
                stderr=subprocess.PIPE, # Capture stderr for error reporting
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            # Setup non-blocking reading of stderr
            import threading
            import queue
            
            stderr_queue = queue.Queue()
            
            def read_stderr():
                while True:
                    line = process.stderr.readline()
                    if not line and process.poll() is not None:
                        break
                    if line:
                        stderr_queue.put(line)
            
            # Start thread to read stderr
            stderr_thread = threading.Thread(target=read_stderr)
            stderr_thread.daemon = True
            stderr_thread.start()

            last_file_count = 0
            start_time = time.time()
            last_stderr_check = time.time()

            # Monitor process completion and update progress based on file count
            while process.poll() is None:
                # Check file count periodically
                try:
                    frame_files = os.listdir(self.temp_dir)
                    file_count = len(frame_files)

                    if file_count > last_file_count:
                        update_amount = file_count - last_file_count
                        progress_bar.update(update_amount)
                        last_file_count = file_count
                        # Update description if we have an estimate
                        if estimated_total_frames:
                             progress_bar.set_description(f"{progress_desc}: {file_count}/{estimated_total_frames}")
                        else:
                            progress_bar.set_description(f"{progress_desc}: {file_count} frames")

                    # Check and collect stderr (limit how often we process to avoid slowdown)
                    current_time = time.time()
                    if current_time - last_stderr_check > 1.0:  # Check every second
                        while not stderr_queue.empty():
                            line = stderr_queue.get_nowait()
                            stderr_chunks.append(line)
                            # Only log severe errors, ignore aspect ratio warnings
                            if "Cannot store exact aspect ratio" not in line and "[warning]" not in line.lower():
                                print(f"FFmpeg: {line.strip()}")
                        last_stderr_check = current_time

                    # Check for process timeout
                    if time.time() - start_time > process_timeout_seconds:
                        raise subprocess.TimeoutExpired(command, process_timeout_seconds)

                except FileNotFoundError:
                     # Temp dir might not exist yet briefly at the start
                     pass
                except Exception as e:
                    print(f"Error during progress monitoring: {str(e)}")
                    # Continue monitoring the process itself

                # Small sleep to prevent high CPU usage and allow interrupts
                try:
                    time.sleep(0.1) # Check more frequently for better responsiveness
                except KeyboardInterrupt:
                    print("Keyboard interrupt received. Terminating FFmpeg...")
                    if process:
                        process.terminate()
                    progress_bar.close()
                    raise

            # Collect any remaining stderr
            while not stderr_queue.empty():
                stderr_chunks.append(stderr_queue.get_nowait())
            
            # Process finished, check return code
            return_code = process.returncode
            
            # Update progress bar to completion or final count
            final_frame_count = len(os.listdir(self.temp_dir))
            if estimated_total_frames:
                 progress_bar.n = final_frame_count # Set final count precisely
                 progress_bar.total = final_frame_count # Adjust total if estimate was wrong
            else:
                 # If indeterminate, just update description
                 progress_bar.set_description(f"{progress_desc}: {final_frame_count} frames")

            progress_bar.close()

            print(f"Extraction complete: {final_frame_count} frames extracted")

            # Check result
            if return_code != 0:
                error_message = f"FFmpeg failed with exit code {return_code}."
                if stderr_chunks:
                    error_message += f"FFmpeg stderr: {''.join(stderr_chunks)}"
                raise Exception(error_message)

            return True

        except KeyboardInterrupt:
            # Already handled termination in the loop
            print("Cancelled by user during frame extraction. Cleaning up...")
            # Ensure process is terminated if loop was exited prematurely
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
            raise # Re-raise KeyboardInterrupt for outer handler
        except subprocess.TimeoutExpired:
             print(f"FFmpeg process timed out after {process_timeout_seconds} seconds. Terminating.")
             if process and process.poll() is None:
                 process.terminate()
                 try:
                    process.wait(timeout=5)
                 except subprocess.TimeoutExpired:
                    process.kill()
             raise Exception("FFmpeg process timed out.")
        except Exception as e:
            print(f"Error during frame extraction: {str(e)}")
            if progress_bar and not progress_bar.disable: # Check if progress bar was initialized
                progress_bar.close()
            if process and process.poll() is None:
                process.terminate()
            # Include stderr in exception if available
            if stderr_chunks:
                 e = Exception(f"{str(e)}FFmpeg stderr:{''.join(stderr_chunks)}")
            raise e # Re-raise the exception
    
    def _get_image_paths_from_dir(self) -> List[str]:
        """Scan input directory, find, sort, and return image paths."""
        image_paths = []
        # Use defined constant for supported extensions
        supported_extensions_str = ', '.join(self.SUPPORTED_IMAGE_EXTENSIONS)
        print(f"Scanning directory {self.input_path} for images ({supported_extensions_str})...")

        try:
            for entry in os.scandir(self.input_path):
                if entry.is_file():
                    _, ext = os.path.splitext(entry.name)
                    if ext.lower() in self.SUPPORTED_IMAGE_EXTENSIONS:
                        image_paths.append(entry.path)
        except FileNotFoundError:
            print(f"Error: Input directory not found: {self.input_path}")
            raise
        except Exception as e:
            print(f"Error scanning directory {self.input_path}: {str(e)}")
            raise

        # Sort paths alphabetically for consistent ordering
        image_paths.sort()

        if not image_paths:
            print(f"Warning: No supported image files ({supported_extensions_str}) found in {self.input_path}.")

        print(f"Found {len(image_paths)} images.")
        return image_paths
    
    def _get_frame_paths(self) -> List[str]:
        """Get list of all extracted frame paths (from temp dir)."""
        frame_files = os.listdir(self.temp_dir)
        # Sort frames by number to maintain sequence
        frame_files.sort(key=lambda x: int(os.path.splitext(x)[0].split('_')[1]))
        return [os.path.join(self.temp_dir, f) for f in frame_files]
    
    def _calculate_sharpness(self, frame_paths: List[str]) -> List[Dict[str, Any]]:
        """Calculate sharpness scores for all frames/images using parallel processing."""
        frames_data = []
        desc = "Calculating sharpness for frames" if self.input_type in ["video", "video_directory"] else "Calculating sharpness for images"

        # Use ThreadPoolExecutor for parallel processing
        # Adjust max_workers based on your system's capabilities, cpu_count() is a reasonable default
        num_workers = min(cpu_count(), len(frame_paths)) if len(frame_paths) > 0 else 1
        
        with tqdm(total=len(frame_paths), desc=desc) as progress_bar:
            futures = {}
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
                    # Submit tasks: store future mapped to its original index and path
                    for idx, path in enumerate(frame_paths):
                        future = executor.submit(self._process_image, path)
                        futures[future] = {"index": idx, "path": path}

                    # Process completed futures
                    for future in concurrent.futures.as_completed(futures):
                        task_info = futures[future]
                        path = task_info["path"]
                        idx = task_info["index"]
                        frame_id = os.path.basename(path)

                        try:
                            score = future.result() # Get score or raise exception if task failed
                            frame_data = {
                                "id": frame_id,
                                "path": path,
                                "index": idx,
                                "sharpnessScore": score
                            }
                            frames_data.append(frame_data)
                        except ImageProcessingError as e:
                            # Log specific image processing errors and continue
                            print(f"Warning: {str(e)}")
                        except Exception as e:
                            # Log unexpected errors during future processing
                            print(f"Error retrieving result for {path}: {str(e)}")
                            # Optionally re-raise if it's critical, or just log and skip frame

                        progress_bar.update(1) # Update progress as each task finishes

            except KeyboardInterrupt:
                print("Keyboard interrupt received during sharpness calculation.")
                print("Attempting to cancel pending tasks and save partial results...")
                # Executor shutdown (implicit in 'with' block) will attempt to wait,
                # but KeyboardInterrupt should expedite this.
                # Results gathered so far in frames_data will be kept.
                pass # Let finally block handle sorting
            except Exception as e:
                 # Catch broader exceptions during executor setup/management
                 print(f"Unexpected error during parallel sharpness calculation: {str(e)}")
                 # Depending on the error, might want to re-raise or exit
            finally:
                 # Ensure sorting happens even if interrupted or errors occurred
                 frames_data.sort(key=lambda x: x["index"])
                 
        return frames_data

    @staticmethod
    def _process_image(path: str) -> float:
        """Process a single image and return its sharpness score"""
        try:
            img_gray = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
            if img_gray is None:
                # Raise custom exception if image reading fails
                raise ImageProcessingError(f"Failed to read image: {path}")

            height, width = img_gray.shape
            # Use INTER_AREA for downscaling - generally preferred
            img_half = cv2.resize(img_gray, (width // 2, height // 2), interpolation=cv2.INTER_AREA)

            # Calculate Laplacian variance
            score = float(cv2.Laplacian(img_half, cv2.CV_64F).var())

            return score
        except cv2.error as e:
            # Wrap OpenCV errors
            raise ImageProcessingError(f"OpenCV error processing {path}: {str(e)}") from e

    def _save_frames(self, selected_frames: List[Dict[str, Any]], progress_bar=None) -> None:
        """Save selected frames/images to output directory."""
        metadata_list = []
        for i, frame_data in enumerate(selected_frames):
            src_path = frame_data["path"]
            original_id = frame_data["id"]
            original_index = frame_data["index"]
            sharpness_score = frame_data["sharpnessScore"]

            # Use original filename for directory input, sequential naming for video input
            if self.input_type == "directory":
                filename = original_id  # Use the original filename directly
            else:
                # Use the defined constant format string for video frames and video directory
                filename = self.OUTPUT_FILENAME_FORMAT.format(
                    seq=i+1,
                    ext=self.output_format
                )
            dst_path = os.path.join(self.output_dir, filename)

            try:
                # If width is set and we're in directory mode (video modes already handle this during extraction)
                if self.width > 0 and self.input_type == "directory":
                    # Load the image with OpenCV
                    img = cv2.imread(src_path)
                    if img is None:
                        raise ImageProcessingError(f"Failed to read image for resizing: {src_path}")
                    
                    # Calculate height to maintain aspect ratio
                    height = int(img.shape[0] * (self.width / img.shape[1]))
                    # Ensure height is even
                    if height % 2 != 0:
                        height += 1
                    
                    # Resize the image
                    resized_img = cv2.resize(img, (self.width, height), interpolation=cv2.INTER_AREA)
                    
                    # Save the resized image
                    cv2.imwrite(dst_path, resized_img)
                else:
                    # Normal copy for non-resized or video frames
                    shutil.copy2(src_path, dst_path)
            except Exception as e:
                 print(f"Error saving {src_path} to {dst_path}: {e}")
                 # Optionally skip this frame and continue, or re-raise
                 continue

            metadata_list.append({
                "output_filename": filename,
                "original_id": original_id, # Original filename or frame ID
                "original_index": original_index,
                "sharpness_score": sharpness_score
            })

            if progress_bar:
                progress_bar.update(1)

        # Save metadata about the selected files
        metadata_path = os.path.join(self.output_dir, "selected_metadata.json")
        try:
            with open(metadata_path, "w") as f:
                json.dump({
                    "input_path": self.input_path,
                    "input_type": self.input_type,
                    "total_selected": len(metadata_list),
                    "selection_method": self.selection_method,
                    # Include resize width in metadata if set
                    "resize_width": self.width if self.width > 0 else None,
                    # Include method-specific params in metadata
                    **self._get_method_params_for_metadata(),
                    "selected_items": metadata_list
                }, f, indent=2)
        except Exception as e:
             print(f"Error writing metadata file {metadata_path}: {str(e)}")

    def _get_method_params_for_metadata(self) -> Dict[str, Any]:
        """Returns parameters relevant to the current selection method for metadata."""
        params = {}
        # Include width parameter regardless of method (if set)
        if self.width > 0:
            params["resize_width"] = self.width
            
        if self.selection_method == "best-n":
            params["num_frames_requested"] = self.num_frames
            params["min_buffer"] = self.min_buffer
        elif self.selection_method == "batched":
            params["batch_size"] = self.batch_size
            params["batch_buffer"] = self.batch_buffer
        elif self.selection_method == "outlier-removal":
            params["outlier_window_size"] = self.outlier_window_size
            params["outlier_sensitivity"] = self.outlier_sensitivity
        return params