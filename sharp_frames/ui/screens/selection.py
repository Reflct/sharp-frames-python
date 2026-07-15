"""
Interactive selection screen for Sharp Frames TUI.
"""

import asyncio
from typing import Dict, Any, Optional, List

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.css.query import NoMatches
from textual.events import Resize
from textual.geometry import Size
from textual.message import Message
from textual.reactive import reactive
from textual.screen import Screen
from textual.scroll_view import ScrollView
from textual.strip import Strip
from textual.widget import Widget
from textual.widgets import (
    Button, Footer, Header, Input, Label, Select, Static
)

from rich.segment import Segment
from rich.style import Style

from ...models.frame_data import ExtractionResult, FrameData
from ...processing.tui_processor import TUIProcessor
from ..keyboard import OptionSelect, select_focused_option


class SharpnessChart(ScrollView):
    """Horizontally scrollable frame-by-frame sharpness timeline."""

    FRAME_STRIDE = 2
    BAR_GLYPHS = (" ", "▁", "▂", "▃", "▄", "▅", "▆", "▇", "█")
    VERTICAL_SUBDIVISIONS = len(BAR_GLYPHS) - 1
    can_focus = True

    BINDINGS = [
        Binding("left", "scroll_left", "Scroll Left", show=False),
        Binding("right", "scroll_right", "Scroll Right", show=False),
        Binding("ctrl+pageup", "page_left", "Page Left", show=False),
        Binding("ctrl+pagedown", "page_right", "Page Right", show=False),
        Binding("home", "first_frame", "First Frame", show=False),
        Binding("end", "last_frame", "Last Frame", show=False),
    ]

    COMPONENT_CLASSES = {
        "sharpness-chart--background",
        "sharpness-chart--selected",
        "sharpness-chart--unselected",
        "sharpness-chart--title",
    }

    DEFAULT_CSS = """
    SharpnessChart {
        height: 13;
        width: 100%;
        border: solid $primary;
        margin: 1 0;
        overflow-x: auto;
        overflow-y: hidden;
        background: $background;
    }

    SharpnessChart:focus {
        border: tall $accent;
    }

    SharpnessChart .sharpness-chart--background {
        color: $background;
        background: $background;
    }

    SharpnessChart .sharpness-chart--selected {
        color: $primary-lighten-2;
        background: $background;
        text-style: bold;
    }

    SharpnessChart .sharpness-chart--unselected {
        color: $text-muted;
        background: $background;
    }

    SharpnessChart .sharpness-chart--title {
        color: $primary;
        background: $background;
        text-style: bold;
    }
    """

    def __init__(
        self,
        frames: List[FrameData],
        selected_indices: Optional[set[int]] = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.frames = frames
        self.selected_indices = set(selected_indices or ())
        self.timeline_width = max(len(frames) * self.FRAME_STRIDE, 1)
        self.virtual_size = Size(self.timeline_width, 1)
        self.border_title = "Frame selection"
        self.border_subtitle = "Arrows scroll | Ctrl+PgUp/PgDn page | Home/End"

        if self.frames:
            scores = [f.sharpness_score for f in self.frames]
            self.min_score = min(scores)
            self.max_score = max(scores)
            self.score_range = max(self.max_score - self.min_score, 1)
        else:
            self.min_score = 0
            self.max_score = 1
            self.score_range = 1

    def on_resize(self, _event: Resize) -> None:
        """Keep the virtual canvas as tall as the visible chart."""
        scrollbar_rows = int(self.timeline_width > self.size.width)
        self.virtual_size = Size(
            self.timeline_width,
            max(self.size.height - scrollbar_rows, 1),
        )

    def update_selection(self, selected_indices: set[int]) -> None:
        """Update the selection status and refresh the chart."""
        self.selected_indices = set(selected_indices)
        self.refresh()

    def action_first_frame(self) -> None:
        """Scroll directly to the beginning of the analyzed timeline."""
        self.scroll_to(x=0, animate=False)

    def action_scroll_left(self) -> None:
        """Scroll left by one complete frame slot."""
        self.scroll_relative(x=-self.FRAME_STRIDE, animate=False)

    def action_scroll_right(self) -> None:
        """Scroll right by one complete frame slot."""
        self.scroll_relative(x=self.FRAME_STRIDE, animate=False)

    def action_last_frame(self) -> None:
        """Scroll directly to the end of the analyzed timeline."""
        self.scroll_to(x=self.max_scroll_x, animate=False)

    def render_line(self, y: int) -> Strip:
        """Render only the visible frame window at the current scroll offset."""
        blank_style = self.get_component_rich_style(
            "sharpness-chart--background"
        )
        width = self.size.width
        viewport_height = self.scrollable_content_region.height
        if width < 1 or y >= viewport_height:
            return Strip([], 0)

        if y == 0:
            start, stop = self._visible_frame_range(width)
            return self._render_window_title(width, start, stop, blank_style)

        if not self.frames:
            return Strip([Segment(" " * width, blank_style)], width)

        return self._render_chart_line(
            width,
            y - 1,
            max(viewport_height - 1, 1),
            blank_style,
        )

    def _render_chart_line(
        self,
        width: int,
        chart_y: int,
        chart_height: int,
        blank_style: Style,
    ) -> Strip:
        """Render frame bars and their guaranteed blank separator columns."""
        selected_style = self.get_component_rich_style(
            "sharpness-chart--selected"
        )
        unselected_style = self.get_component_rich_style(
            "sharpness-chart--unselected"
        )
        segments = [
            self._render_timeline_column(
                virtual_column,
                chart_y,
                chart_height,
                selected_style,
                unselected_style,
                blank_style,
            )
            for virtual_column in range(
                int(self.scroll_offset.x),
                int(self.scroll_offset.x) + width,
            )
        ]
        return Strip(segments, width)

    def _render_timeline_column(
        self,
        virtual_column: int,
        chart_y: int,
        chart_height: int,
        selected_style: Style,
        unselected_style: Style,
        blank_style: Style,
    ) -> Segment:
        """Render a bar column or the blank gap following it."""
        frame_position, slot_column = divmod(virtual_column, self.FRAME_STRIDE)
        if slot_column or frame_position >= len(self.frames):
            return Segment(" ", blank_style)

        frame = self.frames[frame_position]
        normalized = (frame.sharpness_score - self.min_score) / self.score_range
        glyph = self._bar_glyph(normalized, chart_y, chart_height)
        if glyph == " ":
            return Segment(" ", blank_style)

        style = (
            selected_style
            if frame.index in self.selected_indices
            else unselected_style
        )
        return Segment(glyph, style)

    @classmethod
    def _bar_glyph(
        cls, normalized: float, chart_y: int, chart_height: int
    ) -> str:
        """Render a bar cell with eighth-row vertical precision."""
        subdivisions = cls.VERTICAL_SUBDIVISIONS
        available_units = max(chart_height * subdivisions, 1)
        clamped = max(0.0, min(float(normalized), 1.0))
        filled_units = max(1, int((clamped * available_units) + 0.5))
        row_from_bottom = chart_height - 1 - chart_y
        units_in_row = filled_units - (row_from_bottom * subdivisions)
        units_in_row = max(0, min(units_in_row, subdivisions))
        return cls.BAR_GLYPHS[units_in_row]

    def _visible_frame_range(self, width: int) -> tuple[int, int]:
        """Return the frame positions represented by the visible viewport."""
        scroll_x = min(int(self.scroll_offset.x), self.timeline_width)
        visible_end = min(scroll_x + width, self.timeline_width)
        start = min(
            (scroll_x + self.FRAME_STRIDE - 1) // self.FRAME_STRIDE,
            len(self.frames),
        )
        stop = min(
            (visible_end + self.FRAME_STRIDE - 1) // self.FRAME_STRIDE,
            len(self.frames),
        )
        return start, stop

    def _render_window_title(
        self,
        width: int,
        start: int,
        stop: int,
        blank_style: Style,
    ) -> Strip:
        """Render a centered description of the visible timeline window."""
        if not self.frames:
            title = "No analyzed frames"
        else:
            title = f"Frames {start + 1:,}-{stop:,} of {len(self.frames):,}"
        title = title[:width]
        left_padding = max((width - len(title)) // 2, 0)
        right_padding = width - left_padding - len(title)
        title_style = self.get_component_rich_style("sharpness-chart--title")
        return Strip(
            [
                Segment(" " * left_padding, blank_style),
                Segment(title, title_style),
                Segment(" " * right_padding, blank_style),
            ],
            width,
        )


class InputWithControls(Widget):
    """Input field with increment/decrement controls."""
    
    DEFAULT_CSS = """
    InputWithControls {
        height: 3;
        layout: horizontal;
        margin: 0 0 1 0;
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
        height: 3;
        width: 7;
        margin: 0;
        padding: 0;
        min-width: 7;
        min-height: 3;
        max-height: 3;
        max-width: 7;
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

    """
    
    def __init__(self, value: str = "", input_id: str = "", min_value: int = 0, max_value: int = 10000, step: int = 1, **kwargs):
        super().__init__(**kwargs)
        self.input_id = input_id
        self.min_value = min_value
        self.max_value = max_value
        self.step = step
        self._value = value
    
    def compose(self) -> ComposeResult:
        """Compose the input with increment/decrement buttons."""
        yield Input(value=self._value, id=self.input_id)
        with Container(classes="stepper-controls"):
            yield Button(
                label="−",
                classes="stepper-button decrement-btn",
                id=f"{self.input_id}_dec",
                variant="default",
            )
            yield Button(
                label="+",
                classes="stepper-button increment-btn",
                id=f"{self.input_id}_inc",
                variant="default",
            )
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle increment/decrement button presses."""
        button_id = event.button.id
        if button_id and button_id.endswith("_inc"):
            self._increment()
        elif button_id and button_id.endswith("_dec"):
            self._decrement()
    
    def _increment(self) -> None:
        """Increment the input value."""
        input_widget = self.query_one(f"#{self.input_id}", Input)
        try:
            current_value = int(input_widget.value) if input_widget.value else 0
            new_value = min(current_value + self.step, self.max_value)
            input_widget.value = str(new_value)
            # Trigger the input changed event manually
            input_widget.post_message(Input.Changed(input_widget, str(new_value)))
        except ValueError:
            # If current value is invalid, set to minimum
            input_widget.value = str(self.min_value)
            input_widget.post_message(Input.Changed(input_widget, str(self.min_value)))
    
    def _decrement(self) -> None:
        """Decrement the input value."""
        input_widget = self.query_one(f"#{self.input_id}", Input)
        try:
            current_value = int(input_widget.value) if input_widget.value else 0
            new_value = max(current_value - self.step, self.min_value)
            input_widget.value = str(new_value)
            # Trigger the input changed event manually
            input_widget.post_message(Input.Changed(input_widget, str(new_value)))
        except ValueError:
            # If current value is invalid, set to minimum
            input_widget.value = str(self.min_value)
            input_widget.post_message(Input.Changed(input_widget, str(self.min_value)))
    
    @property
    def value(self) -> str:
        """Get the current input value."""
        try:
            input_widget = self.query_one(f"#{self.input_id}", Input)
            return input_widget.value
        except NoMatches:
            return self._value
    
    @value.setter
    def value(self, new_value: str) -> None:
        """Set the input value."""
        self._value = new_value
        try:
            input_widget = self.query_one(f"#{self.input_id}", Input)
            input_widget.value = new_value
        except NoMatches:
            pass


class SelectionScreen(Screen):
    """Interactive selection screen with real-time preview."""
    
    BINDINGS = [
        Binding("ctrl+c", "cancel", "Cancel"),
        Binding("escape", "cancel", "Cancel"),
        Binding(
            "enter",
            "confirm",
            "Confirm Selection",
            key_display="Enter",
            priority=True,
        ),
        Binding(
            "space",
            "select_current_option",
            "Select",
            show=False,
            priority=True,
        ),
        Binding("f1", "help", "Help", show=True),
    ]
    
    # Reactive attributes for real-time updates
    selected_count = reactive(0)
    selected_method = reactive("batched")
    
    class SelectionPreview(Message):
        """Message sent when selection preview is updated."""
        def __init__(self, count: int, method: str, **params) -> None:
            self.count = count
            self.method = method
            self.params = params
            super().__init__()
    
    def __init__(self, processor: TUIProcessor, extraction_result: ExtractionResult, config: Dict[str, Any]):
        """
        Initialize SelectionScreen.
        
        Args:
            processor: TUIProcessor instance with completed extraction/analysis
            extraction_result: Result from extraction and analysis phase
            config: Configuration dictionary
        """
        super().__init__()
        self.processor = processor
        self.extraction_result = extraction_result
        self.config = config
        
        # Selection state
        self.current_method = "batched"
        self.current_parameters = {"batch_size": 5, "batch_buffer": 2}  # Default parameters for batched
        self.preview_task = None  # For debouncing preview updates
        self.selected_indices = set()  # Track which frames are selected
        
        # Method definitions with default parameters - matching legacy application exactly
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
                "name": "Outlier Detection",
                "description": "Remove frames with unusually low sharpness scores compared to neighbors",
                "parameters": {
                    "outlier_sensitivity": {"type": "int", "default": 60, "min": 0, "max": 100, "label": "Detection sensitivity (0-100)"},
                    "outlier_window_size": {"type": "int", "default": 15, "min": 5, "max": 31, "label": "Local comparison window"}
                }
            }
        }
    
    def compose(self) -> ComposeResult:
        """Create a clean, focused selection screen UI."""
        yield Header()
        
        # Calculate initial values
        total_frames = len(self.extraction_result.frames)
        initial_count = min(300, total_frames)  # Default to 300 or total if less
        
        # Main container with all content
        with Container(id="main_content"):
            # Title section - single line with left and right text
            with Horizontal(id="title_section", classes="title_section"):
                yield Static("Select Frames", classes="title_left")
                yield Static(
                    self._frame_count_summary(), classes="title_right"
                )
            
            # Sharpness chart - one horizontally scrollable column per frame
            yield SharpnessChart(
                self.extraction_result.frames,
                selected_indices=self.selected_indices,
                id="sharpness_chart"
            )
            
            # Controls section - method and parameters side by side
            with Horizontal(id="controls_section", classes="controls"):
                # Method selection on the left
                with Container(id="method_container", classes="control_group"):
                    yield Label("Selection Method", classes="control_label")
                    yield OptionSelect(
                        options=[(info["name"], key) for key, info in self.method_definitions.items()],
                        value="batched",
                        id="method_select"
                    )
                    yield Static(self.method_definitions[self.current_method]["description"], 
                               id="method_description", classes="description")
                
                # Parameters on the right
                with Container(id="parameter_container", classes="control_group"):
                    yield Label("Parameters", classes="control_label")
                    with Container(id="parameter_inputs", classes="parameter_inputs"):
                        # Initial parameters for batched method (default)
                        yield Label("Frames per batch:", classes="param_label")
                        yield InputWithControls(
                            value="5",
                            input_id="param_batched_batch_size",
                            min_value=1,
                            max_value=100,
                            step=1,
                            classes="param_input_with_controls"
                        )
                        yield Label("Frames to skip between batches:", classes="param_label")
                        yield InputWithControls(
                            value="2",
                            input_id="param_batched_batch_buffer",
                            min_value=0,
                            max_value=50,
                            step=1,
                            classes="param_input_with_controls"
                        )
            
            # Action buttons inside main content for better positioning
            with Horizontal(id="action_buttons", classes="action_buttons"):
                yield Button("← Back", id="back_button", variant="default")
                yield Button(f"Save {initial_count:,} Images", id="confirm_button", variant="primary")
        
        yield Footer()

    def _frame_count_summary(self) -> str:
        """Summarize analyzed and excluded inputs for the title row."""
        analyzed_count = len(self.extraction_result.frames)
        summary = f"Choose from {analyzed_count:,} analyzed frames"
        analysis = self.extraction_result.metadata.get("sharpness_analysis", {})
        unreadable_count = int(analysis.get("unreadable_count", 0) or 0)
        if unreadable_count:
            summary += f" | {unreadable_count:,} unreadable excluded"
        return summary
    
    def on_mount(self) -> None:
        """Initialize the screen when mounted."""
        # Parameter inputs are already created in compose() with correct initial values
        # Just update the preview with the initial values
        self._update_preview_async()
    
    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle method selection change."""
        if event.select.id == "method_select":
            self.current_method = event.value
            self.selected_method = event.value
            
            # Reset parameters to defaults for new method
            method_info = self.method_definitions[self.current_method]
            self.current_parameters = {}
            for param_name, param_info in method_info["parameters"].items():
                self.current_parameters[param_name] = param_info["default"]
            
            self._update_method_description()
            # Use async task for parameter updates
            asyncio.create_task(self._update_parameter_inputs_async())
            self._update_preview_async()
    
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle parameter input changes."""
        input_id = event.input.id
        if not input_id or not input_id.startswith("param_"):
            return
            
        # Extract method and parameter name from ID
        # Format: param_{method}_{param_name}
        for method in self.method_definitions:
            prefix = f"param_{method}_"
            if input_id.startswith(prefix):
                param_name = input_id[len(prefix):]
                
                # Only process inputs for the current method
                if method != self.current_method:
                    return
                
                self._handle_parameter_change(param_name, event.value)
                return
    
    def _handle_parameter_change(self, param_name: str, value_str: str) -> None:
        """Process a parameter value change."""
        try:
            param_info = self.method_definitions[self.current_method]["parameters"][param_name]
            
            # Parse and validate the value
            if not value_str.strip():
                value = param_info["default"]
            elif param_info["type"] == "int":
                value = int(value_str)
                value = max(param_info.get("min", 1), min(value, param_info.get("max", 10000)))
            else:
                value = value_str
                
            # Update if changed
            old_value = self.current_parameters.get(param_name)
            if old_value != value:
                self.current_parameters[param_name] = value
                self._update_preview_async()
                
        except ValueError:
            # Invalid numeric input - revert to current value
            self.app.log.warning(f"Invalid numeric input for {param_name}: '{value_str}'")
            self._revert_parameter_input(param_name)
        except KeyError:
            # Parameter not found in method definition - this shouldn't happen
            self.app.log.error(f"Parameter '{param_name}' not found for method '{self.current_method}'")
            self._revert_parameter_input(param_name)
        except Exception as e:
            # Unexpected error - log and revert
            self.app.log.error(f"Unexpected error handling parameter change for {param_name}: {e}")
            self._revert_parameter_input(param_name)
    
    def _revert_parameter_input(self, param_name: str) -> None:
        """Revert a parameter input to its current valid value."""
        try:
            current_value = self.current_parameters.get(param_name, 
                self.method_definitions[self.current_method]["parameters"][param_name]["default"])
            # Find the input widget and reset its value
            input_widget = self.query_one(f"#param_{self.current_method}_{param_name}", Input)
            input_widget.value = str(current_value)
        except Exception as e:
            self.app.log.error(f"Failed to revert parameter input for {param_name}: {e}")
            # Last resort - don't crash the UI
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "back_button":
            self.action_cancel()
        elif event.button.id == "confirm_button":
            self.action_confirm()
        elif event.button.id == "start_over_button":
            self.action_start_over()
    
    def action_cancel(self) -> None:
        """Cancel selection and return to previous screen."""
        self.app.pop_screen()
    
    def action_confirm(self) -> None:
        """Confirm selection and proceed with saving."""
        self._start_final_processing()

    def action_select_current_option(self) -> None:
        """Use Space to select the option under the current focus."""
        select_focused_option(self.app.focused)
    
    def action_start_over(self) -> None:
        """Reset everything and return to the first step of configuration."""
        # Clean up any temporary directory from the processor
        if self.processor and hasattr(self.processor, 'cleanup_temp_directory'):
            self.processor.cleanup_temp_directory()
        
        # Reset configuration screen to first step
        # The configuration screen should be at index 0 in the screen stack  
        if len(self.app.screen_stack) >= 3:  # Config, Processing, Selection
            config_screen = self.app.screen_stack[0]
            if hasattr(config_screen, 'reset_to_first_step'):
                config_screen.reset_to_first_step()
        
        # Pop both selection and processing screens to return to configuration at step 1
        self.app.pop_screen()  # Pop selection screen
        self.app.pop_screen()  # Pop processing screen
    
    def action_help(self) -> None:
        """Show help information."""
        help_text = """
# Frame Selection

Choose how to select the best frames from your analyzed video/images.

## Selection Methods

**Best N Frames**: Select a specific number of the sharpest frames with good distribution across the timeline. Ideal when you know exactly how many frames you need.

**Batched Selection**: Divide all frames into equal groups and pick the sharpest from each group. Great for ensuring even coverage across the entire video.

**Outlier Detection**: Automatically reject frames that are significantly blurrier than their local neighbors. Best when you want to keep most frames but remove clear sharpness outliers.

## How It Works

1. **Choose a method** from the dropdown
2. **Adjust parameters** as needed 
3. **Watch the count update** in real-time as you change settings
4. **Press "Process"** when you're happy with the selection

The preview count updates instantly as you make changes, so you can experiment freely!

## Shortcuts

- **Enter**: Process selected frames
- **Escape**: Go back to configuration  
- **F1**: Show this help
        """
        self.app.push_screen("help", help_text)
    
    def _update_method_description(self) -> None:
        """Update the method description text."""
        description = self.method_definitions[self.current_method]["description"]
        description_widget = self.query_one("#method_description", Static)
        description_widget.update(description)
    
    async def _update_parameter_inputs_async(self) -> None:
        """Update parameter input widgets based on selected method (async version)."""
        try:
            container = self.query_one("#parameter_inputs", Container)
            
            # Get all current children to remove
            children_to_remove = list(container.children)
            
            # Remove all children and wait for removal
            for child in children_to_remove:
                await child.remove()
            
            # Add inputs for current method
            method_info = self.method_definitions[self.current_method]
            widgets_to_mount = []
            first_input = None
            param_count = 0
            
            for param_name, param_info in method_info["parameters"].items():
                input_id = f"param_{self.current_method}_{param_name}"
                current_value = self.current_parameters.get(param_name, param_info["default"])
                
                # Create label
                label = Label(param_info["label"] + ":", classes="param_label")
                widgets_to_mount.append(label)
                
                if param_info["type"] in ["int", "float"]:
                    # Create input widget with controls
                    min_val = param_info.get("min", 0)
                    max_val = param_info.get("max", 10000)
                    step_val = 1
                    
                    # Adjust step size based on parameter type and range
                    if param_name == "outlier_sensitivity":
                        step_val = 5  # Percentage values work better with 5% steps
                    elif max_val <= 100:
                        step_val = 1  # Small ranges use step of 1
                    elif max_val <= 1000:
                        step_val = 10  # Medium ranges use step of 10
                    else:
                        step_val = 50  # Large ranges use step of 50
                    
                    input_widget = InputWithControls(
                        value=str(current_value),
                        input_id=input_id,
                        min_value=min_val,
                        max_value=max_val,
                        step=step_val,
                        classes="param_input_with_controls"
                    )
                    widgets_to_mount.append(input_widget)
                    param_count += 1
                    
                    # Remember first input for focus
                    if param_count == 1:
                        first_input = input_widget
            
            # Mount all widgets at once and wait for completion
            if widgets_to_mount:
                await container.mount_all(widgets_to_mount)
            
            # Focus the first input after mounting is complete
            if first_input:
                # Focus the actual input field within the InputWithControls widget
                try:
                    input_field = first_input.query_one(Input)
                    input_field.focus()
                except NoMatches:
                    first_input.focus()
                    
        except Exception as e:
            self.app.log.error(f"Error updating parameter inputs: {e}")
    
    def _update_preview_async(self) -> None:
        """Update preview with debouncing to avoid too frequent updates."""
        # Cancel previous preview task if still running
        if self.preview_task and not self.preview_task.done():
            self.preview_task.cancel()
        
        # Schedule new preview update
        self.preview_task = asyncio.create_task(self._update_preview_debounced())
    
    async def _update_preview_debounced(self) -> None:
        """Update preview with small delay to debounce rapid changes."""
        try:
            # Small delay to debounce rapid parameter changes
            await asyncio.sleep(0.1)  # 100ms debounce
            
            # Get preview from processor
            count = self.processor.preview_selection(self.current_method, **self.current_parameters)
            
            # Update UI elements
            self._update_preview_display(count)
            
            # Post message for other components that might be listening
            await self.post_message(self.SelectionPreview(count, self.current_method, **self.current_parameters))
            
        except asyncio.CancelledError:
            # Task was cancelled, ignore
            pass
        except Exception as e:
            self.app.log.error(f"Error updating preview: {e}")
    
    def _update_preview_display(self, count: int) -> None:
        """Update the preview display with new count in the button."""
        self.selected_count = count
        
        # Update selected indices for the chart
        # Get which frames would be selected with current settings
        try:
            # Use the actual selection method to get the selected frames
            selected_frames = self.processor.selector.select_frames(
                self.extraction_result.frames,
                self.current_method,
                **self.current_parameters
            )
            self.selected_indices = {frame.index for frame in selected_frames}
            
            # Update the chart
            chart = self.query_one("#sharpness_chart", SharpnessChart)
            chart.update_selection(self.selected_indices)
        except Exception as e:
            self.app.log.error(f"Error updating chart selection: {e}")
        
        # Update the action button to show what will happen
        confirm_btn = self.query_one("#confirm_button", Button)
        if count > 0:
            confirm_btn.label = f"Save {count:,} Images"
            confirm_btn.disabled = False
        else:
            confirm_btn.label = "No Images Selected"
            confirm_btn.disabled = True
    
    def _start_final_processing(self) -> None:
        """Start the final processing phase (selection and saving)."""
        # Disable UI during processing
        self.query_one("#confirm_button", Button).disabled = True
        self.query_one("#method_select", Select).disabled = True
        
        # Create final config without mixing in selection parameters
        # The parameters will be passed separately to complete_selection
        final_config = self.config.copy()
        final_config['selection_method'] = self.current_method
        
        # Start processing in background
        asyncio.create_task(self._process_final_selection(final_config))
    
    async def _process_final_selection(self, final_config: Dict[str, Any]) -> None:
        """Process the final selection and saving."""
        selected_count = self.selected_count
        processing_label = None
        
        try:
            # Show processing indicator
            processing_label = await self._show_processing_indicator()
            
            # Run the final selection in background thread
            success = await self._execute_selection_in_background(final_config)
            
            if success:
                await self._handle_selection_success(processing_label, selected_count, final_config)
            else:
                await self._handle_selection_failure(processing_label)
                
        except Exception as e:
            self.app.log.error(f"Error during final processing: {e}")
            await self._handle_selection_error(processing_label, str(e))
    
    async def _show_processing_indicator(self) -> Label:
        """Show the processing indicator and return the label widget."""
        processing_label = Label("🔄 Processing selection...", classes="processing_indicator")
        await self.query_one("#main_content").mount(processing_label)
        return processing_label
    
    async def _execute_selection_in_background(self, final_config: Dict[str, Any]) -> bool:
        """Execute the selection process in a background thread."""
        # Run the final selection (this is CPU intensive, so we run it in a thread)
        # Note: run_in_executor doesn't support keyword arguments, so we use a lambda
        return await asyncio.get_event_loop().run_in_executor(
            None, 
            lambda: self.processor.complete_selection(
                self.current_method,
                final_config,
                **self.current_parameters
            )
        )
    
    async def _handle_selection_success(self, processing_label: Label, selected_count: int, final_config: Dict[str, Any]) -> None:
        """Handle successful selection completion."""
        # Show success message
        processing_label.update("✅ Selection completed successfully!")
        await asyncio.sleep(1)
        
        # Remove processing label and show success UI
        await processing_label.remove()
        
        # Create and mount success container
        success_container = self._create_success_container(selected_count, final_config)
        await self.query_one("#main_content").mount(success_container)
        
        # Focus the start over button
        self.query_one("#start_over_button", Button).focus()
    
    async def _handle_selection_failure(self, processing_label: Label) -> None:
        """Handle selection failure."""
        processing_label.update("❌ Selection failed. Please try again.")
        await asyncio.sleep(3)
        await processing_label.remove()
        self._re_enable_ui()
    
    async def _handle_selection_error(self, processing_label: Optional[Label], error_message: str) -> None:
        """Handle unexpected errors during selection."""
        if processing_label:
            try:
                processing_label.update(f"❌ Error: {error_message}")
                await asyncio.sleep(3)
                await processing_label.remove()
            except Exception:
                # Ignore errors when trying to update/remove the label
                pass
        self._re_enable_ui()
    
    def _create_success_container(self, selected_count: int, final_config: Dict[str, Any]) -> Horizontal:
        """Create the success message container."""
        return Horizontal(
            Container(
                Static("✅ Images saved successfully!", classes="success_message"),
                Static(f"Saved {selected_count} frames to {final_config['output_dir']}", classes="success_details"),
                classes="success_text_container"
            ),
            Button("Start Over", id="start_over_button", variant="primary"),
            id="success_container",
            classes="success_container"
        )
    
    def _re_enable_ui(self) -> None:
        """Re-enable UI controls after processing."""
        try:
            self.query_one("#confirm_button", Button).disabled = False
            self.query_one("#method_select", Select).disabled = False
        except Exception:
            # Ignore errors if widgets don't exist
            pass
