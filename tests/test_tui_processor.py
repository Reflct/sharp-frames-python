"""
Tests for TUIProcessor orchestrator.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from sharp_frames.processing.tui_processor import TUIProcessor
from sharp_frames.models.frame_data import ExtractionResult, FrameData
from tests.fixtures import (
    sample_config_video,
    sample_config_directory,
    sample_config_video_directory,
    sample_frames_data,
    sample_video_directory_frames,
    mock_extraction_result
)


class TestTUIProcessor:
    """Test cases for TUIProcessor orchestrator."""
    
    def setup_method(self):
        """Set up test environment."""
        self.processor = TUIProcessor()
    
    def test_init(self):
        """Test TUIProcessor initialization."""
        assert self.processor is not None
        assert hasattr(self.processor, 'extractor')
        assert hasattr(self.processor, 'analyzer')
        assert hasattr(self.processor, 'selector')
        assert hasattr(self.processor, 'saver')
        assert self.processor.current_result is None
    
    def test_extract_and_analyze_video(self, sample_config_video):
        """Test extract and analyze phase for video input."""
        config = sample_config_video.copy()
        
        # Mock the components
        mock_extraction_result = ExtractionResult(
            frames=[
                FrameData("/tmp/frame_001.jpg", 0, 0.0, output_name="00001"),
                FrameData("/tmp/frame_002.jpg", 1, 0.0, output_name="00002")
            ],
            metadata={'fps': 30, 'duration': 5.0},
            input_type='video',
            temp_dir='/tmp/sharp_frames_test'
        )
        
        analyzed_result = ExtractionResult(
            frames=[
                FrameData("/tmp/frame_001.jpg", 0, 125.5, output_name="00001"),
                FrameData("/tmp/frame_002.jpg", 1, 150.0, output_name="00002")
            ],
            metadata={'fps': 30, 'duration': 5.0},
            input_type='video',
            temp_dir='/tmp/sharp_frames_test'
        )
        
        with patch.object(self.processor.extractor, 'extract_frames', return_value=mock_extraction_result) as mock_extract, \
             patch.object(self.processor.analyzer, 'calculate_sharpness', return_value=analyzed_result) as mock_analyze:
            
            result = self.processor.extract_and_analyze(config)
            
            mock_extract.assert_called_once_with(config)
            mock_analyze.assert_called_once_with(mock_extraction_result)
            
            assert result == analyzed_result
            assert self.processor.current_result == analyzed_result
            assert result.input_type == 'video'
            assert len(result.frames) == 2
            assert result.frames[0].sharpness_score == 125.5
            assert result.frames[1].sharpness_score == 150.0
    
    def test_extract_and_analyze_image_directory(self, sample_config_directory):
        """Test extract and analyze phase for image directory input."""
        config = sample_config_directory.copy()
        
        mock_extraction_result = ExtractionResult(
            frames=[
                FrameData("/path/img_001.jpg", 0, 0.0, output_name="img_001"),
                FrameData("/path/img_002.jpg", 1, 0.0, output_name="img_002")
            ],
            metadata={'source_type': 'directory'},
            input_type='directory'
        )
        
        analyzed_result = ExtractionResult(
            frames=[
                FrameData("/path/img_001.jpg", 0, 200.0, output_name="img_001"),
                FrameData("/path/img_002.jpg", 1, 175.5, output_name="img_002")
            ],
            metadata={'source_type': 'directory'},
            input_type='directory'
        )
        
        with patch.object(self.processor.extractor, 'extract_frames', return_value=mock_extraction_result), \
             patch.object(self.processor.analyzer, 'calculate_sharpness', return_value=analyzed_result):
            
            result = self.processor.extract_and_analyze(config)
            
            assert result == analyzed_result
            assert result.input_type == 'directory'
            assert result.temp_dir is None  # No temp directory for image directories
    
    def test_extract_and_analyze_video_directory_preserves_attribution(self, sample_config_video_directory):
        """Test that video directory processing preserves video attribution."""
        config = sample_config_video_directory.copy()
        
        # Create frames with video attribution
        frames_with_attribution = [
            FrameData("/tmp/video_001/frame_001.jpg", 0, 125.0, 
                     source_video="video_001", source_index=0, output_name="video01_00001"),
            FrameData("/tmp/video_002/frame_001.jpg", 1, 150.0,
                     source_video="video_002", source_index=0, output_name="video02_00002")
        ]
        
        mock_extraction_result = ExtractionResult(
            frames=frames_with_attribution,
            metadata={'video_count': 2},
            input_type='video_directory',
            temp_dir='/tmp/sharp_frames_test'
        )
        
        analyzed_result = ExtractionResult(
            frames=frames_with_attribution,  # Sharpness already set for simplicity
            metadata={'video_count': 2},
            input_type='video_directory',
            temp_dir='/tmp/sharp_frames_test'
        )
        
        with patch.object(self.processor.extractor, 'extract_frames', return_value=mock_extraction_result), \
             patch.object(self.processor.analyzer, 'calculate_sharpness', return_value=analyzed_result):
            
            result = self.processor.extract_and_analyze(config)
            
            # Verify video attribution is preserved
            assert len(result.frames) == 2
            assert result.frames[0].source_video == "video_001"
            assert result.frames[0].output_name == "video01_00001"
            assert result.frames[1].source_video == "video_002"
            assert result.frames[1].output_name == "video02_00002"
    
    def test_preview_selection_success(self, sample_frames_data):
        """Test selection preview functionality."""
        # Set up current result
        self.processor.current_result = ExtractionResult(
            frames=sample_frames_data,
            metadata={'fps': 30},
            input_type='video'
        )
        
        with patch.object(self.processor.selector, 'preview_selection', return_value=15) as mock_preview:
            count = self.processor.preview_selection('best_n', n=15)
            
            mock_preview.assert_called_once_with(sample_frames_data, 'best_n', n=15)
            assert count == 15
    
    def test_preview_selection_no_extraction_result(self):
        """Test preview selection fails when no extraction result is available."""
        # Ensure no current result
        self.processor.current_result = None
        
        with pytest.raises(RuntimeError, match="No extraction result available"):
            self.processor.preview_selection('best_n', n=10)
    
    def test_preview_selection_different_methods(self, sample_frames_data):
        """Test preview selection with different methods and parameters."""
        self.processor.current_result = ExtractionResult(
            frames=sample_frames_data,
            metadata={'fps': 30},
            input_type='video'
        )
        
        with patch.object(self.processor.selector, 'preview_selection') as mock_preview:
            mock_preview.return_value = 10
            
            # Test best_n
            count = self.processor.preview_selection('best_n', n=10)
            mock_preview.assert_called_with(sample_frames_data, 'best_n', n=10)
            assert count == 10
            
            # Test batched
            mock_preview.return_value = 5
            count = self.processor.preview_selection('batched', batch_count=5)
            mock_preview.assert_called_with(sample_frames_data, 'batched', batch_count=5)
            assert count == 5
            
            # Test outlier_removal
            mock_preview.return_value = 75
            count = self.processor.preview_selection('outlier_removal', factor=1.5)
            mock_preview.assert_called_with(sample_frames_data, 'outlier_removal', factor=1.5)
            assert count == 75
    
    def test_complete_selection_success(self, sample_frames_data, sample_config_video):
        """Test complete selection and save process."""
        config = sample_config_video.copy()
        
        # Set up current result
        self.processor.current_result = ExtractionResult(
            frames=sample_frames_data,
            metadata={'fps': 30},
            input_type='video',
            temp_dir='/tmp/sharp_frames_test'
        )
        
        # Mock selected frames (subset of original)
        selected_frames = sample_frames_data[:10]
        
        with patch.object(self.processor.selector, 'select_frames', return_value=selected_frames) as mock_select, \
             patch.object(self.processor.saver, 'save_frames', return_value=True) as mock_save:
            
            result = self.processor.complete_selection('best_n', config, n=10)
            
            mock_select.assert_called_once_with(sample_frames_data, 'best_n', n=10)
            mock_save.assert_called_once_with(selected_frames, config)
            assert result is True
    
    def test_complete_selection_no_extraction_result(self, sample_config_video):
        """Test complete selection fails when no extraction result is available."""
        config = sample_config_video.copy()
        self.processor.current_result = None
        
        with pytest.raises(RuntimeError, match="No extraction result available"):
            self.processor.complete_selection('best_n', config, n=10)
    
    def test_complete_selection_preserves_video_attribution(self, sample_video_directory_frames, sample_config_video_directory):
        """Test that complete selection preserves video attribution through the pipeline."""
        config = sample_config_video_directory.copy()
        
        # Set up current result with video attribution
        self.processor.current_result = ExtractionResult(
            frames=sample_video_directory_frames,
            metadata={'video_count': 3},
            input_type='video_directory',
            temp_dir='/tmp/sharp_frames_test'
        )
        
        # Mock selection to return subset with video attribution
        selected_frames = sample_video_directory_frames[:5]  # First 5 frames
        
        with patch.object(self.processor.selector, 'select_frames', return_value=selected_frames), \
             patch.object(self.processor.saver, 'save_frames', return_value=True) as mock_save:
            
            result = self.processor.complete_selection('best_n', config, n=5)
            
            # Verify that frames with video attribution were passed to saver
            saved_frames_call = mock_save.call_args[0][0]  # First argument to save_frames
            
            assert len(saved_frames_call) == 5
            for frame in saved_frames_call:
                assert frame.source_video is not None
                assert frame.output_name.startswith('video')
            
            assert result is True
    
    def test_cleanup_temp_directory(self, sample_config_video):
        """Test cleanup of temporary directories."""
        config = sample_config_video.copy()
        
        # Set up result with temp directory
        self.processor.current_result = ExtractionResult(
            frames=[],
            metadata={'fps': 30},
            input_type='video',
            temp_dir='/tmp/sharp_frames_test'
        )
        
        with patch('shutil.rmtree') as mock_rmtree:
            self.processor.cleanup_temp_directory()
            
            mock_rmtree.assert_called_once_with('/tmp/sharp_frames_test')
            # Current result should still exist but temp_dir should be cleared
            assert self.processor.current_result is not None
            assert self.processor.current_result.temp_dir is None
    
    def test_cleanup_temp_directory_no_temp_dir(self, sample_config_directory):
        """Test cleanup when no temp directory exists (e.g., image directory input)."""
        # Set up result without temp directory
        self.processor.current_result = ExtractionResult(
            frames=[],
            metadata={'source_type': 'directory'},
            input_type='directory',
            temp_dir=None
        )
        
        with patch('shutil.rmtree') as mock_rmtree:
            self.processor.cleanup_temp_directory()
            
            # Should not attempt to remove anything
            mock_rmtree.assert_not_called()
    
    def test_cleanup_temp_directory_no_current_result(self):
        """Test cleanup when no current result exists."""
        self.processor.current_result = None
        
        with patch('shutil.rmtree') as mock_rmtree:
            self.processor.cleanup_temp_directory()
            
            mock_rmtree.assert_not_called()
    
    def test_get_current_frame_count(self, sample_frames_data):
        """Test getting current frame count."""
        # No result initially
        assert self.processor.get_current_frame_count() == 0
        
        # With result
        self.processor.current_result = ExtractionResult(
            frames=sample_frames_data,
            metadata={'fps': 30},
            input_type='video'
        )
        
        assert self.processor.get_current_frame_count() == len(sample_frames_data)
    
    def test_get_current_metadata(self, sample_frames_data):
        """Test getting current extraction metadata."""
        # No result initially
        assert self.processor.get_current_metadata() == {}
        
        # With result
        metadata = {'fps': 30, 'duration': 10.0, 'resolution': '1920x1080'}
        self.processor.current_result = ExtractionResult(
            frames=sample_frames_data,
            metadata=metadata,
            input_type='video'
        )
        
        assert self.processor.get_current_metadata() == metadata
    
    def test_reset_current_result(self, sample_frames_data):
        """Test resetting the current result."""
        # Set up a result
        self.processor.current_result = ExtractionResult(
            frames=sample_frames_data,
            metadata={'fps': 30},
            input_type='video'
        )
        
        # Reset
        self.processor.reset_current_result()
        
        assert self.processor.current_result is None
    
    def test_error_handling_in_extraction(self, sample_config_video):
        """Test error handling during extraction phase."""
        config = sample_config_video.copy()
        
        with patch.object(self.processor.extractor, 'extract_frames', side_effect=Exception("Extraction failed")):
            with pytest.raises(Exception, match="Extraction failed"):
                self.processor.extract_and_analyze(config)
            
            # Should not have set current_result on failure
            assert self.processor.current_result is None
    
    def test_error_handling_in_analysis(self, sample_config_video):
        """Test error handling during analysis phase."""
        config = sample_config_video.copy()
        
        mock_extraction_result = ExtractionResult(
            frames=[FrameData("/tmp/frame_001.jpg", 0, 0.0, output_name="00001")],
            metadata={'fps': 30},
            input_type='video'
        )
        
        with patch.object(self.processor.extractor, 'extract_frames', return_value=mock_extraction_result), \
             patch.object(self.processor.analyzer, 'calculate_sharpness', side_effect=Exception("Analysis failed")):
            
            with pytest.raises(Exception, match="Analysis failed"):
                self.processor.extract_and_analyze(config)
            
            # Should not have set current_result on failure
            assert self.processor.current_result is None
    
    def test_component_integration(self, sample_config_video):
        """Test that all components work together properly."""
        config = sample_config_video.copy()
        
        # This test verifies that the TUIProcessor properly orchestrates
        # all components without mocking internal calls
        
        mock_frames = [
            FrameData("/tmp/frame_001.jpg", 0, 100.0, output_name="00001"),
            FrameData("/tmp/frame_002.jpg", 1, 150.0, output_name="00002"),
            FrameData("/tmp/frame_003.jpg", 2, 125.0, output_name="00003")
        ]
        
        with patch.object(self.processor.extractor, 'extract_frames') as mock_extract, \
             patch.object(self.processor.analyzer, 'calculate_sharpness') as mock_analyze, \
             patch.object(self.processor.selector, 'select_frames') as mock_select, \
             patch.object(self.processor.selector, 'preview_selection') as mock_preview, \
             patch.object(self.processor.saver, 'save_frames') as mock_save:
            
            # Set up the chain of calls
            extraction_result = ExtractionResult(frames=mock_frames, metadata={}, input_type='video')
            mock_extract.return_value = extraction_result
            mock_analyze.return_value = extraction_result
            mock_preview.return_value = 2
            mock_select.return_value = mock_frames[:2]
            mock_save.return_value = True
            
            # Execute full workflow
            analyzed_result = self.processor.extract_and_analyze(config)
            preview_count = self.processor.preview_selection('best_n', n=2)
            save_result = self.processor.complete_selection('best_n', config, n=2)
            
            # Verify the chain of calls
            mock_extract.assert_called_once_with(config)
            mock_analyze.assert_called_once_with(extraction_result)
            mock_preview.assert_called_once_with(mock_frames, 'best_n', n=2)
            mock_select.assert_called_once_with(mock_frames, 'best_n', n=2)
            mock_save.assert_called_once_with(mock_frames[:2], config)
            
            # Verify results
            assert analyzed_result == extraction_result
            assert preview_count == 2
            assert save_result is True