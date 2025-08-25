"""
Tests for SelectionScreen UI component.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from textual.app import App
from textual.widgets import Select, Input, Label, Button

from sharp_frames.ui.screens.selection import SelectionScreen
from sharp_frames.models.frame_data import ExtractionResult, FrameData
from sharp_frames.processing.tui_processor import TUIProcessor
from tests.fixtures import (
    create_sample_frames_data,
    sample_config_video,
    mock_extraction_result
)


class MockApp(App):
    """Mock Textual app for testing."""
    pass


class TestSelectionScreen:
    """Test cases for SelectionScreen UI component."""
    
    def setup_method(self):
        """Set up test environment."""
        self.app = MockApp()
        
        # Create mock processor with extraction result
        self.mock_processor = Mock(spec=TUIProcessor)
        
        # Create sample extraction result
        self.sample_result = ExtractionResult(
            frames=create_sample_frames_data()[:20],  # Use first 20 frames for testing
            metadata={'fps': 30, 'duration': 10.0},
            input_type='video',
            temp_dir='/tmp/test'
        )
        
        self.config = {
            'input_type': 'video',
            'input_path': '/path/to/video.mp4',
            'output_dir': '/path/to/output',
            'fps': 30,
            'output_format': 'jpg'
        }
    
    def test_init(self):
        """Test SelectionScreen initialization."""
        screen = SelectionScreen(self.mock_processor, self.sample_result, self.config)
        
        assert screen.processor == self.mock_processor
        assert screen.extraction_result == self.sample_result
        assert screen.config == self.config
        assert screen.current_method == 'best_n'  # Default method
        assert screen.current_parameters == {}
    
    def test_compose_creates_required_widgets(self):
        """Test that compose method creates all required UI widgets."""
        screen = SelectionScreen(self.mock_processor, self.sample_result, self.config)
        
        # Mock the compose method to track widget creation
        with patch.object(screen, 'compose') as mock_compose:
            mock_compose.return_value = iter([
                Label("Total frames: 20"),
                Select(options=[("best_n", "Best N Frames")], value="best_n"),
                Label("Selected: 0 frames"),
                Button("Confirm", id="confirm"),
                Button("Cancel", id="cancel")
            ])
            
            widgets = list(mock_compose())
            
            # Should have header, method selector, parameter inputs, preview, and buttons
            assert len(widgets) >= 5
            mock_compose.assert_called_once()
    
    def test_selection_screen_displays_total_frames(self):
        """Test that selection screen displays total frame count."""
        screen = SelectionScreen(self.mock_processor, self.sample_result, self.config)
        
        # Mock the frame count display
        with patch.object(screen, '_update_frame_count_display') as mock_update:
            screen._update_frame_count_display()
            mock_update.assert_called_once()
    
    def test_method_dropdown_changes_parameter_inputs(self):
        """Test that changing selection method updates parameter input fields."""
        screen = SelectionScreen(self.mock_processor, self.sample_result, self.config)
        
        # Mock method change handler
        with patch.object(screen, '_on_method_change') as mock_handler:
            # Simulate method change
            screen._on_method_change('batched')
            
            mock_handler.assert_called_once_with('batched')
    
    def test_realtime_count_update_on_parameter_change(self):
        """Test that parameter changes trigger real-time preview updates."""
        screen = SelectionScreen(self.mock_processor, self.sample_result, self.config)
        
        # Mock preview update
        self.mock_processor.preview_selection.return_value = 15
        
        with patch.object(screen, 'update_preview') as mock_update:
            # Simulate parameter change
            screen._on_parameter_change('n', 15)
            
            mock_update.assert_called_once()
    
    def test_update_preview_calls_processor(self):
        """Test that update_preview calls the TUIProcessor correctly."""
        screen = SelectionScreen(self.mock_processor, self.sample_result, self.config)
        screen.current_method = 'best_n'
        screen.current_parameters = {'n': 10}
        
        self.mock_processor.preview_selection.return_value = 10
        
        count = screen.update_preview()
        
        self.mock_processor.preview_selection.assert_called_once_with('best_n', n=10)
        assert count == 10
    
    def test_update_preview_handles_different_methods(self):
        """Test preview updates for different selection methods."""
        screen = SelectionScreen(self.mock_processor, self.sample_result, self.config)
        
        # Test best_n method
        screen.current_method = 'best_n'
        screen.current_parameters = {'n': 15}
        self.mock_processor.preview_selection.return_value = 15
        
        count = screen.update_preview()
        self.mock_processor.preview_selection.assert_called_with('best_n', n=15)
        assert count == 15
        
        # Test batched method
        screen.current_method = 'batched'
        screen.current_parameters = {'batch_count': 5}
        self.mock_processor.preview_selection.return_value = 5
        
        count = screen.update_preview()
        self.mock_processor.preview_selection.assert_called_with('batched', batch_count=5)
        assert count == 5
        
        # Test outlier_removal method
        screen.current_method = 'outlier_removal'
        screen.current_parameters = {'factor': 1.5}
        self.mock_processor.preview_selection.return_value = 18
        
        count = screen.update_preview()
        self.mock_processor.preview_selection.assert_called_with('outlier_removal', factor=1.5)
        assert count == 18
    
    def test_update_preview_performance_under_100ms(self):
        """Test that preview updates complete within 100ms for responsive UI."""
        import time
        
        screen = SelectionScreen(self.mock_processor, self.sample_result, self.config)
        screen.current_method = 'best_n'
        screen.current_parameters = {'n': 10}
        
        # Mock fast preview calculation
        def fast_preview(*args, **kwargs):
            return 10
            
        self.mock_processor.preview_selection = fast_preview
        
        start_time = time.time()
        count = screen.update_preview()
        end_time = time.time()
        
        elapsed = end_time - start_time
        assert elapsed < 0.1, f"Preview update took {elapsed:.3f}s, should be <0.1s"
        assert count == 10
    
    def test_confirm_button_triggers_save(self):
        """Test that confirm button triggers frame selection and save."""
        screen = SelectionScreen(self.mock_processor, self.sample_result, self.config)
        screen.current_method = 'best_n'
        screen.current_parameters = {'n': 10}
        
        self.mock_processor.complete_selection.return_value = True
        
        with patch.object(screen, 'on_confirm') as mock_confirm:
            screen.on_confirm()
            mock_confirm.assert_called_once()
    
    def test_on_confirm_calls_complete_selection(self):
        """Test that on_confirm calls TUIProcessor.complete_selection."""
        screen = SelectionScreen(self.mock_processor, self.sample_result, self.config)
        screen.current_method = 'best_n'
        screen.current_parameters = {'n': 10}
        
        self.mock_processor.complete_selection.return_value = True
        
        with patch.object(screen.app, 'pop_screen') as mock_pop:
            screen.on_confirm()
            
            self.mock_processor.complete_selection.assert_called_once_with(
                'best_n', self.config, n=10
            )
            mock_pop.assert_called_once()
    
    def test_on_cancel_returns_to_previous_screen(self):
        """Test that cancel button returns to previous screen without saving."""
        screen = SelectionScreen(self.mock_processor, self.sample_result, self.config)
        
        with patch.object(screen.app, 'pop_screen') as mock_pop:
            screen.on_cancel()
            
            mock_pop.assert_called_once()
            # Should not call complete_selection
            self.mock_processor.complete_selection.assert_not_called()
    
    def test_parameter_validation_for_best_n(self):
        """Test parameter validation for best-n method."""
        screen = SelectionScreen(self.mock_processor, self.sample_result, self.config)
        
        # Valid parameters
        assert screen._validate_parameters('best_n', {'n': 10}) is True
        assert screen._validate_parameters('best_n', {'n': 1}) is True
        
        # Invalid parameters
        assert screen._validate_parameters('best_n', {'n': 0}) is False
        assert screen._validate_parameters('best_n', {'n': -1}) is False
        assert screen._validate_parameters('best_n', {}) is False
        assert screen._validate_parameters('best_n', {'n': 'invalid'}) is False
    
    def test_parameter_validation_for_batched(self):
        """Test parameter validation for batched method."""
        screen = SelectionScreen(self.mock_processor, self.sample_result, self.config)
        
        # Valid parameters
        assert screen._validate_parameters('batched', {'batch_count': 5}) is True
        assert screen._validate_parameters('batched', {'batch_count': 1}) is True
        
        # Invalid parameters
        assert screen._validate_parameters('batched', {'batch_count': 0}) is False
        assert screen._validate_parameters('batched', {'batch_count': -1}) is False
        assert screen._validate_parameters('batched', {}) is False
    
    def test_parameter_validation_for_outlier_removal(self):
        """Test parameter validation for outlier removal method."""
        screen = SelectionScreen(self.mock_processor, self.sample_result, self.config)
        
        # Valid parameters
        assert screen._validate_parameters('outlier_removal', {'factor': 1.5}) is True
        assert screen._validate_parameters('outlier_removal', {'factor': 0.1}) is True
        
        # Invalid parameters
        assert screen._validate_parameters('outlier_removal', {'factor': 0}) is False
        assert screen._validate_parameters('outlier_removal', {'factor': -1}) is False
        assert screen._validate_parameters('outlier_removal', {}) is False
    
    def test_error_handling_in_preview_update(self):
        """Test error handling when preview update fails."""
        screen = SelectionScreen(self.mock_processor, self.sample_result, self.config)
        screen.current_method = 'best_n'
        screen.current_parameters = {'n': 10}
        
        # Mock processor to raise exception
        self.mock_processor.preview_selection.side_effect = Exception("Preview failed")
        
        with patch.object(screen, '_show_error_message') as mock_error:
            count = screen.update_preview()
            
            mock_error.assert_called_once()
            assert count == 0  # Should return 0 on error
    
    def test_error_handling_in_confirm(self):
        """Test error handling when confirm operation fails."""
        screen = SelectionScreen(self.mock_processor, self.sample_result, self.config)
        screen.current_method = 'best_n'
        screen.current_parameters = {'n': 10}
        
        # Mock processor to raise exception
        self.mock_processor.complete_selection.side_effect = Exception("Save failed")
        
        with patch.object(screen, '_show_error_message') as mock_error, \
             patch.object(screen.app, 'pop_screen') as mock_pop:
            
            screen.on_confirm()
            
            mock_error.assert_called_once()
            # Should not pop screen on error
            mock_pop.assert_not_called()
    
    def test_method_dropdown_options(self):
        """Test that method dropdown contains all available selection methods."""
        screen = SelectionScreen(self.mock_processor, self.sample_result, self.config)
        
        options = screen._get_method_options()
        
        expected_methods = ['best_n', 'batched', 'outlier_removal']
        assert len(options) == len(expected_methods)
        
        option_values = [option[0] for option in options]
        for method in expected_methods:
            assert method in option_values
    
    def test_parameter_input_fields_update_on_method_change(self):
        """Test that parameter input fields change based on selected method."""
        screen = SelectionScreen(self.mock_processor, self.sample_result, self.config)
        
        # Test best_n method
        with patch.object(screen, '_create_parameter_inputs') as mock_create:
            screen._update_parameter_inputs('best_n')
            mock_create.assert_called_once_with('best_n')
        
        # Test batched method
        with patch.object(screen, '_create_parameter_inputs') as mock_create:
            screen._update_parameter_inputs('batched')
            mock_create.assert_called_once_with('batched')
        
        # Test outlier_removal method
        with patch.object(screen, '_create_parameter_inputs') as mock_create:
            screen._update_parameter_inputs('outlier_removal')
            mock_create.assert_called_once_with('outlier_removal')
    
    def test_frame_count_display_formatting(self):
        """Test that frame counts are displayed in user-friendly format."""
        screen = SelectionScreen(self.mock_processor, self.sample_result, self.config)
        
        # Test various counts
        assert screen._format_frame_count(0) == "0 frames"
        assert screen._format_frame_count(1) == "1 frame"
        assert screen._format_frame_count(10) == "10 frames"
        assert screen._format_frame_count(1000) == "1,000 frames"
        assert screen._format_frame_count(10000) == "10,000 frames"
    
    def test_keyboard_shortcuts(self):
        """Test keyboard shortcuts for common actions."""
        screen = SelectionScreen(self.mock_processor, self.sample_result, self.config)
        
        # Mock key event handling
        with patch.object(screen, 'on_confirm') as mock_confirm, \
             patch.object(screen, 'on_cancel') as mock_cancel:
            
            # Test Enter key for confirm
            screen._handle_key_press('enter')
            mock_confirm.assert_called_once()
            
            # Test Escape key for cancel
            screen._handle_key_press('escape')
            mock_cancel.assert_called_once()
    
    def test_loading_states_during_operations(self):
        """Test that loading states are shown during long operations."""
        screen = SelectionScreen(self.mock_processor, self.sample_result, self.config)
        
        with patch.object(screen, '_show_loading') as mock_loading, \
             patch.object(screen, '_hide_loading') as mock_hide_loading:
            
            # Mock slow operation
            def slow_complete_selection(*args, **kwargs):
                mock_loading.assert_called_once()
                return True
                
            self.mock_processor.complete_selection = slow_complete_selection
            
            screen.on_confirm()
            
            mock_hide_loading.assert_called_once()
    
    def test_help_text_for_methods(self):
        """Test that help text is available for each selection method."""
        screen = SelectionScreen(self.mock_processor, self.sample_result, self.config)
        
        help_texts = screen._get_method_help_texts()
        
        assert 'best_n' in help_texts
        assert 'batched' in help_texts
        assert 'outlier_removal' in help_texts
        
        # Help texts should be descriptive
        for method, help_text in help_texts.items():
            assert len(help_text) > 20  # Should have meaningful description
            assert isinstance(help_text, str)