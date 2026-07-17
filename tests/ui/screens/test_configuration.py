"""Tests for the active two-phase configuration wizard."""

from unittest.mock import Mock, PropertyMock, patch

import pytest

from sharp_frames.ui.screens.configuration import ConfigurationForm
from sharp_frames.ui.screens.processing import ProcessingScreen


EXPECTED_STEPS = [
    "input_type",
    "input_path",
    "output_dir",
    "fps",
    "output_format",
    "width",
    "force_overwrite",
    "confirm",
]


def test_configuration_uses_extraction_only_steps():
    form = ConfigurationForm()

    assert form.steps == EXPECTED_STEPS
    assert list(form.step_handlers) == EXPECTED_STEPS
    assert form.current_step == 0
    assert form.config_data == {}
    assert "selection_method" not in form.steps
    assert "method_params" not in form.steps


@pytest.mark.parametrize("input_type", ["video", "video_directory"])
def test_video_inputs_show_video_specific_steps(input_type):
    form = ConfigurationForm()
    form.config_data = {"input_type": input_type}

    assert form._should_show_step("fps") is True
    assert form._should_show_step("output_format") is True


def test_image_directory_skips_video_specific_steps():
    form = ConfigurationForm()
    form.config_data = {"input_type": "directory"}

    assert form._should_show_step("fps") is False
    assert form._should_show_step("output_format") is False
    assert all(
        form._should_show_step(step)
        for step in EXPECTED_STEPS
        if step not in {"fps", "output_format"}
    )


def test_save_current_step_validates_and_merges_handler_data():
    form = ConfigurationForm()
    handler = form.step_handlers["input_type"]

    with (
        patch.object(form, "_clear_error"),
        patch.object(handler, "validate", return_value=True) as validate,
        patch.object(
            handler, "get_data", return_value={"input_type": "video"}
        ) as get_data,
    ):
        assert form._save_current_step() is True

    validate.assert_called_once_with(form)
    get_data.assert_called_once_with(form)
    assert form.config_data == {"input_type": "video"}


def test_save_current_step_does_not_read_data_after_validation_failure():
    form = ConfigurationForm()
    handler = form.step_handlers["input_type"]

    with (
        patch.object(form, "_clear_error"),
        patch.object(handler, "validate", return_value=False),
        patch.object(handler, "get_data") as get_data,
    ):
        assert form._save_current_step() is False

    get_data.assert_not_called()
    assert form.config_data == {}


def test_navigation_skips_hidden_directory_steps():
    form = ConfigurationForm()
    form.config_data = {"input_type": "directory"}
    form.current_step = EXPECTED_STEPS.index("output_dir")

    with (
        patch.object(form, "_save_current_step", return_value=True),
        patch.object(form, "show_current_step") as show,
    ):
        form._next_step()

    assert form.get_current_step_name() == "width"
    show.assert_called_once()

    with patch.object(form, "show_current_step") as show:
        form._back_step()

    assert form.get_current_step_name() == "output_dir"
    show.assert_called_once()


def test_reset_clears_configuration_and_renders_first_step():
    form = ConfigurationForm()
    form.current_step = 5
    form.config_data = {"input_type": "video"}

    with patch.object(form, "show_current_step") as show:
        form.reset_to_first_step()

    assert form.current_step == 0
    assert form.config_data == {}
    show.assert_called_once()


def test_action_process_passes_collected_config_to_processing_screen():
    form = ConfigurationForm()
    form.config_data = {
        "input_type": "video",
        "input_path": "/video.mp4",
        "output_dir": "/output",
    }
    app = Mock()

    with patch.object(
        ConfigurationForm, "app", new_callable=PropertyMock, return_value=app
    ):
        form.action_process()

    pushed = app.push_screen.call_args.args[0]
    assert isinstance(pushed, ProcessingScreen)
    assert pushed.config == form.config_data


def test_cancel_and_help_delegate_to_the_app():
    form = ConfigurationForm()
    app = Mock()

    with patch.object(
        ConfigurationForm, "app", new_callable=PropertyMock, return_value=app
    ):
        form.action_cancel()
        form.action_help()

    app.exit.assert_called_once_with(result="cancelled")
    help_call = app.push_screen.call_args
    assert help_call.args[0] == "help"
    assert "Sharp Frames Configuration Help" in help_call.args[1]
    assert "Selection Process" in help_call.args[1]
