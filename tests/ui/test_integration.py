"""
Integration tests for Sharp Frames UI components.
Tests screen transitions and two-phase workflow.
"""

import pytest
from unittest.mock import patch, MagicMock
import os
import tempfile
import shutil

from sharp_frames.ui.app import SharpFramesApp
from sharp_frames.ui.screens.configuration import ConfigurationForm
from sharp_frames.ui.screens.processing import ProcessingScreen
from sharp_frames.ui.screens.selection import SelectionScreen
from sharp_frames.models.frame_data import FrameData


class TestUIIntegration:
    """Test UI integration and screen transitions."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_input_dir = os.path.join(self.temp_dir, "input")
        self.test_output_dir = os.path.join(self.temp_dir, "output")
        os.makedirs(self.test_input_dir)
        os.makedirs(self.test_output_dir)
        
        # Create mock frame data
        self.mock_frames = [
            FrameData(
                path=f"/tmp/frame_{i:05d}.jpg",
                index=i,
                sharpness_score=float(100 - i),
                source_video="test_video.mp4",
                source_index=i,
                output_name=f"frame_{i:05d}.jpg"
            )
            for i in range(10)
        ]
    
    def teardown_method(self):
        """Clean up test environment."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_two_phase_app_initialization(self):
        """Test that SharpFramesApp initializes correctly."""
        app = SharpFramesApp()
        
        assert app.CSS is not None
        assert app.TITLE == "Sharp Frames - by Reflct.app"
        assert hasattr(app, '_last_escape_time')
        assert hasattr(app, '_escape_count')
        assert hasattr(app, '_last_action_time')
    
    def test_configuration_form_initialization(self):
        """Test TwoPhaseConfigurationForm initialization."""
        form = TwoPhaseConfigurationForm()
        
        # Check step configuration
        expected_steps = [
            "input_type", "input_path", "output_dir", "fps",
            "output_format", "width", "force_overwrite", "confirm"
        ]
        assert form.steps == expected_steps
        assert form.current_step == 0
        assert form.config_data == {}
        
        # Check step handlers exist
        for step in expected_steps:
            assert step in form.step_handlers
            assert hasattr(form.step_handlers[step], 'validate')
            assert hasattr(form.step_handlers[step], 'get_data')
    
    def test_configuration_form_step_navigation(self):
        """Test step navigation in configuration form."""
        form = TwoPhaseConfigurationForm()
        
        # Test initial state
        assert form.current_step == 0
        progress = form.get_step_progress()
        assert progress == (1, 8)  # Step 1 of 8
        
        # Mock the DOM-dependent methods
        with patch.object(form, '_render_current_step'), \
             patch.object(form, '_update_navigation_buttons'), \
             patch.object(form.step_handlers['input_type'], 'validate', return_value=True), \
             patch.object(form.step_handlers['input_type'], 'get_data', return_value={'input_type': 'video'}):
            
            # Test moving forward
            form._handle_next()
            assert form.current_step == 1
            assert form.config_data['input_type'] == 'video'
            
            # Test moving backward
            form._handle_back()
            assert form.current_step == 0
    
    @patch('sharp_frames.processing.tui_processor.TUIProcessor')
    def test_processing_screen_initialization(self, mock_processor_class):
        """Test TwoPhaseProcessingScreen initialization."""
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor
        
        config_data = {
            'input_type': 'video',
            'input_path': '/test/video.mp4',
            'output_dir': self.test_output_dir,
            'fps': 10,
            'output_format': 'jpg'
        }
        
        screen = TwoPhaseProcessingScreen(config_data)
        
        assert screen.config == config_data
        assert screen.processor is None  # Not initialized until processing starts
        assert screen._phase_1_complete == False
        assert screen.extraction_result is None
    
    @patch('sharp_frames.processing.tui_processor.TUIProcessor')
    def test_selection_screen_initialization(self, mock_processor_class):
        """Test SelectionScreen initialization."""
        # Create mock processor and extraction result
        mock_processor = MagicMock()
        mock_extraction_result = MagicMock()
        mock_extraction_result.frames = self.mock_frames
        
        config = {
            'input_type': 'video',
            'input_path': '/test/video.mp4',
            'output_dir': self.test_output_dir,
            'output_format': 'jpg'
        }
        
        screen = SelectionScreen(mock_processor, mock_extraction_result, config)
        
        assert screen.processor == mock_processor
        assert screen.extraction_result == mock_extraction_result
        assert screen.config == config
        assert screen.current_method == "best_n"
        assert screen.current_parameters == {"n": 50}
    
    def test_selection_screen_preview_calculation(self):
        """Test selection screen preview calculation setup."""
        # Create mock processor and extraction result
        mock_processor = MagicMock()
        mock_extraction_result = MagicMock()
        mock_extraction_result.frames = self.mock_frames
        
        config = {
            'input_type': 'video',
            'input_path': '/test/video.mp4',
            'output_dir': self.test_output_dir,
            'output_format': 'jpg'
        }
        
        screen = SelectionScreen(mock_processor, mock_extraction_result, config)
        
        # Test that screen has the necessary attributes for preview calculation
        assert hasattr(screen, 'current_method')
        assert hasattr(screen, 'current_parameters')
        assert hasattr(screen, 'extraction_result')
        assert screen.current_method == "best_n"
    
    def test_config_data_flow(self):
        """Test configuration data flow through screens."""
        # Start with configuration form
        form = TwoPhaseConfigurationForm()
        
        # Set some test data
        test_config = {
            'input_type': 'video',
            'input_path': '/test/input.mp4',
            'output_dir': self.test_output_dir,
            'fps': 15,
            'output_format': 'png',
            'width': 1920,
            'force_overwrite': True
        }
        
        for key, value in test_config.items():
            form.set_config_data(key, value)
        
        # Verify data is stored correctly
        config_data = form.get_config_data()
        for key, value in test_config.items():
            assert config_data[key] == value
        
        # Test that processing screen receives the config
        with patch('sharp_frames.processing.tui_processor.TUIProcessor') as mock_processor_class:
            mock_processor = MagicMock()
            mock_processor_class.return_value = mock_processor
            
            processing_screen = TwoPhaseProcessingScreen(config_data)
            assert processing_screen.config == config_data
    
    def test_file_path_detection(self):
        """Test file path detection in app."""
        app = SharpFramesApp()
        
        # Test various path formats
        assert app._looks_like_file_path("/absolute/path/video.mp4") == True
        assert app._looks_like_file_path("C:\\Windows\\path\\video.mp4") == True
        assert app._looks_like_file_path("~/home/user/video.mp4") == True
        assert app._looks_like_file_path("./relative/path.mp4") == True
        assert app._looks_like_file_path("../parent/path.mp4") == True
        
        # Test non-paths
        assert app._looks_like_file_path("just some text") == False
        assert app._looks_like_file_path("") == False
        assert app._looks_like_file_path("a") == False
    
    def test_screen_stack_management(self):
        """Test proper screen stack management logic."""
        app = SharpFramesApp()
        
        # Test that the action_cancel method exists and has the expected behavior patterns
        assert hasattr(app, 'action_cancel')
        assert callable(app.action_cancel)
        
        # Test escape sequence handling exists  
        assert hasattr(app, '_last_escape_time')
        assert hasattr(app, '_escape_count')
        assert hasattr(app, '_last_action_time')
        
        # Test signal handler management
        assert hasattr(app, 'setup_signal_handlers')
        assert hasattr(app, 'restore_signal_handlers')
        
        # Test file path routing capability
        assert hasattr(app, '_looks_like_file_path')
        assert hasattr(app, '_route_file_path_to_input')
        assert hasattr(app, '_get_target_input_for_step')
    
    def test_signal_handler_management(self):
        """Test signal handler setup and restoration."""
        app = SharpFramesApp()
        
        # Test setup
        app.setup_signal_handlers()
        assert isinstance(app._original_signal_handlers, dict)
        
        # Test restoration (should not raise errors)
        app.restore_signal_handlers()
        
        # Should be able to call multiple times without issues
        app.setup_signal_handlers()
        app.restore_signal_handlers()


class TestScreenTransitions:
    """Test screen transitions and workflow."""
    
    @patch('sharp_frames.processing.tui_processor.TUIProcessor')
    def test_config_to_processing_transition(self, mock_processor_class):
        """Test transition from configuration to processing screen."""
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor
        
        # Create configuration form
        form = TwoPhaseConfigurationForm()
        
        # Set up mock app using patch
        mock_app = MagicMock()
        
        # Mock validation success and app reference
        with patch.object(form, '_validate_final_config', return_value=True), \
             patch.object(form, 'app', mock_app):
            
            # Set some config data
            form.config_data = {
                'input_type': 'video',
                'input_path': '/test/video.mp4',
                'output_dir': '/test/output',
                'output_format': 'jpg'
            }
            
            # Trigger processing start
            form._start_processing()
            
            # Verify processing screen was pushed
            mock_app.push_screen.assert_called_once()
            
            # Verify the screen is a TwoPhaseProcessingScreen
            pushed_screen = mock_app.push_screen.call_args[0][0]
            assert isinstance(pushed_screen, TwoPhaseProcessingScreen)
            assert pushed_screen.config == form.config_data
    
    def test_selection_to_completion(self):
        """Test selection screen completion flow."""
        # Create mock components
        mock_processor = MagicMock()
        mock_extraction_result = MagicMock()
        
        mock_frames = [
            FrameData(path=f"/tmp/frame_{i}.jpg", index=i, sharpness_score=float(i))
            for i in range(10)
        ]
        mock_extraction_result.frames = mock_frames
        
        config = {
            'input_type': 'video',
            'input_path': '/test/video.mp4',
            'output_dir': '/test/output',
            'output_format': 'jpg'
        }
        
        screen = SelectionScreen(mock_processor, mock_extraction_result, config)
        
        # Mock app
        mock_app = MagicMock()
        
        # Test that screen has completion method
        assert hasattr(screen, '_handle_confirm')
        
        # Test that screen has selection methods
        assert hasattr(screen, 'current_method')
        assert hasattr(screen, 'current_parameters')
    
    def test_error_handling_in_transitions(self):
        """Test error handling during screen transitions."""
        form = TwoPhaseConfigurationForm()
        
        # Mock app and query methods
        mock_app = MagicMock()
        mock_app.log = MagicMock()
        mock_step_description = MagicMock()
        
        # Mock processing screen creation to raise an error
        with patch('sharp_frames.ui.screens.processing_v2.TwoPhaseProcessingScreen', 
                   side_effect=Exception("Test error")), \
             patch.object(form, 'app', mock_app), \
             patch.object(form, 'query_one', return_value=mock_step_description), \
             patch.object(form, '_validate_final_config', return_value=True):
            
            form.config_data = {
                'input_type': 'video',
                'input_path': '/test/video.mp4',
                'output_dir': '/test/output',
                'output_format': 'jpg'
            }
            
            form._start_processing()
            
            # Should log error
            mock_app.log.error.assert_called()
            
            # Should update description with error message
            mock_step_description.update.assert_called()
            # Verify error message contains expected text
            error_message = mock_step_description.update.call_args[0][0]
            assert "Error starting processing" in error_message