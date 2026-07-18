"""Tests for the FrameSelector adapter over canonical selection algorithms."""

from collections import Counter

import pytest

from sharp_frames.models.frame_data import FrameData
from sharp_frames.processing.frame_selector import FrameSelector


def make_frames(scores, source=None, index_offset=0):
    return [
        FrameData(
            path=f"/tmp/{source or 'frames'}/frame_{position:05d}.jpg",
            index=index_offset + position,
            sharpness_score=score,
            source_video=source,
            source_index=position if source else None,
            output_name=f"{index_offset + position + 1:05d}",
        )
        for position, score in enumerate(scores)
    ]


class TestFrameSelector:
    def setup_method(self):
        self.selector = FrameSelector(show_progress=False)

    def test_init(self):
        assert self.selector.show_progress is False

    @pytest.mark.parametrize(
        ("method", "params"),
        [
            ("best_n", {"n": 8, "min_buffer": 2}),
            ("batched", {"batch_size": 4, "batch_buffer": 2}),
            (
                "outlier_removal",
                {"outlier_sensitivity": 70, "outlier_window_size": 7},
            ),
        ],
    )
    def test_preview_is_exact(self, method, params):
        frames = make_frames([100, 95, 90, 20, 100, 95, 90] * 4)

        assert self.selector.preview_selection(frames, method, **params) == len(
            self.selector.select_frames(frames, method, **params)
        )

    def test_empty_input_and_invalid_method(self):
        assert self.selector.select_frames([], "best_n", n=10) == []
        assert self.selector.preview_selection([], "batched") == 0
        with pytest.raises(ValueError, match="Unsupported selection method"):
            self.selector.select_frames(make_frames([100]), "unknown")

    def test_best_n_balances_timeline_and_sharpness(self):
        frames = make_frames([1_000 - index * 10 for index in range(20)])

        selected = self.selector.select_frames(frames, "best_n", n=5, min_buffer=0)
        indices = [frame.index for frame in selected]

        assert len(selected) == 5
        assert all(
            any(start <= index < start + 4 for index in indices)
            for start in range(0, 20, 4)
        )

    def test_best_n_enforces_intervening_frame_buffer(self):
        frames = make_frames(range(10, 3, -1))

        selected = self.selector.select_frames(frames, "best_n", n=3, min_buffer=3)

        assert len(selected) == 2
        assert all(
            right.index - left.index >= 4
            for left, right in zip(selected, selected[1:])
        )

    def test_best_n_returns_original_objects_and_preserves_metadata(self):
        frames = make_frames(range(10), source="video_001")

        selected = self.selector.select_frames(frames, "best_n", n=3, min_buffer=0)

        assert all(any(frame is original for original in frames) for frame in selected)
        assert all(frame.source_video == "video_001" for frame in selected)
        assert [frame.index for frame in selected] == sorted(frame.index for frame in selected)

    def test_best_n_fairly_allocates_across_sources(self):
        frames = [
            *make_frames([1_000] * 10, source="video_a"),
            *make_frames([1] * 10, source="video_b", index_offset=10),
        ]

        selected = self.selector.select_frames(frames, "best_n", n=5, min_buffer=0)

        assert Counter(frame.source_video for frame in selected) == {
            "video_a": 3,
            "video_b": 2,
        }

    def test_batched_selects_one_sharpest_frame_per_source_local_batch(self):
        frames = [
            *make_frames([1, 2, 3, 4, 5, 6], source="video_a"),
            *make_frames([6, 5, 4, 3, 2, 1], source="video_b", index_offset=6),
        ]

        selected = self.selector.select_frames(
            frames, "batched", batch_size=4, batch_buffer=0
        )

        assert [frame.index for frame in selected] == [3, 5, 6, 10]

    def test_outlier_removal_removes_local_blur_but_keeps_sharp_peaks(self):
        frames = make_frames([100, 100, 100, 1, 100, 300, 100, 100, 100])

        selected = self.selector.select_frames(
            frames,
            "outlier_removal",
            outlier_sensitivity=100,
            outlier_window_size=7,
        )
        selected_scores = [frame.sharpness_score for frame in selected]

        assert 1 not in selected_scores
        assert 300 in selected_scores

    def test_outlier_sensitivity_zero_keeps_every_frame(self):
        frames = make_frames([100, 100, 1, 100, 100])

        selected = self.selector.select_frames(
            frames,
            "outlier_removal",
            outlier_sensitivity=0,
            outlier_window_size=5,
        )

        assert selected == frames

    def test_selection_is_deterministic(self):
        frames = make_frames([50 + ((index * 37) % 101) for index in range(100)])

        first = self.selector.select_frames(frames, "best_n", n=20, min_buffer=2)
        second = self.selector.select_frames(frames, "best_n", n=20, min_buffer=2)

        assert [frame.index for frame in first] == [frame.index for frame in second]
