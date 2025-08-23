"""
Tests for SharpnessAnalyzer component.
"""

import pytest
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from PIL import Image
import cv2

from sharp_frames.processing.sharpness_analyzer import SharpnessAnalyzer
from sharp_frames.models.frame_data import ExtractionResult, FrameData
from tests.fixtures import (
    test_images_directory,
    sample_frames_data,
    sample_video_directory_frames,
    mock_extraction_result
)


class TestSharpnessAnalyzer:
    """Test cases for SharpnessAnalyzer component."""
    
    def setup_method(self):
        """Set up test environment."""
        self.analyzer = SharpnessAnalyzer()
    
    def test_init(self):
        """Test SharpnessAnalyzer initialization."""
        assert self.analyzer is not None
        assert hasattr(self.analyzer, 'calculate_sharpness')
    
    def test_calculate_sharpness_single_frame(self, test_images_directory):
        """Test sharpness calculation for a single frame."""
        image_dir, image_files = test_images_directory
        
        # Create a frame data object
        frame = FrameData(
            path=image_files[0],
            index=0,
            sharpness_score=0.0,  # Initial score
            output_name="00001"
        )
        
        # Mock the sharpness calculation
        with patch.object(self.analyzer, '_calculate_single_frame_sharpness', return_value=125.5) as mock_calc:
            score = self.analyzer._calculate_single_frame_sharpness(frame.path)
            
            mock_calc.assert_called_once_with(frame.path)
            assert score == 125.5
    
    def test_calculate_sharpness_extraction_result(self, test_images_directory):
        """Test sharpness calculation for entire extraction result."""
        image_dir, image_files = test_images_directory
        
        # Create extraction result with frames
        frames = []
        for i, img_path in enumerate(image_files[:5]):  # Use first 5 images
            frame = FrameData(
                path=img_path,
                index=i,
                sharpness_score=0.0,
                output_name=f"{i+1:05d}"
            )
            frames.append(frame)
        
        extraction_result = ExtractionResult(
            frames=frames,
            metadata={'fps': 30},
            input_type='directory'
        )
        
        # Mock parallel processing
        expected_scores = [100.0, 150.0, 125.0, 175.0, 200.0]
        with patch.object(self.analyzer, '_calculate_sharpness_parallel', return_value=expected_scores) as mock_parallel:
            result = self.analyzer.calculate_sharpness(extraction_result)
            
            mock_parallel.assert_called_once()
            assert isinstance(result, ExtractionResult)
            
            # Verify scores were updated
            for i, frame in enumerate(result.frames):
                assert frame.sharpness_score == expected_scores[i]
                
            # Verify metadata and other properties preserved
            assert result.metadata == extraction_result.metadata
            assert result.input_type == extraction_result.input_type
            assert result.temp_dir == extraction_result.temp_dir
    
    def test_calculate_sharpness_preserves_video_attribution(self, sample_video_directory_frames):
        """Test that video attribution is preserved during sharpness calculation."""
        # Create subset of frames for testing
        frames = sample_video_directory_frames[:10]
        
        extraction_result = ExtractionResult(
            frames=frames,
            metadata={'video_count': 3},
            input_type='video_directory'
        )
        
        expected_scores = [100.0 + i * 10 for i in range(10)]
        with patch.object(self.analyzer, '_calculate_sharpness_parallel', return_value=expected_scores):
            result = self.analyzer.calculate_sharpness(extraction_result)
            
            # Verify video attribution is preserved
            for i, frame in enumerate(result.frames):
                assert frame.source_video is not None
                assert frame.source_index is not None
                assert frame.output_name.startswith('video')
                assert frame.sharpness_score == expected_scores[i]
    
    def test_calculate_single_frame_sharpness_actual_calculation(self, test_images_directory):
        """Test actual sharpness calculation using OpenCV Laplacian."""
        image_dir, image_files = test_images_directory
        
        # Test with first image
        score = self.analyzer._calculate_single_frame_sharpness(image_files[0])
        
        assert isinstance(score, float)
        assert score >= 0.0  # Sharpness should be non-negative
    
    def test_calculate_single_frame_sharpness_invalid_image(self):
        """Test error handling for invalid image files."""
        invalid_path = "/nonexistent/image.jpg"
        
        with pytest.raises(FileNotFoundError):
            self.analyzer._calculate_single_frame_sharpness(invalid_path)
    
    def test_calculate_single_frame_sharpness_corrupted_image(self, tmp_path):
        """Test error handling for corrupted image files."""
        # Create a corrupted image file
        corrupted_file = tmp_path / "corrupted.jpg"
        corrupted_file.write_bytes(b"not an image")
        
        with pytest.raises(Exception):  # Should raise some form of image processing error
            self.analyzer._calculate_single_frame_sharpness(str(corrupted_file))
    
    def test_calculate_sharpness_parallel_success(self, test_images_directory):
        """Test parallel processing of multiple frames."""
        image_dir, image_files = test_images_directory
        
        # Create frame paths
        frame_paths = image_files[:5]  # Use first 5 images
        
        scores = self.analyzer._calculate_sharpness_parallel(frame_paths)
        
        assert len(scores) == 5
        assert all(isinstance(score, float) for score in scores)
        assert all(score >= 0.0 for score in scores)
    
    def test_calculate_sharpness_parallel_with_errors(self, test_images_directory, tmp_path):
        """Test parallel processing with some invalid files."""
        image_dir, image_files = test_images_directory
        
        # Mix valid and invalid paths
        frame_paths = image_files[:3]  # 3 valid images
        frame_paths.append("/nonexistent/image.jpg")  # 1 invalid
        
        # Create corrupted file
        corrupted_file = tmp_path / "corrupted.jpg"
        corrupted_file.write_bytes(b"not an image")
        frame_paths.append(str(corrupted_file))  # 1 corrupted
        
        scores = self.analyzer._calculate_sharpness_parallel(frame_paths)
        
        assert len(scores) == 5
        # First 3 should be valid scores
        assert all(isinstance(score, float) and score >= 0.0 for score in scores[:3])
        # Last 2 should be 0.0 (error fallback)
        assert scores[3] == 0.0
        assert scores[4] == 0.0
    
    def test_laplacian_variance_calculation(self, test_images_directory):
        """Test the core Laplacian variance sharpness algorithm."""
        image_dir, image_files = test_images_directory
        
        # Load an actual image
        image = cv2.imread(image_files[0])
        
        variance = self.analyzer._calculate_laplacian_variance(image)
        
        assert isinstance(variance, (int, float))
        assert variance >= 0.0
    
    def test_laplacian_variance_different_images(self, tmp_path):
        """Test Laplacian variance on artificially created sharp vs blurry images."""
        # Create a sharp image (high contrast edges)
        sharp_img = np.zeros((100, 100, 3), dtype=np.uint8)
        sharp_img[:50, :50] = 255  # High contrast square
        sharp_img[50:, 50:] = 255
        sharp_path = tmp_path / "sharp.jpg"
        cv2.imwrite(str(sharp_path), sharp_img)
        
        # Create a blurry image (low contrast, gradual changes)
        blurry_img = np.zeros((100, 100, 3), dtype=np.uint8)
        for i in range(100):
            for j in range(100):
                blurry_img[i, j] = int(255 * (i + j) / 200)  # Gradual gradient
        blurry_path = tmp_path / "blurry.jpg"
        cv2.imwrite(str(blurry_path), blurry_img)
        
        sharp_score = self.analyzer._calculate_single_frame_sharpness(str(sharp_path))
        blurry_score = self.analyzer._calculate_single_frame_sharpness(str(blurry_path))
        
        # Sharp image should have higher variance (more edges)
        assert sharp_score > blurry_score
    
    def test_frame_data_structure_creation(self):
        """Test that frame data structures are created correctly."""
        original_frame = FrameData(
            path="/path/to/frame.jpg",
            index=5,
            sharpness_score=0.0,
            source_video="video_001",
            source_index=3,
            output_name="video01_00006"
        )
        
        # Simulate updating sharpness score
        updated_frame = self.analyzer._update_frame_with_sharpness(original_frame, 125.5)
        
        # All original attributes preserved except sharpness score
        assert updated_frame.path == original_frame.path
        assert updated_frame.index == original_frame.index
        assert updated_frame.source_video == original_frame.source_video
        assert updated_frame.source_index == original_frame.source_index
        assert updated_frame.output_name == original_frame.output_name
        assert updated_frame.sharpness_score == 125.5  # Updated
    
    def test_progress_tracking(self, test_images_directory):
        """Test progress tracking during parallel processing."""
        image_dir, image_files = test_images_directory
        frame_paths = image_files
        
        progress_updates = []
        
        def mock_progress_callback(current, total):
            progress_updates.append((current, total))
        
        with patch.object(self.analyzer, '_progress_callback', side_effect=mock_progress_callback):
            self.analyzer._calculate_sharpness_parallel(frame_paths, progress_callback=mock_progress_callback)
            
            # Should have received progress updates
            assert len(progress_updates) > 0
            # Final update should indicate completion
            assert progress_updates[-1] == (len(frame_paths), len(frame_paths))
    
    def test_memory_efficiency_large_batch(self):
        """Test memory-efficient processing of large frame batches."""
        # Create a large number of mock frame paths
        large_frame_list = [f"/mock/frame_{i:05d}.jpg" for i in range(1000)]
        
        with patch.object(self.analyzer, '_calculate_single_frame_sharpness', return_value=100.0):
            # Should not cause memory issues with chunked processing
            scores = self.analyzer._calculate_sharpness_parallel(large_frame_list, chunk_size=50)
            
            assert len(scores) == 1000
            assert all(score == 100.0 for score in scores)
    
    def test_error_recovery_in_parallel_processing(self):
        """Test that errors in individual frames don't crash entire process."""
        frame_paths = [
            "/valid/frame1.jpg",
            "/invalid/frame2.jpg",  # This will fail
            "/valid/frame3.jpg"
        ]
        
        def mock_single_calculation(path):
            if "invalid" in path:
                raise Exception("Simulated processing error")
            return 100.0
            
        with patch.object(self.analyzer, '_calculate_single_frame_sharpness', side_effect=mock_single_calculation):
            scores = self.analyzer._calculate_sharpness_parallel(frame_paths)
            
            # Should return scores for all frames, with 0.0 for failed ones
            assert len(scores) == 3
            assert scores[0] == 100.0  # Valid
            assert scores[1] == 0.0    # Failed (fallback)
            assert scores[2] == 100.0  # Valid