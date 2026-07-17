"""
Updated processing screen for Sharp Frames UI with two-phase support.
"""

import threading
import logging
import traceback
from typing import Dict, Any

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container
from textual.reactive import reactive
from textual.screen import Screen
from textual.binding import Binding
from textual.widget import Widget
from textual.widgets import Header, Footer, Button, Static
from textual.worker import WorkerState

from ..constants import WorkerNames
from ..utils import ErrorContext
from .selection import SelectionScreen

# Set up debug logging
logger = logging.getLogger(__name__)


class BlockProgressBar(Widget):
    """A full-cell progress bar with a compact percentage label."""

    progress = reactive(0.0)
    total = 100.0

    COMPONENT_CLASSES = {
        "block-progress--filled",
        "block-progress--empty",
        "block-progress--percentage",
    }

    def update(self, *, progress: float) -> None:
        """Update progress on a fixed zero-to-one-hundred scale."""
        self.progress = max(0.0, min(float(progress), self.total))

    def render(self) -> Text:
        """Render a solid, full-height cell track and its percentage."""
        percentage = self.progress / self.total if self.total else 0.0
        label = f" {self.progress:.0f}%".rjust(6)
        label_width = min(len(label), self.size.width)
        bar_width = max(self.size.width - label_width, 0)
        filled_width = round(bar_width * percentage)

        result = Text()
        result.append(
            " " * filled_width,
            self.get_component_rich_style("block-progress--filled"),
        )
        result.append(
            " " * (bar_width - filled_width),
            self.get_component_rich_style("block-progress--empty"),
        )
        result.append(
            label[-label_width:] if label_width else "",
            self.get_component_rich_style("block-progress--percentage"),
        )
        return result


class ProcessingScreen(Screen):
    """Screen for two-phase processing (extraction/analysis → interactive selection)."""

    PHASE_LABEL = "Phase 1 of 2"
    
    BINDINGS = [
        Binding("ctrl+c", "cancel", "Cancel Processing"),
    ]
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__()
        self.config = config
        self.processor = None
        self.extraction_result = None
        
        # Thread-safe state management
        self._state_lock = threading.RLock()
        self._processing_cancelled = False
        self._phase_1_complete = False
        
        self.current_phase = ""
        self.phase_progress = 0
        self.total_phases = 2  # Phase 1: extraction/analysis, Phase 2: selection (interactive)
        self.last_error = None
        
        logger.info(f"TwoPhaseProcessingScreen initialized with config: {config}")
    
    @property
    def processing_cancelled(self) -> bool:
        """Thread-safe getter for processing cancelled state."""
        with self._state_lock:
            return self._processing_cancelled
    
    @processing_cancelled.setter
    def processing_cancelled(self, value: bool) -> None:
        """Thread-safe setter for processing cancelled state."""
        with self._state_lock:
            self._processing_cancelled = value
    
    @property
    def phase_1_complete(self) -> bool:
        """Thread-safe getter for phase 1 complete state."""
        with self._state_lock:
            return self._phase_1_complete
    
    @phase_1_complete.setter
    def phase_1_complete(self, value: bool) -> None:
        """Thread-safe setter for whether phase one is terminal."""
        with self._state_lock:
            self._phase_1_complete = value

    def _set_terminal_state(
        self,
        status: str,
        phase: str,
        *,
        detail: str = "",
        progress: float = 0,
    ) -> None:
        """Mark phase one terminal and present a closeable screen."""
        self.phase_1_complete = True
        self.query_one("#status-text", Static).update(status)
        self.query_one("#phase-text", Static).update(phase)
        detail_text = self.query_one("#detail-text", Static)
        detail_text.update(detail)
        detail_text.display = bool(detail)
        self.query_one("#progress-bar", BlockProgressBar).update(progress=progress)
        close_button = self.query_one("#cancel-processing", Button)
        close_button.label = "Close"
        close_button.disabled = False

    def compose(self) -> ComposeResult:
        """Create the processing layout."""
        logger.info("TwoPhaseProcessingScreen compose() called")
        yield Header()
        
        with Container(id="processing-container"):
            yield Static("", id="status-text")
            yield Static("", id="phase-text")
            yield BlockProgressBar(id="progress-bar")
            yield Static("", id="detail-text", classes="detail")
            yield Button("Cancel", variant="default", id="cancel-processing")
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Called when the screen is mounted."""
        logger.info("TwoPhaseProcessingScreen mounted")
        self.start_phase_1_processing()
    
    def start_phase_1_processing(self) -> None:
        """Start Phase 1: extraction and analysis processing."""
        try:
            logger.info("Starting Phase 1 processing...")
            
            # Update UI elements  
            status_text = self.query_one("#status-text")
            phase_text = self.query_one("#phase-text")
            progress_bar = self.query_one("#progress-bar")
            detail_text = self.query_one("#detail-text")
            
            logger.info("UI elements found successfully")
            
            # Validate configuration
            if not self._validate_config(self.config):
                logger.error("Configuration validation failed")
                self._set_terminal_state(
                    "Configuration needs attention",
                    "Unable to start processing",
                    detail="Please check your settings and try again.",
                )
                return
            
            logger.info("Configuration validation passed")
            
            # Show Phase 1 initialization
            status_text.update(f"Preparing frames · {self.PHASE_LABEL}")
            phase_text.update("Starting extraction and analysis…")
            detail_text.display = True
            detail_text.update(
                "This may take a few minutes depending on the input size."
            )
            progress_bar.update(progress=0)
            
            logger.info("Starting Phase 1 worker thread...")
            
            # Start Phase 1 processing in background worker
            self.run_worker(self._process_phase_1, exclusive=True, thread=True, name=f"{WorkerNames.FRAME_PROCESSOR}_phase1")
            
            logger.info("Phase 1 worker thread started successfully")
            
        except Exception as e:
            logger.error(f"Error in start_phase_1_processing(): {e}")
            logger.error(traceback.format_exc())
            self._set_terminal_state(
                "Error starting processing",
                str(e),
            )
    
    def _validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate configuration for Phase 1 processing."""
        logger.info("Validating config for Phase 1")
        
        # Check required fields
        if not config.get('input_path'):
            logger.error("Missing input path")
            return False
        
        if not config.get('output_dir'):
            logger.error("Missing output directory")
            return False
        
        # Use ErrorContext for comprehensive validation
        try:
            error_msg = ErrorContext.analyze_processing_failure(config)
            if error_msg != "Processing failed due to an unexpected error. Check input files and system resources.":
                logger.warning(f"ErrorContext found issue: {error_msg}")
                return False
        except Exception as e:
            logger.error(f"ErrorContext analysis failed: {e}")
        
        # Check system dependencies
        try:
            dependency_error = ErrorContext.check_system_dependencies(
                require_video_tools=config.get('input_type') in {'video', 'video_directory'}
            )
            if dependency_error:
                logger.error(f"System dependency error: {dependency_error}")
                return False
        except Exception as e:
            logger.error(f"System dependency check failed: {e}")
        
        logger.info("Phase 1 validation checks passed")
        return True
    
    def _process_phase_1(self) -> bool:
        """Worker function for Phase 1: extraction and analysis."""
        logger.info("Phase 1 worker started")
        
        # Import TUIProcessor
        from ...processing.tui_processor import TUIProcessor
        
        try:
            logger.info("Creating TUIProcessor...")
            self.processor = TUIProcessor()

            if self.processing_cancelled:
                self.processor.cancel_processing()
                logger.info("Phase 1 was cancelled before processor startup completed")
                return False
            logger.info("Starting extraction and analysis...")
            
            # Create progress callback
            def progress_callback(phase, current, total, description):
                """Progress callback for TUIProcessor."""
                # Calculate overall progress percentage
                if total > 0:
                    progress_pct = (current / total) * 100
                else:
                    progress_pct = 0
                
                # Update UI from thread
                self.app.call_from_thread(
                    self._update_progress_ui,
                    phase, current, total, progress_pct, description
                )
            
            # Run Phase 1: extract and analyze with progress callback
            self.extraction_result = self.processor.extract_and_analyze(self.config, progress_callback)

            if self.processing_cancelled:
                logger.info("Phase 1 completed after cancellation was requested")
                return False

            if not self.extraction_result or not self.extraction_result.frames:
                logger.error("Phase 1 completed but no frames were extracted")
                self.app.call_from_thread(
                    self._update_progress_ui,
                    "error", 0, 100, 0, "No frames were extracted"
                )
                return False
            
            logger.info(f"Phase 1 completed successfully - {len(self.extraction_result.frames)} frames processed")
            
            # Update progress to completion
            self.app.call_from_thread(
                self._update_progress_ui,
                "complete", 100, 100, 100, f"Phase 1 complete - {len(self.extraction_result.frames)} frames ready"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error in Phase 1 processing: {e}")
            logger.error(traceback.format_exc())
            raise
    
    def _update_progress_ui(self, phase: str, current: int, total: int, total_progress: float, description: str):
        """Update the UI with progress information."""
        logger.debug(f"Updating UI: {phase} - {current}/{total} - {total_progress}% - {description}")
        
        try:
            # Thread-safe state check
            with self._state_lock:
                if self._processing_cancelled:
                    logger.debug("UI update ignored - processing cancelled")
                    return
                
            status_text = self.query_one("#status-text")
            phase_text = self.query_one("#phase-text")
            progress_bar = self.query_one("#progress-bar")
            detail_text = self.query_one("#detail-text")
            
            count = (
                f"{current:,} of {total:,} frames"
                if total > 0
                else "Working…"
            )

            if phase == "extraction":
                status_text.update(f"Extracting frames · {self.PHASE_LABEL}")
                phase_text.update(count)
                detail_text.update("")
                detail_text.display = False

            elif phase == "analysis" or "sharpness" in phase.lower():
                status_text.update(
                    f"Analysing frame sharpness · {self.PHASE_LABEL}"
                )
                phase_text.update(count)
                detail_text.update("")
                detail_text.display = False

            elif phase == "complete":
                status_text.update(f"Analysis complete · {self.PHASE_LABEL}")
                phase_text.update("Ready for interactive selection")
                detail_text.update("")
                detail_text.display = False

            elif phase == "error":
                status_text.update("Processing failed")
                phase_text.update("Frame preparation stopped")
                detail_text.update(description)
                detail_text.display = True

            else:
                status_text.update(f"Processing frames · {self.PHASE_LABEL}")
                phase_text.update(count)
                detail_text.update(description)
                detail_text.display = bool(description)

            progress_bar.update(progress=total_progress)
            
        except Exception as e:
            logger.error(f"Error updating progress UI: {e}")
    
    def on_worker_state_changed(self, event) -> None:
        """Handle terminal states from the phase-one worker."""
        worker = event.worker
        if worker.name != f"{WorkerNames.FRAME_PROCESSOR}_phase1":
            return

        state = worker.state
        logger.info(f"Phase 1 worker state changed: {state}")
        if state == WorkerState.SUCCESS:
            result = worker.result
            logger.info(f"Phase 1 worker finished with result: {result}")
            if self.processing_cancelled:
                self._set_terminal_state(
                    "Processing cancelled",
                    "No frames were saved",
                )
            elif result and self.extraction_result:
                self.phase_1_complete = True
                self.query_one("#status-text", Static).update("Analysis complete")
                self.query_one("#phase-text", Static).update(
                    "Opening interactive selection…"
                )
                self.query_one("#progress-bar", BlockProgressBar).update(
                    progress=100
                )
                self._transition_to_selection_screen()
            else:
                self._set_terminal_state(
                    "Processing failed",
                    "Frame extraction or analysis did not complete",
                )
            return

        if state == WorkerState.CANCELLED:
            logger.info("Phase 1 worker was cancelled")
            self._set_terminal_state(
                "Processing cancelled",
                "No frames were saved",
            )
            return

        if state == WorkerState.ERROR:
            error = worker.error
            logger.error(f"Phase 1 worker error: {error}")
            self.last_error = error
            error_msg = "Unknown error occurred"
            if error is not None:
                error_msg = ErrorContext.analyze_processing_failure(
                    self.config, error
                )
                if hasattr(error, "__traceback__"):
                    error_details = "".join(
                        traceback.format_exception(
                            type(error), error, error.__traceback__
                        )
                    )
                    logger.error(
                        f"Detailed error traceback:\n{error_details}"
                    )
            self._set_terminal_state(
                "Processing error",
                error_msg,
            )
    
    def _transition_to_selection_screen(self) -> None:
        """Transition to the interactive selection screen."""
        try:
            logger.info("Transitioning to SelectionScreen")
            
            # Create and push the selection screen
            selection_screen = SelectionScreen(
                processor=self.processor,
                extraction_result=self.extraction_result,
                config=self.config
            )
            
            # Push the new screen (this will handle the transition)
            self.app.push_screen(selection_screen)
            
        except Exception as e:
            logger.error(f"Error transitioning to selection screen: {e}")
            logger.error(traceback.format_exc())
            self._set_terminal_state(
                "Error opening selection screen",
                str(e),
            )
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel-processing":
            self.action_cancel()

    def action_cancel(self) -> None:
        """Close a terminal screen or request cooperative cancellation."""
        if self.phase_1_complete:
            self.app.pop_screen()
            return
        if self.processing_cancelled:
            return

        logger.info("Cancelling Phase 1 processing")
        self.processing_cancelled = True

        try:
            self.query_one("#status-text", Static).update("Cancelling…")
            self.query_one("#phase-text", Static).update(
                "Stopping background work safely…"
            )
            self.query_one("#progress-bar", BlockProgressBar).update(progress=0)
            self.query_one("#cancel-processing", Button).disabled = True
        except Exception as e:
            logger.error(f"Error updating UI during cancellation: {e}")

        if self.processor and hasattr(self.processor, "cancel_processing"):
            try:
                self.processor.cancel_processing()
                logger.info("Processor cancellation requested")
            except Exception as e:
                logger.error(f"Error cancelling processor: {e}")

        # The thread worker remains active until extraction and temporary-file
        # cleanup finish, then its terminal state makes this screen closeable.
    
    def on_unmount(self) -> None:
        """Clean up when screen is unmounted."""
        logger.info("TwoPhaseProcessingScreen unmounting")
        
        # Clean up processor if needed
        if self.processor:
            try:
                self.processor.cleanup_temp_directory()
            except Exception as e:
                logger.warning(f"Error cleaning up processor: {e}")
        
