"""
Updated processing screen for Sharp Frames UI with two-phase support.
"""

import threading
import logging
import traceback
import os
from typing import Dict, Any, Optional

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Header, Footer, Button, Static, ProgressBar
from textual.screen import Screen
from textual.binding import Binding

from ..constants import WorkerNames, ProcessingPhases
from ..utils import ErrorContext
from .selection import SelectionScreen

# Set up debug logging
logger = logging.getLogger(__name__)


class ProcessingScreen(Screen):
    """Screen for two-phase processing (extraction/analysis → interactive selection)."""
    
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
        """Thread-safe setter for phase 1 complete state."""
        with self._state_lock:
            self._phase_1_complete = value
    
    def compose(self) -> ComposeResult:
        """Create the processing layout."""
        logger.info("TwoPhaseProcessingScreen compose() called")
        yield Header()
        
        with Container(id="processing-container"):
            yield Static("Sharp Frames - Two Phase Processing", classes="title")
            yield Static("", id="status-text")
            yield Static("", id="phase-text")
            yield ProgressBar(id="progress-bar", show_eta=False)
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
                status_text.update("❌ Configuration validation failed")
                phase_text.update("Please check your settings and try again.")
                self.query_one("#cancel-processing").label = "Close"
                return
            
            logger.info("Configuration validation passed")
            
            # Show Phase 1 initialization
            status_text.update("🔄 Phase 1: Initializing extraction and analysis...")
            phase_text.update("Preparing to process frames...")
            detail_text.update("This may take a few minutes depending on input size.")
            progress_bar.update(progress=0)
            
            logger.info("Starting Phase 1 worker thread...")
            
            # Start Phase 1 processing in background worker
            self.run_worker(self._process_phase_1, exclusive=True, thread=True, name=f"{WorkerNames.FRAME_PROCESSOR}_phase1")
            
            logger.info("Phase 1 worker thread started successfully")
            
        except Exception as e:
            logger.error(f"Error in start_phase_1_processing(): {e}")
            logger.error(traceback.format_exc())
            self.query_one("#status-text").update(f"❌ Error starting processing: {str(e)}")
            self.query_one("#cancel-processing").label = "Close"
    
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
            dependency_error = ErrorContext.check_system_dependencies()
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
            self.app.call_from_thread(
                self._update_progress_ui,
                "error", 0, 100, 0, f"Error: {str(e)}"
            )
            return False
    
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
            
            if phase == "extraction":
                status_text.update("🔄 Phase 1: Extracting frames...")
                phase_text.update(f"Progress: {current}/{total}" if total > 0 else "Extracting frames...")
                
            elif phase == "analysis" or "sharpness" in phase.lower():
                status_text.update("🔍 Phase 1: Analyzing frame sharpness...")
                phase_text.update(f"Analyzing: {current}/{total}" if total > 0 else "Calculating sharpness scores...")
                
            elif phase == "complete":
                status_text.update("✅ Phase 1 Complete!")
                phase_text.update("Ready for interactive selection")
                
            elif phase == "error":
                status_text.update("❌ Phase 1 Failed")
                phase_text.update("Processing error occurred")
                
            # Update progress bar and detail
            progress_bar.update(progress=total_progress)
            detail_text.update(description)
            
        except Exception as e:
            logger.error(f"Error updating progress UI: {e}")
    
    def on_worker_state_changed(self, event) -> None:
        """Handle worker state changes."""
        if event.worker.name != f"{WorkerNames.FRAME_PROCESSOR}_phase1":
            return
            
        logger.info(f"Phase 1 worker state changed: {event.worker.state}")
        
        status_text = self.query_one("#status-text")
        phase_text = self.query_one("#phase-text")
        progress_bar = self.query_one("#progress-bar")
        
        if event.worker.is_finished:
            logger.info(f"Phase 1 worker finished with result: {event.worker.result}")
            
            if event.worker.result and self.extraction_result:
                # Phase 1 completed successfully
                self.phase_1_complete = True
                logger.info("Phase 1 completed successfully, transitioning to selection screen")
                
                status_text.update("✅ Phase 1 Complete - Transitioning to selection...")
                phase_text.update("Opening interactive selection screen...")
                progress_bar.update(progress=100)
                
                # Transition to selection screen
                self._transition_to_selection_screen()
                
            else:
                # Phase 1 failed
                logger.error("Phase 1 failed")
                if self.processing_cancelled:
                    status_text.update("⚠️ Phase 1 cancelled by user.")
                    phase_text.update("Processing was cancelled.")
                else:
                    status_text.update("❌ Phase 1 failed.")
                    phase_text.update("Frame extraction or analysis failed.")
                
                progress_bar.update(progress=0)
                self.query_one("#cancel-processing").label = "Close"
                
        elif event.worker.is_cancelled:
            logger.info("Phase 1 worker was cancelled")
            self.phase_1_complete = True
            status_text.update("⚠️ Phase 1 cancelled.")
            phase_text.update("Processing was cancelled.")
            progress_bar.update(progress=0)
            self.query_one("#cancel-processing").label = "Close"
    
    def on_worker_state_error(self, event) -> None:
        """Handle worker errors."""
        if event.worker.name != f"{WorkerNames.FRAME_PROCESSOR}_phase1":
            return
            
        logger.error(f"Phase 1 worker error: {event.error}")
        
        self.phase_1_complete = True
        self.last_error = event.error
        
        # Analyze error and provide user-friendly message
        error_msg = "Unknown error occurred"
        if event.error:
            error_msg = ErrorContext.analyze_processing_failure(self.config, event.error)
            
            # Log detailed error
            if hasattr(event.error, '__traceback__'):
                error_details = ''.join(traceback.format_exception(
                    type(event.error), event.error, event.error.__traceback__
                ))
                logger.error(f"Detailed error traceback:\n{error_details}")
        
        # Update UI
        status_text = self.query_one("#status-text")
        phase_text = self.query_one("#phase-text")
        progress_bar = self.query_one("#progress-bar")
        
        status_text.update(f"❌ Phase 1 Error")
        phase_text.update(error_msg)
        progress_bar.update(progress=0)
        self.query_one("#cancel-processing").label = "Close"
    
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
            
            # Fallback error display
            status_text = self.query_one("#status-text")
            status_text.update(f"❌ Error opening selection screen: {str(e)}")
            self.query_one("#cancel-processing").label = "Close"
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel-processing":
            if self.phase_1_complete:
                # Processing is complete, this is now a "Close" button
                self.app.pop_screen()
            else:
                # Cancel processing
                self.action_cancel()
    
    def action_cancel(self) -> None:
        """Cancel the current processing."""
        logger.info("Cancelling Phase 1 processing")
        
        # Set cancellation flag
        self.processing_cancelled = True
        
        # Cancel processor operations
        if self.processor and hasattr(self.processor, 'cancel_processing'):
            try:
                self.processor.cancel_processing()
                logger.info("Processor cancellation requested")
            except Exception as e:
                logger.error(f"Error cancelling processor: {e}")
        
        # Cancel any running workers
        try:
            for worker in self.workers:
                if not worker.is_finished:
                    worker.cancel()
                    logger.info(f"Worker {worker.name} cancellation requested")
        except Exception as e:
            logger.error(f"Error cancelling workers: {e}")
        
        # Update UI
        try:
            status_text = self.query_one("#status-text")
            phase_text = self.query_one("#phase-text")
            progress_bar = self.query_one("#progress-bar")
            
            status_text.update("⚠️ Cancelling...")
            phase_text.update("Please wait while processing stops...")
            progress_bar.update(progress=0)
            
        except Exception as e:
            logger.error(f"Error updating UI during cancellation: {e}")
        
        # Close the screen after a short delay to allow cleanup
        def delayed_close():
            try:
                self.app.pop_screen()
            except Exception as e:
                logger.error(f"Error closing screen: {e}")
        
        # Schedule delayed close (give 2 seconds for cleanup)
        import threading
        threading.Timer(2.0, delayed_close).start()
    
    def on_unmount(self) -> None:
        """Clean up when screen is unmounted."""
        logger.info("TwoPhaseProcessingScreen unmounting")
        
        # Clean up processor if needed
        if self.processor:
            try:
                self.processor.cleanup_temp_directory()
            except Exception as e:
                logger.warning(f"Error cleaning up processor: {e}")
        
