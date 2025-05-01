# Changelog

All notable changes to the Sharp Frames project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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