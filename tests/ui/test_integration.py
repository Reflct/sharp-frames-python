"""Integration tests for the active Textual two-phase workflow."""

from unittest.mock import Mock, PropertyMock, patch

import pytest
from textual.app import App
from textual.containers import Container
from textual.notifications import Notification
from textual.worker import WorkerState
from textual.widgets import (
    Button,
    Checkbox,
    Input,
    RadioSet,
    Select,
    Static,
)

from sharp_frames.models.frame_data import ExtractionResult, FrameData
from sharp_frames.ui.app import SharpFramesApp
from sharp_frames.ui.constants import WorkerNames
from sharp_frames.ui.screens.configuration import (
    AsciiTitleShimmer,
    ConfigurationForm,
)
from sharp_frames.ui.screens.processing import BlockProgressBar, ProcessingScreen
from sharp_frames.ui.screens.selection import (
    InputWithControls,
    SelectionScreen,
    SharpnessChart,
)
from sharp_frames.ui.styles import SHARP_FRAMES_CSS
from sharp_frames.ui.utils.error_analysis import ErrorContext


class ScreenHarness(App):
    """Minimal app that mounts one production screen for DOM assertions."""

    def __init__(self, target_screen):
        super().__init__()
        self.target_screen = target_screen

    def on_mount(self):
        self.push_screen(self.target_screen)


class StyledScreenHarness(ScreenHarness):
    """Screen harness using the production application stylesheet."""

    CSS = SHARP_FRAMES_CSS


def _extraction_result(frame_count=10):
    return ExtractionResult(
        frames=[
            FrameData(f"/tmp/frame_{index:05d}.jpg", index, float(index + 1))
            for index in range(frame_count)
        ],
        metadata={"fps": 10},
        input_type="video",
        temp_dir="/tmp/frames",
    )


def test_app_initialization_and_path_detection():
    app = SharpFramesApp()

    assert app.TITLE == "Sharp Frames - by Reflct.app"
    assert app._looks_like_file_path("/absolute/video.mp4") is True
    assert app._looks_like_file_path(r"C:\\video.mp4") is True
    assert app._looks_like_file_path("../relative/video.mp4") is True
    assert app._looks_like_file_path("ordinary text") is False


def test_limited_notifications_keep_only_the_newest_three_in_a_channel():
    app = SharpFramesApp()
    unrelated = Notification(
        "Something else happened",
        title="Other notification",
        timeout=60,
    )
    app._notifications.add(unrelated)

    for frame_number in range(1, 6):
        app.notify_limited(
            f"Frame {frame_number}",
            channel="frame-preview",
            limit=3,
            title="Inline preview",
            timeout=60,
        )

    frame_notifications = [
        notification
        for notification in app._notifications
        if notification.title == "Inline preview"
    ]
    assert [item.message for item in frame_notifications] == [
        "Frame 3",
        "Frame 4",
        "Frame 5",
    ]
    assert unrelated in app._notifications


@pytest.mark.asyncio
async def test_configuration_screen_mounts_current_wizard_controls():
    form = ConfigurationForm()

    async with ScreenHarness(form).run_test() as pilot:
        await pilot.pause(0.2)

        assert str(form.query_one("#step-info", Static).render())
        assert str(form.query_one("#next-btn", Button).label) == "Next"
        assert form.query_one("#back-btn", Button).disabled is True
        assert form.get_current_step_name() == "input_type"


def test_title_shimmer_changes_only_color_across_the_full_title():
    title_markup = next(
        value
        for value in ConfigurationForm.compose.__code__.co_consts
        if isinstance(value, str) and "███████" in value
    )
    title = AsciiTitleShimmer(title_markup)
    base_frame = title.frames[0]
    base_span_count = len(base_frame.spans)

    assert all(frame.plain == base_frame.plain for frame in title.frames)
    assert title.frames[-1].spans == base_frame.spans

    shimmer_spans = [
        span
        for frame in title.frames[1:-1]
        for span in frame.spans[base_span_count:]
    ]
    assert shimmer_spans
    assert AsciiTitleShimmer._CORE_COLOR in {
        str(span.style) for span in shimmer_spans
    }

    shimmer_columns = []
    for span in shimmer_spans:
        line_start = base_frame.plain.rfind("\n", 0, span.start) + 1
        shimmer_columns.append(span.start - line_start)

    occupied_columns = [
        column
        for row in base_frame.plain.splitlines()
        for column, character in enumerate(row)
        if not character.isspace()
    ]
    assert min(shimmer_columns) == min(occupied_columns)
    assert max(shimmer_columns) == max(occupied_columns)


@pytest.mark.asyncio
async def test_title_shimmer_finishes_on_the_original_title(monkeypatch):
    monkeypatch.setattr(AsciiTitleShimmer, "INITIAL_DELAY_SECONDS", 0.001)
    monkeypatch.setattr(AsciiTitleShimmer, "FRAME_INTERVAL_SECONDS", 0.005)

    # The final frame renders the same spans as the initial one, so completion
    # must be observed through the frame callbacks rather than the render
    # output. Timers fire late on slow CI runners; poll with a deadline
    # instead of sleeping for the nominal animation duration.
    shown_frames = []
    original_show_frame = AsciiTitleShimmer._show_frame

    def recording_show_frame(self, frame_index):
        shown_frames.append(frame_index)
        original_show_frame(self, frame_index)

    monkeypatch.setattr(AsciiTitleShimmer, "_show_frame", recording_show_frame)
    form = ConfigurationForm()

    async with ScreenHarness(form).run_test() as pilot:
        title = form.query_one("#ascii-title", AsciiTitleShimmer)
        last_frame_index = len(title.frames) - 1
        for _ in range(200):
            if shown_frames and shown_frames[-1] == last_frame_index:
                break
            await pilot.pause(0.05)
        assert shown_frames and shown_frames[-1] == last_frame_index

        rendered = title.render()
        assert rendered.plain == title.frames[-1].plain
        assert [
            (span.start, span.end) for span in rendered.spans
        ] == [
            (span.start, span.end) for span in title.frames[-1].spans
        ]


@pytest.mark.asyncio
async def test_title_shimmer_stays_static_when_animations_are_disabled():
    form = ConfigurationForm()
    app = ScreenHarness(form)
    app.animation_level = "none"

    async with app.run_test():
        title = form.query_one("#ascii-title", AsciiTitleShimmer)
        rendered = title.render()

        assert rendered.plain == title.frames[0].plain
        assert [
            (span.start, span.end) for span in rendered.spans
        ] == [
            (span.start, span.end) for span in title.frames[0].spans
        ]


@pytest.mark.asyncio
async def test_configuration_form_caps_fields_on_wide_terminals():
    form = ConfigurationForm()
    form.current_step = form.steps.index("input_path")
    form.config_data = {"input_type": "video"}

    async with StyledScreenHarness(form).run_test(size=(240, 50)) as pilot:
        await pilot.pause(0.2)

        form_container = form.query_one("#main-container", Container)
        path_input = form.query_one("#input-path", Input)

        assert form_container.outer_size.width == 110
        assert path_input.size.width < 110
        assert form_container.region.x == (
            240 - form_container.outer_size.width
        ) // 2


@pytest.mark.asyncio
async def test_configuration_form_remains_fluid_below_its_width_cap():
    form = ConfigurationForm()
    form.current_step = form.steps.index("input_path")
    form.config_data = {"input_type": "video"}

    async with StyledScreenHarness(form).run_test(size=(80, 40)) as pilot:
        await pilot.pause(0.2)

        form_container = form.query_one("#main-container", Container)
        path_input = form.query_one("#input-path", Input)

        assert form_container.outer_size.width == 80
        assert path_input.outer_size.width < 80


@pytest.mark.asyncio
async def test_selection_caps_controls_but_keeps_chart_fluid():
    result = _extraction_result(frame_count=20)
    processor = Mock()
    processor.preview_selection.return_value = 4
    processor.selector.select_frames.return_value = result.frames[:4]
    screen = SelectionScreen(
        processor,
        result,
        {"input_type": "video", "output_dir": "/output"},
    )

    async with StyledScreenHarness(screen).run_test(size=(240, 60)) as pilot:
        await pilot.pause(0.25)

        controls = screen.query_one("#controls_section")
        chart = screen.query_one("#sharpness_chart", SharpnessChart)

        assert controls.outer_size.width == 120
        assert controls.region.x == (240 - controls.outer_size.width) // 2
        assert chart.outer_size.width > controls.outer_size.width
        assert chart.outer_size.height > 13


@pytest.mark.asyncio
async def test_parameter_controls_have_one_row_between_groups():
    result = _extraction_result(frame_count=20)
    processor = Mock()
    processor.preview_selection.return_value = 4
    processor.selector.select_frames.return_value = result.frames[:4]
    screen = SelectionScreen(
        processor,
        result,
        {"input_type": "video", "output_dir": "/output"},
    )

    async with StyledScreenHarness(screen).run_test(size=(160, 60)) as pilot:
        await pilot.pause(0.25)

        title = screen.query_one("#parameter_container .control_label")
        parameter_inputs = screen.query_one("#parameter_inputs", Container)
        labels = list(parameter_inputs.query(".param_label"))
        controls = list(parameter_inputs.query(InputWithControls))

        assert labels[0].region.y - title.region.bottom == 1
        assert controls[0].region.y == labels[0].region.bottom
        assert labels[1].region.y - controls[0].region.bottom == 1
        assert controls[1].region.y == labels[1].region.bottom
        assert controls[1].styles.margin.bottom == 0


@pytest.mark.asyncio
async def test_processing_status_caps_width_on_wide_terminals():
    screen = ProcessingScreen(
        {
            "input_type": "video",
            "input_path": "/video.mp4",
            "output_dir": "/output",
        }
    )

    with patch.object(screen, "start_phase_1_processing"):
        async with StyledScreenHarness(screen).run_test(
            size=(240, 50)
        ) as pilot:
            await pilot.pause(0.2)

            status = screen.query_one("#processing-container", Container)

            assert status.outer_size.width == 84
            assert status.region.x == (240 - status.outer_size.width) // 2


@pytest.mark.asyncio
async def test_processing_progress_shows_one_count_and_real_percentage():
    screen = ProcessingScreen(
        {
            "input_type": "video",
            "input_path": "/video.mp4",
            "output_dir": "/output",
        }
    )

    with patch.object(screen, "start_phase_1_processing"):
        async with StyledScreenHarness(screen).run_test(
            size=(100, 40)
        ) as pilot:
            await pilot.pause(0.2)
            screen._update_progress_ui(
                "extraction",
                current=650,
                total=1_814,
                total_progress=35.83,
                description="Extracted 650/1814 frames",
            )
            await pilot.pause()

            status = str(screen.query_one("#status-text", Static).render())
            count = str(screen.query_one("#phase-text", Static).render())
            detail = str(screen.query_one("#detail-text", Static).render())
            progress = screen.query_one("#progress-bar", BlockProgressBar)

            assert status == "Extracting frames · Phase 1 of 2"
            assert count == "650 of 1,814 frames"
            assert detail == ""
            assert screen.query_one("#detail-text", Static).display is False
            assert progress.total == 100
            assert progress.progress == pytest.approx(35.83)
            rendered_bar = progress.render()
            filled_style = progress.get_component_rich_style(
                "block-progress--filled"
            )
            assert filled_style.bgcolor is not None
            assert len(rendered_bar.plain) == progress.size.width
            assert not list(screen.query("#processing-kicker"))

            cancel = screen.query_one("#cancel-processing", Button)
            cancel.focus()
            await pilot.pause()
            assert cancel.styles.text_style.reverse is False


@pytest.mark.asyncio
async def test_enter_advances_without_toggling_focused_checkbox():
    form = ConfigurationForm()
    form.config_data = {"input_type": "video"}

    async with ScreenHarness(form).run_test() as pilot:
        form.current_step = form.steps.index("force_overwrite")
        form.show_current_step()
        await pilot.pause(0.2)

        checkbox = form.query_one("#force-overwrite", Checkbox)
        checkbox.focus()
        assert checkbox.value is False

        await pilot.press("enter")
        await pilot.pause()

        assert form.get_current_step_name() == "confirm"
        assert form.config_data["force_overwrite"] is False


@pytest.mark.asyncio
async def test_space_toggles_focused_checkbox_without_advancing():
    form = ConfigurationForm()
    form.config_data = {"input_type": "video"}

    async with ScreenHarness(form).run_test() as pilot:
        form.current_step = form.steps.index("force_overwrite")
        form.show_current_step()
        await pilot.pause(0.2)

        checkbox = form.query_one("#force-overwrite", Checkbox)
        checkbox.focus()
        await pilot.press("space")
        await pilot.pause()

        assert checkbox.value is True
        assert form.get_current_step_name() == "force_overwrite"


@pytest.mark.asyncio
async def test_space_selects_focused_radio_button_without_advancing():
    form = ConfigurationForm()

    async with ScreenHarness(form).run_test() as pilot:
        await pilot.pause(0.2)

        radio_set = form.query_one("#input-type-selection", RadioSet)
        radio_set.focus()
        await pilot.press("down", "space")
        await pilot.pause()

        assert radio_set.pressed_index == 1
        assert form.get_current_step_name() == "input_type"


@pytest.mark.asyncio
async def test_space_selects_highlighted_dropdown_option():
    form = ConfigurationForm()
    form.config_data = {"input_type": "video"}

    async with ScreenHarness(form).run_test() as pilot:
        form.current_step = form.steps.index("output_format")
        form.show_current_step()
        await pilot.pause(0.2)

        select = form.query_one("#format-select", Select)
        select.focus()
        await pilot.press("space", "down", "space")
        await pilot.pause()

        assert select.value == "png"
        assert select.expanded is False
        assert form.get_current_step_name() == "output_format"


@pytest.mark.asyncio
async def test_enter_advances_input_step_exactly_once():
    form = ConfigurationForm()
    form.config_data = {"input_type": "video"}
    handler = form.step_handlers["input_path"]

    with (
        patch.object(handler, "validate", return_value=True),
        patch.object(
            handler,
            "get_data",
            return_value={"input_path": "/tmp/video.mp4"},
        ),
    ):
        async with ScreenHarness(form).run_test() as pilot:
            form.current_step = form.steps.index("input_path")
            form.show_current_step()
            await pilot.pause(0.2)

            form.query_one("#input-path").focus()
            await pilot.press("enter")
            await pilot.pause()

            assert form.get_current_step_name() == "output_dir"


@pytest.mark.asyncio
async def test_selection_enter_confirms_with_method_menu_focused():
    processor = Mock()
    processor.preview_selection.return_value = 4
    processor.selector.select_frames.return_value = _extraction_result().frames[:4]
    screen = SelectionScreen(
        processor,
        _extraction_result(),
        {"input_type": "video", "output_dir": "/output"},
    )

    with patch.object(screen, "_start_final_processing") as process:
        async with ScreenHarness(screen).run_test() as pilot:
            await pilot.pause(0.2)
            method_select = screen.query_one("#method_select", Select)
            method_select.focus()

            await pilot.press("enter")
            await pilot.pause()

            process.assert_called_once_with()
            assert method_select.expanded is False


@pytest.mark.asyncio
async def test_selection_space_chooses_highlighted_method():
    processor = Mock()
    processor.preview_selection.return_value = 4
    processor.selector.select_frames.return_value = _extraction_result().frames[:4]
    screen = SelectionScreen(
        processor,
        _extraction_result(),
        {"input_type": "video", "output_dir": "/output"},
    )

    async with ScreenHarness(screen).run_test() as pilot:
        await pilot.pause(0.2)
        method_select = screen.query_one("#method_select", Select)
        method_select.focus()

        await pilot.press("space", "up", "space")
        await pilot.pause(0.2)

        assert method_select.value == "best_n"
        assert method_select.expanded is False
        assert screen.current_method == "best_n"


@pytest.mark.asyncio
async def test_selection_screen_mounts_and_updates_real_preview():
    result = _extraction_result()
    processor = Mock()
    processor.preview_selection.return_value = 4
    processor.selector.select_frames.return_value = result.frames[:4]
    screen = SelectionScreen(
        processor,
        result,
        {"input_type": "video", "output_dir": "/output"},
    )

    async with ScreenHarness(screen).run_test() as pilot:
        await pilot.pause(0.25)

        assert screen.query_one("#method_select", Select).value == "batched"
        assert screen.query_one("#sharpness_chart", SharpnessChart)
        confirm = screen.query_one("#confirm_button", Button)
        assert str(confirm.label) == "Save 4 Images"
        assert confirm.disabled is False
        assert screen.selected_indices == {0, 1, 2, 3}

    processor.preview_selection.assert_not_called()
    processor.selector.select_frames.assert_called_once_with(
        result.frames,
        "batched",
        batch_size=5,
        batch_buffer=2,
    )


def test_processing_screen_initializes_thread_safe_state():
    config = {
        "input_type": "video",
        "input_path": "/video.mp4",
        "output_dir": "/output",
    }
    screen = ProcessingScreen(config)

    assert screen.config == config
    assert screen.processor is None
    assert screen.extraction_result is None
    assert screen.processing_cancelled is False
    assert screen.phase_1_complete is False

    screen.processing_cancelled = True
    screen.phase_1_complete = True
    assert screen.processing_cancelled is True
    assert screen.phase_1_complete is True


@pytest.mark.asyncio
async def test_processing_validation_failure_close_button_pops_screen():
    screen = ProcessingScreen({})
    app = ScreenHarness(screen)

    with patch.object(screen, "_validate_config", return_value=False):
        async with app.run_test() as pilot:
            await pilot.pause()
            button = screen.query_one("#cancel-processing", Button)
            assert str(button.label) == "Close"
            assert screen.phase_1_complete is True

            screen.on_button_pressed(Button.Pressed(button))
            await pilot.pause()

            assert app.screen is not screen


@pytest.mark.asyncio
async def test_processing_false_worker_result_becomes_closeable():
    screen = ProcessingScreen(
        {"input_type": "video", "input_path": "/input", "output_dir": "/output"}
    )

    with patch.object(screen, "start_phase_1_processing"):
        async with ScreenHarness(screen).run_test() as pilot:
            await pilot.pause()
            worker = Mock()
            worker.name = f"{WorkerNames.FRAME_PROCESSOR}_phase1"
            worker.state = WorkerState.SUCCESS
            worker.result = False

            screen.on_worker_state_changed(Mock(worker=worker))

            assert screen.phase_1_complete is True
            assert str(screen.query_one("#cancel-processing", Button).label) == "Close"
            assert "failed" in str(
                screen.query_one("#status-text", Static).render()
            ).lower()


@pytest.mark.asyncio
async def test_processing_cancel_signals_without_cancelling_thread_worker():
    screen = ProcessingScreen(
        {"input_type": "video", "input_path": "/input", "output_dir": "/output"}
    )
    screen.processor = Mock()

    with patch.object(screen, "start_phase_1_processing"):
        async with ScreenHarness(screen).run_test() as pilot:
            await pilot.pause()
            screen.action_cancel()

            screen.processor.cancel_processing.assert_called_once_with()
            assert screen.processing_cancelled is True
            assert screen.phase_1_complete is False
            assert screen.query_one("#cancel-processing", Button).disabled is True


@pytest.mark.parametrize(
    ("input_type", "requires_video_tools"),
    [("directory", False), ("video", True), ("video_directory", True)],
)
def test_processing_validation_requests_dependencies_by_input_type(
    input_type, requires_video_tools
):
    config = {
        "input_type": input_type,
        "input_path": "/input",
        "output_dir": "/output",
    }
    screen = ProcessingScreen(config)
    generic = (
        "Processing failed due to an unexpected error. "
        "Check input files and system resources."
    )

    with (
        patch.object(ErrorContext, "analyze_processing_failure", return_value=generic),
        patch.object(
            ErrorContext, "check_system_dependencies", return_value=None
        ) as dependencies,
    ):
        assert screen._validate_config(config) is True

    dependencies.assert_called_once_with(
        require_video_tools=requires_video_tools
    )


@pytest.mark.parametrize("missing_key", ["input_path", "output_dir"])
def test_processing_validation_rejects_missing_required_paths(missing_key):
    config = {
        "input_type": "directory",
        "input_path": "/input",
        "output_dir": "/output",
    }
    config.pop(missing_key)

    assert ProcessingScreen(config)._validate_config(config) is False


def test_processing_transitions_with_the_same_processor_result_and_config():
    screen = ProcessingScreen(
        {"input_type": "video", "input_path": "/video", "output_dir": "/output"}
    )
    screen.processor = Mock()
    screen.extraction_result = _extraction_result()
    app = Mock()

    with patch.object(
        ProcessingScreen, "app", new_callable=PropertyMock, return_value=app
    ):
        screen._transition_to_selection_screen()

    pushed = app.push_screen.call_args.args[0]
    assert isinstance(pushed, SelectionScreen)
    assert pushed.processor is screen.processor
    assert pushed.extraction_result is screen.extraction_result
    assert pushed.config == screen.config


@pytest.mark.parametrize(
    ("step", "expected"),
    [("input_path", "input-path"), ("output_dir", "output-dir-input")],
)
def test_file_path_routing_targets_the_active_configuration_step(step, expected):
    app = SharpFramesApp()
    configuration = Mock(spec=ConfigurationForm)
    configuration.get_current_step_name.return_value = step

    assert app._get_target_input_for_step(configuration, "/tmp/input.mp4") == expected


def test_file_path_routing_ignores_non_path_steps():
    app = SharpFramesApp()
    configuration = Mock(spec=ConfigurationForm)
    configuration.get_current_step_name.return_value = "fps"

    assert app._get_target_input_for_step(configuration, "/tmp/input.mp4") is None
