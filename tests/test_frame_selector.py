"""
Tests for FrameSelector component.
"""

import pytest
from unittest.mock import Mock, patch

from sharp_frames.processing.frame_selector import FrameSelector
from sharp_frames.models.frame_data import FrameData
from tests.fixtures import (
    sample_frames_data,
    mock_sharpness_scores,
    expected_selection_outcomes
)


class TestFrameSelector:
    """Test cases for FrameSelector component."""
    
    def setup_method(self):
        """Set up test environment."""
        self.selector = FrameSelector()
    
    def test_init(self):
        """Test FrameSelector initialization."""
        assert self.selector is not None
        assert hasattr(self.selector, 'preview_selection')
        assert hasattr(self.selector, 'select_frames')
    
    def test_preview_selection_best_n(self, sample_frames_data):
        """Test preview count for best-n selection method."""
        frames = sample_frames_data
        
        # Test various n values
        assert self.selector.preview_selection(frames, 'best_n', n=10) == 10
        assert self.selector.preview_selection(frames, 'best_n', n=50) == 50
        assert self.selector.preview_selection(frames, 'best_n', n=200) == 100  # Capped at total frames
        assert self.selector.preview_selection(frames, 'best_n', n=0) == 0
    
    def test_preview_selection_batched(self, sample_frames_data):
        """Test preview count for batched selection method."""
        frames = sample_frames_data
        
        # Test with batch_size and batch_buffer parameters (legacy compatibility)
        # With 100 frames, batch_size=5, batch_buffer=2 means we select 5, skip 2, repeat
        # This gives us approximately 100 / (5+2) * 5 = ~71 frames
        result = self.selector.preview_selection(frames, 'batched', batch_size=5, batch_buffer=2)
        assert 60 <= result <= 75  # Allow some flexibility in the calculation
        
        # Simple case: batch_size=10, batch_buffer=0 (no skipping)
        assert self.selector.preview_selection(frames, 'batched', batch_size=10, batch_buffer=0) == 100
        
        # Edge case: batch_size=1, batch_buffer=9 (select 1, skip 9)
        assert self.selector.preview_selection(frames, 'batched', batch_size=1, batch_buffer=9) == 10
    
    def test_preview_selection_outlier_removal(self, mock_sharpness_scores):
        """Test preview count for outlier removal method."""
        # Create frames with predictable sharpness distribution
        frames = []
        for i, score in enumerate(mock_sharpness_scores):
            frame = FrameData(
                path=f"/tmp/frame_{i:05d}.jpg",
                index=i,
                sharpness_score=score,
                output_name=f"{i+1:05d}"
            )
            frames.append(frame)
        
        # With outlier_sensitivity and outlier_window_size parameters (legacy compatibility)
        # Higher sensitivity (closer to 100) removes more outliers
        count_high = self.selector.preview_selection(frames, 'outlier_removal', 
                                                     outlier_sensitivity=80, outlier_window_size=15)
        count_medium = self.selector.preview_selection(frames, 'outlier_removal', 
                                                       outlier_sensitivity=50, outlier_window_size=15)
        count_low = self.selector.preview_selection(frames, 'outlier_removal', 
                                                    outlier_sensitivity=20, outlier_window_size=15)
        
        # Higher sensitivity should select fewer frames (more aggressive removal)
        assert count_high < count_medium < count_low
        assert all(count > 0 for count in [count_05, count_15, count_20])
    
    def test_preview_selection_invalid_method(self, sample_frames_data):
        """Test error handling for invalid selection method."""
        frames = sample_frames_data
        
        with pytest.raises(ValueError, match="Unsupported selection method"):
            self.selector.preview_selection(frames, 'invalid_method')
    
    def test_preview_selection_empty_frames(self):
        """Test preview with empty frame list."""
        empty_frames = []
        
        assert self.selector.preview_selection(empty_frames, 'best_n', n=10) == 0
        assert self.selector.preview_selection(empty_frames, 'batched', batch_size=5, batch_buffer=2) == 0
        assert self.selector.preview_selection(empty_frames, 'outlier_removal', 
                                              outlier_sensitivity=50, outlier_window_size=15) == 0
    
    def test_select_frames_best_n(self, sample_frames_data):
        """Test actual frame selection using best-n method."""
        frames = sample_frames_data
        n = 10
        
        selected = self.selector.select_frames(frames, 'best_n', n=n)
        
        assert len(selected) == n
        assert all(isinstance(frame, FrameData) for frame in selected)
        
        # Verify frames are sorted by sharpness (highest first)
        scores = [frame.sharpness_score for frame in selected]
        assert scores == sorted(scores, reverse=True)
        
        # Verify these are actually the top n frames
        all_scores = [frame.sharpness_score for frame in frames]
        top_n_scores = sorted(all_scores, reverse=True)[:n]
        assert scores == top_n_scores
    
    def test_select_frames_batched(self, sample_frames_data):
        """Test actual frame selection using batched method."""
        frames = sample_frames_data  # 100 frames
        batch_size = 5
        batch_buffer = 10
        
        selected = self.selector.select_frames(frames, 'batched', batch_size=batch_size, batch_buffer=batch_buffer)
        
        # With batch_size=5 and batch_buffer=10, we select 5 frames, skip 10, repeat
        # Expected number: floor(100 / (5+10)) * 5 = floor(6.67) * 5 = 6 * 5 = 30 frames
        # Plus any remainder frames in the last incomplete batch
        assert 25 <= len(selected) <= 35
        assert all(isinstance(frame, FrameData) for frame in selected)
        
        # Verify frames come in batches with gaps
        indices = [frame.index for frame in selected]
        indices.sort()
        
        # Check that frames come in groups (batches)
        # Can't check exact indices as it depends on sharpness within each batch
    
    def test_select_frames_outlier_removal(self, mock_sharpness_scores):
        """Test actual frame selection using outlier removal method."""
        # Create frames with known score distribution
        frames = []
        for i, score in enumerate(mock_sharpness_scores):
            frame = FrameData(
                path=f"/tmp/frame_{i:05d}.jpg",
                index=i,
                sharpness_score=score,
                output_name=f"{i+1:05d}"
            )
            frames.append(frame)
        
        selected = self.selector.select_frames(frames, 'outlier_removal', 
                                              outlier_sensitivity=50, outlier_window_size=15)
        
        assert len(selected) > 0
        assert len(selected) < len(frames)  # Should remove some frames
        assert all(isinstance(frame, FrameData) for frame in selected)
        
        # Verify outliers were removed (very high and very low scores)
        selected_scores = [frame.sharpness_score for frame in selected]
        
        # Should not include the extreme outliers
        # Very low scores (10-30) and very high scores (200-300) should be removed
        assert all(score > 40 for score in selected_scores)  # No very low scores
        assert all(score < 180 for score in selected_scores)  # No very high scores
    
    def test_select_frames_preserves_frame_data(self, sample_frames_data):
        """Test that all frame data attributes are preserved during selection."""
        # Add video attribution to some frames
        frames = sample_frames_data[:10]
        for i, frame in enumerate(frames):
            if i % 3 == 0:  # Every 3rd frame has video attribution
                frame.source_video = f"video_{i//3 + 1:03d}"
                frame.source_index = i % 10
                frame.output_name = f"video{i//3 + 1:02d}_{i+1:05d}"
        
        selected = self.selector.select_frames(frames, 'best_n', n=5)
        
        # Verify all attributes are preserved
        for frame in selected:
            # Find original frame
            original = next(f for f in frames if f.index == frame.index)
            
            assert frame.path == original.path
            assert frame.index == original.index
            assert frame.sharpness_score == original.sharpness_score
            assert frame.source_video == original.source_video
            assert frame.source_index == original.source_index
            assert frame.output_name == original.output_name
    
    def test_select_frames_maintains_order_within_method(self, sample_frames_data):
        """Test that frame selection maintains consistent ordering."""
        frames = sample_frames_data
        
        # Run selection multiple times
        selected1 = self.selector.select_frames(frames, 'best_n', n=10)
        selected2 = self.selector.select_frames(frames, 'best_n', n=10)
        
        # Should get same results
        assert len(selected1) == len(selected2)
        for f1, f2 in zip(selected1, selected2):
            assert f1.index == f2.index
            assert f1.sharpness_score == f2.sharpness_score
    
    def test_select_frames_edge_cases(self, sample_frames_data):
        """Test edge cases in frame selection."""
        frames = sample_frames_data
        
        # Select more frames than available
        selected = self.selector.select_frames(frames, 'best_n', n=200)
        assert len(selected) == len(frames)
        
        # Select zero frames
        selected = self.selector.select_frames(frames, 'best_n', n=0)
        assert len(selected) == 0
        
        # Single frame
        single_frame = frames[:1]
        selected = self.selector.select_frames(single_frame, 'best_n', n=10)
        assert len(selected) == 1
    
    def test_best_n_weighted_scoring(self):
        """Test that best-n selection uses weighted scoring combining sharpness and distribution."""
        # Create frames with specific scores to test weighting
        frames = []
        for i in range(10):
            frame = FrameData(
                path=f"/tmp/frame_{i:05d}.jpg",
                index=i,
                sharpness_score=100.0 + i * 10,  # Increasing sharpness
                output_name=f"{i+1:05d}"
            )
            frames.append(frame)
        
        with patch.object(self.selector, '_calculate_weighted_scores') as mock_weighted:
            # Mock weighted scores that favor distribution over raw sharpness
            mock_weighted.return_value = [50 + i * 5 for i in range(10)]  # Different from sharpness scores
            
            selected = self.selector.select_frames(frames, 'best_n', n=5)
            
            mock_weighted.assert_called_once_with(frames)
            assert len(selected) == 5
    
    def test_batched_selection_algorithm(self):
        """Test the batched selection algorithm distributes frames correctly."""
        # Create 20 frames
        frames = []
        for i in range(20):
            frame = FrameData(
                path=f"/tmp/frame_{i:05d}.jpg",
                index=i,
                sharpness_score=50.0 + i * 2,  # Varying scores
                output_name=f"{i+1:05d}"
            )
            frames.append(frame)
        
        # Select 4 batches from 20 frames
        selected = self.selector.select_frames(frames, 'batched', batch_size=4, batch_buffer=0)
        
        assert len(selected) == 4
        
        # Verify frames come from different batches
        # Batch 1: frames 0-4, Batch 2: frames 5-9, etc.
        selected_indices = sorted([frame.index for frame in selected])
        
        # Should have one frame from each batch range
        assert any(0 <= idx <= 4 for idx in selected_indices)  # Batch 1
        assert any(5 <= idx <= 9 for idx in selected_indices)  # Batch 2
        assert any(10 <= idx <= 14 for idx in selected_indices)  # Batch 3
        assert any(15 <= idx <= 19 for idx in selected_indices)  # Batch 4
    
    def test_outlier_removal_algorithm(self):
        """Test the outlier removal algorithm correctly identifies and removes outliers."""
        # Create frames with known distribution
        # Most frames: scores 100-150 (normal range)
        # Outliers: scores 10-20 (too low) and 300-400 (too high)
        frames = []
        scores = ([15, 12, 18] +  # Low outliers
                 [100 + i * 2 for i in range(25)] +  # Normal range
                 [350, 380, 320])  # High outliers
        
        for i, score in enumerate(scores):
            frame = FrameData(
                path=f"/tmp/frame_{i:05d}.jpg",
                index=i,
                sharpness_score=score,
                output_name=f"{i+1:05d}"
            )
            frames.append(frame)
        
        selected = self.selector.select_frames(frames, 'outlier_removal', 
                                              outlier_sensitivity=50, outlier_window_size=15)
        selected_scores = [frame.sharpness_score for frame in selected]
        
        # Should exclude the extreme outliers
        assert all(score >= 50 for score in selected_scores)  # No very low scores
        assert all(score <= 200 for score in selected_scores)  # No very high scores
        
        # Should keep the normal range frames
        assert len(selected) >= 20  # Most of the 25 normal frames should remain