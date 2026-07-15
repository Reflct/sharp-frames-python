"""Integration tests for the active Textual two-phase workflow."""

from unittest.mock import Mock, PropertyMock, patch

import pytest
from textual.app import App
from textual.widgets import Button, Checkbox, Select, Static

from sharp_frames.models.frame_data import ExtractionResult, FrameData
from sharp_frames.ui.app import SharpFramesApp
from sharp_frames.ui.screens.configuration import ConfigurationForm
from sharp_frames.ui.screens.processing import ProcessingScreen
from sharp_frames.ui.screens.selection import SelectionScreen, SharpnessChart
from sharp_frames.ui.utils.error_analysis import ErrorContext


class ScreenHarness(App):
    """Minimal app that mounts one production screen for DOM assertions."""

    def __init__(self, target_screen):
        super().__init__()
        self.target_screen = target_screen

    def on_mount(self):
        self.push_screen(self.target_screen)


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


@pytest.mark.asyncio
async def test_configuration_screen_mounts_current_wizard_controls():
    form = ConfigurationForm()

    async with ScreenHarness(form).run_test() as pilot:
        await pilot.pause(0.2)

        assert str(form.query_one("#step-info", Static).render())
        assert str(form.query_one("#next-btn", Button).label) == "Next"
        assert form.query_one("#back-btn", Button).disabled is True
        assert form.get_current_step_name() == "input_type"


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

    processor.preview_selection.assert_called_with(
        "batched", batch_size=5, batch_buffer=2
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
