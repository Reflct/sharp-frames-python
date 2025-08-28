"""
Interactive selection screen for Sharp Frames TUI.
"""

import asyncio
from typing import Dict, Any, Optional, List

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.screen import Screen
from textual.strip import Strip
from textual.widget import Widget
from textual.widgets import (
    Button, Footer, Header, Input, Label, Select, Static
)

from rich.segment import Segment
from rich.style import Style

from ...models.frame_data import ExtractionResult, FrameData
from ...processing.tui_processor import TUIProcessor


class SharpnessChart(Widget):
    """Bar chart widget to display sharpness scores and selection status."""
    
    DEFAULT_CSS = """
    SharpnessChart {
        height: 12;
        width: 100%;
        border: solid $primary;
        margin: 1 0;
    }
    """
    
    def __init__(self, frames: List[FrameData], selected_indices: set = None, max_frames: int = 100, **kwargs):
        super().__init__(**kwargs)
        self.frames = frames[:max_frames]  # Only show first 100 frames
        self.selected_indices = selected_indices or set()
        self.max_frames = max_frames
        
        # Calculate min and max sharpness for normalization
        if self.frames:
            scores = [f.sharpness_score for f in self.frames]
            self.min_score = min(scores)
            self.max_score = max(scores)
            self.score_range = self.max_score - self.min_score if self.max_score > self.min_score else 1
        else:
            self.min_score = 0
            self.max_score = 1
            self.score_range = 1
    
    def update_selection(self, selected_indices: set):
        """Update the selection status and refresh the chart."""
        self.selected_indices = selected_indices
        self.refresh()
    
    def render_line(self, y: int) -> "Strip":
        """Render a single line of the chart."""
        from textual.strip import Strip
        
        width = self.size.width
        height = self.size.height - 2  # Account for border
        
        if not self.frames or width < 10 or height < 1:
            return Strip([Segment(" " * width)])
        
        # First line is the title
        if y == 0:
            title = "Frame selection - first 100"
            padding = (width - len(title)) // 2
            return Strip([
                Segment(" " * padding),
                Segment(title, Style(color="#3190FF", bold=True)),
                Segment(" " * (width - padding - len(title)))
            ])
        
        # Chart content starts from line 1
        chart_y = y - 1
        chart_height = height - 1  # Reserve first line for title
        
        # Calculate bar dimensions
        num_frames = min(len(self.frames), 100)  # Max 100 frames
        bar_width = 1  # Each bar is 1 character wide
        gap_width = 1  # 1 character gap between bars
        
        segments = []
        
        for i in range(num_frames):
            frame = self.frames[i]
            
            # Normalize sharpness score to chart height
            normalized_score = (frame.sharpness_score - self.min_score) / self.score_range
            bar_height = int(normalized_score * chart_height)
            
            # Determine if we should draw the bar at this y position
            # chart_y=0 is top of chart, chart_height-1 is bottom
            should_draw = (chart_height - 1 - chart_y) < bar_height
            
            # Choose color based on selection status
            if frame.index in self.selected_indices:
                color = Style(color="white", bold=True)
            else:
                color = Style(color="#666666")  # Light grey for unselected
            
            # Draw the bar
            if should_draw:
                segments.append(Segment("█", color))
            else:
                segments.append(Segment(" "))
            
            # Add gap after bar (except for the last one)
            if i < num_frames - 1:
                segments.append(Segment(" "))
        
        # Calculate total width used
        total_used = num_frames * bar_width + (num_frames - 1) * gap_width
        
        # Fill remaining space
        remaining = width - total_used
        if remaining > 0:
            segments.append(Segment(" " * remaining))
        
        return Strip(segments)


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
    }
    
    InputWithControls .increment-controls {
        width: 8;
        layout: horizontal;
        height: 3;
    }
    
    InputWithControls .increment-btn,
    InputWithControls .decrement-btn {
        height: 3;
        width: 3;
        margin: 0;
        padding: 0;
        min-width: 3;
        min-height: 3;
        max-height: 3;
        max-width: 3;
        content-align: center middle;
        text-align: center;
    }
    
    InputWithControls .decrement-btn {
        margin-right: 2;
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
        with Container(classes="increment-controls"):
            yield Button(label="-", classes="decrement-btn", id=f"{self.input_id}_dec", variant="primary")
            yield Button(label="+", classes="increment-btn", id=f"{self.input_id}_inc", variant="primary")
    
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
        except:
            return self._value
    
    @value.setter
    def value(self, new_value: str) -> None:
        """Set the input value."""
        self._value = new_value
        try:
            input_widget = self.query_one(f"#{self.input_id}", Input)
            input_widget.value = new_value
        except:
            pass


class SelectionScreen(Screen):
    """Interactive selection screen with real-time preview."""
    
    BINDINGS = [
        Binding("ctrl+c", "cancel", "Cancel"),
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "confirm", "Confirm Selection", key_display="Enter"),
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
                "name": "Outlier Removal",
                "description": "Remove frames with unusually low sharpness scores compared to neighbors",
                "parameters": {
                    "outlier_sensitivity": {"type": "int", "default": 50, "min": 0, "max": 100, "label": "Removal aggressiveness (0-100)"},
                    "outlier_window_size": {"type": "int", "default": 15, "min": 3, "max": 30, "label": "Neighbor comparison window"}
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
                yield Static(f"Choose from {total_frames:,} analyzed frames", classes="title_right")
            
            # Sharpness chart - shows first 100 frames
            yield SharpnessChart(
                self.extraction_result.frames,
                selected_indices=self.selected_indices,
                max_frames=100,
                id="sharpness_chart"
            )
            
            # Controls section - method and parameters side by side
            with Horizontal(id="controls_section", classes="controls"):
                # Method selection on the left
                with Container(id="method_container", classes="control_group"):
                    yield Label("Selection Method", classes="control_label")
                    yield Select(
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

**Outlier Removal**: Automatically remove frames that are significantly blurrier than their neighbors. Best when you want to keep most frames but remove the obviously bad ones.

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
                except:
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
