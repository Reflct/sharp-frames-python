"""
Configuration screen for Sharp Frames UI.
Removes selection method configuration (moved to post-extraction SelectionScreen).
"""

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.css.query import NoMatches
from textual.widgets import Header, Footer, Button, Input, Label, Static
from textual.screen import Screen
from textual.binding import Binding

from ..utils import sanitize_path_input
from ..keyboard import select_focused_option

from ..constants import UIElementIds
from ..components.step_handlers import (
    InputTypeStepHandler,
    InputPathStepHandler,
    OutputDirStepHandler,
    FpsStepHandler,
    OutputFormatStepHandler,
    WidthStepHandler,
    ForceOverwriteStepHandler,
    ConfirmStepHandler
)
from ..components.validators import ValidationHelpers


class AsciiTitleShimmer(Static):
    """Run a single diagonal colour shimmer across the full ASCII title."""

    INITIAL_DELAY_SECONDS = 0.16
    FRAME_INTERVAL_SECONDS = 0.045
    _ROW_OFFSET = 2
    _POSITION_STEP = 5
    _OUTER_BAND_WIDTH = 3
    _EDGE_COLOR = "#55A9FF"
    _MID_COLOR = "#8DCCFF"
    _CORE_COLOR = "#D6EEFF"

    def __init__(self, title_markup: str) -> None:
        base_text = Text.from_markup(title_markup)
        title_rows = self._title_rows(base_text.plain)
        self.frames = self._build_frames(
            base_text,
            title_rows,
        )
        super().__init__(self.frames[0], id="ascii-title", classes="title")

    @staticmethod
    def _title_rows(plain_title: str) -> list[tuple[int, str]]:
        """Return global offsets and visible content for the six logo rows."""
        rows: list[tuple[int, str]] = []
        offset = 0
        for line in plain_title.splitlines(keepends=True):
            visible_line = line.rstrip("\r\n")
            if visible_line.strip():
                rows.append((offset, visible_line))
            offset += len(line)
        return rows

    @classmethod
    def _build_frames(
        cls,
        base_text: Text,
        title_rows: list[tuple[int, str]],
    ) -> tuple[Text, ...]:
        """Build fixed-layout colour frames for one diagonal shimmer pass."""
        title_width = max(len(row) for _, row in title_rows)
        final_position = (
            title_width - 1
            + (len(title_rows) - 1) * cls._ROW_OFFSET
            + cls._OUTER_BAND_WIDTH
        )
        positions = range(
            -cls._OUTER_BAND_WIDTH,
            final_position + cls._POSITION_STEP,
            cls._POSITION_STEP,
        )
        shimmer_frames = tuple(
            cls._build_shimmer_frame(
                base_text,
                title_rows,
                position,
            )
            for position in positions
        )
        return (base_text.copy(), *shimmer_frames, base_text.copy())

    @classmethod
    def _build_shimmer_frame(
        cls,
        base_text: Text,
        title_rows: list[tuple[int, str]],
        position: int,
    ) -> Text:
        """Overlay one three-tone diagonal band without changing any glyphs."""
        frame = base_text.copy()
        for row_index, (row_offset, row) in enumerate(title_rows):
            for column in range(len(row)):
                if row[column].isspace():
                    continue
                diagonal_position = column + row_index * cls._ROW_OFFSET
                distance = abs(diagonal_position - position)
                color = cls._color_for_distance(distance)
                if color is not None:
                    character_offset = row_offset + column
                    frame.stylize(
                        color,
                        character_offset,
                        character_offset + 1,
                    )
        return frame

    @classmethod
    def _color_for_distance(cls, distance: int) -> str | None:
        """Return a soft edge, mid tone, or pale core for the shimmer band."""
        if distance == 0:
            return cls._CORE_COLOR
        if distance == 1:
            return cls._MID_COLOR
        if distance <= cls._OUTER_BAND_WIDTH:
            return cls._EDGE_COLOR
        return None

    def on_mount(self) -> None:
        """Schedule one pass, respecting Textual's reduced-animation setting."""
        if self.app.animation_level == "none":
            return

        self.set_timer(
            self.INITIAL_DELAY_SECONDS,
            self._start_shimmer,
            name="title-shimmer-start",
        )

    def _start_shimmer(self) -> None:
        """Advance frames on one interval timer so they can never reorder.

        Independent per-frame timers whose deadlines sit closer together
        than the platform timer resolution (notably Windows) may fire out
        of order, ending the pass on a shimmer frame instead of the title.
        """
        self._show_frame(1)
        self._next_frame_index = 2
        self._shimmer_timer = self.set_interval(
            self.FRAME_INTERVAL_SECONDS,
            self._advance_frame,
            name="title-shimmer",
        )

    def _advance_frame(self) -> None:
        """Show the next frame and stop the interval after the last one.

        A tick that was already queued when the timer stopped may still
        invoke this callback once more, so it no-ops after the last frame.
        """
        if self._next_frame_index > len(self.frames) - 1:
            return
        self._show_frame(self._next_frame_index)
        if self._next_frame_index >= len(self.frames) - 1:
            self._shimmer_timer.stop()
        self._next_frame_index += 1

    def _show_frame(self, frame_index: int) -> None:
        """Swap colour spans without recalculating the stable title layout."""
        self.update(self.frames[frame_index], layout=False)


class ConfigurationForm(Screen):
    """Configuration form for Sharp Frames processing (selection method removed)."""
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+c", "cancel", "Cancel"),
        Binding("f1", "help", "Help", show=True),
        Binding(
            "enter", "next_step", "Next", show=False, priority=True
        ),
        Binding(
            "space",
            "select_current_option",
            "Select",
            show=False,
            priority=True,
        ),
    ]
    
    def __init__(self):
        super().__init__()
        self.config_data = {}
        self.current_step = 0
        
        # Individual step list - each control on its own step
        self.steps = [
            "input_type",
            "input_path", 
            "output_dir",
            "fps",
            "output_format",
            "width", 
            "force_overwrite",
            "confirm"
        ]
        
        # Initialize step handlers (excluding selection-related ones)
        self.step_handlers = {}
        self._initialize_step_handlers()
    
    def _initialize_step_handlers(self):
        """Initialize step handlers for the configuration process."""
        # Create step handlers for each configuration step
        self.step_handlers = {
            "input_type": InputTypeStepHandler(),
            "input_path": InputPathStepHandler(),
            "output_dir": OutputDirStepHandler(),
            "fps": FpsStepHandler(),
            "output_format": OutputFormatStepHandler(),
            "width": WidthStepHandler(),
            "force_overwrite": ForceOverwriteStepHandler(),
            "confirm": ConfirmStepHandler()
        }
        
        # Set up validation helpers
        self.validation_helpers = ValidationHelpers()
    
    def compose(self) -> ComposeResult:
        """Create the wizard layout - same style as legacy."""
        yield Header()
        ascii_title = """
███████[#2575E6]╗[/#2575E6]██[#2575E6]╗[/#2575E6]  ██[#2575E6]╗[/#2575E6] █████[#2575E6]╗[/#2575E6] ██████[#2575E6]╗[/#2575E6] ██████[#2575E6]╗[/#2575E6]     ███████[#2575E6]╗[/#2575E6]██████[#2575E6]╗[/#2575E6]  █████[#2575E6]╗[/#2575E6] ███[#2575E6]╗[/#2575E6]   ███[#2575E6]╗[/#2575E6]███████[#2575E6]╗[/#2575E6]███████[#2575E6]╗[/#2575E6]
██[#2575E6]╔[/#2575E6][#2575E6]════╝[/#2575E6]██[#2575E6]║[/#2575E6]  ██[#2575E6]║[/#2575E6]██[#2575E6]╔══[/#2575E6]██[#2575E6]╗[/#2575E6]██[#2575E6]╔══[/#2575E6]██[#2575E6]╗[/#2575E6]██[#2575E6]╔══[/#2575E6]██[#2575E6]╗[/#2575E6]    ██[#2575E6]╔[/#2575E6][#2575E6]════╝[/#2575E6]██[#2575E6]╔══[/#2575E6]██[#2575E6]╗[/#2575E6]██[#2575E6]╔══[/#2575E6]██[#2575E6]╗[/#2575E6]████[#2575E6]╗[/#2575E6] ████[#2575E6]║[/#2575E6]██[#2575E6]╔[/#2575E6][#2575E6]════╝[/#2575E6]██[#2575E6]╔[/#2575E6][#2575E6]════╝[/#2575E6]
███████[#2575E6]╗[/#2575E6]███████[#2575E6]║[/#2575E6]███████[#2575E6]║[/#2575E6]██████[#2575E6]╔╝[/#2575E6]██████[#2575E6]╔╝[/#2575E6]    █████[#2575E6]╗[/#2575E6]  ██████[#2575E6]╔╝[/#2575E6]███████[#2575E6]║[/#2575E6]██[#2575E6]╔[/#2575E6]████[#2575E6]╔[/#2575E6]██[#2575E6]║[/#2575E6]█████[#2575E6]╗[/#2575E6]  ███████[#2575E6]╗[/#2575E6]
[#2575E6]╚[/#2575E6][#2575E6]════[/#2575E6]██[#2575E6]║[/#2575E6]██[#2575E6]╔══[/#2575E6]██[#2575E6]║[/#2575E6]██[#2575E6]╔══[/#2575E6]██[#2575E6]║[/#2575E6]██[#2575E6]╔══[/#2575E6]██[#2575E6]╗[/#2575E6]██[#2575E6]╔═══╝[/#2575E6]     ██[#2575E6]╔══╝[/#2575E6]  ██[#2575E6]╔══[/#2575E6]██[#2575E6]╗[/#2575E6]██[#2575E6]╔══[/#2575E6]██[#2575E6]║[/#2575E6]██[#2575E6]║╚[/#2575E6]██[#2575E6]╔╝[/#2575E6]██[#2575E6]║[/#2575E6]██[#2575E6]╔══╝[/#2575E6]  [#2575E6]╚[/#2575E6][#2575E6]════[/#2575E6]██[#2575E6]║[/#2575E6]
███████[#2575E6]║[/#2575E6]██[#2575E6]║[/#2575E6]  ██[#2575E6]║[/#2575E6]██[#2575E6]║[/#2575E6]  ██[#2575E6]║[/#2575E6]██[#2575E6]║[/#2575E6]  ██[#2575E6]║[/#2575E6]██[#2575E6]║[/#2575E6]         ██[#2575E6]║[/#2575E6]     ██[#2575E6]║[/#2575E6]  ██[#2575E6]║[/#2575E6]██[#2575E6]║[/#2575E6]  ██[#2575E6]║[/#2575E6]██[#2575E6]║[/#2575E6] [#2575E6]╚═╝[/#2575E6] ██[#2575E6]║[/#2575E6]███████[#2575E6]╗[/#2575E6]███████[#2575E6]║[/#2575E6]
[#2575E6]╚══════╝╚═╝[/#2575E6]  [#2575E6]╚═╝╚═╝[/#2575E6]  [#2575E6]╚═╝╚═╝[/#2575E6]  [#2575E6]╚═╝╚═╝[/#2575E6]         [#2575E6]╚═╝[/#2575E6]     [#2575E6]╚═╝[/#2575E6]  [#2575E6]╚═╝╚═╝[/#2575E6]  [#2575E6]╚═╝╚═╝[/#2575E6]     [#2575E6]╚═╝╚══════╝╚══════╝[/#2575E6]
        """
        # The whole form block (logo, step info, inputs, and its buttons) is
        # vertically centred as one unit, with the CTAs sitting under the
        # controls rather than docked to the bottom of the screen.
        with Container(id="form-sequence"):
            with Container(id="main-container"):
                yield AsciiTitleShimmer(ascii_title)
                yield Static("", id="step-info", classes="step-info")
                yield Static("", id="step-description", classes="step-description")
                yield Container(id="step-container")
                with Horizontal(classes="buttons"):
                    yield Button(
                        "Back", variant="default", id="back-btn", disabled=True
                    )
                    yield Button("Next", variant="primary", id="next-btn")
                    yield Button("Cancel", variant="default", id="cancel-btn")

        yield Footer()
    
    def on_mount(self) -> None:
        """Set up the wizard when mounted."""
        self.show_current_step()
    
    def reset_to_first_step(self) -> None:
        """Reset the configuration form to the first step."""
        self.current_step = 0
        self.config_data = {}  # Clear previous configuration
        self.show_current_step()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events - same pattern as legacy."""
        if event.button.id == UIElementIds.NEXT_BTN:
            self._next_step()
        elif event.button.id == UIElementIds.BACK_BTN:
            self._back_step()
        elif event.button.id == UIElementIds.CANCEL_BTN:
            self.action_cancel()
    
    def on_radio_set_changed(self, event) -> None:
        """Handle RadioSet selection change - allow Enter to progress."""
        # Don't auto-progress on selection change, just allow Enter to work
        pass
    
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes and sanitize file paths."""
        input_id = event.input.id
        
        # Path inputs that need sanitization
        path_inputs = ['input-path', 'output-dir-input']
        
        if input_id in path_inputs:
            current_value = event.value
            sanitized_value = sanitize_path_input(current_value)
            
            # Only update if sanitization changed the value
            if sanitized_value != current_value:
                event.input.value = sanitized_value
    
    def show_current_step(self) -> None:
        """Display the current step of the wizard - same pattern as legacy."""
        step_container = self.query_one("#step-container")
        # Clear all children from the container using legacy pattern
        for child in list(step_container.children):
            child.remove()
        
        step = self.steps[self.current_step]
        visible_steps = [s for s in self.steps if self._should_show_step(s)]
        step_number = visible_steps.index(step) + 1 if step in visible_steps else 1
        total_visible = len(visible_steps)
        
        # Update step info - same format as legacy
        step_info = self.query_one("#step-info")
        step_title = self.step_handlers[step].get_title()
        step_description = self.step_handlers[step].get_description()
        step_info.update(f"Step {step_number} of {total_visible}: {step_title}\n{step_description}")
        
        # Update navigation buttons - same logic as legacy
        back_btn = self.query_one("#back-btn")
        next_btn = self.query_one("#next-btn")
        
        back_btn.disabled = (self.current_step == 0)
        
        if step == "confirm":
            next_btn.label = "Start Processing"
            next_btn.variant = "success"
        else:
            next_btn.label = "Next"
            next_btn.variant = "primary"
        
        # Render step content using handler
        if step in self.step_handlers:
            self.step_handlers[step].render(self, step_container)
        else:
            # Fallback for unknown steps
            step_container.mount(Label(f"Unknown step: {step}", classes="error-message"))
        
        # Set focus to the appropriate widget for this step
        self.set_timer(0.1, self._focus_step_widget)
    
    def _focus_step_widget(self) -> None:
        """Set focus to the main widget for the current step."""
        step = self.steps[self.current_step]

        try:
            step_container = self.query_one("#step-container")
            # Focus based on step type
            if step == "input_type":
                # Focus the RadioSet
                radio_set = step_container.query_one("#input-type-selection")
                radio_set.focus()
            elif step in ["input_path", "output_dir", "fps", "width"]:
                # Focus the Input field
                input_field = step_container.query_one("Input")
                input_field.focus()
            elif step == "output_format":
                # Focus the Select field
                select_field = step_container.query_one("Select")
                select_field.focus()
            elif step == "force_overwrite":
                # Focus the Checkbox field
                checkbox_field = step_container.query_one("Checkbox")
                checkbox_field.focus()
            else:
                # Default: focus the first focusable widget in the step
                focusable_widgets = step_container.query("Input, Select, RadioSet, Checkbox")
                if focusable_widgets:
                    focusable_widgets[0].focus()
        except Exception:
            # If focusing fails, don't crash - just continue
            pass
    
    def _should_show_step(self, step: str) -> bool:
        """Check if a step should be shown based on current configuration."""
        # Show/hide steps based on input type
        if step in ["fps", "output_format"] and self.config_data.get("input_type") not in ["video", "video_directory"]:
            return False
        return True
    
    def _next_step(self) -> None:
        """Move to the next step if current step is valid - same logic as legacy."""
        # Save current step data
        if not self._save_current_step():
            return  # Validation failed, stay on current step
        
        # Skip steps that shouldn't be shown
        next_step = self.current_step + 1
        while next_step < len(self.steps) and not self._should_show_step(self.steps[next_step]):
            next_step += 1
        
        if next_step < len(self.steps):
            self.current_step = next_step
            self.show_current_step()
        else:
            # Last step - process the configuration (go to processing screen)
            self.action_process()
    
    def _back_step(self) -> None:
        """Move to the previous step - same logic as legacy."""
        # Skip steps that shouldn't be shown
        prev_step = self.current_step - 1
        while prev_step >= 0 and not self._should_show_step(self.steps[prev_step]):
            prev_step -= 1
        
        if prev_step >= 0:
            self.current_step = prev_step
            self.show_current_step()
    
    def _save_current_step(self) -> bool:
        """Save the current step data and validate - same pattern as legacy."""
        step = self.steps[self.current_step]
        handler = self.step_handlers.get(step)
        
        if not handler:
            return True
        
        try:
            self._clear_error()
            
            # Validate step
            if not handler.validate(self):
                return False
            
            # Get data from step
            step_data = handler.get_data(self)
            self.config_data.update(step_data)
            
            return True
            
        except Exception as e:
            self._show_error(f"Error: {str(e)}")
            return False
    
    def _clear_error(self) -> None:
        """Clear any error messages - same as legacy."""
        try:
            error_widget = self.query_one(".error-message")
            error_widget.remove()
        except NoMatches:
            pass  # No error message to remove
    
    def _show_error(self, message: str) -> None:
        """Show error message - same as legacy."""
        try:
            step_container = self.query_one("#step-container")
            error_label = Label(message, classes="error-message")
            step_container.mount(error_label)
        except Exception as e:
            print(f"Failed to show error message: {e}")
    
    def action_next_step(self) -> None:
        """Move to the next step regardless of the focused control."""
        self._next_step()

    def action_select_current_option(self) -> None:
        """Use Space to select the option under the current focus."""
        select_focused_option(self.app.focused)
    
    def action_cancel(self) -> None:
        """Cancel the configuration and exit - same as legacy."""
        self.app.exit(result="cancelled")
    
    def action_process(self) -> None:
        """Start processing with the collected configuration - transition to processing."""
        # Import here to avoid circular imports
        from .processing import ProcessingScreen
        
        # Push the processing screen with our configuration
        processing_screen = ProcessingScreen(self.config_data)
        self.app.push_screen(processing_screen)
    
    def action_help(self) -> None:
        """Show help information - same as legacy."""
        help_text = """
# Sharp Frames Configuration Help

**Interactive Mode**: This mode separates frame extraction from selection, allowing you to:
1. Extract and analyze all frames first
2. Interactively select frames with real-time preview
3. Adjust selection criteria without re-processing

## Configuration Steps

**Input Type**: Choose between single video, video directory, or image directory.

**Input Path**: Specify the path to your video file(s) or image directory.

**Output Directory**: Where selected frames will be saved.

**FPS** (video only): Frames per second to extract from video.

**Output Format**: Image format for saved frames (JPG or PNG).

**Width**: Optional resizing width (maintains aspect ratio).

**Force Overwrite**: Overwrite existing files without confirmation.

## Selection Process

After configuration, frames will be extracted and analyzed. You'll then see an interactive selection screen where you can:
- Choose selection method (Best N, Batched, Outlier Detection)
- Adjust parameters with real-time preview
- See exactly how many frames will be selected

Press F1 on any screen for context-specific help.
        """
        self.app.push_screen("help", help_text)
    
    def get_current_step_name(self) -> str:
        """Get the name of the current step."""
        return self.steps[self.current_step]
