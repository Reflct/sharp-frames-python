"""
Windows compatibility utilities for Sharp Frames.

This module provides utilities to handle Windows-specific issues and ensure
cross-platform compatibility for the Sharp Frames application.
"""

import os
import sys
import platform
import subprocess
import tempfile
from typing import Dict, Any, List, Tuple, Optional


class WindowsCompatibility:
    """Utility class for Windows compatibility checks and fixes."""
    
    @staticmethod
    def is_windows() -> bool:
        """Check if running on Windows."""
        return os.name == 'nt' or sys.platform.startswith('win')
    
    @staticmethod
    def get_platform_info() -> Dict[str, str]:
        """Get detailed platform information."""
        return {
            'os_name': os.name,
            'sys_platform': sys.platform,
            'platform_system': platform.system(),
            'platform_release': platform.release(),
            'platform_version': platform.version(),
            'platform_machine': platform.machine(),
            'platform_processor': platform.processor()
        }
    
    @staticmethod
    def normalize_path(path: str) -> str:
        """Normalize path for current platform."""
        if not path:
            return path
        return os.path.normpath(os.path.expanduser(path))
    
    @staticmethod
    def get_executable_name(base_name: str) -> str:
        """Get the correct executable name for the current platform."""
        if WindowsCompatibility.is_windows():
            # On Windows, add .exe if not already present
            if not base_name.lower().endswith('.exe'):
                return f"{base_name}.exe"
        return base_name
    
    @staticmethod
    def get_subprocess_creation_flags() -> int:
        """Get appropriate subprocess creation flags for the platform."""
        if WindowsCompatibility.is_windows():
            # On Windows, hide console window and create new process group
            return subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        return 0
    
    @staticmethod
    def check_ffmpeg_availability() -> Tuple[bool, str]:
        """Check if FFmpeg is available and return executable path."""
        ffmpeg_name = WindowsCompatibility.get_executable_name('ffmpeg')
        ffprobe_name = WindowsCompatibility.get_executable_name('ffprobe')
        
        try:
            # Test FFmpeg
            result = subprocess.run(
                [ffmpeg_name, '-version'], 
                capture_output=True, 
                text=True, 
                timeout=10,
                creationflags=WindowsCompatibility.get_subprocess_creation_flags()
            )
            if result.returncode != 0:
                return False, f"FFmpeg not available: {result.stderr}"
            
            # Test FFprobe
            result = subprocess.run(
                [ffprobe_name, '-version'], 
                capture_output=True, 
                text=True, 
                timeout=10,
                creationflags=WindowsCompatibility.get_subprocess_creation_flags()
            )
            if result.returncode != 0:
                return False, f"FFprobe not available: {result.stderr}"
                
            return True, "FFmpeg and FFprobe are available"
            
        except FileNotFoundError as e:
            return False, f"FFmpeg executables not found: {e}"
        except Exception as e:
            return False, f"Error checking FFmpeg: {e}"
    
    @staticmethod
    def validate_paths(paths: List[str]) -> Dict[str, Dict[str, Any]]:
        """Validate a list of paths and return detailed information."""
        results = {}
        
        for path in paths:
            normalized = WindowsCompatibility.normalize_path(path)
            results[path] = {
                'original': path,
                'normalized': normalized,
                'exists': os.path.exists(normalized),
                'is_file': os.path.isfile(normalized) if os.path.exists(normalized) else None,
                'is_dir': os.path.isdir(normalized) if os.path.exists(normalized) else None,
                'is_absolute': os.path.isabs(normalized),
                'parent_exists': os.path.exists(os.path.dirname(normalized)) if normalized else False
            }
            
        return results
    
    @staticmethod
    def create_safe_temp_directory() -> str:
        """Create a temporary directory with platform-appropriate settings."""
        temp_dir = tempfile.mkdtemp(prefix="sharp_frames_")
        
        if WindowsCompatibility.is_windows():
            # On Windows, ensure the temp directory is accessible
            try:
                # Test write access
                test_file = os.path.join(temp_dir, 'test_write.tmp')
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
            except Exception as e:
                # If we can't write to temp dir, fall back to user temp
                try:
                    import shutil
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except:
                    pass
                temp_dir = tempfile.mkdtemp(prefix="sharp_frames_", dir=os.path.expanduser("~/AppData/Local/Temp"))
        
        return temp_dir
    
    @staticmethod
    def test_path_operations() -> Dict[str, Any]:
        """Test various path operations for Windows compatibility."""
        test_paths = [
            "C:\\Users\\Test\\Documents\\video.mp4",  # Windows absolute
            "C:/Users/Test/Documents/video.mp4",     # Windows absolute with forward slashes
            "\\\\server\\share\\video.mp4",          # UNC path
            "/home/user/video.mp4",                   # Unix absolute
            "~/Documents/video.mp4",                  # Home directory
            "./video.mp4",                           # Relative
            "../videos/test.mp4"                     # Relative with parent
        ]
        
        results = {
            'platform_info': WindowsCompatibility.get_platform_info(),
            'path_validation': WindowsCompatibility.validate_paths(test_paths),
            'ffmpeg_check': WindowsCompatibility.check_ffmpeg_availability(),
            'temp_directory': None,
            'executable_names': {
                'ffmpeg': WindowsCompatibility.get_executable_name('ffmpeg'),
                'ffprobe': WindowsCompatibility.get_executable_name('ffprobe')
            },
            'subprocess_flags': WindowsCompatibility.get_subprocess_creation_flags()
        }
        
        # Test temp directory creation
        try:
            temp_dir = WindowsCompatibility.create_safe_temp_directory()
            results['temp_directory'] = {
                'path': temp_dir,
                'exists': os.path.exists(temp_dir),
                'writable': os.access(temp_dir, os.W_OK)
            }
            # Clean up
            try:
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
            except:
                pass
        except Exception as e:
            results['temp_directory'] = {'error': str(e)}
        
        return results


def run_compatibility_test() -> None:
    """Run a comprehensive compatibility test and print results."""
    print("Sharp Frames Windows Compatibility Test")
    print("=" * 50)
    
    test_results = WindowsCompatibility.test_path_operations()
    
    print(f"Platform: {test_results['platform_info']['platform_system']} {test_results['platform_info']['platform_release']}")
    print(f"OS Name: {test_results['platform_info']['os_name']}")
    print(f"Python Platform: {test_results['platform_info']['sys_platform']}")
    print()
    
    # FFmpeg check
    ffmpeg_available, ffmpeg_msg = test_results['ffmpeg_check']
    print(f"FFmpeg Status: {'✅ Available' if ffmpeg_available else '❌ Not Available'}")
    print(f"FFmpeg Message: {ffmpeg_msg}")
    print(f"FFmpeg Executable: {test_results['executable_names']['ffmpeg']}")
    print(f"FFprobe Executable: {test_results['executable_names']['ffprobe']}")
    print()
    
    # Subprocess flags
    print(f"Subprocess Creation Flags: {test_results['subprocess_flags']}")
    print()
    
    # Temp directory
    temp_info = test_results['temp_directory']
    if temp_info and 'error' not in temp_info:
        print(f"Temp Directory Test: ✅ Success")
        print(f"Temp Path: {temp_info['path']}")
        print(f"Writable: {temp_info['writable']}")
    else:
        print(f"Temp Directory Test: ❌ Failed")
        if temp_info and 'error' in temp_info:
            print(f"Error: {temp_info['error']}")
    print()
    
    # Path validation
    print("Path Validation Tests:")
    for path, info in test_results['path_validation'].items():
        status = "✅" if info['normalized'] != info['original'] or info['exists'] else "🔍"
        print(f"  {status} Original: {path}")
        print(f"     Normalized: {info['normalized']}")
        print(f"     Exists: {info['exists']}")
        print()


if __name__ == "__main__":
    run_compatibility_test()