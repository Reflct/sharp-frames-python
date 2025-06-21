# Changelog

All notable changes to the Sharp Frames project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.3] - 2025-01-21

### Fixed
- Processing improvements

## [0.2.2] - 2025-01-21

### Fixed
- macOS processing failures with FFmpeg subprocesses

## [0.2.1] - 2025-01-21

### Fixed
- macOS terminal compatibility: Fixed random app crashes caused by spurious ANSI escape sequences

## [0.2.0] - 2025-01-XX

### Added
- Textual-based UI as default interface
- Step-by-step configuration with validation
- Video directory processing - process all videos in a folder
- Path validators with existence and permission checking
- Numeric field validators with range validation
- Thread-safe subprocess management and cleanup
- Tests

### Changed
- Default behavior: `sharp-frames` now launches textual interface
- Legacy interactive mode moved to `--interactive` flag
- Improved error messages with actionable context
- Enhanced configuration parameter handling

### Fixed
- Configuration parameter mapping and validation
- Resource cleanup for temporary files and subprocesses
- Error reporting specificity and usefulness

## [0.1.3] - 2025-05-15

### Added
- Image resizing feature: New `--width` parameter to specify a custom width for extracted frames
- Proportional scaling that preserves aspect ratio for both video extraction and directory processing
- Interactive mode prompt for specifying resize width

### Fixed
- Improved FFmpeg subprocess handling to better manage stderr output

## [0.1.2] - 2024-06-18

### Added
- Preserve original filenames when processing images from a directory
- Added debug output for improved diagnostics and troubleshooting

### Fixed
- Inconsistent filename handling between video and directory inputs

## [0.1.1] - 2024-06-13

### Changed
- Updated default batch buffer value from 0 to 2 for better results in batched mode
- Simplified installation instructions to focus on pip/pipx installation only
- Improved FFmpeg dependency detection and warning messages
- Removed manual installation instructions from README (now requires pip installation)

### Fixed
- Fixed import issues that caused errors when running without installation

## [0.1.0] - 2024-06-13

### Added
- Initial release
- Support for extracting frames from video files
- Support for processing directories of images
- Three frame selection methods:
  - best-n: Select best frames while maintaining minimum distance
  - batched: Select best frame from each batch
  - outlier-removal: Remove outliers based on comparison with neighbors
- Interactive mode with guided prompts
- Proper Python package structure for pip and pipx installation
- Command-line interface with `sharp-frames` command 