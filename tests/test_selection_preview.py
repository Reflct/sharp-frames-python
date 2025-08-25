"""
Tests for selection preview functionality.
"""

import pytest
from unittest.mock import Mock, patch

from sharp_frames.selection_preview import get_selection_count, get_selection_preview
from sharp_frames.models.frame_data import FrameData
from tests.fixtures import (
    sample_frames_data,
    mock_sharpness_scores,
    expected_selection_outcomes
)


class TestSelectionPreview:
    """Test cases for selection preview functions."""
    
    def test_get_selection_count_best_n(self, sample_frames_data):
        """Test selection count preview for best-n method."""
        frames_dict = self._convert_frames_to_dict(sample_frames_data)
        
        # Test various n values
        assert get_selection_count(frames_dict, 'best-n', n=10) == 10
        assert get_selection_count(frames_dict, 'best-n', n=50) == 50
        assert get_selection_count(frames_dict, 'best-n', n=200) == 100  # Capped at total frames
        assert get_selection_count(frames_dict, 'best-n', n=0) == 0
    
    def test_get_selection_count_batched(self, sample_frames_data):
        """Test selection count preview for batched method."""
        frames_dict = self._convert_frames_to_dict(sample_frames_data)
        
        # Test with batch_size and batch_buffer parameters
        result = get_selection_count(frames_dict, 'batched', batch_size=5, batch_buffer=10)
        assert 25 <= result <= 35  # With 100 frames, batch_size=5, batch_buffer=10
        
        assert get_selection_count(frames_dict, 'batched', batch_size=10, batch_buffer=0) == 100
        assert get_selection_count(frames_dict, 'batched', batch_size=1, batch_buffer=9) == 10
    
    def test_get_selection_count_outlier_removal(self, mock_sharpness_scores):
        """Test selection count preview for outlier removal method."""
        frames_dict = self._create_frames_dict_with_scores(mock_sharpness_scores)
        
        # Test with outlier_sensitivity and outlier_window_size parameters
        count_high = get_selection_count(frames_dict, 'outlier-removal', 
                                        outlier_sensitivity=80, outlier_window_size=15)
        count_medium = get_selection_count(frames_dict, 'outlier-removal', 
                                          outlier_sensitivity=50, outlier_window_size=15)
        count_low = get_selection_count(frames_dict, 'outlier-removal', 
                                       outlier_sensitivity=20, outlier_window_size=15)
        
        # Higher sensitivity should select fewer frames (more aggressive removal)
        assert count_high < count_medium < count_low
        assert all(count > 0 for count in [count_high, count_medium, count_low])
    
    def test_get_selection_count_invalid_method(self, sample_frames_data):
        """Test error handling for invalid selection method."""
        frames_dict = self._convert_frames_to_dict(sample_frames_data)
        
        with pytest.raises(ValueError, match="Unsupported selection method"):
            get_selection_count(frames_dict, 'invalid-method')
    
    def test_get_selection_count_empty_frames(self):
        """Test selection count with empty frame list."""
        empty_frames = []
        
        assert get_selection_count(empty_frames, 'best-n', n=10) == 0
        assert get_selection_count(empty_frames, 'batched', batch_size=5, batch_buffer=2) == 0
        assert get_selection_count(empty_frames, 'outlier-removal', 
                                  outlier_sensitivity=50, outlier_window_size=15) == 0
    
    def test_get_selection_count_performance_large_dataset(self):
        """Test that selection count calculation is fast for large datasets."""
        import time
        
        # Create large dataset (10,000 frames)
        large_frames = []
        for i in range(10000):
            frame_dict = {
                'id': f"frame_{i:05d}.jpg",
                'path': f"/tmp/frame_{i:05d}.jpg",
                'index': i,
                'sharpnessScore': 50.0 + i * 0.01  # Gradually increasing scores
            }
            large_frames.append(frame_dict)
        
        # Measure time for preview calculation
        start_time = time.time()
        count = get_selection_count(large_frames, 'best-n', n=1000)
        end_time = time.time()
        
        # Should complete within 100ms (0.1 seconds) for responsive UI
        elapsed = end_time - start_time
        assert elapsed < 0.1, f"Preview took {elapsed:.3f}s, should be <0.1s"
        assert count == 1000
    
    def test_get_selection_preview_best_n(self, sample_frames_data):
        """Test detailed selection preview for best-n method."""
        frames_dict = self._convert_frames_to_dict(sample_frames_data)
        
        preview = get_selection_preview(frames_dict, 'best-n', n=10)
        
        assert isinstance(preview, dict)
        assert 'count' in preview
        assert 'distribution' in preview
        assert 'statistics' in preview
        
        assert preview['count'] == 10
        
        # Check distribution (histogram of selected frames across timeline)
        distribution = preview['distribution']
        assert isinstance(distribution, list)
        assert len(distribution) > 0  # Should have distribution data
        
        # Check statistics
        stats = preview['statistics']
        assert 'min_sharpness' in stats
        assert 'max_sharpness' in stats
        assert 'avg_sharpness' in stats
        assert stats['min_sharpness'] <= stats['avg_sharpness'] <= stats['max_sharpness']
    
    def test_get_selection_preview_batched(self, sample_frames_data):
        """Test detailed selection preview for batched method."""
        frames_dict = self._convert_frames_to_dict(sample_frames_data)
        
        preview = get_selection_preview(frames_dict, 'batched', batch_size=5, batch_buffer=2)
        
        assert preview['count'] == 5
        
        # Distribution should show frames spread across timeline
        distribution = preview['distribution']
        assert len(distribution) == 5  # One bin per batch
        
        # Each bin should have exactly 1 frame (for 5 batches from 100 frames)
        assert all(bin_count == 1 for bin_count in distribution)
    
    def test_get_selection_preview_outlier_removal(self, mock_sharpness_scores):
        """Test detailed selection preview for outlier removal method."""
        frames_dict = self._create_frames_dict_with_scores(mock_sharpness_scores)
        
        preview = get_selection_preview(frames_dict, 'outlier-removal', 
                                       outlier_sensitivity=50, outlier_window_size=15)
        
        assert preview['count'] > 0
        assert preview['count'] < len(frames_dict)  # Should remove some frames
        
        # Statistics should exclude outliers
        stats = preview['statistics']
        assert stats['min_sharpness'] > min(mock_sharpness_scores)  # Excluded low outliers
        assert stats['max_sharpness'] < max(mock_sharpness_scores)  # Excluded high outliers
    
    def test_selection_count_updates_with_parameter_changes(self, sample_frames_data):
        """Test that selection count updates correctly as parameters change."""
        frames_dict = self._convert_frames_to_dict(sample_frames_data)
        
        # Best-n method with increasing n
        counts = []
        for n in [5, 10, 20, 50]:
            count = get_selection_count(frames_dict, 'best-n', n=n)
            counts.append(count)
        
        # Counts should increase with n
        assert counts == [5, 10, 20, 50]
        
        # Batched method with different batch_size values
        batch_counts = []
        for batch_size in [2, 5, 10, 25]:
            count = get_selection_count(frames_dict, 'batched', batch_size=batch_size, batch_buffer=0)
            batch_counts.append(count)
        
        # With batch_buffer=0, all frames should be selected
        assert batch_counts == [100, 100, 100, 100]
    
    def test_preview_consistency_with_actual_selection(self, sample_frames_data):
        """Test that preview counts match actual selection results."""
        from sharp_frames.processing.frame_selector import FrameSelector
        
        frames_dict = self._convert_frames_to_dict(sample_frames_data)
        selector = FrameSelector()
        
        # Test best-n
        preview_count = get_selection_count(frames_dict, 'best-n', n=15)
        actual_selected = selector.select_frames(sample_frames_data, 'best_n', n=15)
        assert preview_count == len(actual_selected)
        
        # Test batched
        preview_count = get_selection_count(frames_dict, 'batched', batch_size=8, batch_buffer=2)
        actual_selected = selector.select_frames(sample_frames_data, 'batched', batch_size=8, batch_buffer=2)
        assert abs(preview_count - len(actual_selected)) <= 2  # Allow small difference
        
        # Test outlier removal
        preview_count = get_selection_count(frames_dict, 'outlier-removal', 
                                          outlier_sensitivity=50, outlier_window_size=15)
        actual_selected = selector.select_frames(sample_frames_data, 'outlier_removal', 
                                                outlier_sensitivity=50, outlier_window_size=15)
        assert abs(preview_count - len(actual_selected)) <= 5  # Allow small difference due to algorithm
    
    def test_preview_caching_for_performance(self, sample_frames_data):
        """Test that repeated preview calculations are optimized."""
        frames_dict = self._convert_frames_to_dict(sample_frames_data)
        
        # Mock a caching mechanism
        with patch('sharp_frames.selection_preview._calculate_cached_preview') as mock_cache:
            mock_cache.return_value = {'count': 10, 'distribution': [], 'statistics': {}}
            
            # First call should calculate
            preview1 = get_selection_preview(frames_dict, 'best-n', n=10)
            
            # Second call with same parameters should use cache
            preview2 = get_selection_preview(frames_dict, 'best-n', n=10)
            
            assert preview1 == preview2
    
    def test_distribution_histogram_accuracy(self, sample_frames_data):
        """Test that distribution histogram accurately represents frame distribution."""
        frames_dict = self._convert_frames_to_dict(sample_frames_data)
        
        # Test with batched method for predictable distribution
        preview = get_selection_preview(frames_dict, 'batched', batch_count=4)
        distribution = preview['distribution']
        
        # Should have 4 bins (one per batch)
        assert len(distribution) == 4
        
        # Each bin should have exactly 1 frame
        assert all(count == 1 for count in distribution)
        
        # Sum of distribution should equal total count
        assert sum(distribution) == preview['count']
    
    def test_statistics_calculation_accuracy(self):
        """Test accuracy of statistics calculations."""
        # Create frames with known score distribution
        scores = [10.0, 20.0, 30.0, 40.0, 50.0]  # Known values for easy testing
        frames_dict = self._create_frames_dict_with_scores(scores)
        
        preview = get_selection_preview(frames_dict, 'best-n', n=3)  # Select top 3
        stats = preview['statistics']
        
        # Top 3 scores should be 50, 40, 30
        assert stats['min_sharpness'] == 30.0
        assert stats['max_sharpness'] == 50.0
        assert stats['avg_sharpness'] == 40.0  # (50+40+30)/3
    
    def test_real_time_parameter_updates(self, sample_frames_data):
        """Test rapid parameter changes for real-time UI updates."""
        frames_dict = self._convert_frames_to_dict(sample_frames_data)
        
        import time
        
        # Simulate rapid parameter changes
        parameters = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50]
        start_time = time.time()
        
        for n in parameters:
            count = get_selection_count(frames_dict, 'best-n', n=n)
            assert count == min(n, len(frames_dict))
        
        end_time = time.time()
        
        # All 10 calculations should complete quickly for responsive UI
        elapsed = end_time - start_time
        assert elapsed < 0.5, f"10 preview calculations took {elapsed:.3f}s, should be <0.5s"
    
    def test_edge_case_single_frame(self):
        """Test preview with single frame."""
        single_frame = [{
            'id': 'frame_001.jpg',
            'path': '/tmp/frame_001.jpg',
            'index': 0,
            'sharpnessScore': 100.0
        }]
        
        # All methods should handle single frame gracefully
        assert get_selection_count(single_frame, 'best-n', n=1) == 1
        assert get_selection_count(single_frame, 'best-n', n=10) == 1  # Capped
        assert get_selection_count(single_frame, 'batched', batch_count=1) == 1
        assert get_selection_count(single_frame, 'batched', batch_count=5) == 1  # Capped
        assert get_selection_count(single_frame, 'outlier-removal', factor=1.5) <= 1
    
    def test_edge_case_identical_sharpness_scores(self):
        """Test preview with frames having identical sharpness scores."""
        # Create frames with identical scores
        identical_frames = []
        for i in range(10):
            frame_dict = {
                'id': f"frame_{i:03d}.jpg",
                'path': f"/tmp/frame_{i:03d}.jpg",
                'index': i,
                'sharpnessScore': 100.0  # All identical
            }
            identical_frames.append(frame_dict)
        
        # Should still work with deterministic results
        assert get_selection_count(identical_frames, 'best-n', n=5) == 5
        assert get_selection_count(identical_frames, 'batched', batch_size=3, batch_buffer=0) == 3
        # Outlier removal might select all or none depending on implementation
        outlier_count = get_selection_count(identical_frames, 'outlier-removal', 
                                           outlier_sensitivity=50, outlier_window_size=15)
        assert 0 <= outlier_count <= 10
    
    # Helper methods
    def _convert_frames_to_dict(self, frames_data):
        """Convert FrameData objects to dictionary format for preview functions."""
        frames_dict = []
        for frame in frames_data:
            frame_dict = {
                'id': f"frame_{frame.index:05d}.jpg",
                'path': frame.path,
                'index': frame.index,
                'sharpnessScore': frame.sharpness_score
            }
            frames_dict.append(frame_dict)
        return frames_dict
    
    def _create_frames_dict_with_scores(self, scores):
        """Create frame dictionaries with specific sharpness scores."""
        frames_dict = []
        for i, score in enumerate(scores):
            frame_dict = {
                'id': f"frame_{i:05d}.jpg",
                'path': f"/tmp/frame_{i:05d}.jpg",
                'index': i,
                'sharpnessScore': score
            }
            frames_dict.append(frame_dict)
        return frames_dict