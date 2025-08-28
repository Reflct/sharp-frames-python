"""
CSS styles for Sharp Frames UI components.
"""

# Main application styles
SHARP_FRAMES_CSS = """
Screen {
    layout: vertical;
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
    margin: 1 0;
    padding: 1;
    border: solid #3190FF;
    background: $surface;
}

.buttons {
    margin: 0 0 1 0;
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
    height: 1fr;
    min-height: 0;
}

#step-container {
    height: 1fr;
    padding: 0 1;
    min-height: 0;
    overflow: auto;
}

#processing-container {
    padding: 1;
    text-align: center;
}

#phase-text {
    margin: 0 0 2 0;
    color: $text-muted;
    text-style: italic;
}

Input {
    margin: 0;
}

Select {
    margin: 0;
}

RadioSet {
    margin: 0;
}

Checkbox {
    margin: 0;
}

Label {
    margin: 0;
}

/* Input field enhancements */
Input.-valid {
    border: solid $success;
}

Input.-invalid {
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

/* New Selection Screen Styles - Clean Layout without Preview */
#main_content {
    padding: 1;
    height: auto;
}

/* Title section - horizontal layout */
.title_section {
    height: 1;
    margin: 0 0 1 0;
}

.title_left {
    text-style: bold;
    color: $primary;
    text-align: left;
    height: 1;
    width: 1fr;
}

.title_right {
    color: $text-muted;
    text-align: right;
    height: 1;
    width: 1fr;
}

/* Sharpness chart */
SharpnessChart {
    height: 12;
    width: 100%;
    border: solid $primary;
    margin: 1 0;
    background: $surface-lighten-1;
}

/* Controls section takes remaining space */
.controls {
    margin: 1 0 2 0;
    height: auto;
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

InputWithControls Input {
    width: 20;
    margin: 0 1 0 0;
    height: 3;
}

InputWithControls .increment-controls {
    width: 8;
    layout: horizontal;
    height: 3;
}

InputWithControls .increment-btn,
InputWithControls .decrement-btn {
    height: 3 !important;
    width: 3 !important;
    margin: 0 !important;
    padding: 0 !important;
    min-width: 3 !important;
    min-height: 3 !important;
    max-height: 3 !important;
    max-width: 3 !important;
    content-align: center middle;
    text-align: center;
}

InputWithControls .decrement-btn {
    margin-right: 2 !important;
}

/* Action buttons inside main content */
.action_buttons {
    align: center middle;
    margin: 2 0 1 0;
    height: 3;
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
}

.success_text_container {
    layout: vertical;
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
""" 