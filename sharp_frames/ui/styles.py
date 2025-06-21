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
    color: $accent;
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
    color: $primary;
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
    border: solid $primary;
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
""" 