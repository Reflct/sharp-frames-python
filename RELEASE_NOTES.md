# Sharp Frames v0.1.3 Release Notes

We're excited to announce the release of Sharp Frames v0.1.3, which introduces a new image resizing feature and important fixes to improve reliability.

## New Feature: Image Resizing

This release adds support for resizing extracted frames or processed images to a specified width while maintaining aspect ratio. This is particularly useful when working with high-resolution videos or images and you need a more manageable output size.

### How to Use

- **Command Line**: Use the new `--width` parameter to specify the desired width in pixels
  ```bash
  sharp-frames my_video.mp4 ./output_dir --width 800
  ```

- **Interactive Mode**: You'll now be prompted for a resize width (enter 0 for no resizing)

### Technical Notes

- The resize feature works for both video extraction and directory processing modes
- Aspect ratio is always preserved - only the width needs to be specified
- For video processing, resizing happens during the extraction phase using FFmpeg
- For directory processing, resizing happens during the save phase using OpenCV
- Output dimensions are always even to ensure compatibility with video codecs

## Fixes

- **Improved FFmpeg Subprocess Handling**: Resolved issues with subprocess buffer management that could cause the extraction process to hang
- **Odd Dimension Handling**: Fixed issues with videos that have odd pixel dimensions by ensuring even output dimensions

## Upgrading

To upgrade to the latest version, run:

```bash
pip install --upgrade sharp-frames
```

Or if you used pipx:

```bash
pipx upgrade sharp-frames
```

## Feedback and Support

If you encounter any issues or have suggestions for future improvements, please submit them to our GitHub repository or join our Discord community. We appreciate your feedback!

---

The Sharp Frames Team at Reflct.app 