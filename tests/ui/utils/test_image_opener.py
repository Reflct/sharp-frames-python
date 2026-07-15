"""Tests for opening analyzed frames in a platform viewer."""

from unittest.mock import patch

import pytest

from sharp_frames.ui.utils.image_opener import open_image_file


def test_macos_uses_default_open_command(tmp_path):
    image = tmp_path / "frame with spaces.jpg"
    image.touch()

    with patch("sharp_frames.ui.utils.image_opener.subprocess.Popen") as popen:
        open_image_file(str(image), system_name="Darwin")

    assert popen.call_args.args[0] == ["open", str(image)]
    assert popen.call_args.kwargs["start_new_session"] is True


def test_linux_uses_xdg_open(tmp_path):
    image = tmp_path / "frame.jpg"
    image.touch()

    with patch("sharp_frames.ui.utils.image_opener.subprocess.Popen") as popen:
        open_image_file(str(image), system_name="Linux")

    assert popen.call_args.args[0] == ["xdg-open", str(image)]


def test_windows_uses_startfile(tmp_path):
    image = tmp_path / "frame.jpg"
    image.touch()

    with patch(
        "sharp_frames.ui.utils.image_opener.os.startfile", create=True
    ) as startfile:
        open_image_file(str(image), system_name="Windows")

    startfile.assert_called_once_with(str(image))


def test_missing_frame_reports_that_temp_file_is_unavailable(tmp_path):
    with pytest.raises(FileNotFoundError, match="no longer available"):
        open_image_file(str(tmp_path / "missing.jpg"), system_name="Darwin")
