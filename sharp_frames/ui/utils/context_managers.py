"""
Context managers for resource management in Sharp Frames UI.
"""

import os
import shutil
import tempfile
import subprocess
import concurrent.futures
from typing import Optional, List, Generator
from contextlib import contextmanager


@contextmanager
def managed_subprocess(command: List[str], timeout: Optional[float] = None, app_instance=None) -> Generator[subprocess.Popen, None, None]:
    """Context manager for subprocess with guaranteed cleanup.
    
    Args:
        command: Command to execute as subprocess
        timeout: Optional timeout (kept for compatibility but not used directly)
        app_instance: Optional SharpFramesApp instance to handle signal restoration
    
    Note: This context manager yields the process without waiting for completion.
    The calling code is responsible for monitoring the process and handling timeouts.
    The timeout parameter is kept for compatibility but not used directly here.
    """
    process = None
    signal_handlers_restored = False
    
    try:
        # Restore original signal handlers before running subprocess
        if app_instance and hasattr(app_instance, 'restore_signal_handlers'):
            app_instance.restore_signal_handlers()
            signal_handlers_restored = True
        
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        yield process
    except Exception as e:
        if process:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            process.wait()
        raise e
    finally:
        # Clean up subprocess
        if process:
            if process.poll() is None:  # Still running
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        
        # Reinstall app signal handlers
        if signal_handlers_restored and app_instance and hasattr(app_instance, 'reinstall_signal_handlers'):
            app_instance.reinstall_signal_handlers()


@contextmanager
def managed_temp_directory() -> Generator[str, None, None]:
    """Context manager for temporary directory with guaranteed cleanup."""
    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp(prefix="sharp_frames_")
        yield temp_dir
    finally:
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                print(f"Warning: Could not clean up temp directory {temp_dir}: {e}")


@contextmanager 
def managed_thread_pool(max_workers: int) -> Generator[concurrent.futures.ThreadPoolExecutor, None, None]:
    """Context manager for thread pool with guaranteed cleanup."""
    executor = None
    try:
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        yield executor
    finally:
        if executor:
            executor.shutdown(wait=True, cancel_futures=True) 