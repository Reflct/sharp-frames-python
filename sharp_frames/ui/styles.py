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
""" 