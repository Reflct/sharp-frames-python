"""
Interactive selection screen for Sharp Frames TUI.
"""

import asyncio
from typing import Dict, Any, Optional, Callable
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Header, Footer, Button, Static, Label, Select, Input, 
    ProgressBar, Collapsible, Sparkline
)
from textual.screen import Screen
from textual.binding import Binding
from textual.message import Message
from textual.reactive import reactive

from ...processing.tui_processor import TUIProcessor
from ...models.frame_data import ExtractionResult
from ...selection_preview import get_selection_preview


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
        self.current_parameters = {"n": 50}  # Default parameters
        self.preview_task = None  # For debouncing preview updates
        
        # Method definitions with default parameters
        self.method_definitions = {
            "best_n": {
                "name": "Best N Frames",
                "description": "Select the N sharpest frames with good distribution",
                "parameters": {
                    "n": {"type": "int", "default": 50, "min": 1, "max": 10000, "label": "Number of frames"}
                }
            },
            "batched": {
                "name": "Batched Selection", 
                "description": "Divide into batches and select the sharpest from each",
                "parameters": {
                    "batch_count": {"type": "int", "default": 10, "min": 1, "max": 1000, "label": "Number of batches"}
                }
            },
            "outlier_removal": {
                "name": "Outlier Removal",
                "description": "Remove frames with unusually low sharpness scores",
                "parameters": {
                    "factor": {"type": "float", "default": 1.5, "min": 0.1, "max": 3.0, "step": 0.1, "label": "Sensitivity factor"}
                }
            }
        }
    
    def compose(self) -> ComposeResult:
        """Create the selection screen UI layout."""
        yield Header()
        
        with Container(id="selection_container"):
            # Frame information section
            with Container(id="frame_info_section", classes="section"):
                yield Label(f"📊 Frame Analysis Complete", classes="section_header")
                with Horizontal(classes="info_grid"):
                    yield Static(f"Total frames: {len(self.extraction_result.frames):,}", id="total_frames")
                    yield Static(f"Input type: {self.extraction_result.input_type}", id="input_type") 
                    
                    stats = self.processor.get_sharpness_statistics()
                    if stats:
                        yield Static(f"Avg sharpness: {stats['average']:.1f}", id="avg_sharpness")
                        yield Static(f"Range: {stats['min']:.1f} - {stats['max']:.1f}", id="sharpness_range")
            
            # Method selection section
            with Container(id="method_section", classes="section"):
                yield Label("🎯 Selection Method", classes="section_header")
                yield Select(
                    options=[(key, info["name"]) for key, info in self.method_definitions.items()],
                    value=self.current_method,
                    id="method_select"
                )
                yield Static("", id="method_description", classes="method_description")
            
            # Parameters section
            with Container(id="parameters_section", classes="section"):
                yield Label("⚙️ Parameters", classes="section_header")
                with Container(id="parameter_inputs"):
                    pass  # Will be populated dynamically
            
            # Preview section
            with Container(id="preview_section", classes="section"):
                yield Label("👀 Selection Preview", classes="section_header")
                with Horizontal(classes="preview_grid"):
                    yield Static("Selected frames: 0", id="preview_count", classes="preview_stat")
                    yield Static("Percentage: 0.0%", id="preview_percentage", classes="preview_stat")
                
                with Collapsible(title="📈 Detailed Statistics", collapsed=True):
                    yield Static("Min sharpness: 0.0", id="preview_min_sharpness")
                    yield Static("Max sharpness: 0.0", id="preview_max_sharpness") 
                    yield Static("Avg sharpness: 0.0", id="preview_avg_sharpness")
                    yield Sparkline([0], id="preview_distribution", classes="distribution_chart")
            
            # Action buttons
            with Horizontal(id="action_buttons", classes="button_row"):
                yield Button("← Back", id="back_button", variant="default")
                yield Button("Confirm Selection", id="confirm_button", variant="primary")
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Initialize the screen when mounted."""
        self._update_method_description()
        self._update_parameter_inputs() 
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
            self._update_parameter_inputs()
            self._update_preview_async()
    
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle parameter input changes."""
        input_id = event.input.id
        if input_id and input_id.startswith("param_"):
            param_name = input_id[6:]  # Remove "param_" prefix
            
            try:
                # Parse and validate the parameter value
                param_info = self.method_definitions[self.current_method]["parameters"][param_name]
                
                if param_info["type"] == "int":
                    value = int(event.value) if event.value else param_info["default"]
                    value = max(param_info.get("min", 1), min(value, param_info.get("max", 10000)))
                elif param_info["type"] == "float":
                    value = float(event.value) if event.value else param_info["default"]
                    value = max(param_info.get("min", 0.1), min(value, param_info.get("max", 3.0)))
                else:
                    value = event.value
                
                self.current_parameters[param_name] = value
                self._update_preview_async()
                
            except (ValueError, KeyError):
                # Invalid input, ignore for now
                pass
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "back_button":
            self.action_cancel()
        elif event.button.id == "confirm_button":
            self.action_confirm()
    
    def action_cancel(self) -> None:
        """Cancel selection and return to previous screen."""
        self.app.pop_screen()
    
    def action_confirm(self) -> None:
        """Confirm selection and proceed with saving."""
        self._start_final_processing()
    
    def action_help(self) -> None:
        """Show help information."""
        help_text = """
# Selection Methods

**Best N Frames**: Selects the N sharpest frames while maintaining good distribution across the timeline.

**Batched Selection**: Divides frames into batches and selects the sharpest frame from each batch.

**Outlier Removal**: Removes frames with unusually low sharpness compared to their neighbors.

# Shortcuts

- **Enter**: Confirm selection
- **Escape**: Cancel and return
- **F1**: Show this help
        """
        self.app.push_screen("help", help_text)
    
    def _update_method_description(self) -> None:
        """Update the method description text."""
        description = self.method_definitions[self.current_method]["description"]
        description_widget = self.query_one("#method_description", Static)
        description_widget.update(description)
    
    def _update_parameter_inputs(self) -> None:
        """Update parameter input widgets based on selected method."""
        container = self.query_one("#parameter_inputs", Container)
        
        # Clear existing inputs
        container.remove_children()
        
        # Add inputs for current method
        method_info = self.method_definitions[self.current_method]
        for param_name, param_info in method_info["parameters"].items():
            with container:
                label = Label(param_info["label"])
                
                if param_info["type"] in ["int", "float"]:
                    input_widget = Input(
                        str(self.current_parameters.get(param_name, param_info["default"])),
                        id=f"param_{param_name}",
                        placeholder=str(param_info["default"])
                    )
                    container.mount(label)
                    container.mount(input_widget)
    
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
        """Update the preview display with new count."""
        self.selected_count = count
        
        total_frames = len(self.extraction_result.frames)
        percentage = (count / total_frames * 100) if total_frames > 0 else 0
        
        # Update basic stats
        self.query_one("#preview_count", Static).update(f"Selected frames: {count:,}")
        self.query_one("#preview_percentage", Static).update(f"Percentage: {percentage:.1f}%")
        
        # Try to get detailed preview for statistics
        try:
            # Convert frames to dict format for preview function
            frames_dict = []
            for frame in self.extraction_result.frames:
                frames_dict.append({
                    'id': f"frame_{frame.index:05d}",
                    'path': frame.path,
                    'index': frame.index,
                    'sharpnessScore': frame.sharpness_score
                })
            
            # Get detailed preview
            preview = get_selection_preview(frames_dict, self.current_method, **self.current_parameters)
            
            # Update detailed statistics
            stats = preview.get('statistics', {})
            self.query_one("#preview_min_sharpness", Static).update(f"Min sharpness: {stats.get('min_sharpness', 0):.1f}")
            self.query_one("#preview_max_sharpness", Static).update(f"Max sharpness: {stats.get('max_sharpness', 0):.1f}")
            self.query_one("#preview_avg_sharpness", Static).update(f"Avg sharpness: {stats.get('avg_sharpness', 0):.1f}")
            
            # Update distribution sparkline
            distribution = preview.get('distribution', [])
            if distribution:
                sparkline = self.query_one("#preview_distribution", Sparkline)
                sparkline.data = distribution
                
        except Exception as e:
            self.app.log.warning(f"Could not update detailed preview: {e}")
    
    def _start_final_processing(self) -> None:
        """Start the final processing phase (selection and saving)."""
        # Disable UI during processing
        self.query_one("#confirm_button", Button).disabled = True
        self.query_one("#method_select", Select).disabled = True
        
        # Update config with selection method and parameters
        final_config = self.config.copy()
        final_config['selection_method'] = self.current_method
        final_config.update(self.current_parameters)
        
        # Start processing in background
        asyncio.create_task(self._process_final_selection(final_config))
    
    async def _process_final_selection(self, final_config: Dict[str, Any]) -> None:
        """Process the final selection and saving."""
        try:
            # Show processing indicator
            processing_label = Label("🔄 Processing selection...", classes="processing_indicator")
            self.query_one("#selection_container").mount(processing_label)
            
            # Run the final selection (this is CPU intensive, so we might want to thread it)
            success = await asyncio.get_event_loop().run_in_executor(
                None, 
                self.processor.complete_selection,
                self.current_method,
                final_config,
                **self.current_parameters
            )
            
            if success:
                # Show success message briefly, then exit
                processing_label.update("✅ Selection completed successfully!")
                await asyncio.sleep(2)
                self.app.pop_screen()
            else:
                # Show error and re-enable UI
                processing_label.update("❌ Selection failed. Please try again.")
                await asyncio.sleep(3)
                processing_label.remove()
                self.query_one("#confirm_button", Button).disabled = False
                self.query_one("#method_select", Select).disabled = False
                
        except Exception as e:
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
    
    def _format_frame_count(self, count: int) -> str:
        """Format frame count for display."""
        if count == 1:
            return "1 frame"
        else:
            return f"{count:,} frames"