"""
Interactive selection screen for Sharp Frames TUI.
"""

import asyncio
from typing import Dict, Any, Optional
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import (
    Header, Footer, Button, Static, Label, Select, Input
)
from textual.screen import Screen
from textual.binding import Binding
from textual.message import Message
from textual.reactive import reactive

from ...processing.tui_processor import TUIProcessor
from ...models.frame_data import ExtractionResult


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
    selected_method = reactive("best_n")
    
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
        self.current_method = "best_n"
        self.current_parameters = {"n": 300, "min_buffer": 3}  # Default parameters for best_n
        self.preview_task = None  # For debouncing preview updates
        
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
            # Title section
            yield Static("Select Frames", classes="main_title")
            yield Static(f"Choose from {total_frames:,} analyzed frames", classes="subtitle")
            
            # Controls section - method and parameters side by side
            with Horizontal(id="controls_section", classes="controls"):
                # Method selection on the left
                with Container(id="method_container", classes="control_group"):
                    yield Label("Selection Method", classes="control_label")
                    yield Select(
                        options=[(info["name"], key) for key, info in self.method_definitions.items()],
                        value=self.current_method,
                        id="method_select"
                    )
                    yield Static(self.method_definitions[self.current_method]["description"], 
                               id="method_description", classes="description")
                
                # Parameters on the right
                with Container(id="parameter_container", classes="control_group"):
                    yield Label("Parameters", classes="control_label")
                    with Container(id="parameter_inputs", classes="parameter_inputs"):
                        # Initial parameters for best_n method (default)
                        yield Label("Number of frames:", classes="param_label")
                        yield Input(
                            value="300",
                            id="param_best_n_n",
                            classes="param_input"
                        )
                        yield Label("Minimum distance between frames:", classes="param_label")
                        yield Input(
                            value="3",
                            id="param_best_n_min_buffer",
                            classes="param_input"
                        )
            
            # Action buttons inside main content for better positioning
            with Horizontal(id="action_buttons", classes="action_buttons"):
                yield Button("← Back", id="back_button", variant="default")
                yield Button(f"Save {initial_count:,} Images", id="confirm_button", variant="success")
        
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
                
        except (ValueError, KeyError) as e:
            # Invalid input - revert to current value
            self.app.log.warning(f"Invalid input for {param_name}: '{value_str}'")
            try:
                current_value = self.current_parameters.get(param_name, 
                    self.method_definitions[self.current_method]["parameters"][param_name]["default"])
                # Find the input widget and reset its value
                input_widget = self.query_one(f"#param_{self.current_method}_{param_name}", Input)
                input_widget.value = str(current_value)
            except:
                pass
    
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
                    # Create input widget
                    input_widget = Input(
                        value=str(current_value),
                        id=input_id,
                        classes="param_input"
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
        try:
            with open("debug_save.log", "a") as f:
                f.write(f"=== SAVE PROCESS STARTED ===\n")
                f.write(f"Method: {self.current_method}\n")
                f.write(f"Parameters: {self.current_parameters}\n")
                f.write(f"Config: {final_config}\n")
                f.write(f"Total frames available: {len(self.extraction_result.frames)}\n")
            
            # Store the selected count for use in success message
            selected_count = self.selected_count
            
            # Show processing indicator
            processing_label = Label("🔄 Processing selection...", classes="processing_indicator")
            self.query_one("#main_content").mount(processing_label)
            
            with open("debug_save.log", "a") as f:
                f.write("Starting executor call...\n")
            
            # Run the final selection (this is CPU intensive, so we run it in a thread)
            # Note: run_in_executor doesn't support keyword arguments, so we use a lambda
            success = await asyncio.get_event_loop().run_in_executor(
                None, 
                lambda: self.processor.complete_selection(
                    self.current_method,
                    final_config,
                    **self.current_parameters
                )
            )
            
            with open("debug_save.log", "a") as f:
                f.write(f"Executor completed. Success: {success}\n")
            
            if success:
                # Show success message
                processing_label.update("✅ Selection completed successfully!")
                await asyncio.sleep(1)
                
                # Remove processing label and show success UI
                await processing_label.remove()
                
                # Show success message with Start Over button in horizontal layout
                success_container = Horizontal(
                    Container(
                        Static("✅ Images saved successfully!", classes="success_message"),
                        Static(f"Saved {selected_count} frames to {final_config['output_dir']}", classes="success_details"),
                        classes="success_text_container"
                    ),
                    Button("Start Over", id="start_over_button", variant="primary"),
                    id="success_container",
                    classes="success_container"
                )
                await self.query_one("#main_content").mount(success_container)
                
                # Focus the start over button
                self.query_one("#start_over_button", Button).focus()
            else:
                # Show error and re-enable UI
                processing_label.update("❌ Selection failed. Please try again.")
                await asyncio.sleep(3)
                processing_label.remove()
                self.query_one("#confirm_button", Button).disabled = False
                self.query_one("#method_select", Select).disabled = False
                
        except Exception as e:
            with open("debug_save.log", "a") as f:
                f.write(f"EXCEPTION in SelectionScreen._process_final_selection: {e}\n")
                f.write(f"Exception type: {type(e).__name__}\n")
                import traceback
                f.write(f"Traceback:\n{traceback.format_exc()}\n")
            
            self.app.log.error(f"Error during final processing: {e}")
            # Re-enable UI on error
            try:
                processing_label.update(f"❌ Error: {str(e)}")
                await asyncio.sleep(3)
                processing_label.remove()
            except:
                pass
            self.query_one("#confirm_button", Button).disabled = False
            self.query_one("#method_select", Select).disabled = False
