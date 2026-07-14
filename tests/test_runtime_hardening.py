"""Regression tests for extraction lifecycle and platform support."""

import io
import shutil
import subprocess
import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from sharp_frames.models.frame_data import ExtractionResult, FrameData
from sharp_frames.processing.frame_extractor import FrameExtractor
from sharp_frames.processing.tui_processor import TUIProcessor
from sharp_frames.sharp_frames_processor import SharpFrames
from sharp_frames.ui.components.validators import (
    ImageDirectoryValidator,
    VideoFileValidator,
)
from sharp_frames.ui.utils.error_analysis import ErrorContext
from sharp_frames.video_utils import (
    SUPPORTED_IMAGE_EXTENSIONS,
    SUPPORTED_VIDEO_EXTENSIONS,
    get_ffmpeg_installation_hint,
)


class CompletedFakeProcess:
    """Popen stand-in that has already completed."""

    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = io.StringIO(stdout)
        self.stderr = io.StringIO(stderr)

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode


class RunningFakeProcess:
    """Popen stand-in that runs until terminate is called."""

    def __init__(self):
        self.returncode = None
        self.stdout = io.StringIO("")
        self.stderr = io.StringIO("")
        self.terminated = threading.Event()

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        if self.returncode is not None:
            return self.returncode
        if not self.terminated.wait(timeout or 0):
            raise subprocess.TimeoutExpired("ffmpeg", timeout)
        return self.returncode

    def terminate(self):
        self.returncode = 143
        self.terminated.set()

    def kill(self):
        self.returncode = -9
        self.terminated.set()


class StubbornFakeProcess:
    """Process stand-in that never acknowledges terminate or kill."""

    def __init__(self):
        self.terminate_called = False
        self.kill_called = False

    def poll(self):
        return None

    def terminate(self):
        self.terminate_called = True

    def kill(self):
        self.kill_called = True

    def wait(self, timeout=None):
        raise subprocess.TimeoutExpired("ffmpeg", timeout)


def _create_frames(directory: Path, count: int) -> None:
    for index in range(1, count + 1):
        (directory / f"frame_{index:05d}.jpg").touch()


def test_ffmpeg_nonzero_exit_rejects_partial_output(tmp_path):
    """A failed process must never be accepted because it wrote many files."""
    _create_frames(tmp_path, 12)
    process = CompletedFakeProcess(1, stdout="frame=12\nprogress=end\n", stderr="conversion failed")
    extractor = FrameExtractor()

    with patch("subprocess.Popen", return_value=process) as popen:
        success = extractor._run_ffmpeg_extraction(
            "input.mp4", str(tmp_path), 10, "jpg", 0, duration=2.0
        )

    assert success is False
    command = popen.call_args.args[0]
    assert command[command.index("-progress") + 1] == "pipe:1"


def test_ffmpeg_success_requires_clean_exit_and_reports_completion(tmp_path):
    _create_frames(tmp_path, 2)
    process = CompletedFakeProcess(0, stdout="frame=2\nprogress=end\n")
    progress = Mock()
    extractor = FrameExtractor()
    extractor.progress_callback = progress

    with patch("subprocess.Popen", return_value=process):
        success = extractor._run_ffmpeg_extraction(
            "input.mp4", str(tmp_path), 2, "jpg", 0, duration=1.0
        )

    assert success is True
    progress.assert_any_call("extraction", 2, 2, "Extraction complete: 2 frames")


def test_ffmpeg_timeout_terminates_process_and_rejects_output(tmp_path):
    _create_frames(tmp_path, 20)
    process = RunningFakeProcess()
    extractor = FrameExtractor()

    with patch("subprocess.Popen", return_value=process), patch.object(
        extractor,
        "_wait_for_process",
        side_effect=subprocess.TimeoutExpired("ffmpeg", 300),
    ):
        success = extractor._run_ffmpeg_extraction(
            "input.mp4", str(tmp_path), 10, "jpg", 0, duration=1.0
        )

    assert success is False
    assert process.terminated.is_set()
    assert not any(
        thread.name.startswith("sharp-frames-ffmpeg-")
        for thread in threading.enumerate()
    )


def test_cancel_processing_terminates_active_ffmpeg(tmp_path):
    process = RunningFakeProcess()
    extractor = FrameExtractor()

    with patch("subprocess.Popen", return_value=process):
        worker = threading.Thread(
            target=extractor._run_ffmpeg_extraction,
            args=("input.mp4", str(tmp_path), 10, "jpg", 0),
        )
        worker.start()
        time.sleep(0.05)
        extractor.cancel_processing()
        worker.join(timeout=1)

    assert process.terminated.is_set()
    assert not worker.is_alive()


def test_keyboard_interrupt_terminates_active_ffmpeg(tmp_path):
    process = RunningFakeProcess()
    extractor = FrameExtractor()

    with patch("subprocess.Popen", return_value=process), patch.object(
        extractor, "_wait_for_process", side_effect=KeyboardInterrupt
    ):
        with pytest.raises(KeyboardInterrupt):
            extractor._run_ffmpeg_extraction(
                "input.mp4", str(tmp_path), 10, "jpg", 0
            )

    assert process.terminated.is_set()


def test_termination_escalation_does_not_mask_original_failure():
    process = StubbornFakeProcess()

    FrameExtractor._terminate_process(process)

    assert process.terminate_called is True
    assert process.kill_called is True


def test_ffprobe_missing_is_reported_without_unbound_local_error():
    extractor = FrameExtractor()
    with patch("subprocess.run", side_effect=FileNotFoundError):
        with pytest.raises(RuntimeError, match="FFprobe not found"):
            extractor._get_video_info("input.mp4")


def test_ffprobe_failure_preserves_actionable_stderr():
    extractor = FrameExtractor()
    failed_probe = subprocess.CompletedProcess(
        ["ffprobe"], 1, stdout="", stderr="Invalid data found when processing input"
    )

    with patch("subprocess.run", return_value=failed_probe) as run_probe:
        with pytest.raises(RuntimeError, match="Invalid data found"):
            extractor._get_video_info("broken.mp4")

    command = run_probe.call_args.args[0]
    assert command[command.index("-v") + 1] == "error"


def test_progress_callback_failure_does_not_stop_pipe_drain():
    extractor = FrameExtractor()
    extractor.progress_callback = Mock(side_effect=RuntimeError("UI unavailable"))
    stream = io.StringIO("frame=1\nframe=2\nprogress=end\n")

    extractor._read_ffmpeg_progress(stream, estimated_total=2)

    assert stream.tell() == len(stream.getvalue())
    assert extractor.progress_callback is None


def test_tui_cancel_reaches_extractor():
    processor = TUIProcessor()
    with patch.object(processor.extractor, "cancel_processing") as cancel_extraction:
        processor.cancel_processing()
    cancel_extraction.assert_called_once_with()


def test_tui_cleans_extracted_temp_dir_when_analysis_fails(tmp_path):
    temp_dir = tmp_path / "frames"
    temp_dir.mkdir()
    frame_path = temp_dir / "frame_00001.jpg"
    frame_path.touch()
    result = ExtractionResult(
        frames=[FrameData(str(frame_path), 0, 0.0, output_name="00001")],
        metadata={},
        temp_dir=str(temp_dir),
        input_type="video",
    )
    processor = TUIProcessor()

    with patch.object(processor.extractor, "extract_frames", return_value=result), patch.object(
        processor.analyzer, "calculate_sharpness", side_effect=RuntimeError("analysis failed")
    ):
        with pytest.raises(RuntimeError, match="analysis failed"):
            processor.extract_and_analyze({"input_type": "video", "input_path": "input.mp4"})

    assert not temp_dir.exists()
    assert result.temp_dir is None
    assert processor.current_result is None


def test_tui_cancellation_during_analysis_cleans_and_discards_result(tmp_path):
    temp_dir = tmp_path / "frames"
    temp_dir.mkdir()
    frame_path = temp_dir / "frame_00001.jpg"
    frame_path.touch()
    result = ExtractionResult(
        frames=[FrameData(str(frame_path), 0, 1.0, output_name="00001")],
        metadata={},
        temp_dir=str(temp_dir),
        input_type="video",
    )
    processor = TUIProcessor()

    def cancel_during_analysis(extraction_result, progress_callback=None):
        processor.cancel_processing()
        return extraction_result

    with patch.object(processor.extractor, "extract_frames", return_value=result), patch.object(
        processor.analyzer, "calculate_sharpness", side_effect=cancel_during_analysis
    ):
        cancelled_result = processor.extract_and_analyze(
            {"input_type": "video", "input_path": "input.mp4"}
        )

    assert cancelled_result.frames == []
    assert processor.current_result is None
    assert not temp_dir.exists()


def test_processor_can_be_explicitly_reset_after_cancellation():
    processor = TUIProcessor()
    processor.cancel_processing()

    processor.reset_current_result()

    assert processor._cancelled is False
    assert processor.extractor._cancellation_event.is_set() is False
    assert processor.analyzer._cancellation_event.is_set() is False


def test_image_only_dependency_check_does_not_invoke_ffmpeg():
    with patch("subprocess.run", side_effect=AssertionError("video tools should not be checked")), patch(
        "cv2.cvtColor", return_value=Mock()
    ):
        assert ErrorContext.check_system_dependencies(require_video_tools=False) is None


@pytest.mark.parametrize(
    ("system_name", "expected"),
    [
        ("Windows", "bin directory to PATH"),
        ("Darwin", "brew install ffmpeg"),
        ("Linux", "sudo apt install ffmpeg"),
    ],
)
def test_missing_video_tool_guidance_is_platform_specific(system_name, expected):
    with patch("sharp_frames.video_utils.platform.system", return_value=system_name):
        assert expected in get_ffmpeg_installation_hint()


def test_media_extensions_use_one_shared_contract():
    assert FrameExtractor().SUPPORTED_IMAGE_EXTENSIONS == SUPPORTED_IMAGE_EXTENSIONS
    assert ImageDirectoryValidator.SUPPORTED_IMAGE_EXTENSIONS == SUPPORTED_IMAGE_EXTENSIONS
    assert VideoFileValidator.SUPPORTED_VIDEO_EXTENSIONS == SUPPORTED_VIDEO_EXTENSIONS
    assert {".webp", ".tif"} <= SUPPORTED_IMAGE_EXTENSIONS
    assert {".m4v", ".3gp", ".ts", ".mts", ".m2ts"} <= SUPPORTED_VIDEO_EXTENSIONS


def test_direct_cli_discovers_shared_image_formats(tmp_path):
    expected = {tmp_path / "photo.webp", tmp_path / "scan.tif", tmp_path / "map.ppm"}
    for path in expected:
        path.touch()
    (tmp_path / "notes.txt").touch()
    processor = SharpFrames(
        input_path=str(tmp_path),
        input_type="directory",
        output_dir=str(tmp_path / "output"),
    )

    assert set(map(Path, processor._get_image_paths_from_dir())) == expected


def test_minimal_progress_conflict_aborts_without_overwrite(tmp_path, capsys):
    from sharp_frames.processing.minimal_progress import MinimalProgressSharpFrames

    output_dir = tmp_path / "output"
    output_dir.mkdir()
    existing = output_dir / "keep.jpg"
    existing.write_bytes(b"keep")
    processor = MinimalProgressSharpFrames(
        input_path=str(tmp_path),
        input_type="directory",
        output_dir=str(output_dir),
        force_overwrite=False,
    )

    with patch.object(processor, "_check_dependencies", return_value=True):
        assert processor._setup() is False

    assert existing.read_bytes() == b"keep"
    assert str(existing) in capsys.readouterr().out


def test_video_directory_cancellation_stops_before_next_video(tmp_path):
    temp_dir = tmp_path / "extracted"
    temp_dir.mkdir()
    extractor = FrameExtractor()

    def cancel_after_first(*args, **kwargs):
        extractor.cancel_processing()
        return []

    with patch(
        "sharp_frames.processing.frame_extractor.get_video_files_in_directory",
        return_value=["one.mp4", "two.mp4"],
    ), patch.object(extractor, "_create_temp_directory", return_value=str(temp_dir)), patch.object(
        extractor, "_extract_single_video", side_effect=cancel_after_first
    ) as extract_one:
        with pytest.raises(RuntimeError, match="cancelled"):
            extractor._extract_video_directory_frames(
                {"input_path": str(tmp_path), "input_type": "video_directory"}
            )

    assert extract_one.call_count == 1
    assert not temp_dir.exists()


def test_video_directory_all_failures_do_not_leak_temp_dir(tmp_path):
    temp_dir = tmp_path / "extracted"
    temp_dir.mkdir()
    extractor = FrameExtractor()

    with patch(
        "sharp_frames.processing.frame_extractor.get_video_files_in_directory",
        return_value=["broken.mp4"],
    ), patch.object(extractor, "_create_temp_directory", return_value=str(temp_dir)), patch.object(
        extractor, "_extract_single_video", side_effect=RuntimeError("bad video")
    ):
        result = extractor._extract_video_directory_frames(
            {"input_path": str(tmp_path), "input_type": "video_directory"}
        )

    assert result.frames == []
    assert result.temp_dir is None
    assert not temp_dir.exists()


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="FFmpeg and FFprobe are required for the extraction integration test",
)
def test_real_ffmpeg_extraction_completes_and_reports_progress(tmp_path):
    video_path = tmp_path / "synthetic.mp4"
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "testsrc2=size=160x120:rate=10:duration=1",
            "-pix_fmt", "yuv420p", str(video_path),
        ],
        check=True,
    )
    progress = Mock()
    extractor = FrameExtractor()
    result = extractor.extract_frames(
        {
            "input_type": "video",
            "input_path": str(video_path),
            "fps": 5,
            "output_format": "jpg",
            "width": 0,
        },
        progress,
    )

    try:
        assert len(result.frames) == 5
        assert all(Path(frame.path).is_file() for frame in result.frames)
        assert any(call.args[0] == "extraction" for call in progress.call_args_list)
    finally:
        if result.temp_dir:
            shutil.rmtree(result.temp_dir)
