"""Regression tests for frame output safety and metadata accuracy."""

import json
from pathlib import Path

import cv2
import numpy as np

from sharp_frames.models.frame_data import FrameData
from sharp_frames.processing.frame_saver import FrameSaver


def _write_image(path: Path, color: tuple[int, int, int]) -> None:
    image = np.full((12, 16, 3), color, dtype=np.uint8)
    assert cv2.imwrite(str(path), image)


def _write_rgba_image(path: Path) -> None:
    image = np.zeros((12, 16, 4), dtype=np.uint8)
    image[..., :3] = (10, 40, 200)
    image[..., 3] = np.linspace(0, 255, 16, dtype=np.uint8)
    assert cv2.imwrite(str(path), image)


def _config(output_dir: Path, **overrides):
    config = {
        "input_type": "directory",
        "input_path": str(output_dir.parent / "input"),
        "output_dir": str(output_dir),
        "output_format": "jpg",
        "width": 0,
        "force_overwrite": False,
    }
    config.update(overrides)
    return config


def test_noninteractive_conflict_aborts_without_mutating_output(tmp_path, capsys):
    source = tmp_path / "source.jpg"
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    existing = output_dir / "SOURCE.JPG"
    _write_image(source, (0, 255, 0))
    existing.write_bytes(b"original output")

    result = FrameSaver(show_progress=False).save_frames(
        [FrameData(str(source), 0, 10.0, output_name="source")],
        _config(output_dir),
    )

    assert result is False
    assert existing.read_bytes() == b"original output"
    assert sorted(path.name for path in output_dir.iterdir()) == ["SOURCE.JPG"]
    assert str(existing) in capsys.readouterr().out


def test_unrelated_output_files_do_not_block_save(tmp_path):
    source = tmp_path / "source.jpg"
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    finder_metadata = output_dir / ".DS_Store"
    _write_image(source, (0, 255, 0))
    finder_metadata.write_bytes(b"finder metadata")

    result = FrameSaver(show_progress=False).save_frames(
        [FrameData(str(source), 0, 10.0, output_name="source")],
        _config(output_dir),
    )

    assert result is True
    assert finder_metadata.read_bytes() == b"finder metadata"
    assert (output_dir / "source.jpg").is_file()
    assert (output_dir / "selected_metadata.json").is_file()


def test_existing_metadata_blocks_save_without_force_overwrite(tmp_path):
    source = tmp_path / "source.jpg"
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    metadata = output_dir / "selected_metadata.json"
    _write_image(source, (0, 255, 0))
    metadata.write_bytes(b"original metadata")

    result = FrameSaver(show_progress=False).save_frames(
        [FrameData(str(source), 0, 10.0, output_name="source")],
        _config(output_dir),
    )

    assert result is False
    assert metadata.read_bytes() == b"original metadata"
    assert not (output_dir / "source.jpg").exists()


def test_directory_image_is_transcoded_to_requested_format(tmp_path):
    source = tmp_path / "source.png"
    output_dir = tmp_path / "output"
    _write_image(source, (255, 0, 0))

    result = FrameSaver(show_progress=False).save_frames(
        [FrameData(str(source), 0, 12.5, output_name="source")],
        _config(output_dir),
    )

    output = output_dir / "source.jpg"
    assert result is True
    assert output.read_bytes().startswith(b"\xff\xd8\xff")
    assert cv2.imread(str(output)) is not None

    metadata = json.loads((output_dir / "selected_metadata.json").read_text())
    assert metadata["output_format"] == "jpg"
    assert metadata["total_saved"] == 1
    assert metadata["total_failed"] == 0
    assert metadata["selected_frames"][0]["output_filename"] == "source.jpg"


def test_transcoding_to_png_preserves_alpha(tmp_path):
    source = tmp_path / "source.webp"
    output_dir = tmp_path / "output"
    _write_rgba_image(source)

    result = FrameSaver(show_progress=False).save_frames(
        [FrameData(str(source), 0, 12.5, output_name="source")],
        _config(output_dir, output_format="png"),
    )

    output = cv2.imread(
        str(output_dir / "source.png"), cv2.IMREAD_UNCHANGED
    )
    assert result is True
    assert output is not None
    assert output.shape[2] == 4
    assert output[..., 3].min() == 0
    assert output[..., 3].max() == 255


def test_resizing_png_preserves_alpha(tmp_path):
    source = tmp_path / "source.png"
    output_dir = tmp_path / "output"
    _write_rgba_image(source)

    result = FrameSaver(show_progress=False).save_frames(
        [FrameData(str(source), 0, 12.5, output_name="source")],
        _config(output_dir, output_format="png", width=8),
    )

    output = cv2.imread(
        str(output_dir / "source.png"), cv2.IMREAD_UNCHANGED
    )
    assert result is True
    assert output is not None
    assert output.shape == (6, 8, 4)
    assert output[..., 3].min() < output[..., 3].max()


def test_jpeg_output_composites_transparency_on_white(tmp_path):
    source = tmp_path / "source.png"
    output_dir = tmp_path / "output"
    image = np.zeros((12, 16, 4), dtype=np.uint8)
    assert cv2.imwrite(str(source), image)

    result = FrameSaver(show_progress=False).save_frames(
        [FrameData(str(source), 0, 12.5, output_name="source")],
        _config(output_dir, output_format="jpg"),
    )

    output = cv2.imread(str(output_dir / "source.jpg"))
    assert result is True
    assert output is not None
    assert output.mean() > 245


def test_duplicate_directory_stems_get_deterministic_unique_names(tmp_path):
    png_source = tmp_path / "foo.png"
    jpg_source = tmp_path / "foo.jpg"
    output_dir = tmp_path / "output"
    _write_image(png_source, (255, 0, 0))
    _write_image(jpg_source, (0, 0, 255))
    frames = [
        FrameData(str(png_source), 0, 20.0, output_name="foo"),
        FrameData(str(jpg_source), 1, 30.0, output_name="foo"),
    ]

    result = FrameSaver(show_progress=False).save_frames(frames, _config(output_dir))

    assert result is True
    assert (output_dir / "foo.jpg").is_file()
    assert (output_dir / "foo_2.jpg").is_file()
    metadata = json.loads((output_dir / "selected_metadata.json").read_text())
    assert [item["output_filename"] for item in metadata["selected_frames"]] == [
        "foo.jpg",
        "foo_2.jpg",
    ]


def test_video_naming_conventions_are_unchanged(tmp_path):
    saver = FrameSaver(show_progress=False)
    frame = FrameData(
        str(tmp_path / "frame.jpg"),
        4,
        10.0,
        source_video="video_002",
        source_index=4,
        output_name="video002_00005",
    )

    assert saver._get_output_filename(frame, 0, "video", "png") == "frame_00001.png"
    assert (
        saver._get_output_filename(frame, 0, "video_directory", "png")
        == "video002_00005.png"
    )


def test_partial_failure_writes_truthful_metadata(tmp_path):
    good_source = tmp_path / "good.jpg"
    missing_source = tmp_path / "missing.jpg"
    output_dir = tmp_path / "output"
    _write_image(good_source, (10, 20, 30))
    frames = [
        FrameData(str(good_source), 0, 40.0, output_name="good"),
        FrameData(str(missing_source), 1, 50.0, output_name="missing"),
    ]

    result = FrameSaver(show_progress=False).save_frames(frames, _config(output_dir))

    assert result is False
    assert (output_dir / "good.jpg").is_file()
    assert not (output_dir / "missing.jpg").exists()

    metadata = json.loads((output_dir / "selected_metadata.json").read_text())
    assert metadata["total_selected"] == 2
    assert metadata["total_saved"] == 1
    assert metadata["total_failed"] == 1
    assert metadata["selection_summary"]["total_frames"] == 1
    assert [item["output_filename"] for item in metadata["selected_frames"]] == [
        "good.jpg"
    ]
