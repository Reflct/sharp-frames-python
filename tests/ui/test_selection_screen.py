"""Tests for the active interactive selection screen API."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from textual.app import App, ComposeResult

from sharp_frames.models.frame_data import ExtractionResult, FrameData
from sharp_frames.ui.screens.selection import (
    InputWithControls,
    SelectionScreen,
    SharpnessChart,
)


@pytest.fixture
def extraction_result():
    frames = [
        FrameData(f"/tmp/frame_{index:05d}.jpg", index, float(index + 1))
        for index in range(20)
    ]
    return ExtractionResult(
        frames=frames,
        metadata={"fps": 30},
        input_type="video",
        temp_dir="/tmp/frames",
    )


@pytest.fixture
def screen(extraction_result):
    processor = Mock()
    processor.preview_selection.return_value = 10
    return SelectionScreen(
        processor,
        extraction_result,
        {
            "input_type": "video",
            "input_path": "/video.mp4",
            "output_dir": "/output",
            "output_format": "jpg",
        },
    )


def test_initial_state_matches_visible_default_controls(screen):
    assert screen.current_method == "batched"
    assert screen.current_parameters == {"batch_size": 5, "batch_buffer": 2}
    assert screen.selected_indices == set()
    assert set(screen.method_definitions) == {
        "best_n",
        "batched",
        "outlier_removal",
    }


def test_method_definitions_expose_valid_defaults_and_ranges(screen):
    for method in screen.method_definitions.values():
        assert method["name"]
        assert len(method["description"]) > 20
        assert method["parameters"]
        for parameter in method["parameters"].values():
            assert parameter["min"] <= parameter["default"] <= parameter["max"]


@pytest.mark.asyncio
async def test_method_change_resets_parameters_to_method_defaults(screen):
    event = SimpleNamespace(
        select=SimpleNamespace(id="method_select"),
        value="best_n",
    )

    with (
        patch.object(screen, "_update_method_description") as description,
        patch.object(
            screen, "_update_parameter_inputs_async", new=AsyncMock()
        ) as inputs,
        patch.object(screen, "_update_preview_async") as preview,
    ):
        screen.on_select_changed(event)
        await asyncio.sleep(0)

    assert screen.current_method == "best_n"
    assert screen.current_parameters == {"n": 300, "min_buffer": 3}
    description.assert_called_once_with()
    inputs.assert_awaited_once_with()
    preview.assert_called_once_with()


def test_parameter_changes_are_clamped_and_trigger_preview(screen):
    with patch.object(screen, "_update_preview_async") as preview:
        screen._handle_parameter_change("batch_size", "1000")

    assert screen.current_parameters["batch_size"] == 100
    preview.assert_called_once_with()


def test_blank_parameter_restores_declared_default(screen):
    screen.current_parameters["batch_size"] = 8

    with patch.object(screen, "_update_preview_async") as preview:
        screen._handle_parameter_change("batch_size", "")

    assert screen.current_parameters["batch_size"] == 5
    preview.assert_called_once_with()


def test_input_change_routes_only_current_method_parameters(screen):
    current_event = SimpleNamespace(
        input=SimpleNamespace(id="param_batched_batch_buffer"), value="7"
    )
    other_event = SimpleNamespace(
        input=SimpleNamespace(id="param_best_n_n"), value="7"
    )

    with patch.object(screen, "_handle_parameter_change") as handle:
        screen.on_input_changed(current_event)
        screen.on_input_changed(other_event)

    handle.assert_called_once_with("batch_buffer", "7")


def test_confirm_delegates_to_final_processing(screen):
    with patch.object(screen, "_start_final_processing") as start:
        screen.action_confirm()

    start.assert_called_once_with()


@pytest.mark.asyncio
async def test_background_selection_passes_method_config_and_parameters(screen):
    screen.current_method = "best_n"
    screen.current_parameters = {"n": 12, "min_buffer": 2}
    screen.processor.complete_selection.return_value = True
    config = {**screen.config, "selection_method": "best_n"}

    result = await screen._execute_selection_in_background(config)

    assert result is True
    screen.processor.complete_selection.assert_called_once_with(
        "best_n", config, n=12, min_buffer=2
    )


def test_selection_preview_message_preserves_payload(screen):
    message = screen.SelectionPreview(14, "best_n", n=14, min_buffer=3)

    assert message.count == 14
    assert message.method == "best_n"
    assert message.params == {"n": 14, "min_buffer": 3}


def test_chart_normalizes_scores_without_discarding_frames(extraction_result):
    frames = [
        FrameData(f"/tmp/frame_{index:05d}.jpg", index, float(index + 1))
        for index in range(5_000)
    ]
    chart = SharpnessChart(frames, selected_indices={2, 4, 4_999})

    assert len(chart.frames) == 5_000
    assert chart.virtual_size.width == 5_000
    assert chart.min_score == 1.0
    assert chart.max_score == 5_000.0
    assert chart.score_range == 4_999.0
    assert chart.selected_indices == {2, 4, 4_999}


@pytest.mark.asyncio
async def test_chart_scrolls_across_thousands_of_frames():
    frames = [
        FrameData(f"/tmp/frame_{index:05d}.jpg", index, float(index + 1))
        for index in range(5_000)
    ]
    chart = SharpnessChart(frames)

    class ChartApp(App):
        def compose(self) -> ComposeResult:
            yield chart

    async with ChartApp().run_test(size=(80, 24)) as pilot:
        await pilot.pause()

        assert chart.max_scroll_x > 4_000
        assert chart.max_scroll_y == 0
        assert chart.render_line(1).cell_length == chart.size.width
        bottom_line = chart.render_line(chart.scrollable_content_region.height - 1)
        assert bottom_line.text[0] == "█"

        chart.focus()
        await pilot.press("right")
        await pilot.pause(0.1)
        assert chart.scroll_offset.x > 0

        await pilot.press("end")
        await pilot.pause()
        assert chart.is_horizontal_scroll_end
        assert chart.render_line(0).text.rstrip().endswith("of 5,000")

        await pilot.press("home")
        await pilot.pause()
        assert chart.scroll_offset.x == 0


def test_input_with_controls_retains_value_before_mount():
    control = InputWithControls(
        value="5", input_id="batch-size", min_value=1, max_value=10
    )

    assert control.value == "5"
    control.value = "7"
    assert control.value == "7"
