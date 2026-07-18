# Sharp Frames Python

Extract and select the sharpest frames from videos or directories of images using advanced sharpness scoring algorithms. Features a modern text-based interface for easy configuration and powerful command-line options for automation.

## Installation

```bash
pip install sharp-frames
```

Or with pipx for isolated installation:

```bash
pipx install sharp-frames
```

**IMPORTANT: Video Processing Requirement**: Install an FFmpeg distribution that includes both `ffmpeg` and `ffprobe`. Both executables must be on `PATH`; image-directory processing does not require them.
- **Windows**: Download from [FFmpeg website](https://ffmpeg.org/download.html) and add to PATH
- **macOS**: `brew install ffmpeg`
- **Linux**: `sudo apt install ffmpeg`

HDR-to-SDR extraction additionally requires an FFmpeg build with the `zscale` filter (`libzimg`). You can verify support with `ffmpeg -filters | grep zscale`. Non-HDR video processing does not require `zscale`.

## Quick Start

### Modern Interface (Default)
```bash
sharp-frames
```
Launches an intuitive step-by-step wizard for configuring your processing options.

### Direct Processing
```bash
sharp-frames input_video.mp4 output_folder
sharp-frames image_directory output_folder
```

## Usage Modes

### Interactive Configuration
- **Fancy UI**: `sharp-frames` (default) - Step-by-step with validation
- **Legacy**: `sharp-frames --interactive` - Terminal prompts for all options

### Direct Processing
```bash
sharp-frames <input> <output> [options]
```

**Input Types:**
- Video files: `.mp4`, `.avi`, `.mov`, `.mkv`, `.wmv`, `.flv`, `.webm`, `.m4v`, `.3gp`, `.3g2`, `.ogv`, `.ts`, `.mts`, `.m2ts`, `.mpg`, `.mpeg`, `.vob`
- Video directories: Processes all videos in a folder
- Image directories: `.jpg`, `.jpeg`, `.png`, `.bmp`, `.tif`, `.tiff`, `.webp`, `.ppm`, `.pgm`, `.pbm`

## Selection Methods

### Best-N (Default)
Selects a target number of the sharpest frames while maintaining distribution across the source.
```bash
--selection-method best-n --num-frames 300 --min-buffer 3
```

### Batched
Divides content into batches and selects the sharpest frame from each batch.
```bash
--selection-method batched --batch-size 5 --batch-buffer 2
```

### Outlier Detection
Removes unusually blurry frames by comparing each frame to its neighbors.
```bash
--selection-method outlier-removal --outlier-window-size 15 --outlier-sensitivity 60
```

## Command Line Options

### Basic Options
- `--fps <int>`: Frame extraction rate for videos (default: 10)
- `--format <jpg|png>`: Output image format (default: jpg)
- `--width <int>`: Resize width in pixels, maintains aspect ratio (default: 0, no resize)
- `--force-overwrite`: Overwrite existing output files without confirmation

### Selection Method Parameters
- `--num-frames <int>`: Number of frames to select (best-n, default: 300)
- `--min-buffer <int>`: Minimum number of intervening frames between selected frames (best-n, default: 3)
- `--batch-size <int>`: Frames per batch (batched, default: 5)
- `--batch-buffer <int>`: Frames to skip between batches (batched, default: 2)
- `--outlier-window-size <int>`: Local comparison window, minimum 5 (outlier-removal, default: 15)
- `--outlier-sensitivity <int>`: Detection sensitivity 0-100 (outlier-removal, default: 60)

## Examples

### Video Processing
```bash
# Default settings
sharp-frames video.mp4 output_frames

# Custom frame rate and selection
sharp-frames video.mp4 output --fps 15 --num-frames 500

# Batch selection with resizing
sharp-frames video.mp4 output --selection-method batched --width 1920

# Process all videos in a directory
sharp-frames video_folder output_frames --fps 5
```

### Image Processing
```bash
# Select best images from directory
sharp-frames image_folder selected_images --num-frames 100

# Remove blurry images
sharp-frames photos selected --selection-method outlier-removal --outlier-sensitivity 75
```

## Features

- **Smart File Validation**: Automatic format detection with helpful error messages
- **Textual Interface**: Step-by-step wizard with real-time validation and help system
- **Flexible Input**: Process single videos, video directories, or image directories
- **Multiple Algorithms**: Three selection methods optimized for different use cases
- **Real-time Progress**: Live progress tracking for all processing stages
- **Parallel Processing**: Multi-core sharpness calculation for faster processing
- **Image Resizing**: Optional width-based resizing with aspect ratio preservation
- **Safe Operation**: Validates paths, permissions, and file formats before processing
- **Comprehensive Output**: Selected files plus detailed metadata JSON

## Requirements

- Python 3.10 or higher
- Dependencies installed automatically: `opencv-python`, `numpy`, `tqdm`,
  `textual`, `textual-image`
- FFmpeg and FFprobe (for video processing only)
- FFmpeg `zscale`/`libzimg` support (for HDR-to-SDR processing only)

## How It Works

1. **Validation**: Checks input paths, file formats, and system dependencies
2.  **Extraction**: Videos are extracted to frames at specified FPS using FFmpeg
3.  **Analysis**: Normalizes analysis resolution, lightly denoises each image,
    and combines Laplacian variance with Tenengrad focus scoring in parallel.
    Unreadable inputs are excluded and reported.
4.  **Selection**: Applies the chosen source-aware algorithm to select the best
    naturally ordered frames/images.
5.  **Output**: Saves selected content with metadata including scores and parameters

## Output

- Selected frames/images with descriptive filenames
- `selected_metadata.json` with processing details, parameters, and sharpness scores
- Transcodes selected images to the configured output format (`jpg` by default)
- Automatic output directory creation with permission validation

## Help & Support

- Press `F1` in the textual interface for context-sensitive help
- Use `Ctrl+C` to safely cancel processing at any time
- All validation errors include specific guidance for resolution
- Visit [Sharp Frames](https://sharp-frames.reflct.app) for the full desktop application
