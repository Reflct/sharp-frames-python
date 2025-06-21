# Sharp Frames v0.2.0 Release Notes

## New Features

### Textual Interface (Default)
- Replaces command-line prompts with step-by-step wizard
- Real-time input validation and error feedback
- Enhanced error messages with specific guidance

### Video Directory Processing
- Process all videos in a folder with a single command
- Automatically detects and processes supported video formats
- Maintains individual processing settings for each video

### Usage Changes
```bash
# New default behavior
sharp-frames                    # Launches textual interface

# Existing functionality unchanged  
sharp-frames input.mp4 output/  # Direct processing
sharp-frames video_folder/ output/  # Process all videos in folder
sharp-frames --interactive      # Legacy prompts
```

## Technical Changes

### Added
- Path validation with existence/permission checking
- Numeric field validation with range checking
- Thread-safe subprocess management
- UI component testing
- Enhanced error analysis and reporting

### Fixed
- Configuration parameter mapping
- Resource cleanup (temp files, subprocesses)
- Error message specificity

## Breaking Changes
- `sharp-frames` without arguments now launches UI instead of showing help
- Use `sharp-frames --help` for command-line help

## Installation
```bash
pip install --upgrade sharp-frames
# or
pipx upgrade sharp-frames
```

## Dependencies
- Added: `textual>=0.41.0`
- All existing dependencies unchanged 