"""
Frame extraction component for Sharp Frames.
"""

import os
import tempfile
import subprocess
import shutil
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from pathlib import Path

from ..models.frame_data import FrameData, ExtractionResult
from ..video_utils import get_video_files_in_directory

if TYPE_CHECKING:
    from .colorspace import VideoColorInfo


class FrameExtractor:
    """Handles frame extraction from videos and loading from directories."""
    
    def __init__(self):
        """Initialize FrameExtractor."""
        self.SUPPORTED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
        
    def extract_frames(self, config: Dict[str, Any], progress_callback=None) -> ExtractionResult:
        """Extract/load frames based on input type."""
        input_type = config.get('input_type')
        self.progress_callback = progress_callback
        
        if input_type == 'directory':
            return self._load_images(config['input_path'])
        elif input_type == 'video':
            return self._extract_video_frames(config)
        elif input_type == 'video_directory':
            return self._extract_video_directory_frames(config)
        else:
            raise ValueError(f"Unsupported input type: {input_type}")
    
    def _load_images(self, image_directory: str) -> ExtractionResult:
        """Load images from directory."""
        if not os.path.exists(image_directory):
            raise FileNotFoundError(f"Directory not found: {image_directory}")
        
        image_files = self._filter_image_files(image_directory)
        
        # Create frame data for each image
        frames = []
        for i, image_path in enumerate(image_files):
            frame = FrameData(
                path=image_path,
                index=i,
                sharpness_score=0.0,  # Will be calculated later
                output_name=self._get_image_output_name(image_path)
            )
            frames.append(frame)
        
        metadata = {
            'source_type': 'directory',
            'total_images': len(frames),
            'image_directory': image_directory
        }
        
        return ExtractionResult(
            frames=frames,
            metadata=metadata,
            temp_dir=None,  # No temp directory needed for images
            input_type='directory'
        )
    
    def _extract_video_frames(self, config: Dict[str, Any]) -> ExtractionResult:
        """Extract frames from single video file."""
        from .colorspace import get_color_info_description

        video_path = config['input_path']
        fps = config.get('fps', 10)
        output_format = config.get('output_format', 'jpg')
        width = config.get('width', 0)

        # Create temporary directory for extraction
        temp_dir = self._create_temp_directory()

        try:
            # Extract video info (includes color space data)
            video_info = self._get_video_info(video_path)
            duration = self._extract_duration_from_info(video_info)

            # Extract color space from existing video_info (no extra ffprobe call)
            color_info = self._extract_color_info_from_video_info(video_info)
            if color_info.needs_conversion:
                color_desc = get_color_info_description(color_info)
                if self.progress_callback:
                    self.progress_callback("extraction", 0, 0, f"Detected {color_desc}, will convert to sRGB")

            # Perform FFmpeg extraction with color space handling
            if not self._run_ffmpeg_extraction(video_path, temp_dir, fps, output_format, width, duration, color_info):
                raise RuntimeError("Frame extraction failed")
            
            # Get extracted frame paths
            frame_files = self._get_extracted_frame_files(temp_dir)
            
            # Create frame data
            frames = []
            for i, frame_path in enumerate(frame_files):
                frame = FrameData(
                    path=frame_path,
                    index=i,
                    sharpness_score=0.0,  # Will be calculated later
                    output_name=f"{i+1:05d}"
                )
                frames.append(frame)
            
            metadata = {
                'fps': fps,
                'duration': duration,
                'source_video': video_path,
                'total_frames_extracted': len(frames),
                'output_format': output_format
            }
            
            return ExtractionResult(
                frames=frames,
                metadata=metadata,
                temp_dir=temp_dir,
                input_type='video'
            )
            
        except Exception as e:
            # Clean up temp directory on failure
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
            raise e
    
    def _extract_video_directory_frames(self, config: Dict[str, Any]) -> ExtractionResult:
        """Extract frames from all videos in directory, preserving video attribution."""
        video_directory = config['input_path']
        fps = config.get('fps', 10)
        output_format = config.get('output_format', 'jpg')
        width = config.get('width', 0)
        
        # Get video files
        video_files = get_video_files_in_directory(video_directory)
        if not video_files:
            return ExtractionResult(
                frames=[],
                metadata={'video_count': 0, 'video_directory': video_directory},
                temp_dir=None,
                input_type='video_directory'
            )
        
        # Create main temporary directory
        temp_dir = self._create_temp_directory()
        
        try:
            all_frames = []
            global_index = 0
            successful_videos = 0
            
            for video_index, video_path in enumerate(video_files):
                video_name = f"video_{video_index + 1:03d}"
                
                try:
                    # Extract frames from this video
                    video_frames = self._extract_single_video(
                        video_path, video_index, temp_dir, config
                    )
                    
                    # Update global indices and add to collection
                    for frame in video_frames:
                        frame.index = global_index
                        global_index += 1
                        all_frames.append(frame)
                    
                    successful_videos += 1
                    
                except Exception as e:
                    print(f"Warning: Failed to extract frames from {os.path.basename(video_path)}: {e}")
                    continue
            
            metadata = {
                'video_count': len(video_files),
                'successful_videos': successful_videos,
                'video_directory': video_directory,
                'fps': fps,
                'total_frames_extracted': len(all_frames),
                'output_format': output_format
            }
            
            return ExtractionResult(
                frames=all_frames,
                metadata=metadata,
                temp_dir=temp_dir,
                input_type='video_directory'
            )
            
        except Exception as e:
            # Clean up temp directory on failure
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
            raise e
    
    def _extract_single_video(self, video_path: str, video_index: int, temp_dir: str, config: Dict[str, Any]) -> List[FrameData]:
        """Extract frames from a single video with video attribution."""
        video_name = f"video_{video_index + 1:03d}"
        video_temp_dir = os.path.join(temp_dir, video_name)
        os.makedirs(video_temp_dir, exist_ok=True)

        fps = config.get('fps', 10)
        output_format = config.get('output_format', 'jpg')
        width = config.get('width', 0)

        # Get video info (includes color space data)
        video_info = self._get_video_info(video_path)
        duration = self._extract_duration_from_info(video_info)

        # Extract color space from existing video_info (no extra ffprobe call)
        color_info = self._extract_color_info_from_video_info(video_info)

        # Extract frames with color space handling
        if not self._run_ffmpeg_extraction(video_path, video_temp_dir, fps, output_format, width, duration, color_info):
            raise RuntimeError(f"Failed to extract frames from {video_path}")
        
        # Get extracted frame files
        frame_files = self._get_extracted_frame_files(video_temp_dir)
        
        # Create frame data with video attribution
        frames = []
        for source_index, frame_path in enumerate(frame_files):
            frame = self._create_frame_data_with_video_attribution(
                frame_path, 0, 0.0, video_name, source_index
            )
            frames.append(frame)
        
        return frames
    
    def _create_frame_data_with_video_attribution(self, path: str, index: int, score: float, 
                                                  source_video: str, source_index: int) -> FrameData:
        """Create frame data with video attribution for video directory processing."""
        # Extract video number from source_video (e.g., "video_001" -> "01")
        video_num = source_video.split('_')[1]  # "001"
        output_name = f"video{video_num}_{source_index + 1:05d}"
        
        return FrameData(
            path=path,
            index=index,
            sharpness_score=score,
            source_video=source_video,
            source_index=source_index,
            output_name=output_name
        )
    
    def _create_frame_data(self, path: str, index: int, score: float) -> FrameData:
        """Create frame data without video attribution."""
        return FrameData(
            path=path,
            index=index,
            sharpness_score=score,
            output_name=f"{index + 1:05d}"
        )
    
    def _filter_image_files(self, directory: str) -> List[str]:
        """Filter and return image file paths from directory."""
        image_files = []
        
        try:
            for entry in os.scandir(directory):
                if entry.is_file():
                    _, ext = os.path.splitext(entry.name)
                    if ext.lower() in self.SUPPORTED_IMAGE_EXTENSIONS:
                        image_files.append(entry.path)
        except OSError as e:
            raise FileNotFoundError(f"Could not scan directory {directory}: {e}")
        
        # Sort for consistent ordering
        image_files.sort()
        return image_files
    
    def _get_image_output_name(self, image_path: str) -> str:
        """Get output name for image (preserving original name without extension)."""
        return Path(image_path).stem
    
    def _create_temp_directory(self) -> str:
        """Create a temporary directory for frame extraction."""
        return tempfile.mkdtemp(prefix="sharp_frames_")
    
    def _get_video_info(self, video_path: str) -> Dict[str, Any]:
        """Get video information using FFprobe."""
        try:
            # Use proper executable name based on platform
            ffprobe_executable = 'ffprobe.exe' if os.name == 'nt' else 'ffprobe'
            
            cmd = [
                ffprobe_executable, '-v', 'quiet', '-print_format', 'json',
                '-show_format', '-show_streams', os.path.normpath(video_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                raise RuntimeError(f"FFprobe failed: {result.stderr}")
            
            import json
            return json.loads(result.stdout)
            
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"FFprobe timeout for {video_path}")
        except FileNotFoundError:
            raise RuntimeError("FFprobe not found. Please install FFmpeg.")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON from FFprobe: {e}")
    
    def _extract_duration_from_info(self, video_info: Dict[str, Any]) -> Optional[float]:
        """Extract duration from video info."""
        try:
            format_info = video_info.get('format', {})
            duration_str = format_info.get('duration')
            return float(duration_str) if duration_str else None
        except (ValueError, TypeError):
            return None

    def _extract_color_info_from_video_info(self, video_info: Dict[str, Any]) -> 'VideoColorInfo':
        """Extract color space info from existing video_info (avoids extra ffprobe call)."""
        from .colorspace import parse_color_info_from_stream, VideoColorInfo, ColorPrimaries, TransferFunction, ColorMatrix

        streams = video_info.get('streams', [])
        # Find the first video stream
        for stream in streams:
            if stream.get('codec_type') == 'video':
                return parse_color_info_from_stream(stream)

        # No video stream found, return default
        return VideoColorInfo(
            color_primaries=ColorPrimaries.UNKNOWN,
            transfer_function=TransferFunction.UNKNOWN,
            color_matrix=ColorMatrix.UNKNOWN,
            is_hdr=False
        )
    
    def _run_ffmpeg_extraction(self, video_path: str, output_dir: str, fps: int,
                              output_format: str, width: int, duration: Optional[float] = None,
                              color_info: Optional['VideoColorInfo'] = None) -> bool:
        """Run FFmpeg to extract frames from video with progress monitoring and color space conversion."""
        from .colorspace import build_colorspace_filter

        output_pattern = os.path.join(output_dir, f"frame_%05d.{output_format}")

        # Build video filters - order matters!
        vf_filters = []

        # 1. Color space conversion FIRST (before any scaling)
        if color_info is not None:
            colorspace_filter = build_colorspace_filter(color_info)
            if colorspace_filter:
                vf_filters.append(colorspace_filter)

        # 2. FPS filter
        vf_filters.append(f"fps={fps}")

        # 3. Scale filter (after color conversion)
        if width > 0:
            # Use lanczos scaling for high-quality downsampling
            vf_filters.append(f"scale={width}:-1:flags=lanczos")

        vf_string = ",".join(vf_filters)
        
        # Use proper executable name based on platform
        ffmpeg_executable = 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg'
        
        # Build FFmpeg command - normalize paths for Windows
        cmd = [
            ffmpeg_executable, 
            '-hwaccel', 'auto',  # Auto-detect and use available hardware acceleration
            '-i', os.path.normpath(video_path),
            '-vf', vf_string,
        ]
        
        # Add quality settings for JPEG output
        if output_format.lower() in ['jpg', 'jpeg']:
            cmd.extend(['-q:v', '1'])  # Highest JPEG quality (1-31, lower is better)
        
        cmd.extend([
            '-y',  # Overwrite output files
            os.path.normpath(output_pattern)
        ])
        
        try:
            # Estimate total frames if duration is available
            estimated_total = 0
            if duration and fps:
                estimated_total = int(duration * fps)
                if self.progress_callback:
                    self.progress_callback("extraction", 0, estimated_total, f"Extracting frames at {fps}fps")
            else:
                if self.progress_callback:
                    self.progress_callback("extraction", 0, 0, "Extracting frames (unknown total)")
            
            # Set timeout based on duration if available
            timeout = 3600  # 1 hour default
            if duration:
                # Rough estimation: 10 seconds per minute of video
                timeout = max(300, int(duration * 10))
            
            # Start FFmpeg process for progress monitoring
            import threading
            import time
            
            # Windows-specific process creation flags
            creation_flags = 0
            if os.name == 'nt':
                # On Windows, create new process group and hide console window
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
            
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True,
                creationflags=creation_flags if os.name == 'nt' else 0
            )
            
            # Monitor progress by counting extracted files
            last_file_count = 0
            start_time = time.time()
            last_progress_time = start_time  # Track when we last saw progress
            stall_timeout = 10.0  # Consider stalled if no progress for 10 seconds
            
            while process.poll() is None:
                current_time = time.time()
                elapsed = current_time - start_time
                
                # Check for timeout
                if elapsed > timeout:
                    process.kill()
                    raise subprocess.TimeoutExpired(cmd, timeout)
                
                # Count extracted files
                if os.path.exists(output_dir):
                    try:
                        file_count = len([f for f in os.listdir(output_dir) if f.startswith('frame_')])
                        
                        if file_count > last_file_count:
                            # We have new frames, update progress time
                            last_progress_time = current_time
                            
                            if self.progress_callback:
                                if estimated_total:
                                    self.progress_callback("extraction", file_count, estimated_total, 
                                                        f"Extracted {file_count}/{estimated_total} frames")
                                else:
                                    self.progress_callback("extraction", file_count, 0, f"Extracted {file_count} frames")
                            last_file_count = file_count
                            
                            # Check if we've reached the expected total
                            if estimated_total > 0 and file_count >= estimated_total:
                                process.terminate()
                                break
                        
                        # Check for stalled extraction (prevents hanging on Windows)
                        if current_time - last_progress_time > stall_timeout:
                            process.terminate()
                            break
                    except Exception:
                        pass  # Continue if file counting fails
                
                time.sleep(0.1)  # Small delay to avoid excessive polling
            
            # Ensure process is terminated and wait for it to finish
            if process.poll() is None:
                process.terminate()
                try:
                    # Wait up to 5 seconds for graceful termination
                    stdout, stderr = process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    stdout, stderr = process.communicate()
            else:
                # Process already finished, get results
                stdout, stderr = process.communicate()
            
            # Check if extraction was successful based on frame count
            # Don't rely on return code since we may have terminated the process
            if os.path.exists(output_dir):
                actual_frame_count = len([f for f in os.listdir(output_dir) if f.startswith('frame_')])
                
                # Consider successful if we have frames and either:
                # 1. We reached the expected count, or
                # 2. We have a reasonable number of frames (at least 10)
                success = actual_frame_count > 0 and (
                    (estimated_total > 0 and actual_frame_count >= estimated_total * 0.95) or  # Allow 5% tolerance
                    actual_frame_count >= 10
                )
                
                if not success:
                    print(f"FFmpeg extraction incomplete: {actual_frame_count} frames")
                    if stderr:
                        print(f"FFmpeg stderr: {stderr}")
                    return False
            else:
                return False
            
            # Final progress update
            if os.path.exists(output_dir):
                final_frame_count = len([f for f in os.listdir(output_dir) if f.startswith('frame_')])
                if self.progress_callback:
                    self.progress_callback("extraction", final_frame_count, final_frame_count, 
                                        f"Extraction complete: {final_frame_count} frames")
            
            return True
            
        except subprocess.TimeoutExpired as e:
            print(f"FFmpeg extraction timeout for {video_path}")
            return False
        except FileNotFoundError as e:
            print("FFmpeg not found. Please install FFmpeg.")
            return False
        except Exception as e:
            print(f"Unexpected error during frame extraction: {e}")
            return False
    
    def _get_extracted_frame_files(self, temp_dir: str) -> List[str]:
        """Get list of extracted frame files from temp directory."""
        frame_files = []
        
        try:
            for entry in os.scandir(temp_dir):
                if entry.is_file() and entry.name.startswith('frame_'):
                    frame_files.append(entry.path)
        except OSError:
            return []
        
        # Sort by filename to maintain frame order
        frame_files.sort()
        return frame_files
    
    def _get_supported_image_extensions(self) -> set:
        """Get supported image file extensions."""
        return self.SUPPORTED_IMAGE_EXTENSIONS