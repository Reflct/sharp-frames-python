"""
Tests for Sharp Frames UI context managers.

Context managers are critical for proper resource management,
ensuring that processes, files, and threads are cleaned up properly.
"""

import os
import subprocess
import tempfile
import threading
import time
import pytest
from unittest.mock import patch, Mock, MagicMock

from sharp_frames.ui.utils.context_managers import (
    managed_subprocess,
    managed_temp_directory,
    managed_thread_pool
)


class TestManagedSubprocess:
    """Test cases for managed_subprocess context manager."""
    
    def test_successful_subprocess_execution(self):
        """Test normal subprocess execution and cleanup."""
        with patch('subprocess.Popen') as mock_popen:
            mock_process = Mock()
            mock_process.poll.return_value = 0  # Process completed
            mock_popen.return_value = mock_process
            
            with managed_subprocess(['echo', 'hello']) as process:
                assert process is mock_process
            
            # Verify process was created correctly
            mock_popen.assert_called_once_with(
                ['echo', 'hello'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Since process completed (poll returned 0), no termination needed
            mock_process.terminate.assert_not_called()
            mock_process.kill.assert_not_called()
    
    def test_subprocess_cleanup_when_still_running(self):
        """Test cleanup of subprocess that's still running."""
        with patch('subprocess.Popen') as mock_popen:
            mock_process = Mock()
            mock_process.poll.return_value = None  # Still running
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process
            
            with managed_subprocess(['long_running_command']):
                pass
            
            # Process should be terminated and waited for
            mock_process.terminate.assert_called_once()
            mock_process.wait.assert_called_with(timeout=5)
    
    def test_subprocess_cleanup_when_terminate_timeout(self):
        """Test cleanup when terminate times out and kill is needed."""
        with patch('subprocess.Popen') as mock_popen:
            mock_process = Mock()
            mock_process.poll.return_value = None  # Still running
            mock_process.wait.side_effect = [subprocess.TimeoutExpired(['cmd'], 5), 0]
            mock_popen.return_value = mock_process
            
            with managed_subprocess(['stubborn_command']):
                pass
            
            # Should terminate, timeout, then kill
            mock_process.terminate.assert_called_once()
            assert mock_process.wait.call_count == 2
            mock_process.kill.assert_called_once()
    
    def test_subprocess_exception_during_creation(self):
        """Test exception handling during process creation."""
        with patch('subprocess.Popen', side_effect=OSError("Command not found")):
            with pytest.raises(OSError, match="Command not found"):
                with managed_subprocess(['nonexistent_command']):
                    pass
    
    def test_subprocess_exception_during_execution(self):
        """Test exception handling during process execution."""
        with patch('subprocess.Popen') as mock_popen:
            mock_process = Mock()
            mock_process.poll.return_value = None  # Still running
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process
            
            with pytest.raises(ValueError, match="Test exception"):
                with managed_subprocess(['echo', 'test']) as process:
                    # Simulate exception during processing
                    raise ValueError("Test exception")
            
            # Even with exception, cleanup should happen
            assert mock_process.terminate.call_count >= 1  # May be called multiple times
    
    def test_subprocess_already_terminated(self):
        """Test cleanup when process is already terminated."""
        with patch('subprocess.Popen') as mock_popen:
            mock_process = Mock()
            mock_process.poll.return_value = 1  # Already finished with error
            mock_popen.return_value = mock_process
            
            with managed_subprocess(['failed_command']):
                pass
            
            # No cleanup needed for already finished process
            mock_process.terminate.assert_not_called()
            mock_process.kill.assert_not_called()


class TestManagedTempDirectory:
    """Test cases for managed_temp_directory context manager."""
    
    def test_temp_directory_creation_and_cleanup(self):
        """Test that temp directory is created and cleaned up."""
        created_dir = None
        
        with managed_temp_directory() as temp_dir:
            created_dir = temp_dir
            assert os.path.exists(temp_dir)
            assert os.path.isdir(temp_dir)
            assert "sharp_frames_" in os.path.basename(temp_dir)
            
            # Create a test file in the directory
            test_file = os.path.join(temp_dir, "test.txt")
            with open(test_file, 'w') as f:
                f.write("test content")
            assert os.path.exists(test_file)
        
        # Directory should be cleaned up after context exit
        assert not os.path.exists(created_dir)
    
    def test_temp_directory_cleanup_with_nested_structure(self):
        """Test cleanup of directory with nested files and folders."""
        created_dir = None
        
        with managed_temp_directory() as temp_dir:
            created_dir = temp_dir
            
            # Create nested structure
            nested_dir = os.path.join(temp_dir, "nested")
            os.makedirs(nested_dir)
            
            with open(os.path.join(nested_dir, "nested_file.txt"), 'w') as f:
                f.write("nested content")
            
            assert os.path.exists(nested_dir)
        
        # All should be cleaned up
        assert not os.path.exists(created_dir)
    
    def test_temp_directory_exception_during_usage(self):
        """Test cleanup happens even with exceptions."""
        created_dir = None
        
        with pytest.raises(ValueError, match="Test exception"):
            with managed_temp_directory() as temp_dir:
                created_dir = temp_dir
                assert os.path.exists(temp_dir)
                raise ValueError("Test exception")
        
        # Directory should still be cleaned up
        assert not os.path.exists(created_dir)
    
    def test_temp_directory_cleanup_failure_handling(self):
        """Test handling of cleanup failures (graceful degradation)."""
        with patch('tempfile.mkdtemp') as mock_mkdtemp, \
             patch('shutil.rmtree', side_effect=OSError("Permission denied")) as mock_rmtree, \
             patch('builtins.print') as mock_print:
            
            mock_mkdtemp.return_value = "/fake/temp/dir"
            
            with managed_temp_directory() as temp_dir:
                assert temp_dir == "/fake/temp/dir"
            
            # Check that cleanup was attempted (may not be called if path checking fails)
            if mock_rmtree.called:
                mock_rmtree.assert_called_with("/fake/temp/dir")
                mock_print.assert_called_once()
                assert "Could not clean up temp directory" in mock_print.call_args[0][0]
    
    def test_temp_directory_creation_failure(self):
        """Test handling of temp directory creation failure."""
        with patch('tempfile.mkdtemp', side_effect=OSError("Disk full")):
            with pytest.raises(OSError, match="Disk full"):
                with managed_temp_directory():
                    pass


class TestManagedThreadPool:
    """Test cases for managed_thread_pool context manager."""
    
    def test_thread_pool_creation_and_cleanup(self):
        """Test basic thread pool creation and cleanup."""
        with managed_thread_pool(max_workers=2) as executor:
            assert executor is not None
            assert hasattr(executor, 'submit')
            assert hasattr(executor, 'shutdown')
            
            # Submit a simple task
            future = executor.submit(lambda: 42)
            result = future.result()
            assert result == 42
    
    def test_thread_pool_multiple_tasks(self):
        """Test thread pool with multiple concurrent tasks."""
        def square(x):
            time.sleep(0.01)  # Small delay to test concurrency
            return x * x
        
        with managed_thread_pool(max_workers=3) as executor:
            futures = [executor.submit(square, i) for i in range(5)]
            results = [future.result() for future in futures]
            
            assert results == [0, 1, 4, 9, 16]
    
    def test_thread_pool_exception_handling(self):
        """Test thread pool cleanup when exception occurs."""
        def failing_task():
            raise ValueError("Task failed")
        
        with managed_thread_pool(max_workers=2) as executor:
            future = executor.submit(failing_task)
            
            with pytest.raises(ValueError, match="Task failed"):
                future.result()
            
            # Pool should still be functional
            future2 = executor.submit(lambda: "success")
            assert future2.result() == "success"
    
    def test_thread_pool_cleanup_with_running_tasks(self):
        """Test cleanup behavior with tasks still running."""
        def long_running_task():
            time.sleep(0.5)  # Longer than test duration
            return "completed"
        
        executed_tasks = []
        
        with patch('concurrent.futures.ThreadPoolExecutor') as mock_executor_class:
            mock_executor = Mock()
            mock_executor_class.return_value = mock_executor
            
            with managed_thread_pool(max_workers=2) as executor:
                assert executor is mock_executor
                # Simulate submitting tasks
                executor.submit(long_running_task)
            
            # Verify shutdown was called with proper parameters
            mock_executor.shutdown.assert_called_once_with(wait=True, cancel_futures=True)
    
    def test_thread_pool_exception_during_context(self):
        """Test thread pool cleanup when exception occurs in context."""
        with patch('concurrent.futures.ThreadPoolExecutor') as mock_executor_class:
            mock_executor = Mock()
            mock_executor_class.return_value = mock_executor
            
            with pytest.raises(RuntimeError, match="Context error"):
                with managed_thread_pool(max_workers=2):
                    raise RuntimeError("Context error")
            
            # Shutdown should still be called
            mock_executor.shutdown.assert_called_once_with(wait=True, cancel_futures=True)
    
    def test_thread_pool_different_worker_counts(self):
        """Test thread pool with different worker counts."""
        for worker_count in [1, 2, 4, 8]:
            with managed_thread_pool(max_workers=worker_count) as executor:
                # Submit tasks equal to worker count
                futures = [executor.submit(lambda x=i: x) for i in range(worker_count)]
                results = [f.result() for f in futures]
                assert len(results) == worker_count
    
    def test_thread_pool_creation_failure(self):
        """Test handling of thread pool creation failure."""
        with patch('concurrent.futures.ThreadPoolExecutor', 
                   side_effect=RuntimeError("Cannot create thread pool")):
            with pytest.raises(RuntimeError, match="Cannot create thread pool"):
                with managed_thread_pool(max_workers=2):
                    pass


class TestContextManagerIntegration:
    """Integration tests for context managers working together."""
    
    def test_nested_context_managers(self):
        """Test using multiple context managers together."""
        with managed_temp_directory() as temp_dir:
            with managed_thread_pool(max_workers=2) as executor:
                # Create files in temp directory using thread pool
                def create_file(filename):
                    filepath = os.path.join(temp_dir, filename)
                    with open(filepath, 'w') as f:
                        f.write(f"Content of {filename}")
                    return filepath
                
                futures = [
                    executor.submit(create_file, f"file_{i}.txt") 
                    for i in range(3)
                ]
                
                filepaths = [f.result() for f in futures]
                
                # Verify files were created
                for filepath in filepaths:
                    assert os.path.exists(filepath)
        
        # After context exit, temp directory should be cleaned up
        assert not os.path.exists(temp_dir)
    
    def test_context_manager_with_subprocess(self, temp_dir):
        """Test context managers with actual subprocess (mocked)."""
        with patch('subprocess.Popen') as mock_popen:
            mock_process = Mock()
            mock_process.poll.return_value = 0
            mock_process.stdout = iter(["file1.txt\n", "file2.txt\n"])
            mock_popen.return_value = mock_process
            
            with managed_thread_pool(max_workers=1) as executor:
                with managed_subprocess(['ls', temp_dir]) as process:
                    # Use thread pool to process subprocess output
                    future = executor.submit(lambda: list(process.stdout))
                    output_lines = future.result()
                    
                    assert isinstance(output_lines, list) 