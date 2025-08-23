# TODO - Sharp Frames Python

## Critical Issues

### 1. Command Injection Vulnerability
The application constructs FFmpeg commands using user-provided paths (`self.input_path`) directly in subprocess calls without proper sanitization. While the code uses list-based subprocess calls (which is safer than shell=True), file paths with special characters could still cause issues.
- **Location**: `sharp_frames_processor.py` lines 413-420, 456-465
- **Priority**: HIGH
- **Solution**: Sanitize all file paths before passing to subprocess commands

### 2. Resource Exhaustion Risks
- **Memory Issues**: The `_fill_remaining_slots` function in selection_methods.py iterates through all potential candidates for each remaining slot, which is O(n²) complexity. For large video files with thousands of frames, this could consume excessive memory and CPU.
- **Unbounded Parallel Processing**: The ThreadPoolExecutor uses `cpu_count()` workers without any upper limit, which could overwhelm systems with many cores when processing large frame sets.
- **Location**: `selection_methods.py` lines 82-123, `sharp_frames_processor.py` line 672
- **Priority**: HIGH
- **Solution**: Implement chunked processing and add memory usage limits for parallel processing

### 3. Race Conditions in Temp Directory Cleanup
The temp directory cleanup in the finally block could fail if another process is still accessing the files, leading to incomplete cleanup and disk space leaks.
- **Location**: `sharp_frames_processor.py` lines 259-265
- **Priority**: MEDIUM
- **Solution**: Add retry logic with exponential backoff for temp directory cleanup

## Error Handling Issues

### 4. Silent Failures in Video Processing
When processing video directories, errors in individual videos are caught and logged but don't affect the overall return status. This could lead to partial processing appearing successful.
- **Location**: `sharp_frames_processor.py` lines 319-321
- **Priority**: MEDIUM
- **Solution**: Track failed videos and report partial success appropriately

### 5. Inconsistent Error Propagation
Some errors are caught and re-raised with modified messages, while others are silently logged. This inconsistency makes debugging difficult.
- **Location**: `sharp_frames_processor.py` line 626
- **Priority**: LOW
- **Solution**: Standardize error handling patterns throughout the codebase

### 6. Missing Validation for FFmpeg Output
The code doesn't verify that FFmpeg actually created the expected output files before proceeding with analysis.
- **Location**: `sharp_frames_processor.py` after line 578
- **Priority**: MEDIUM
- **Solution**: Add frame verification after FFmpeg extraction completes

## Performance Issues

### 7. Inefficient Frame Monitoring
The frame extraction monitoring constantly lists directory contents in a tight loop, which is I/O intensive and inefficient.
- **Location**: `sharp_frames_processor.py` lines 521-535
- **Priority**: MEDIUM
- **Solution**: Use file system watchers or implement exponential backoff for directory polling

### 8. Blocking I/O in Progress Updates
The stderr reading thread could block on readline() if FFmpeg produces partial lines, potentially hanging the extraction process.
- **Location**: `sharp_frames_processor.py` lines 503-514
- **Priority**: LOW
- **Solution**: Use non-blocking I/O or asyncio for stderr reading

### 9. Quadratic Complexity in Best-N Selection
The `_fill_remaining_slots` function has O(n²) time complexity as it checks all remaining frames against all selected frames for each selection.
- **Location**: `selection_methods.py` lines 82-123
- **Priority**: MEDIUM
- **Solution**: Optimize selection algorithms using spatial data structures or preprocessing

## Data Integrity Issues

### 10. Frame Ordering Assumptions
The code assumes frame filenames follow a specific pattern (frame_XXXXX) and sorts by extracting the number. This could fail with different naming schemes.
- **Location**: `sharp_frames_processor.py` line 662
- **Priority**: LOW
- **Solution**: Make frame naming and sorting more robust and configurable

### 11. Incomplete Metadata Saving
If the metadata JSON write fails after frames are copied, there's no rollback mechanism, leaving the output in an inconsistent state.
- **Location**: `sharp_frames_processor.py` lines 747-812
- **Priority**: MEDIUM
- **Solution**: Implement transaction-like behavior for output operations

## Platform-Specific Issues

### 12. Signal Handler Conflicts
The TUI's signal handler modifications could interfere with FFmpeg's subprocess handling, especially on macOS where special handling is already implemented.
- **Location**: `ui/app.py` lines 37-76
- **Priority**: LOW
- **Solution**: Review and isolate signal handling for subprocesses

### 13. Windows Path Handling
While the code expands `~` for user paths, it doesn't handle Windows-specific path issues like UNC paths or paths with spaces consistently.
- **Location**: Throughout path handling code
- **Priority**: LOW
- **Solution**: Implement comprehensive cross-platform path normalization

## User Experience Issues

### 14. No Resume Capability
If processing is interrupted, there's no way to resume from where it left off, requiring complete reprocessing.
- **Priority**: MEDIUM
- **Solution**: Implement progress persistence and resume capability

### 15. Limited Format Support
The hardcoded `SUPPORTED_IMAGE_EXTENSIONS` only includes basic formats, missing common formats like `.webp`, `.tiff`, `.bmp`.
- **Location**: `sharp_frames_processor.py` line 62
- **Priority**: LOW
- **Solution**: Expand image format support to include more common formats

## Additional Improvements

### 16. Memory Usage Monitoring
Add memory usage tracking and limits to prevent system exhaustion during processing of large datasets.
- **Priority**: MEDIUM

### 17. Configurable Timeouts
Make all timeouts (FFmpeg process, subprocess operations) configurable rather than hardcoded.
- **Priority**: LOW

### 18. Better Progress Estimation
Improve progress estimation for videos without duration metadata.
- **Priority**: LOW

### 19. Batch Processing API
Add support for processing multiple videos/directories in a single batch with aggregated results.
- **Priority**: LOW

### 20. Dry Run Mode
Implement a dry-run mode that shows what would be processed without actually doing it.
- **Priority**: LOW

## Security Enhancements

### 21. Input Validation
Strengthen input validation for all user-provided parameters, especially file paths and numeric values.
- **Priority**: HIGH

### 22. Temporary File Security
Ensure temporary files are created with appropriate permissions and in secure locations.
- **Priority**: MEDIUM

### 23. Resource Limits
Implement configurable resource limits (CPU, memory, disk space) to prevent denial of service.
- **Priority**: MEDIUM

## Testing Improvements

### 24. Integration Tests
Add comprehensive integration tests for video processing workflows.
- **Priority**: MEDIUM

### 25. Performance Benchmarks
Create performance benchmarks to track and prevent performance regressions.
- **Priority**: LOW

## Documentation

### 26. API Documentation
Add comprehensive API documentation for all public methods and classes.
- **Priority**: LOW

### 27. Error Message Catalog
Create a catalog of all error messages with explanations and solutions.
- **Priority**: LOW

---

## Priority Levels
- **HIGH**: Security vulnerabilities or critical bugs that could cause data loss
- **MEDIUM**: Performance issues or bugs that affect user experience
- **LOW**: Enhancements or minor issues that don't significantly impact functionality

## Implementation Order
1. Address all HIGH priority security issues first
2. Fix MEDIUM priority data integrity and error handling issues
3. Optimize performance bottlenecks
4. Implement user experience improvements
5. Add nice-to-have features and enhancements