"""Tests for the active interactive selection screen API."""

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, PropertyMock, patch

import pytest
from rich.cells import cell_len
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widget import Widget
from textual.widgets import Button, Input, Static

from sharp_frames.models.frame_data import ExtractionResult, FrameData
from sharp_frames.ui.components.raster_preview import RasterImagePreview
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
    processor.selector.select_frames.return_value = extraction_result.frames[:10]
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


@pytest.mark.asyncio
async def test_stale_preview_completion_does_not_update_selection(screen):
    screen._preview_generation = 2

    with (
        patch(
            "sharp_frames.ui.screens.selection.asyncio.sleep",
            new=AsyncMock(),
        ),
        patch(
            "sharp_frames.ui.screens.selection.asyncio.to_thread",
            new=AsyncMock(return_value=screen.extraction_result.frames[:4]),
        ) as to_thread,
        patch.object(screen, "_update_preview_display") as display,
    ):
        await screen._update_preview_debounced(
            1,
            "batched",
            {"batch_size": 5, "batch_buffer": 2},
        )

    to_thread.assert_awaited_once()
    display.assert_not_called()


@pytest.mark.asyncio
async def test_preview_worker_runs_one_selection_thread_at_a_time(screen):
    active = 0
    max_active = 0
    gate = asyncio.Event()

    def blocking_select(frames, method, **params):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        while not gate.is_set():
            time.sleep(0.001)
        active -= 1
        return frames[:3]

    screen.processor.selector.select_frames.side_effect = blocking_select

    with patch(
        "sharp_frames.ui.screens.selection.asyncio.sleep", new=AsyncMock()
    ), patch.object(screen, "_update_preview_display"), patch.object(
        screen, "post_message", new=AsyncMock()
    ):
        screen._update_preview_async()
        await asyncio.sleep(0)
        screen._update_preview_async()
        screen._update_preview_async()
        await asyncio.sleep(0.05)
        gate.set()
        if screen.preview_task is not None:
            await screen.preview_task

    assert max_active == 1


def test_start_over_resets_config_screen_beneath_default_screen(screen):
    default_screen = Mock(spec=[])
    config_screen = Mock(spec=["reset_to_first_step"])
    processing_screen = Mock(spec=[])
    app = Mock()
    app.screen_stack = [default_screen, config_screen, processing_screen, screen]

    with patch.object(
        SelectionScreen, "app", new_callable=PropertyMock, return_value=app
    ):
        screen.action_start_over()

    config_screen.reset_to_first_step.assert_called_once_with()
    assert app.pop_screen.call_count == 2


def test_action_confirm_ignores_repeat_while_saving(screen):
    started = []
    screen.selected_count = 5

    with patch.object(screen, "query_one") as query_one, patch.object(
        screen, "_start_final_processing", side_effect=lambda: started.append(1)
    ):
        query_one.return_value = SimpleNamespace(disabled=False)
        screen._final_processing_task = None
        screen.action_confirm()

        running = SimpleNamespace(done=lambda: False)
        screen._final_processing_task = running
        screen.action_confirm()

    assert started == [1]


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
    screen.selected_count = 4
    screen._final_processing_task = None
    with patch.object(screen, "query_one") as query_one, patch.object(
        screen, "_start_final_processing"
    ) as start:
        query_one.return_value = SimpleNamespace(disabled=False)
        screen.action_confirm()

    start.assert_called_once_with()


def test_confirm_is_ignored_when_no_frames_are_selected(screen):
    screen.selected_count = 0
    screen._final_processing_task = None
    with patch.object(screen, "query_one") as query_one, patch.object(
        screen, "_start_final_processing"
    ) as start:
        query_one.return_value = SimpleNamespace(disabled=True)
        screen.action_confirm()

    start.assert_not_called()


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
    assert chart.inspected_position is None
    assert chart.border_title == "Frame selection"


def test_chart_uses_fractional_blocks_for_sub_row_precision():
    assert SharpnessChart._bar_glyph(0.0, chart_y=2, chart_height=3) == "█"
    assert SharpnessChart._bar_glyph(0.0, chart_y=1, chart_height=3) == " "
    assert SharpnessChart._bar_glyph(1.0, chart_y=0, chart_height=3) == "█"
    assert SharpnessChart._bar_glyph(0.25, chart_y=1, chart_height=3) == "▄"
    assert SharpnessChart._bar_glyph(0.25, chart_y=0, chart_height=3) == " "


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("size", "expected_class"),
    [
        ((120, 56), "-vertical-regular"),
        ((120, 44), "-vertical-compact"),
        ((100, 30), "-vertical-compact"),
        ((80, 24), "-vertical-compact"),
    ],
)
async def test_preview_and_chart_stay_in_viewport_on_short_terminals(
    screen, size, expected_class
):
    class SelectionApp(App):
        CSS = SHARP_FRAMES_CSS

        def on_mount(self):
            self.push_screen(screen)

    async with SelectionApp().run_test(size=size) as pilot:
        await pilot.pause()
        # Simulate a raster-capable terminal with a visible inline preview
        preview = screen.query_one("#frame_preview")
        preview.remove_class("-unsupported")
        preview.display = True
        await pilot.pause()

        assert screen.has_class(expected_class)
        fold = screen.query_one("#main_content").region.bottom
        preview_region = preview.region
        chart_region = screen.query_one("#sharpness_chart").region
        assert preview_region.height > 0
        assert chart_region.height > 0
        assert preview_region.bottom <= fold
        assert chart_region.bottom <= fold
        assert screen.query_one("#action_buttons").region.bottom <= fold


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

        assert chart.outer_size.height > 13
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
        assert bottom_line.text[:8] == "█ █ █ █ "

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


@pytest.mark.asyncio
async def test_clicking_chart_bar_requests_frame_inspection():
    frames = [
        FrameData(f"/tmp/frame_{index:05d}.jpg", index, float(index + 1))
        for index in range(100)
    ]
    chart = SharpnessChart(frames)

    class ChartApp(App):
        CSS = SHARP_FRAMES_CSS

        def __init__(self):
            super().__init__()
            self.inspected = []
            self.opened = []

        def compose(self) -> ComposeResult:
            yield chart

        def on_sharpness_chart_frame_inspect_requested(self, event):
            self.inspected.append(event.frame)

        def on_sharpness_chart_frame_open_requested(self, event):
            self.opened.append(event.frame)

    app = ChartApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.click(chart, offset=(1, 2))
        await pilot.pause()

        assert app.inspected == [frames[0]]
        assert chart.inspected_index == frames[0].index
        assert chart.inspected_position == 0
        assert "Arrows inspect" in chart.border_subtitle

        await pilot.press("right")
        await pilot.pause()
        assert app.inspected[-1] == frames[1]
        assert chart.inspected_index == frames[1].index
        assert chart.inspected_position == 1

        await pilot.press("left")
        await pilot.pause()
        assert app.inspected[-1] == frames[0]
        assert chart.inspected_position == 0

        chart.scroll_to(x=SharpnessChart.FRAME_STRIDE * 2, animate=False)
        await pilot.pause()
        await pilot.click(chart, offset=(1, 2))
        await pilot.pause()

        assert app.inspected[-1] == frames[2]
        assert chart.inspected_index == frames[2].index
        assert chart.inspected_position == 2

        chart._inspect_frame(42)
        await pilot.pause()

        assert app.inspected[-1] == frames[42]
        assert chart.inspected_position == 42
        inspected_left = 42 * SharpnessChart.FRAME_STRIDE
        inspected_right = inspected_left + SharpnessChart.FRAME_STRIDE
        assert int(chart.scroll_offset.x) <= inspected_left
        assert inspected_right <= (
            int(chart.scroll_offset.x) + chart.scrollable_content_region.width
        )

        await pilot.press("o")
        await pilot.pause()
        assert app.opened == [frames[42]]


@pytest.mark.asyncio
async def test_page_keys_inspect_previous_and_next_selected_frames():
    frames = [
        FrameData(f"/tmp/frame_{index:05d}.jpg", index, float(index + 1))
        for index in range(12)
    ]
    chart = SharpnessChart(frames, selected_indices={2, 5, 9})

    class ChartApp(App):
        CSS = SHARP_FRAMES_CSS

        def __init__(self):
            super().__init__()
            self.inspected = []

        def compose(self) -> ComposeResult:
            yield chart

        def on_sharpness_chart_frame_inspect_requested(self, event):
            self.inspected.append(event.frame)

    app = ChartApp()
    async with app.run_test(size=(80, 24)) as pilot:
        chart.focus()

        await pilot.press("pagedown")
        await pilot.pause()
        assert app.inspected[-1] == frames[2]

        await pilot.press("pagedown")
        await pilot.pause()
        assert app.inspected[-1] == frames[5]

        await pilot.press("pageup")
        await pilot.pause()
        assert app.inspected[-1] == frames[2]

        chart._inspect_frame(7)
        await pilot.pause()
        await pilot.press("pagedown")
        await pilot.pause()
        assert app.inspected[-1] == frames[9]

        chart._inspect_frame(7)
        await pilot.pause()
        await pilot.press("pageup")
        await pilot.pause()
        assert app.inspected[-1] == frames[5]

        inspected_count = len(app.inspected)
        chart._inspect_frame(9)
        await pilot.pause()
        await pilot.press("pagedown")
        await pilot.pause()
        assert len(app.inspected) == inspected_count + 1
        assert app.inspected[-1] == frames[9]


@pytest.mark.asyncio
async def test_frame_inspection_handler_keeps_external_open_explicit(screen):
    frame = screen.extraction_result.frames[3]
    event = SimpleNamespace(frame=frame)
    preview = Mock(spec=RasterImagePreview)
    preview.show_frame.return_value = False

    with (
        patch.object(screen, "query_one", return_value=preview),
        patch(
            "sharp_frames.ui.screens.selection.asyncio.to_thread",
            new=AsyncMock(),
        ) as to_thread,
        patch.object(screen, "notify") as notify,
    ):
        await screen.on_sharpness_chart_frame_inspect_requested(event)

    to_thread.assert_not_awaited()
    preview.show_frame.assert_called_once_with(
        frame.path,
        frame_number=frame.index + 1,
        score=frame.sharpness_score,
    )
    assert notify.call_args.kwargs["title"] == "Inline preview unavailable"
    assert "Press O" in notify.call_args.args[0]


@pytest.mark.asyncio
async def test_open_shortcut_opens_inspected_frame_in_default_viewer(screen):
    frame = screen.extraction_result.frames[6]
    event = SimpleNamespace(frame=frame)

    with (
        patch(
            "sharp_frames.ui.screens.selection.asyncio.to_thread",
            new=AsyncMock(),
        ) as to_thread,
        patch.object(screen, "notify") as notify,
    ):
        await screen.on_sharpness_chart_frame_open_requested(event)

    to_thread.assert_awaited_once()
    assert to_thread.await_args.args[1] == frame.path
    assert notify.call_args.kwargs["title"] == "Opened externally"


@pytest.mark.asyncio
async def test_frame_inspection_uses_inline_raster_without_external_open(screen):
    frame = screen.extraction_result.frames[3]
    event = SimpleNamespace(frame=frame)
    preview = Mock(spec=RasterImagePreview)
    preview.show_frame.return_value = True

    with (
        patch.object(screen, "query_one", return_value=preview),
        patch(
            "sharp_frames.ui.screens.selection.asyncio.to_thread",
            new=AsyncMock(),
        ) as to_thread,
        patch.object(screen, "notify") as notify,
    ):
        await screen.on_sharpness_chart_frame_inspect_requested(event)

    to_thread.assert_not_awaited()
    assert notify.call_args.kwargs["title"] == "Inline preview"


@pytest.mark.asyncio
async def test_frame_inspection_falls_back_when_raster_renderer_fails(screen):
    frame = screen.extraction_result.frames[3]
    event = SimpleNamespace(frame=frame)
    preview = Mock(spec=RasterImagePreview)
    preview.show_frame.side_effect = OSError("unsupported image data")

    with (
        patch.object(screen, "query_one", return_value=preview),
        patch(
            "sharp_frames.ui.screens.selection.asyncio.to_thread",
            new=AsyncMock(),
        ) as to_thread,
        patch.object(screen, "notify") as notify,
    ):
        await screen.on_sharpness_chart_frame_inspect_requested(event)

    to_thread.assert_not_awaited()
    assert notify.call_args.kwargs["title"] == "Inline preview unavailable"
    assert "renderer could not show" in notify.call_args.args[0]
    assert "Press O" in notify.call_args.args[0]


def _preview_display_widgets(preview):
    """Map the widgets ``_update_preview_display`` looks up to fakes."""
    return {
        "#sharpness_chart": Mock(),
        "#frame_preview": preview,
        "#confirm_button": SimpleNamespace(label="", disabled=True),
    }


def test_auto_preview_shows_first_selected_frame(screen):
    frames = screen.extraction_result.frames
    preview = Mock(spec=RasterImagePreview)
    preview.raster_supported = True
    widgets = _preview_display_widgets(preview)

    with patch.object(
        screen, "query_one", side_effect=lambda selector, *a, **k: widgets[selector]
    ):
        screen._update_preview_display(3, {5, 8, 12})

    preview.show_frame.assert_called_once_with(
        frames[5].path,
        frame_number=frames[5].index + 1,
        score=frames[5].sharpness_score,
    )


def test_auto_preview_skips_unsupported_raster_terminal(screen):
    preview = Mock(spec=RasterImagePreview)
    preview.raster_supported = False
    widgets = _preview_display_widgets(preview)

    with patch.object(
        screen, "query_one", side_effect=lambda selector, *a, **k: widgets[selector]
    ):
        screen._update_preview_display(3, {5, 8, 12})

    preview.show_frame.assert_not_called()


@pytest.mark.asyncio
async def test_manual_inspection_stops_auto_preview_follow(screen):
    frame = screen.extraction_result.frames[3]
    event = SimpleNamespace(frame=frame)
    preview = Mock(spec=RasterImagePreview)
    preview.raster_supported = True
    preview.show_frame.return_value = True

    with (
        patch.object(screen, "query_one", return_value=preview),
        patch.object(screen, "notify"),
        patch(
            "sharp_frames.ui.screens.selection.asyncio.to_thread",
            new=AsyncMock(),
        ),
    ):
        await screen.on_sharpness_chart_frame_inspect_requested(event)

    assert screen._auto_preview_active is False

    # A later selection recompute must not override the inspected frame.
    preview.show_frame.reset_mock()
    widgets = _preview_display_widgets(preview)
    with patch.object(
        screen, "query_one", side_effect=lambda selector, *a, **k: widgets[selector]
    ):
        screen._update_preview_display(3, {5, 8, 12})

    preview.show_frame.assert_not_called()


@pytest.mark.asyncio
async def test_raster_preview_uses_original_file_and_fit_to_window(tmp_path):
    source = tmp_path / "original-frame.jpg"
    source.write_bytes(b"source image bytes")

    class FakeRasterWidget(Widget):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.image = None

    preview = RasterImagePreview(
        backend_type=FakeRasterWidget,
        backend_name="test raster",
    )

    class PreviewApp(App):
        CSS = SHARP_FRAMES_CSS

        def compose(self) -> ComposeResult:
            yield preview

    async with PreviewApp().run_test(size=(100, 30)) as pilot:
        await pilot.pause()

        assert preview.show_frame(str(source), frame_number=7, score=123.45)
        await pilot.pause()

        raster = preview.query_one("#frame_preview_image", FakeRasterWidget)
        assert raster.image == source
        assert preview.current_path == source
        assert preview.display is True
        assert raster.styles.width.is_auto
        assert raster.styles.height.is_auto
        title = str(
            preview.query_one(".frame-preview-title", Static).render()
        )
        assert title == "Frame 7 · sharpness 123.45 · Press O to open"
        assert "test raster" not in title
        assert "original image fitted to window" not in title.lower()


@pytest.mark.asyncio
async def test_raster_preview_clear_drops_the_backing_file_reference(tmp_path):
    source = tmp_path / "original-frame.jpg"
    source.write_bytes(b"source image bytes")

    class FakeRasterWidget(Widget):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.image = None

    preview = RasterImagePreview(
        backend_type=FakeRasterWidget,
        backend_name="test raster",
    )

    class PreviewApp(App):
        CSS = SHARP_FRAMES_CSS

        def compose(self) -> ComposeResult:
            yield preview

    async with PreviewApp().run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert preview.show_frame(str(source), frame_number=7, score=1.0)
        await pilot.pause()

        preview.clear()
        await pilot.pause()

        raster = preview.query_one("#frame_preview_image", FakeRasterWidget)
        assert raster.image is None
        assert preview.current_path is None
        assert preview.display is False


def test_start_final_processing_clears_inline_preview(screen):
    preview = Mock(spec=RasterImagePreview)
    widgets = {
        "#confirm_button": SimpleNamespace(disabled=False),
        "#method_select": SimpleNamespace(disabled=False),
        "#frame_preview": preview,
    }

    def fake_query_one(selector, *args, **kwargs):
        return widgets[selector]

    screen._final_processing_task = None
    with patch.object(screen, "query_one", side_effect=fake_query_one), patch.object(
        screen, "_process_final_selection", return_value=None
    ), patch("sharp_frames.ui.screens.selection.asyncio.create_task"):
        screen._start_final_processing()

    preview.clear.assert_called_once_with()


@pytest.mark.asyncio
async def test_raster_preview_has_visible_unsupported_terminal_fallback(tmp_path):
    source = tmp_path / "original-frame.jpg"
    source.write_bytes(b"source image bytes")
    preview = RasterImagePreview(backend_type=None)

    class PreviewApp(App):
        CSS = SHARP_FRAMES_CSS

        def compose(self) -> ComposeResult:
            yield preview

    async with PreviewApp().run_test(size=(100, 12)) as pilot:
        await pilot.pause()

        assert not preview.show_frame(str(source), frame_number=7, score=123.45)
        await pilot.pause()

        assert preview.raster_supported is False
        assert preview.display is True
        fallback = str(
            preview.query_one(".frame-preview-fallback", Static).render()
        )
        assert "Press O" in fallback
        assert "Opening the original image" not in fallback


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
