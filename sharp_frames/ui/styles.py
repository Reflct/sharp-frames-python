"""
CSS styles for Sharp Frames UI components.
"""

# Main application styles
SHARP_FRAMES_CSS = """
Screen {
    layout: vertical;
}

ConfigurationForm {
    align-horizontal: center;
}

ProcessingScreen {
    align: center middle;
}

Header {
    dock: top;
}

Footer {
    dock: bottom;
}

.title {
    text-align: center;
    margin: 0 0 1 0;
    color: #3190FF;
    content-align: center middle;
}

.step-info {
    text-align: center;
    margin: 0;
    color: $text-muted;
}

.question {
    text-style: bold;
    margin: 1 0 0 0;
    color: #3190FF;
}

.hint {
    margin: 0;
    color: $text-muted;
    text-style: italic;
}

.error-message {
    margin: 0;
    color: $error;
    text-style: bold;
}

.summary {
    height: auto;
    margin: 1 0;
    padding: 1;
    border: solid #3190FF;
    background: $surface;
}

.buttons {
    margin: 3 0 0 0;
    align: center middle;
    height: 3;
}

Button {
    margin: 0 1;
}

/* Primary button styling - white text on blue background, no highlight */
Button.-primary {
    background: $primary;
    color: white;
    text-style: not reverse;
}

Button.-primary:hover {
    background: $primary-lighten-1;
    color: white;
    text-style: not reverse;
}

Button.-primary:focus {
    background: $primary;
    color: white;
    text-style: not reverse;
}

/* Success button styling - white text on green background, no highlight */
Button.-success {
    background: $success;
    color: white;
    text-style: not reverse;
}

Button.-success:hover {
    background: $success-lighten-1;
    color: white;
    text-style: not reverse;
}

Button.-success:focus {
    background: $success;
    color: white;
    text-style: not reverse;
}

#main-container {
    padding: 1;
    height: auto;
    max-height: 100%;
    min-height: 0;
    width: 110;
    max-width: 100%;
    overflow-y: auto;
}

#form-sequence {
    height: 1fr;
    min-height: 0;
    width: 100%;
    align: center middle;
}

#step-container {
    height: auto;
    width: 100%;
    padding: 0 1;
    min-height: 0;
    overflow: auto;
}

#processing-container {
    padding: 1 3;
    margin: 0;
    height: auto;
    text-align: left;
    width: 84;
    max-width: 100%;
    border: solid $surface-lighten-1;
    background: $surface;
}

#status-text {
    height: auto;
    margin: 0;
    color: $text;
    text-style: bold;
}

#phase-text {
    height: 1;
    margin: 0;
    color: $text-muted;
}

#progress-bar {
    height: 1;
    width: 100%;
    margin: 1 0;
}

#progress-bar .block-progress--filled {
    color: $primary;
    background: $primary;
}

#progress-bar .block-progress--empty {
    color: $surface-lighten-2;
    background: $surface-lighten-2;
}

#progress-bar .block-progress--percentage {
    color: $text;
    background: $surface;
}

#detail-text {
    height: auto;
    margin: 0 0 1 0;
    color: $text-muted;
}

#cancel-processing {
    min-width: 16;
    margin: 1 0 0 0;
    color: white;
    text-style: bold not reverse;
}

#cancel-processing:hover,
#cancel-processing:focus,
#cancel-processing.-active {
    color: white;
    text-style: bold not reverse;
}

Input {
    margin: 0;
    border: solid $surface;
}

Input:focus {
    border: solid $primary;
}

Select {
    margin: 0;
    border: solid $surface;
}

Select:focus {
    border: solid $primary;
}

RadioSet {
    margin: 0;
    padding: 1 2;
    background: $surface;
    border: solid $surface;
}

RadioSet:focus {
    border: solid $primary;
}

Checkbox {
    margin: 0;
    padding: 1 2;
    background: $surface;
    border: solid $surface;
}

Checkbox:focus {
    border: solid $primary;
}

Label {
    margin: 0;
}

/* Field styles for v2 configuration steps */
.field-label {
    margin: 1 0 0 0;
    text-style: bold;
    color: $text;
}

.field-input {
    width: 30;
    margin: 0 0 1 0;
}

.field-select {
    width: 50;
    margin: 0 0 1 0;
}

.field-checkbox {
    margin: 0 0 1 0;
}

.summary-section-title {
    text-style: bold;
    color: $primary;
    margin: 1 0 0 0;
}


/* Input field enhancements - validation states */
Input.-valid {
    border: solid $success;
}

Input.-invalid {
    border: solid $error;
}

Select.-valid {
    border: solid $success;
}

Select.-invalid {
    border: solid $error;
}

/* Selection screen styles */
#selection-container {
    padding: 1;
    height: 1fr;
    layout: horizontal;
}

#method-selection {
    width: 1fr;
    padding: 0 1 0 0;
}

#parameter-inputs {
    width: 1fr;
    padding: 0 1;
    border-left: solid $primary;
}

#preview-panel {
    width: 1fr;
    padding: 0 0 0 1;
    border-left: solid $primary;
}

.method-title {
    text-style: bold;
    margin: 0 0 1 0;
    color: #3190FF;
}

.parameter-group {
    margin: 1 0;
    padding: 1;
    border: solid $surface;
    background: $surface;
}

.parameter-label {
    text-style: bold;
    margin: 0 0 0 0;
    color: $text;
}

.preview-stats {
    margin: 1 0;
    padding: 1;
    border: solid #3190FF;
    background: $surface;
}

.stat-row {
    margin: 0;
    layout: horizontal;
}

.stat-label {
    width: 1fr;
    text-align: left;
    color: $text-muted;
}

.stat-value {
    width: 1fr; 
    text-align: right;
    text-style: bold;
    color: $text;
}

.distribution-info {
    margin: 1 0 0 0;
    padding: 1;
    background: $surface;
    text-style: italic;
    color: $text-muted;
}

#processing-status {
    margin: 1 0;
    text-align: center;
    color: $text-muted;
}

/* Two-phase processing styles */
#phase-container {
    padding: 1;
    text-align: center;
}

#phase-progress {
    margin: 2 0;
}

.phase-title {
    text-style: bold;
    margin: 0 0 1 0;
    color: #3190FF;
    text-align: center;
}

.phase-description {
    margin: 0 0 2 0;
    color: $text-muted;
    text-align: center;
}

.phase-stats {
    margin: 1 0;
    padding: 1;
    border: solid #3190FF;
    background: $surface;
    text-align: left;
}

#extraction-progress {
    margin: 1 0;
}

#analysis-progress {
    margin: 1 0;
}

/* Configuration v2 styles */
#configuration-container {
    padding: 1;
    height: 1fr;
    width: 110;
    max-width: 100%;
}

.step-title {
    text-style: bold;
    margin: 1 0 0 0;
    color: #3190FF;
    text-align: center;
}

.step-description {
    margin: 0 0 1 0;
    color: $text-muted;
    text-align: center;
    text-style: italic;
}

#step-content {
    height: 1fr;
    min-height: 0;
    overflow: auto;
    margin: 1 0;
}

#navigation-buttons {
    dock: bottom;
    height: 3;
    align: center middle;
    margin: 1 0 0 0;
}

.button-row {
    layout: horizontal;
    align: center middle;
    height: 3;
}

/* Performance indicators */
.performance-good {
    color: $success;
    text-style: bold;
}

.performance-warning {
    color: $warning;
    text-style: bold;
}

.performance-error {
    color: $error;
    text-style: bold;
}

/* Selection screen */
#main_content {
    padding: 1;
    height: 1fr;
    min-height: 0;
    overflow-y: auto;
}

.bounded-row {
    height: auto;
    width: 100%;
    align-horizontal: center;
}

/* Full-resolution source preview. The terminal raster backend performs the
   fit-to-window resampling; the source file is never rewritten. It is given
   more of the flexible vertical space than the chart below it. */
RasterImagePreview {
    height: 2fr;
    min-height: 12;
    width: 100%;
    margin: 0 0 1 0;
    padding: 0 1;
    border: solid $surface;
    background: $background;
}

RasterImagePreview.-unsupported {
    height: 5;
    min-height: 5;
    max-height: 5;
}

.frame-preview-title {
    height: 1;
    width: 100%;
    color: $text-muted;
    text-align: center;
}

.frame-preview-canvas {
    height: 1fr;
    width: 100%;
    align: center middle;
    overflow: hidden;
}

#frame_preview_image {
    width: auto;
    height: auto;
    max-width: 100%;
    max-height: 100%;
}

.frame-preview-fallback {
    height: 2;
    width: 100%;
    color: $warning;
    text-align: center;
    content-align: center middle;
}

/* Sharpness chart */
SharpnessChart {
    height: 1fr;
    min-height: 13;
    width: 100%;
    border: solid $primary;
    margin: 1 0;
    background: $background;
}

/* Controls section takes remaining space */
.controls {
    margin: 1 0 2 0;
    height: auto;
    width: 120;
    max-width: 100%;
}

.control_group {
    width: 1fr;
    padding: 1 2 1 1;
    border: solid $surface;
    margin: 0 1;
    height: auto;
    min-height: 12;
}

.control_label {
    text-style: bold;
    color: $primary;
    margin: 0 0 1 0;
    height: 1;
}

.description {
    color: $text-muted;
    text-style: italic;
    margin: 1 0 0 0;
    height: auto;
}

.parameter_inputs {
    margin: 1 0 0 0;
    height: auto;
    min-height: 6;
}

.param_label {
    margin: 1 0 0 0;
    color: $text;
    height: 1;
}

.param_input {
    margin: 0 0 1 0;
    height: 3;
    width: 100%;
}

/* Input with controls styles */
.param_input_with_controls {
    margin: 0 0 1 0;
    height: 3;
    width: 100%;
}

InputWithControls {
    height: 3;
    layout: horizontal;
    margin: 0 0 1 0;
}

/* Keep the parameter panel compact, with one deliberate row after the title
   and between each complete label/input control group. */
#parameter_container {
    padding: 1 2 0 1;
    min-height: 10;
}

#parameter_container .parameter_inputs,
#parameter_container .param_label {
    margin: 0;
}

#parameter_container .control_label,
#parameter_container .param_input_with_controls,
#parameter_container InputWithControls {
    margin: 0 0 1 0;
}

#parameter_container .param_input_with_controls:last-child,
#parameter_container InputWithControls:last-child {
    margin-bottom: 0;
}

#parameter_container .parameter_inputs {
    min-height: 0;
}

InputWithControls Input {
    width: 20;
    margin: 0 1 0 0;
    height: 3;
    border: solid #9f9f9f;
}

InputWithControls Input.-valid {
    border: solid #9f9f9f;
}

InputWithControls Input:focus,
InputWithControls Input.-valid:focus {
    border: solid $primary;
}

InputWithControls .stepper-controls {
    width: 14;
    layout: horizontal;
    height: 3;
}

InputWithControls .stepper-button {
    height: 3 !important;
    width: 7 !important;
    margin: 0 !important;
    padding: 0 !important;
    min-width: 7 !important;
    min-height: 3 !important;
    max-height: 3 !important;
    max-width: 7 !important;
    content-align: center middle;
    text-align: center;
    color: $text-muted;
    background: $surface;
    border: tall $surface-lighten-1;
    text-style: bold;
}

InputWithControls .stepper-button:hover {
    color: $text;
    background: $surface-lighten-1;
    border: tall $surface-lighten-2;
}

InputWithControls .stepper-button:focus {
    color: $text;
    background: $surface;
    border: tall $primary;
}

/* Action buttons inside main content */
.action_buttons {
    align: center middle;
    margin: 2 0 1 0;
    height: 3;
}

/* Compact tier for short terminals. The default spacing needs ~56 rows to
   keep the whole screen above the fold; below that spacing tightens and the
   preview and chart shrink so both stay in the viewport. The chart uses a
   percentage and the preview is the only fr child: with two or more fr
   siblings whose minimums exceed the free space, Textual falls back to
   sizing every fr child against the whole remaining space, which balloons
   the preview and pushes the chart below the fold. The action buttons dock
   to the bottom so Save stays visible even when the controls overflow into
   the scrollable area on tiny terminals. */
SelectionScreen.-vertical-compact #main_content {
    padding: 0 1;
}

SelectionScreen.-vertical-compact RasterImagePreview {
    min-height: 4;
    margin: 0;
}

SelectionScreen.-vertical-compact RasterImagePreview.-unsupported {
    min-height: 5;
}

SelectionScreen.-vertical-compact SharpnessChart {
    height: 25%;
    min-height: 6;
}

SelectionScreen.-vertical-compact .controls {
    margin: 0;
}

SelectionScreen.-vertical-compact .control_group {
    padding: 0 2 0 1;
    min-height: 0;
}

SelectionScreen.-vertical-compact #parameter_container {
    padding: 0 2 0 1;
    min-height: 0;
}

SelectionScreen.-vertical-compact .action_buttons {
    dock: bottom;
    margin: 1 0 0 0;
}

.action_buttons Button {
    margin: 0 2;
    min-width: 15;
}

/* Success container for after save completion */
.success_container {
    layout: horizontal;
    align: center middle;
    padding: 1 2;
    margin: 1 0;
    border: solid $success;
    height: auto;
    width: 100;
    max-width: 100%;
}

.success_text_container {
    layout: vertical;
    height: auto;
    padding: 0 2 0 0;
}

.success_message {
    text-align: left;
    text-style: bold;
    color: $success;
    margin: 0;
    height: 1;
}

.success_details {
    text-align: left;
    color: $text;
    margin: 0;
    height: 1;
}

#start_over_button {
    margin: 0 0 0 2;
    min-width: 12;
}

.processing_indicator {
    text-align: center;
    margin: 2 0;
    padding: 1 2;
    color: $primary;
    text-style: bold;
}

.success-row {
    height: auto;
}
"""
