"""
Tests for configuration screen business logic.

Focuses on testing the pure logic functions rather than UI components.
Tests step visibility logic, validation, and configuration building.
"""

import pytest
from unittest.mock import Mock, patch

from sharp_frames.ui.screens.configuration import ConfigurationForm
from sharp_frames.ui.components.step_handlers import ConfirmStepHandler
from sharp_frames.ui.constants import InputTypes


class TestConfigurationFormLogic:
    """Test cases for configuration form business logic."""
    
    def test_should_show_step_fps_for_video(self):
        """Test that FPS step is shown for video input."""
        form = ConfigurationForm()
        form.config_data = {'input_type': 'video'}
        
        assert form._should_show_step('fps') is True
        assert form._should_show_step('input_type') is True  # Always shown
        assert form._should_show_step('output_dir') is True  # Always shown
    
    def test_should_show_step_fps_for_video_directory(self):
        """Test that FPS step is shown for video directory input."""
        form = ConfigurationForm()
        form.config_data = {'input_type': 'video_directory'}
        
        assert form._should_show_step('fps') is True
        assert form._should_show_step('input_type') is True  # Always shown
        assert form._should_show_step('output_dir') is True  # Always shown
    
    def test_should_show_step_fps_for_directory(self):
        """Test that FPS step is hidden for directory input."""
        form = ConfigurationForm()
        form.config_data = {'input_type': 'directory'}
        
        assert form._should_show_step('fps') is False
        assert form._should_show_step('input_type') is True  # Always shown
    
    def test_should_show_step_method_params_with_methods(self):
        """Test method params step visibility for different selection methods."""
        form = ConfigurationForm()
        
        # Methods that should show params
        methods_with_params = ['best-n', 'batched', 'outlier-removal']
        
        for method in methods_with_params:
            form.config_data = {'selection_method': method}
            assert form._should_show_step('method_params') is True, f"Method {method} should show params"
        
        # Method without params (if any exist)
        form.config_data = {'selection_method': 'some-other-method'}
        assert form._should_show_step('method_params') is False
    
    def test_should_show_step_always_visible_steps(self):
        """Test that certain steps are always visible."""
        form = ConfigurationForm()
        form.config_data = {}
        
        always_visible = ['input_type', 'input_path', 'output_dir', 'selection_method', 
                         'output_format', 'width', 'force_overwrite', 'confirm']
        
        for step in always_visible:
            assert form._should_show_step(step) is True, f"Step {step} should always be visible"


class TestConfigurationValidation:
    """Test cases for configuration validation logic."""
    
    @pytest.fixture
    def mock_form(self):
        """Create a mock configuration form for testing."""
        form = ConfigurationForm()
        form.config_data = {}
        return form
    
    def test_build_config_summary_video_input(self, mock_form):
        """Test configuration summary building for video input."""
        mock_form.config_data = {
            'input_type': 'video',
            'input_path': '/path/to/video.mp4',
            'output_dir': '/output',
            'fps': 10,
            'selection_method': 'best-n',
            'num_frames': 300,
            'min_buffer': 3,
            'output_format': 'jpg',
            'width': 800,
            'force_overwrite': True
        }
        
        # Use the ConfirmStepHandler to build the summary
        handler = ConfirmStepHandler(mock_form.config_data)
        summary = handler._build_config_summary()
        
        # Check that key information is present
        assert 'video.mp4' in summary
        assert '/output' in summary
        assert 'FPS: 10' in summary  # Actual format from implementation
        assert 'best-n' in summary
        assert 'JPG' in summary  # Output format is uppercase
        assert '800px' in summary  # Width includes 'px'
        assert 'Yes' in summary  # Force overwrite shows as "Yes"
    
    def test_build_config_summary_video_directory_input(self, mock_form):
        """Test configuration summary building for video directory input."""
        mock_form.config_data = {
            'input_type': 'video_directory',
            'input_path': '/path/to/videos',
            'output_dir': '/output',
            'fps': 15,
            'selection_method': 'best-n',
            'num_frames': 300,
            'min_buffer': 3,
            'output_format': 'jpg',
            'width': 800,
            'force_overwrite': True
        }
        
        # Use the ConfirmStepHandler to build the summary
        handler = ConfirmStepHandler(mock_form.config_data)
        summary = handler._build_config_summary()
        
        # Check that key information is present
        assert 'videos' in summary
        assert '/output' in summary
        assert 'FPS (per video): 15' in summary  # Should show fps with per video label
        assert 'best-n' in summary
        assert 'JPG' in summary
        assert '800px' in summary
        assert 'Yes' in summary
    
    def test_build_config_summary_directory_input(self, mock_form):
        """Test configuration summary building for directory input."""
        mock_form.config_data = {
            'input_type': 'directory',
            'input_path': '/path/to/images',
            'output_dir': '/output',
            'selection_method': 'batched',
            'batch_size': 10,
            'batch_buffer': 2,
            'output_format': 'png',  # This will be ignored for directory input
            'width': 1024,  # This will be ignored for directory input
            'force_overwrite': False
        }
        
        # Use the ConfirmStepHandler to build the summary
        handler = ConfirmStepHandler(mock_form.config_data)
        summary = handler._build_config_summary()
        
        # Check that key information is present
        assert 'images' in summary
        assert 'batched' in summary
        # For directory input, format and dimensions should be preserved
        assert 'Preserve original formats' in summary
        assert 'Preserve original dimensions' in summary
        # FPS should not be mentioned for directory input
        assert 'FPS:' not in summary  # Actual format check
    
    def test_build_config_summary_outlier_removal_method(self, mock_form):
        """Test summary for outlier removal method with both parameters."""
        mock_form.config_data = {
            'input_type': 'video',
            'input_path': '/video.mp4',
            'output_dir': '/output',
            'fps': 15,
            'selection_method': 'outlier-removal',
            'outlier_window_size': 15,
            'outlier_sensitivity': 50,
            'output_format': 'jpg',
            'width': 800,
            'force_overwrite': False
        }
        
        # Use the ConfirmStepHandler to build the summary
        handler = ConfirmStepHandler(mock_form.config_data)
        summary = handler._build_config_summary()
        
        assert 'outlier-removal' in summary
        assert 'Window size: 15' in summary
        assert 'Sensitivity: 50' in summary
    
    def test_prepare_final_config_removes_ui_fields(self, mock_form):
        """Test that final config copies config_data and removes None values."""
        mock_form.config_data = {
            'input_type': 'video',
            'input_path': '/video.mp4',
            'output_dir': '/output',
            'fps': 10,
            'selection_method': 'best-n',
            'num_frames': 300,
            'min_buffer': 3,
            'output_format': 'jpg',
            'width': 800,
            'force_overwrite': True
        }

        final_config = mock_form._prepare_final_config()

        # Check that all non-None values are copied
        assert final_config['input_type'] == 'video'
        assert final_config['input_path'] == '/video.mp4'
        assert final_config['output_dir'] == '/output'
        assert final_config['fps'] == 10
        assert final_config['selection_method'] == 'best-n'
        assert final_config['output_format'] == 'jpg'
        assert final_config['width'] == 800
        assert final_config['force_overwrite'] is True

        # Only method parameters that were set should be present
        assert 'num_frames' in final_config
        assert final_config['num_frames'] == 300
        assert 'min_buffer' in final_config
        assert final_config['min_buffer'] == 3
        
        # Parameters not in config_data should not be present
        assert 'batch_size' not in final_config
    
    def test_prepare_final_config_batched_method(self, mock_form):
        """Test final config for batched method."""
        mock_form.config_data = {
            'input_type': 'directory',
            'input_path': '/images',
            'output_dir': '/output',
            'selection_method': 'batched',
            'batch_size': 10,  # Set proper parameter name
            'batch_buffer': 2,  # Set proper parameter name
            'output_format': 'png',
            'width': 1024,
            'force_overwrite': False
        }
        
        final_config = mock_form._prepare_final_config()
        
        # Check that values are copied as-is
        assert final_config['selection_method'] == 'batched'
        assert final_config['input_type'] == 'directory'
        assert final_config['input_path'] == '/images'
        assert final_config['output_dir'] == '/output'
        assert final_config['output_format'] == 'png'
        assert final_config['width'] == 1024
        assert final_config['force_overwrite'] is False
        
        # Only parameters that were actually set should be present
        assert 'batch_size' in final_config
        assert final_config['batch_size'] == 10
        assert 'batch_buffer' in final_config
        assert final_config['batch_buffer'] == 2
    
    def test_prepare_final_config_video_directory_method(self, mock_form):
        """Test final config for video directory input."""
        mock_form.config_data = {
            'input_type': 'video_directory',
            'input_path': '/path/to/videos',
            'output_dir': '/output',
            'fps': 15,
            'selection_method': 'best-n',
            'param1': 20,  # num_frames
            'output_format': 'jpg',
            'width': 800,
            'force_overwrite': True
        }
        
        final_config = mock_form._prepare_final_config()
        
        assert final_config['input_type'] == 'video_directory'
        assert final_config['input_path'] == '/path/to/videos'
        assert final_config['fps'] == 15  # Should have fps for video directory
        assert final_config['selection_method'] == 'best-n'
    
    def test_prepare_final_config_outlier_removal_method(self, mock_form):
        """Test final config for outlier removal method."""
        mock_form.config_data = {
            'input_type': 'video',
            'input_path': '/video.mp4',
            'output_dir': '/output',
            'fps': 5,
            'selection_method': 'outlier-removal',
            'outlier_window_size': 15,  # Set proper parameter name
            'outlier_sensitivity': 50,  # Set proper parameter name
            'output_format': 'jpg',
            'width': 800,
            'force_overwrite': True
        }
        
        final_config = mock_form._prepare_final_config()
        
        # Check that values are copied as-is
        assert final_config['selection_method'] == 'outlier-removal'
        assert final_config['input_type'] == 'video'
        assert final_config['input_path'] == '/video.mp4'
        assert final_config['output_dir'] == '/output'
        assert final_config['fps'] == 5
        assert final_config['output_format'] == 'jpg'
        assert final_config['width'] == 800
        assert final_config['force_overwrite'] is True
        
        # Only parameters that were actually set should be present
        assert 'outlier_window_size' in final_config  
        assert final_config['outlier_window_size'] == 15
        assert 'outlier_sensitivity' in final_config
        assert final_config['outlier_sensitivity'] == 50
    
    def test_prepare_final_config_removes_none_values(self, mock_form):
        """Test that None values are filtered out of final config."""
        mock_form.config_data = {
            'input_type': 'video',
            'input_path': '/video.mp4',
            'output_dir': '/output',
            'fps': None,  # Should be filtered
            'selection_method': 'best-n',
            'num_frames': 300,  # Non-None value
            'min_buffer': None,  # Should be filtered
            'output_format': 'jpg',
            'width': None,  # Should be filtered
            'force_overwrite': False
        }
        
        final_config = mock_form._prepare_final_config()
        
        # None values should be filtered out
        assert 'fps' not in final_config
        assert 'min_buffer' not in final_config  
        assert 'width' not in final_config
        
        # Non-None values should be present
        assert final_config['input_type'] == 'video'
        assert final_config['input_path'] == '/video.mp4'
        assert final_config['output_dir'] == '/output'
        assert final_config['selection_method'] == 'best-n'
        assert final_config['num_frames'] == 300
        assert final_config['output_format'] == 'jpg'
        assert final_config['force_overwrite'] is False


class TestConfigurationStepCounting:
    """Test step counting and navigation logic."""
    
    def test_step_counting_video_input(self):
        """Test step count calculation for video input."""
        form = ConfigurationForm()
        form.config_data = {'input_type': 'video', 'selection_method': 'best-n'}
        
        # Count visible steps
        visible_steps = [step for step in form.steps if form._should_show_step(step)]
        
        # Video input should include FPS step
        assert 'fps' in visible_steps
        assert 'method_params' in visible_steps  # best-n has params
        
        # Should have reasonable number of steps (not too many, not too few)
        assert 8 <= len(visible_steps) <= 12
    
    def test_step_counting_directory_input(self):
        """Test step count calculation for directory input."""
        form = ConfigurationForm()
        form.config_data = {'input_type': 'directory', 'selection_method': 'best-n'}
        
        visible_steps = [step for step in form.steps if form._should_show_step(step)]
        
        # Directory input should not include FPS step
        assert 'fps' not in visible_steps
        assert 'method_params' in visible_steps  # best-n has params
        
        # Should have one less step than video (no FPS)
        assert 7 <= len(visible_steps) <= 11
    
    def test_step_counting_method_without_params(self):
        """Test step counting for selection method without parameters."""
        form = ConfigurationForm()
        form.config_data = {'input_type': 'video', 'selection_method': 'no-params-method'}
        
        visible_steps = [step for step in form.steps if form._should_show_step(step)]
        
        # Should not include method_params step
        assert 'method_params' not in visible_steps 