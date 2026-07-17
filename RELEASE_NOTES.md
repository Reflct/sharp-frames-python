# Sharp Frames v0.4.0 Release Notes

## Highlights

- Explore the complete analyzed frame set in a scrollable timeline — click any bar to preview that frame directly in the terminal.
- iPhone and HDR sources (BT.2020, HLG, PQ) are detected and converted to sRGB automatically.
- Get more reliable selections from resolution-normalized focus scoring, trend-aware outlier detection, and improved temporal distribution.
- Preview and execution now share the same selection rules, so displayed counts and chosen frames agree.

## Interface Improvements

- Full-frame selection timeline with click-to-inspect, horizontal scrolling, and keyboard navigation (arrows, PgUp/PgDn through selected frames, Ctrl+PgUp/PgDn paging, Home/End).
- Inline frame preview rendered through Sixel or Kitty terminal graphics, with an external-viewer fallback (press `O`).
- Responsive layout keeps the preview and chart visible on short terminals (down to 80×24) while preserving the spacious layout on large ones.
- Start Over returns to the first setup step with a clean configuration, and Cancel exits the application.
- Clearer configuration controls and validation feedback.
- More actionable dependency and processing errors across supported platforms.

## Reliability and Compatibility

- HDR and wide-gamut color spaces are converted to sRGB/BT.709 through FFmpeg `zscale`, with a clear error for unsupported BT.2020 constant-luminance sources.
- Hardened FFmpeg and FFprobe cancellation, timeouts, output draining, and temporary-directory cleanup.
- Unreadable images are excluded and reported instead of silently receiving valid-looking scores.
- Image exports preserve alpha and handle format conversion, partial failures, metadata accuracy, and case-insensitive filename collisions.
- CI covers Linux, macOS, and Windows on Python 3.10, 3.11, 3.12, and 3.13, plus the minimum supported Textual version.

## Upgrade

```bash
pip install --upgrade sharp-frames
# or
pipx upgrade sharp-frames
```

New dependencies (`textual-image`, `Pillow`) install automatically. FFmpeg and FFprobe remain required for video processing and must be available on `PATH`; HDR-to-SDR conversion additionally requires FFmpeg built with `zscale`/`libzimg` support.
