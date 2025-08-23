# Implementation Plan: Two-Phase Processing with Interactive Selection

## Overview
This document outlines the implementation plan for adding interactive frame selection to the Sharp Frames TUI, allowing users to adjust selection criteria after frame extraction and see real-time preview of selection counts.

## Goals
- Allow users to see how many frames will be selected before committing
- Enable iteration on selection criteria without re-processing videos
- Provide immediate feedback as parameters are adjusted
- **Maintain 100% backward compatibility with CLI and legacy interactive modes**

## Architecture Strategy

### Backward Compatibility Approach
1. **Leave existing `SharpFrames` class untouched** - CLI and legacy modes continue using it
2. **Create modular components** using composition pattern for better maintainability
3. **Build orchestrator for TUI** that coordinates the two-phase flow
4. **Keep `sharp_frames.py` entry point unchanged**

```
CLI/Legacy → SharpFrames → Single-phase processing (unchanged)
TUI → TUIProcessor → Component-based two-phase processing (new)
```

### Component Architecture
Using composition over inheritance for better maintainability:

```python
FrameExtractor: Handles frame extraction from video/images
SharpnessAnalyzer: Calculates sharpness scores  
FrameSelector: Performs frame selection
FrameSaver: Saves selected frames to disk
TUIProcessor: Orchestrates components for two-phase flow
```

### Multi-Input Type Support
The architecture handles all three input types while preserving existing behavior:

- **Video File**: Extract → Analyze → Select → Save (with temp cleanup)
- **Image Directory**: Load → Analyze → Select → Save (no temp needed)
- **Video Directory**: Extract all → Analyze → Select → Save with video prefixes (with temp cleanup)

#### Video Directory Handling
For video directories, we preserve the current naming convention:
- Frames stored in subdirectories: `temp_dir/video_001/frame_00001.jpg`
- Output files maintain video attribution: `video01_00001.jpg`
- Selection works across all frames from all videos combined

## Implementation Plan (Test-Driven Development)

### Phase 1: Test Infrastructure Setup ✅ COMPLETED

#### Step 1.1: Create Test Fixtures ✅ DONE
- ✅ Create test video samples and image directories
- ✅ Create mock frame data with known sharpness scores  
- ✅ Define expected selection outcomes for each method

#### Step 1.2: Write Unit Tests for New Components ✅ DONE

**✅ File: `tests/test_frame_extractor.py`** - COMPLETED
```python
- ✅ test_extract_video_frames()
- ✅ test_load_image_directory()
- ✅ test_extract_video_directory_with_prefixes()
- ✅ test_temp_directory_management()
```

**✅ File: `tests/test_sharpness_analyzer.py`** - COMPLETED
```python
- ✅ test_calculate_sharpness_scores()
- ✅ test_parallel_processing()
- ✅ test_frame_data_structure_creation()
- ✅ test_video_attribution_preservation()
```

**✅ File: `tests/test_frame_selector.py`** - COMPLETED
```python
- ✅ test_preview_selection_count()
- ✅ test_best_n_selection()
- ✅ test_batched_selection()
- ✅ test_outlier_removal_selection()
```

**✅ File: `tests/test_tui_processor.py`** - COMPLETED
```python
- ✅ test_extract_and_analyze_video()
- ✅ test_extract_and_analyze_image_directory()
- ✅ test_extract_and_analyze_video_directory()
- ✅ test_complete_selection_preserves_video_attribution()
```

**✅ File: `tests/test_selection_preview.py`** - COMPLETED
```python
- ✅ test_preview_best_n_selection_count()
- ✅ test_preview_batched_selection_count()
- ✅ test_preview_outlier_removal_count()
- ✅ test_selection_count_updates_with_parameter_changes()
```

**✅ File: `tests/ui/test_selection_screen.py`** - COMPLETED
```python
- ✅ test_selection_screen_displays_total_frames()
- ✅ test_method_dropdown_changes_parameter_inputs()
- ✅ test_realtime_count_update_on_parameter_change()
- ✅ test_confirm_button_triggers_save()
```

**✅ Additional Files Created:**
- ✅ `tests/fixtures.py` - Comprehensive test fixtures and mock data
- ✅ `sharp_frames/models/__init__.py` - Models package
- ✅ `sharp_frames/models/frame_data.py` - FrameData and ExtractionResult classes

### Phase 2: Core Processing Components ✅ COMPLETED

#### Step 2.1: Create Component Classes ✅ COMPLETED

**✅ File: `sharp_frames/models/frame_data.py`** - COMPLETED
```python
✅ @dataclass
class FrameData:
    """Immutable data structure for frame information"""
    path: str
    index: int  # Global index across all frames
    sharpness_score: float
    source_video: Optional[str] = None  # e.g., "video_001"
    source_index: Optional[int] = None  # Index within that video
    output_name: Optional[str] = None  # For preserving naming

✅ @dataclass
class ExtractionResult:
    """Result of frame extraction/loading phase"""
    frames: List[FrameData]
    metadata: Dict[str, Any]  # fps, duration, source_type, etc.
    temp_dir: Optional[str] = None  # For cleanup
    input_type: str = "video"  # video, directory, video_directory
```

**✅ File: `sharp_frames/processing/frame_extractor.py`** - COMPLETED
```python
class FrameExtractor:
    """Handles frame extraction from videos and loading from directories"""
    
    def extract_frames(self, config: Dict) -> ExtractionResult:
        """Extract/load frames based on input type"""
        if config["input_type"] == "directory":
            return self._load_images(config["input_path"])
        elif config["input_type"] == "video":
            return self._extract_video_frames(config)
        elif config["input_type"] == "video_directory":
            return self._extract_video_directory_frames(config)
    
    def _extract_video_directory_frames(self, config: Dict) -> ExtractionResult:
        """Extract frames from all videos, preserving video attribution"""
        # Create frames with video prefixes like current implementation
```

**✅ File: `sharp_frames/processing/sharpness_analyzer.py`** - COMPLETED
```python
class SharpnessAnalyzer:
    """Calculates sharpness scores for frames"""
    
    def calculate_sharpness(self, extraction_result: ExtractionResult) -> ExtractionResult:
        """Add sharpness scores to frame data, preserving all metadata"""
        # Parallel processing similar to current implementation
        # Preserve video attribution in frame data
```

**✅ File: `sharp_frames/processing/frame_selector.py`** - COMPLETED
```python
class FrameSelector:
    """Handles frame selection logic"""
    
    def preview_selection(self, frames: List[FrameData], method: str, **params) -> int:
        """Calculate selection count without modifying data"""
    
    def select_frames(self, frames: List[FrameData], method: str, **params) -> List[FrameData]:
        """Apply selection method and return selected frames"""
```

**✅ File: `sharp_frames/processing/frame_saver.py`** - COMPLETED
```python
class FrameSaver:
    """Handles saving selected frames to disk"""
    
    def save_frames(self, selected_frames: List[FrameData], config: Dict) -> bool:
        """Save frames with proper naming based on input type"""
        # For video_directory: preserve video01_, video02_ prefixes
        # For video: use sequential naming
        # For directory: use original names
```

#### Step 2.2: Create TUI Orchestrator ✅ COMPLETED

**✅ File: `sharp_frames/processing/tui_processor.py`** - COMPLETED
```python
class TUIProcessor:
    """Orchestrates components for two-phase TUI processing"""
    
    def __init__(self):
        self.extractor = FrameExtractor()
        self.analyzer = SharpnessAnalyzer()
        self.selector = FrameSelector()
        self.saver = FrameSaver()
        self.current_result: Optional[ExtractionResult] = None
    
    def extract_and_analyze(self, config: Dict) -> ExtractionResult:
        """Phase 1: Extract and analyze frames"""
        extraction_result = self.extractor.extract_frames(config)
        self.current_result = self.analyzer.calculate_sharpness(extraction_result)
        return self.current_result
    
    def preview_selection(self, method: str, **params) -> int:
        """Preview selection without modifying state"""
        if not self.current_result:
            raise RuntimeError("No extraction result available")
        return self.selector.preview_selection(self.current_result.frames, method, **params)
    
    def complete_selection(self, method: str, config: Dict, **params) -> bool:
        """Phase 2: Select and save frames"""
        selected_frames = self.selector.select_frames(self.current_result.frames, method, **params)
        return self.saver.save_frames(selected_frames, config)
```

**TDD Process:**
1. Write failing tests for each component
2. Implement components to pass tests
3. Test integration between components
4. Refactor while keeping tests green

#### Step 2.3: Create Selection Preview Helper ✅ COMPLETED

**✅ File: `sharp_frames/selection_preview.py`** - COMPLETED

```python
def get_selection_count(frames_with_scores: List[Dict], method: str, **params) -> int:
    """
    Calculate how many frames would be selected without actually selecting them.
    Optimized for speed to enable real-time preview updates.
    """
    
def get_selection_preview(frames_with_scores: List[Dict], method: str, **params) -> Dict:
    """
    Return detailed preview information including:
    - count: number of frames that would be selected
    - distribution: histogram of selected frames across timeline
    - statistics: min/max/avg sharpness of selection
    """
```

**TDD Process:**
1. Test each selection method's count calculation
2. Test edge cases (empty frames, invalid params)
3. Test performance with large frame sets

### Phase 3: UI Components ⏳ PENDING

#### Step 3.1: Create Selection Screen ⏳ TODO

**⏳ File: `sharp_frames/ui/screens/selection.py`** - TODO

```python
class SelectionScreen(Screen):
    """Interactive selection screen with real-time preview."""
    
    def __init__(self, frames_data: Dict[str, Any], initial_config: Dict):
        """
        Initialize with extracted frame data and initial configuration.
        frames_data: Output from TwoPhaseSharpFrames.extract_and_analyze()
        """
        
    def compose(self) -> ComposeResult:
        """
        Create UI layout:
        - Header showing total available frames
        - Method selection dropdown
        - Dynamic parameter inputs based on selected method
        - Real-time frame count preview
        - Optional: histogram visualization of frame distribution
        - Confirm/Cancel buttons
        """
        
    def update_preview(self):
        """
        Update frame count preview based on current settings.
        Called whenever parameters change.
        Must complete within 100ms for responsive feel.
        """
        
    def on_confirm(self):
        """Proceed with selection and saving using current parameters."""
        
    def on_cancel(self):
        """Return to main menu or exit without saving."""
```

**TDD Process:**
1. Mock frames_data and test UI rendering
2. Test parameter input validation
3. Test preview updates with various parameter combinations
4. Test screen transitions

#### Step 3.2: Create New Configuration Flow ⏳ TODO

**⏳ File: `sharp_frames/ui/screens/configuration_v2.py`** - TODO

Modified configuration steps (selection method removed):
1. Input type (video/video directory/image directory)
2. Input path
3. Output directory
4. FPS (for video only)
5. Output format (jpg/png)
6. Width (for resizing)
7. Force overwrite option
8. Confirm and start processing

**TDD Process:**
1. Test step sequence excludes selection method
2. Test configuration passes to processing correctly
3. Test navigation between steps

### Phase 4: Integration ⏳ PENDING  

#### Step 4.1: Update Processing Screen ⏳ TODO

**⏳ File: `sharp_frames/ui/screens/processing.py`** - MODIFY EXISTING

Modifications:
1. Use `TwoPhaseSharpFrames` instead of `MinimalProgressSharpFrames`
2. After extraction/analysis phase completes, transition to `SelectionScreen`
3. Pass extracted frame data to selection screen
4. Handle the two-phase flow with proper progress tracking

```python
def _process_frames(self) -> bool:
    # Phase 1: Extract and analyze
    processor = TUIProcessor()
    extraction_result = processor.extract_and_analyze(self.config)
    
    # Transition to selection screen
    self.app.push_screen(SelectionScreen(processor, extraction_result, self.config))
```

**TDD Process:**
1. Test screen transition from processing to selection
2. Test data passing between screens
3. Test error handling in two-phase flow

#### Step 4.2: Update Step Handlers ⏳ TODO

Remove selection-related handlers from configuration:
- ⏳ Remove `SelectionMethodStepHandler`
- ⏳ Remove `MethodParamsStepHandler`
- ⏳ Update step list in `ConfigurationForm`

### Phase 5: Testing & Edge Cases ⏳ PENDING

#### Step 5.1: Integration Tests ⏳ TODO

**⏳ File: `tests/test_tui_integration.py`** - TODO

```python
- test_full_flow_video_input()
- test_full_flow_image_directory()
- test_full_flow_video_directory_preserves_video_prefixes()
- test_video_directory_naming_convention()
- test_cancel_at_selection_screen()
- test_back_navigation_from_selection()
- test_parameter_persistence_between_screens()
```

#### Step 5.1a: Multi-Input Type Tests ⏳ TODO

**⏳ File: `tests/test_multi_input_compatibility.py`** - TODO

```python
- test_video_directory_frame_attribution()
- test_video_directory_output_naming()
- test_image_directory_no_temp_cleanup()
- test_video_single_temp_cleanup()
- test_all_input_types_selection_semantics()
```

#### Step 5.2: Backward Compatibility Tests ⏳ TODO

**⏳ File: `tests/test_backward_compatibility.py`** - TODO

```python
- test_cli_mode_unchanged()
- test_legacy_interactive_unchanged()
- test_original_processor_still_works()
- test_existing_config_files_compatible()
```

### Phase 6: Polish & Documentation ⏳ PENDING

#### Step 6.1: Performance Optimization
- Implement caching for selection preview calculations
- Add loading states for large frame sets
- Optimize selection algorithms for preview mode
- Target: <100ms preview update for 10,000 frames

#### Step 6.2: User Experience Enhancements
- Add help text explaining each selection method
- Show tooltips for parameters
- Display visual histogram of frame distribution
- Add keyboard shortcuts for common actions
- Implement undo/redo for parameter changes

#### Step 6.3: Documentation Updates
- Update README with new TUI flow
- Document the component-based architecture
- Add usage examples for all input types
- Document video directory naming preservation
- Create migration guide for existing users

## Implementation Timeline

### Week 1: Foundation (Test Infrastructure & Core Components)
- [✅] Day 1-2: Write all test fixtures and test data
- [✅] Day 3-4: Write failing tests for all components
- [✅] Day 5: Implement core components to pass tests
- [🚧] Day 6-7: Write and implement selection preview tests **← CURRENT**

### Week 2: UI Components
- [⏳] Day 1-2: Write failing tests for `SelectionScreen`
- [⏳] Day 3-4: Implement `SelectionScreen` to pass tests
- [⏳] Day 5: Write tests for modified configuration flow
- [⏳] Day 6-7: Update configuration to remove selection steps

### Week 3: Integration
- [⏳] Day 1-2: Write integration tests (failing)
- [⏳] Day 3-4: Connect all components
- [⏳] Day 5: Fix failing integration tests
- [⏳] Day 6-7: Write and verify backward compatibility tests

### Week 4: Polish & Release
- [⏳] Day 1-2: Add edge case handling
- [⏳] Day 3: Performance optimization for large frame sets
- [⏳] Day 4-5: UI polish (loading states, help text, visualizations)
- [⏳] Day 6: Documentation updates
- [⏳] Day 7: Final testing and release preparation

## Success Criteria

### Functional Requirements
1. **All tests pass** - Unit, integration, and backward compatibility tests
2. **CLI mode unchanged** - Existing command-line arguments work identically
3. **Legacy interactive unchanged** - Terminal prompts and flow remain the same
4. **Real-time preview** - Frame count updates as parameters change
5. **Data persistence** - Extracted frames and sharpness scores are reusable

### Performance Requirements
1. **Preview updates** - Complete within 100ms for up to 10,000 frames
2. **Memory efficiency** - Handle videos with 100,000+ frames without OOM
3. **Responsive UI** - No blocking operations in the main thread

### User Experience Requirements
1. **Intuitive flow** - Users understand the two-phase process
2. **Clear feedback** - Current selection count always visible
3. **Easy iteration** - Parameter changes are immediate
4. **Graceful errors** - Clear messages for edge cases

### Technical Requirements
1. **No breaking changes** - Existing users' workflows unaffected
2. **Clean architecture** - Composition-based, single-responsibility components
3. **Maintainable code** - Well-documented and tested
4. **Extensible design** - Easy to add new selection methods
5. **Multi-input compatibility** - All three input types work correctly
6. **Video attribution preserved** - Video directory naming maintains video01_ prefixes

## Multi-Input Type Implementation Details

### Video Directory Frame Attribution
The current implementation stores frames in subdirectories and loses video context during processing. The new architecture must preserve this:

#### Current Implementation Issue
```python
# Current: loses video context
frame_id = os.path.basename(path)  # "frame_00001.jpg"
# Missing: which video did this come from?
```

#### New Implementation Solution
```python
# Enhanced frame data preserves video context
def _create_frame_data(self, path: str, index: int, score: float) -> FrameData:
    # Detect video directory structure
    path_parts = path.split(os.sep)
    if len(path_parts) >= 2 and "video_" in path_parts[-2]:
        video_dir = path_parts[-2]  # e.g., "video_001"
        video_num = video_dir.split("_")[1]  # "001"
        output_name = f"video{video_num}_{index+1:05d}"
        return FrameData(
            path=path,
            index=index,
            sharpness_score=score,
            source_video=video_dir,
            output_name=output_name
        )
```

### Input-Type Specific Processing
Each input type has different requirements:

| Input Type | Extraction | Temp Dir | Naming | Cleanup |
|------------|------------|----------|---------|---------|
| **video** | FFmpeg to temp | Yes | Sequential | Yes |
| **directory** | Load existing | No | Original names | No |
| **video_directory** | FFmpeg each to subdir | Yes | video01_XXXXX | Yes |

### Frame Data Structure Evolution
```python
# Before: simple structure
{
    "id": "frame_00001.jpg",
    "path": "/tmp/frame_00001.jpg", 
    "index": 0,
    "sharpnessScore": 125.4
}

# After: enhanced with video attribution
FrameData(
    path="/tmp/video_001/frame_00001.jpg",
    index=0,  # Global index across all frames
    sharpness_score=125.4,
    source_video="video_001",
    source_index=0,  # Index within source video
    output_name="video01_00001"  # Preserves current naming
)
```

## Risk Mitigation

### Risk 1: Performance with Large Frame Sets
- **Mitigation**: Implement lazy loading and pagination
- **Fallback**: Add option to use traditional flow for very large sets

### Risk 2: Breaking Existing Workflows
- **Mitigation**: Comprehensive backward compatibility tests
- **Fallback**: Keep both implementations with feature flag

### Risk 3: Complex UI State Management
- **Mitigation**: Use proper state management patterns
- **Fallback**: Simplify UI if complexity becomes unmanageable

## Future Enhancements (Post-MVP)

1. **Visual Preview**: Show thumbnail grid of selected frames
2. **Advanced Filters**: Add additional selection criteria (face detection, color analysis)
3. **Batch Operations**: Process multiple videos with same selection criteria
4. **Export Settings**: Save and load selection presets
5. **Cloud Processing**: Option to process large videos in the cloud
6. **ML Selection**: Use machine learning for intelligent frame selection

## Conclusion

This implementation plan provides a structured approach to adding interactive frame selection to Sharp Frames while maintaining complete backward compatibility. The test-driven development approach ensures quality and reliability, while the phased implementation allows for iterative development and early feedback.