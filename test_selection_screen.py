#!/usr/bin/env python3
"""
Test script for the selection screen parameter controls.
"""

import sys
from pathlib import Path
from typing import Dict, Any, List

# Add the package to the path
sys.path.insert(0, str(Path(__file__).parent))

from sharp_frames.models.frame_data import FrameData, ExtractionResult
from sharp_frames.processing.tui_processor import TUIProcessor
from sharp_frames.ui.screens.selection import SelectionScreen
from textual.app import App
from textual.containers import Container, Horizontal
from textual.widgets import Static, Label, Button, Select, Input, Header, Footer
from textual.screen import Screen
from textual.app import ComposeResult


def format_large_number(number: int) -> str:
    """Convert a number to large ASCII-style text."""
    # Simple ASCII art digits for demonstration
    digits = {
        '0': ['███', '█ █', '█ █', '███'],
        '1': ['  █', '  █', '  █', '  █'],
        '2': ['███', '  █', '█  ', '███'],
        '3': ['███', '  █', '  █', '███'],
        '4': ['█ █', '███', '  █', '  █'],
        '5': ['███', '█  ', '  █', '███'],
        '6': ['███', '█  ', '█ █', '███'],
        '7': ['███', '  █', '  █', '  █'],
        '8': ['███', '█ █', '█ █', '███'],
        '9': ['███', '█ █', '  █', '███'],
        ',': ['   ', '   ', ' ▄ ', ' ▄ ']
    }
    
    # Convert number to string with commas
    num_str = f"{number:,}"
    
    # Build ASCII art line by line
    lines = ['', '', '', '']
    for char in num_str:
        if char in digits:
            for i, line in enumerate(digits[char]):
                lines[i] += line + ' '
        else:
            # For other characters, add spaces
            for i in range(4):
                lines[i] += '    '
    
    return '\n'.join(lines)


class MockSelectionScreen(Screen):
    """Mock selection screen for testing the new layout."""
    
    def __init__(self):
        super().__init__()
        self.current_count = 300
        self.total_frames = 1000
        self.current_method = "best_n"
        
        # Method definitions
        self.method_definitions = {
            "best_n": {
                "name": "Best N Frames",
                "description": "Select the N sharpest frames with good distribution",
                "parameters": {
                    "n": {"type": "int", "default": 300, "min": 1, "max": 10000, "label": "Number of frames"},
                    "min_buffer": {"type": "int", "default": 3, "min": 0, "max": 100, "label": "Minimum distance between frames"}
                }
            },
            "batched": {
                "name": "Batched Selection", 
                "description": "Process frames in small consecutive groups with gaps between groups",
                "parameters": {
                    "batch_size": {"type": "int", "default": 5, "min": 1, "max": 100, "label": "Frames per batch"},
                    "batch_buffer": {"type": "int", "default": 2, "min": 0, "max": 50, "label": "Frames to skip between batches"}
                }
            },
            "outlier_removal": {
                "name": "Outlier Removal",
                "description": "Remove frames with unusually low sharpness scores compared to neighbors",
                "parameters": {
                    "outlier_sensitivity": {"type": "int", "default": 50, "min": 0, "max": 100, "label": "Removal aggressiveness (0-100)"},
                    "outlier_window_size": {"type": "int", "default": 15, "min": 3, "max": 30, "label": "Neighbor comparison window"}
                }
            }
        }
    
    def compose(self) -> ComposeResult:
        """Create the improved selection screen layout."""
        yield Header()
        
        # Main content container
        with Container(id="main_content"):
            # Title section
            yield Static("Select Frames", classes="main_title")
            yield Static(f"Choose from {self.total_frames:,} analyzed frames", classes="subtitle")
            
            # Compact preview with large ASCII numbers
            with Container(id="preview_section", classes="preview_main"):
                yield Static(format_large_number(self.current_count), id="ascii_count", classes="ascii_number")
                yield Static("frames will be selected", classes="selection_label")
                yield Static(f"{(self.current_count/self.total_frames*100):.1f}% of total", 
                           classes="percentage")
            
            # Controls section
            with Horizontal(id="controls_section", classes="controls"):
                # Method selection
                with Container(id="method_container", classes="control_group"):
                    yield Label("Selection Method", classes="control_label")
                    yield Select(
                        options=[(info["name"], key) for key, info in self.method_definitions.items()],
                        value=self.current_method,
                        id="method_select"
                    )
                    yield Static(self.method_definitions[self.current_method]["description"], 
                               id="method_description", classes="description")
                
                # Parameters
                with Container(id="parameter_container", classes="control_group"):
                    yield Label("Parameters", classes="control_label")
                    with Container(id="parameter_inputs", classes="parameter_inputs"):
                        # Best N parameters by default
                        yield Label("Number of frames:", classes="param_label")
                        yield Input(value="300", id="param_n", classes="param_input")
                        yield Label("Minimum distance between frames:", classes="param_label")
                        yield Input(value="3", id="param_min_buffer", classes="param_input")
        
        # Fixed bottom buttons like earlier steps
        with Container(classes="bottom_buttons"):
            yield Button("← Back", id="back_button", variant="default")
            yield Button(f"Process {self.current_count:,} Frames", id="confirm_button", variant="success")
        
        yield Footer()
    
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes and update preview."""
        if event.input.id == "param_n":
            try:
                new_count = int(event.value) if event.value.strip() else 300
                new_count = max(1, min(new_count, self.total_frames))
                self.current_count = new_count
                
                # Update ASCII display
                ascii_widget = self.query_one("#ascii_count")
                ascii_widget.update(format_large_number(new_count))
                
                # Update percentage
                percentage_widget = self.query_one(".percentage")
                percentage_widget.update(f"{(new_count/self.total_frames*100):.1f}% of total")
                
                # Update button
                button = self.query_one("#confirm_button")
                button.label = f"Process {new_count:,} Frames"
                
            except ValueError:
                pass
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "back_button":
            self.app.pop_screen()
        elif event.button.id == "confirm_button":
            self.app.exit(f"Processing {self.current_count} frames")


class TestSelectionApp(App):
    """Test app for the selection screen."""
    
    CSS = """
    #main_content {
        padding: 1;
        height: 100%;
    }
    
    .main_title {
        text-align: center;
        text-style: bold;
        color: $primary;
        margin: 0 0 1 0;
        height: 1;
    }
    
    .subtitle {
        text-align: center;
        color: $text-muted;
        margin: 0 0 1 0;
        height: 1;
    }
    
    /* Compact preview section with large ASCII numbers */
    .preview_main {
        border: solid $primary;
        padding: 1 2;
        margin: 0 0 1 0;
        align: center middle;
        background: $boost;
        height: 6;
    }
    
    .ascii_number {
        text-style: bold;
        color: $success;
        text-align: center;
        content-align: center middle;
        height: 3;
        width: 100%;
    }
    
    .selection_label {
        text-align: center;
        margin: 0;
        height: 1;
        color: $text;
    }
    
    .percentage {
        text-align: center;
        color: $text-muted;
        margin: 0;
        height: 1;
    }
    
    /* Controls section takes remaining space */
    .controls {
        margin: 0 0 1 0;
        height: auto;
    }
    
    .control_group {
        width: 1fr;
        padding: 1;
        border: solid $surface;
        margin: 0 1;
        height: auto;
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
    
    /* Fixed buttons at bottom like earlier steps */
    .bottom_buttons {
        dock: bottom;
        height: 5;
        width: 100%;
        background: $surface;
        border-top: solid $primary;
        align: center middle;
        padding: 1;
    }
    
    .bottom_buttons Button {
        margin: 0 2;
        min-width: 20;
    }
    """
    
    def on_mount(self) -> None:
        """Set up the test selection screen."""
        # Use our mock screen with the new layout
        self.push_screen(MockSelectionScreen())


def main():
    """Run the test app."""
    print("Testing Selection Screen Parameter Controls")
    print("=" * 60)
    print("This will launch a test UI with mock data.")
    print("Check that:")
    print("1. Parameter inputs are visible")
    print("2. Changing selection method updates parameters")
    print("3. Changing parameters updates the frame count")
    print("=" * 60)
    print("\nPress Ctrl+C to exit the UI\n")
    
    app = TestSelectionApp()
    app.run()


if __name__ == "__main__":
    main()