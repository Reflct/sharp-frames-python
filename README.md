# Sharp Frames Python

Extracts frames from a video or processes images from a directory, scores them for sharpness, and selects the best frames based on various methods. This script is using the same selection methods as found in the Sharp Frames application by [Reflct](https://reflct.app). For the full version, go to [Sharp Frames](https://sharp-frames.reflct.app), or join our [Discord](https://discord.gg/rfYNxSw3yx) for access to the beta windows version.

## Requirements

- Python 3.6 or higher
- OpenCV (`opencv-python`) - Installed automatically with pip
- NumPy - Installed automatically with pip
- tqdm (for progress visualization) - Installed automatically with pip
- FFmpeg (required **only** for video input, must be installed and in your system PATH)
- FFprobe (optional, recommended for video input to determine duration, must be in PATH)

## Installation

### Install via pip

```bash
pip install sharp-frames
```

Or use pipx for an isolated installation:

```bash
pipx install sharp-frames
```

**Important**: FFmpeg must be installed separately for video processing. The pip/pipx installation does NOT include FFmpeg.

- **Windows**: Download from [FFmpeg website](https://ffmpeg.org/download.html) and add `ffmpeg.exe` to your PATH.
- **macOS** (with Homebrew): `brew install ffmpeg`
- **Linux** (Debian/Ubuntu): `sudo apt update && sudo apt install ffmpeg`

## Usage

```bash
sharp-frames --interactive  # Interactive mode
sharp-frames <input_path> <output_directory> [options]  # With arguments
```

### Arguments

-   `<input_path>`: Path to the input video file **or** a directory containing image files (`.jpg`, `.jpeg`, `.png`).
-   `<output_directory>`: Directory to save selected frames/images (will be created if it doesn't exist).

### Options

-   `--fps <int>`: Frames per second to extract (video input only, default: 10).
-   `--format <jpg|png>`: Output image format for saved files (default: `jpg`).
-   `--width <int>`: Width to resize output images (height will be adjusted proportionally, 0 for no resizing, default: 0).
-   `--force-overwrite`: Overwrite existing files in the output directory without confirmation.
-   `--interactive`: Run in interactive mode, prompting for all options.

**Selection Method Options:**

-   `--selection-method <best-n|batched|outlier-removal>`: Choose the frame selection algorithm (default: `best-n`).

    -   **For `best-n` (default):** Selects a target number of frames (`--num-frames`) aiming for the sharpest images while maintaining a minimum distance (`--min-buffer`) between selections. It uses a two-pass approach to balance sharpness and distribution across the source material.
        -   `--num-frames <int>`: Number of frames/images to select (default: 300).
        -   `--min-buffer <int>`: Minimum frame index gap between selected items (default: 3).

    -   **For `batched`:** Divides the frames/images into batches of a specified size (`--batch-size`) and selects the single sharpest frame from each batch. A buffer (`--batch-buffer`) can be added to skip frames between batches.
        -   `--batch-size <int>`: Number of frames/images in each analysis batch (default: 5). The best frame from each batch is selected.
        -   `--batch-buffer <int>`: Number of frames/images to skip between batches (default: 2).

    -   **For `outlier-removal`:** Analyzes each frame's sharpness relative to its neighbors within a window (`--outlier-window-size`). Frames significantly less sharp than their neighbors (controlled by `--outlier-sensitivity`) are considered outliers and are **not** selected. This method keeps all frames *except* those identified as outliers.
        -   `--outlier-window-size <int>`: Number of neighboring frames to compare against (default: 15, must be odd).
        -   `--outlier-sensitivity <int>`: How aggressively to remove outliers (0-100, higher means more removal, default: 50).


### Cancelling the Process

-   You can safely cancel the process at any time by pressing `Ctrl+C`.
-   The script will attempt to clean up temporary files (if any were created).

## Examples

### Basic video usage (best-n)

```bash
sharp-frames my_video.mp4 ./selected_video_frames
```
(Extracts 10fps, selects 300 best frames with buffer 3)

### Directory usage (best-n)

```bash
sharp-frames ./image_folder ./selected_dir_images --num-frames 50 --min-buffer 1
```
(Processes images in `./image_folder`, selects the best 50 with buffer 1)

### Video usage (batched)

```bash
sharp-frames my_video.mp4 ./selected_batched --selection-method batched --batch-size 10 --batch-buffer 2
```
(Selects the best frame from batches of 10, skipping 2 frames between batches)

### Video usage with resizing 

```bash
sharp-frames my_video.mp4 ./resized_frames --width 800
```
(Extracts frames at 10fps, resizes to 800px width while maintaining aspect ratio, selects 300 best frames)

### Directory usage (outlier removal)

```bash
sharp-frames ./image_folder ./selected_outliers --selection-method outlier-removal --outlier-sensitivity 75
```
(Processes images, removing frames considered outliers with 75% sensitivity)

### Interactive mode

```bash
sharp-frames --interactive
```
(Prompts for input path, output path, and all relevant options)

## Features

1.  **Flexible Input**: Process video files or directories of images.
2.  **Multiple Selection Methods**: Choose between `best-n`, `batched`, or `outlier-removal` algorithms.
3.  **Image Resizing**: Resize output images to a custom width while maintaining aspect ratio.
4.  **Interactive Mode**: Easy-to-use prompts for configuration without CLI arguments.
5.  **Progress Visualization**: Real-time progress bars for dependencies, extraction (video), sharpness calculation, selection, and saving.
6.  **Parallel Processing**: Utilizes multiple CPU cores for faster sharpness calculation.
7.  **Memory Efficiency**: Handles large numbers of frames/images effectively.
8.  **Interruptible**: Can be safely cancelled using `Ctrl+C`.
9.  **Cross-Platform**: Designed to work on Windows, macOS, and Linux (with dependencies installed).

## How it works

1.  **Setup**: Checks dependencies, prepares the output directory.
2.  **Input Loading**:
    *   **Video**: Uses FFmpeg to extract frames at the specified `fps` into a temporary directory.
    *   **Directory**: Scans the input directory for supported image files.
3.  **Sharpness Calculation**: Calculates sharpness scores (Laplacian variance) for all frames/images in parallel.
4.  **Frame Selection**: Selects frames based on the chosen `selection-method` and its parameters.
5.  **Output**: Copies selected frames/images to the output directory with informative filenames. Saves a metadata JSON file summarizing the process.

## Output

-   Selected frames/images saved to the output directory.
-   Metadata file (`selected_metadata.json`) with information about the input, selection parameters, and a list of selected items including their original index and sharpness score. 
