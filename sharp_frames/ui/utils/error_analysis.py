"""
Error analysis utilities for Sharp Frames UI.
"""

import os
import subprocess
from typing import Optional, Dict, Any


class ErrorContext:
    """Class to analyze errors and provide user-friendly messages."""
    
    @staticmethod
    def analyze_ffmpeg_error(return_code: int, stderr_output: str, input_path: str) -> str:
        """Analyze FFmpeg error and provide user-friendly message."""
        if return_code == 1:
            if "No such file or directory" in stderr_output:
                return f"Input file not found: {input_path}. Please check the file path."
            elif "Invalid data found" in stderr_output or "moov atom not found" in stderr_output:
                return f"The video file appears to be corrupted or not a valid video format: {input_path}"
            elif "Permission denied" in stderr_output:
                return f"Permission denied accessing file: {input_path}. Check file permissions."
            elif "Conversion failed" in stderr_output:
                return "Video conversion failed. The video format might not be supported."
        elif return_code == -9 or return_code == 143:
            return "FFmpeg process was terminated (possibly due to timeout or user cancellation)."
        elif "not found" in stderr_output.lower() or "command not found" in stderr_output.lower():
            return "FFmpeg is not installed or not found in system PATH. Please install FFmpeg."
        
        # Generic fallback
        return f"FFmpeg failed with exit code {return_code}. Check video file format and system resources."
    
    @staticmethod
    def analyze_processing_failure(config: Dict[str, Any], error: Exception = None) -> str:
        """Analyze general processing failure and provide user-friendly message.
        
        Args:
            config: Configuration dictionary containing input/output paths and settings
            error: Optional exception that caused the failure
            
        Returns:
            str: User-friendly error message explaining the failure and suggested fixes
            
        Note:
            This method performs various checks including file existence, permissions,
            file types, directory contents, and specific error pattern matching.
        """
        input_path = config.get('input_path', '')
        input_type = config.get('input_type', 'unknown')
        
        # Check basic file system issues
        if input_path and not os.path.exists(input_path):
            return f"Input {input_type} not found: {input_path}"
        
        if input_type == 'video' and input_path:
            if not os.path.isfile(input_path):
                return f"Video input must be a file, but directory found: {input_path}"
            
            # Check file size
            try:
                file_size = os.path.getsize(input_path)
                if file_size == 0:
                    return f"Video file is empty: {input_path}"
                elif file_size < 1024:  # Less than 1KB
                    return f"Video file is suspiciously small ({file_size} bytes): {input_path}"
            except Exception:
                pass
        
        elif input_type == 'directory' and input_path:
            if not os.path.isdir(input_path):
                return f"Directory input must be a directory, but file found: {input_path}"
            
            # Check if directory has images
            try:
                image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}
                files = os.listdir(input_path)
                image_files = [f for f in files if os.path.splitext(f.lower())[1] in image_extensions]
                if not image_files:
                    return f"No image files found in directory: {input_path}"
            except Exception:
                return f"Cannot access directory: {input_path}"
        
        # Check output directory issues
        output_dir = config.get('output_dir', '')
        if output_dir:
            try:
                parent_dir = os.path.dirname(output_dir)
                if parent_dir and not os.path.exists(parent_dir):
                    return f"Output directory parent does not exist: {parent_dir}"
                elif parent_dir and not os.access(parent_dir, os.W_OK):
                    return f"No write permission for output directory: {parent_dir}"
            except Exception:
                pass
        
        # Check specific error types
        if error:
            error_str = str(error).lower()
            if "memory" in error_str or "out of memory" in error_str:
                return "Insufficient memory. Try processing smaller batches or reducing image resolution."
            elif "disk" in error_str or "no space" in error_str:
                return "Insufficient disk space. Free up space or choose a different output location."
            elif "permission" in error_str or "access" in error_str:
                return "Permission denied. Check file/directory permissions."
            elif "timeout" in error_str:
                return "Processing timed out. Try with a smaller input or increase timeout settings."
        
        # Generic fallback
        return "Processing failed due to an unexpected error. Check input files and system resources."
    
    @staticmethod
    def check_system_dependencies() -> Optional[str]:
        """Check system dependencies and return error message if issues found."""
        # Check FFmpeg
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                return "FFmpeg is installed but not working properly. Try reinstalling FFmpeg."
        except subprocess.TimeoutExpired:
            return "FFmpeg check timed out. FFmpeg might be corrupted."
        except FileNotFoundError:
            return "FFmpeg not found. Please install FFmpeg and add it to your system PATH."
        except Exception as e:
            return f"Error checking FFmpeg: {str(e)}"
        
        # Check OpenCV (basic import test)
        try:
            import cv2
            import numpy as np
            # Try a basic operation
            test_img = np.zeros((100, 100, 3), dtype=np.uint8)
            # Test an actual OpenCV function
            gray = cv2.cvtColor(test_img, cv2.COLOR_BGR2GRAY)
            if gray is None:
                return "OpenCV is not working properly. Try reinstalling opencv-python."
        except ImportError as e:
            if "cv2" in str(e):
                return "OpenCV (cv2) not found. Please install opencv-python."
            elif "numpy" in str(e):
                return "NumPy not found. Please install numpy (required for OpenCV)."
            else:
                return f"Missing dependency: {str(e)}"
        except Exception as e:
            return f"Error checking OpenCV: {str(e)}"
        
        return None  # No issues found 