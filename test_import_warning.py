"""Test script to check if FFmpeg warning works."""
import os
import sys
import warnings

# Save original PATH
original_path = os.environ.get('PATH', '')

try:
    # Modify PATH to hide FFmpeg (create a minimal PATH)
    # This is a simple simulation - in a real environment without FFmpeg, 
    # the import would just fail to find it
    minimal_path = os.path.dirname(sys.executable)
    os.environ['PATH'] = minimal_path
    
    # Enable all warnings to be displayed
    warnings.filterwarnings('always')
    
    # Import sharp_frames (should trigger warning)
    print("Importing sharp_frames with modified PATH (FFmpeg should not be found):")
    import sharp_frames
    print("Import completed.")
    
finally:
    # Restore original PATH
    os.environ['PATH'] = original_path
    print("PATH restored to original value.") 