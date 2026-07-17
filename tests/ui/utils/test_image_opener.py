"""Tests for opening analyzed frames in a platform viewer."""

import subprocess
from unittest.mock import patch

import pytest

from sharp_frames.ui.utils.image_opener import open_image_file


def _completed(returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess([], returncode, stdout="", stderr=stderr)


def test_macos_uses_default_open_command(tmp_path):
    image = tmp_path / "frame with spaces.jpg"
    image.touch()

    with patch(
        "sharp_frames.ui.utils.image_opener.subprocess.run",
        return_value=_completed(),
    ) as run:
        open_image_file(str(image), system_name="Darwin")

    assert run.call_args.args[0] == ["open", str(image)]
    assert run.call_args.kwargs["start_new_session"] is True
    assert run.call_args.kwargs["timeout"] == 10


def test_linux_uses_xdg_open(tmp_path):
    image = tmp_path / "frame.jpg"
    image.touch()

    with patch(
        "sharp_frames.ui.utils.image_opener.subprocess.run",
        return_value=_completed(),
    ) as run:
        open_image_file(str(image), system_name="Linux")

    assert run.call_args.args[0] == ["xdg-open", str(image)]


def test_windows_uses_startfile(tmp_path):
    image = tmp_path / "frame.jpg"
    image.touch()

    with patch(
        "sharp_frames.ui.utils.image_opener.os.startfile", create=True
    ) as startfile:
        open_image_file(str(image), system_name="Windows")

    startfile.assert_called_once_with(str(image))


def test_nonzero_launcher_exit_is_reported_as_error(tmp_path):
    image = tmp_path / "frame.jpg"
    image.touch()

    with patch(
        "sharp_frames.ui.utils.image_opener.subprocess.run",
        return_value=_completed(returncode=3, stderr="no opener configured"),
    ):
        with pytest.raises(OSError, match="no opener configured"):
            open_image_file(str(image), system_name="Linux")


def test_launcher_timeout_is_reported_as_error(tmp_path):
    image = tmp_path / "frame.jpg"
    image.touch()

    with patch(
        "sharp_frames.ui.utils.image_opener.subprocess.run",
        side_effect=subprocess.TimeoutExpired("xdg-open", 10),
    ):
        with pytest.raises(OSError, match="Unable to launch"):
            open_image_file(str(image), system_name="Linux")


def test_missing_frame_reports_that_temp_file_is_unavailable(tmp_path):
    with pytest.raises(FileNotFoundError, match="no longer available"):
        open_image_file(str(tmp_path / "missing.jpg"), system_name="Darwin")
