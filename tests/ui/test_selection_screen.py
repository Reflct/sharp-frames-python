"""Tests for the active interactive selection screen API."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from rich.cells import cell_len
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Button, Input

from sharp_frames.models.frame_data import ExtractionResult, FrameData
from sharp_frames.ui.screens.selection import (
    InputWithControls,
    SelectionScreen,
    SharpnessChart,
)
from sharp_frames.ui.styles import SHARP_FRAMES_CSS


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


def test_frame_summary_reports_excluded_unreadable_inputs(screen):
    screen.extraction_result.metadata["sharpness_analysis"] = {
        "input_count": 23,
        "analyzed_count": 20,
        "unreadable_count": 3,
        "unreadable_paths": ["a.png", "b.png", "c.png"],
    }

    assert screen._frame_count_summary() == (
        "Choose from 20 analyzed frames | 3 unreadable excluded"
    )


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
    assert chart.virtual_size.width == 10_000
    assert chart.min_score == 1.0
    assert chart.max_score == 5_000.0
    assert chart.score_range == 4_999.0
    assert chart.selected_indices == {2, 4, 4_999}
    assert chart.border_title == "Frame selection"


def test_chart_uses_fractional_blocks_for_sub_row_precision():
    assert SharpnessChart._bar_glyph(0.0, chart_y=2, chart_height=3) == "▁"
    assert SharpnessChart._bar_glyph(1.0, chart_y=0, chart_height=3) == "█"
    assert SharpnessChart._bar_glyph(0.5, chart_y=1, chart_height=3) == "▄"
    assert SharpnessChart._bar_glyph(0.5, chart_y=0, chart_height=3) == " "


@pytest.mark.asyncio
async def test_chart_scrolls_across_thousands_of_frames():
    frames = [
        FrameData(f"/tmp/frame_{index:05d}.jpg", index, float(index + 1))
        for index in range(5_000)
    ]
    chart = SharpnessChart(frames)

    class ChartApp(App):
        CSS = SHARP_FRAMES_CSS

        def compose(self) -> ComposeResult:
            yield chart

    async with ChartApp().run_test(size=(80, 24)) as pilot:
        await pilot.pause()

        assert chart.max_scroll_x > 9_000
        assert chart.max_scroll_y == 0
        assert chart.render_line(1).cell_length == chart.size.width
        background_style = chart.get_component_rich_style(
            "sharpness-chart--background"
        )
        title_style = chart.get_component_rich_style(
            "sharpness-chart--title"
        )
        assert background_style.bgcolor is not None
        assert title_style.bgcolor == background_style.bgcolor
        title_line = chart.render_line(0)
        assert "Frames 1-39 of 5,000" in title_line.text
        assert all(
            segment.style.bgcolor == background_style.bgcolor
            for segment in title_line
        )
        bottom_line = chart.render_line(chart.scrollable_content_region.height - 1)
        assert bottom_line.text[:8] == "▁ ▁ ▁ ▁ "

        chart.focus()
        await pilot.press("right")
        await pilot.pause(0.1)
        assert chart.scroll_offset.x == SharpnessChart.FRAME_STRIDE
        assert "Frames 2-40 of 5,000" in chart.render_line(0).text

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


@pytest.mark.asyncio
async def test_input_stepper_uses_compact_secondary_buttons():
    control = InputWithControls(
        value="5", input_id="batch-size", min_value=1, max_value=10
    )

    class StepperApp(App):
        CSS = SHARP_FRAMES_CSS

        def compose(self) -> ComposeResult:
            yield control

    async with StepperApp().run_test(size=(60, 12)) as pilot:
        await pilot.pause()

        decrement = control.query_one("#batch-size_dec", Button)
        increment = control.query_one("#batch-size_inc", Button)
        field = control.query_one("#batch-size", Input)
        button_group = control.query_one(".stepper-controls", Container)

        increment.focus()
        await pilot.pause()
        field_border = field.styles.border_top[1]

        assert str(decrement.label) == "−"
        assert str(increment.label) == "+"
        assert decrement.variant == "default"
        assert increment.variant == "default"
        assert field_border.r == field_border.g == field_border.b
        assert decrement.region.width >= decrement.region.height
        assert increment.region.width >= increment.region.height
        for button in (decrement, increment):
            inner_width = button.region.width - 2  # Tall border consumes one cell per side.
            assert (inner_width - cell_len(str(button.label))) % 2 == 0
        assert button_group.region.width == 14
        assert increment.region.x == decrement.region.right
