# Sharp Frames v0.4.0 Release Notes

## Highlights

- Explore the complete analyzed frame set in a scrollable timeline with keyboard navigation.
- Get more reliable selections from resolution-normalized focus scoring and improved temporal distribution.
- Preview and execution now share the same selection rules, so displayed counts and chosen frames agree.

## Reliability and Compatibility

- Hardened FFmpeg and FFprobe cancellation, timeouts, output draining, and temporary-directory cleanup.
- Unreadable images are excluded and reported instead of silently receiving valid-looking scores.
- Image exports handle format conversion, partial failures, metadata accuracy, and case-insensitive filename collisions.
- CI covers Linux, macOS, and Windows on Python 3.10, 3.11, 3.12, and 3.13.

## Interface Improvements

- Clearer configuration controls and validation feedback.
- Improved selection chart contrast, spacing, scrolling, and keyboard controls.
- More actionable dependency and processing errors across supported platforms.

## Upgrade

```bash
pip install --upgrade sharp-frames
# or
pipx upgrade sharp-frames
```

FFmpeg and FFprobe remain required for video processing and must be available on `PATH`.
