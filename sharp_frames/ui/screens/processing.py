"""
Processing screen for Sharp Frames UI.
"""

import threading
from typing import Dict, Any

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Header, Footer, Button, Static, ProgressBar
from textual.screen import Screen
from textual.binding import Binding

from ..constants import WorkerNames, ProcessingPhases
from ..utils import ErrorContext


class ProcessingScreen(Screen):
    """Screen shown during processing."""
    
    BINDINGS = [
        Binding("ctrl+c", "cancel", "Cancel Processing"),
    ]
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__()
        self.config = config
        self.processor = None
        
        # Thread-safe state management
        self._state_lock = threading.RLock()  # Reentrant lock for nested access
        self._processing_cancelled = False
        self._processing_complete = False
        
        self.current_phase = ""
        self.phase_progress = 0
        self.total_phases = 5  # dependencies, extraction/loading, sharpness, selection, saving
        self.last_error = None  # Store last error for analysis
    
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
    def processing_complete(self) -> bool:
        """Thread-safe getter for processing complete state."""
        with self._state_lock:
            return self._processing_complete
    
    @processing_complete.setter
    def processing_complete(self, value: bool) -> None:
        """Thread-safe setter for processing complete state."""
        with self._state_lock:
            self._processing_complete = value

    def compose(self) -> ComposeResult:
        """Create the processing layout."""
        yield Header()
        
        with Container(id="processing-container"):
            yield Static("Processing...", classes="title")
            yield Static("", id="status-text")
            yield Static("", id="phase-text")
            yield ProgressBar(id="progress-bar", show_eta=False)
            yield Button("Cancel", variant="default", id="cancel-processing")
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Start processing when mounted."""
        self.start_processing()
    
    def start_processing(self) -> None:
        """Start the Sharp Frames processing asynchronously."""
        try:
            status_text = self.query_one("#status-text")
            progress_bar = self.query_one("#progress-bar")
            phase_text = self.query_one("#phase-text")
            
            # Validate configuration before starting
            config_issues = self._validate_config()
            if config_issues:
                status_text.update("❌ Configuration Error")
                phase_text.update(f"Config issue: {config_issues}")
                self.query_one("#cancel-processing").label = "Close"
                return
            
            # Immediately show that processing has started
            status_text.update("🔄 Initializing Sharp Frames processor...")
            phase_text.update("Phase 1/5: Starting...")
            progress_bar.update(progress=0)  # Start at 0%
            
            # Start the processing in a background worker
            self.run_worker(self._process_frames, exclusive=True, thread=True, name=WorkerNames.FRAME_PROCESSOR)
            
        except Exception as e:
            self.query_one("#status-text").update(f"❌ Error starting processing: {str(e)}")
            self.query_one("#cancel-processing").label = "Close"
    
    def _validate_config(self) -> str:
        """Validate configuration and return error message if invalid."""
        config = self.config
        
        # Check required fields
        if not config.get('input_path'):
            return "Missing input path"
        
        if not config.get('output_dir'):
            return "Missing output directory"
        
        # Use ErrorContext for comprehensive validation
        error_msg = ErrorContext.analyze_processing_failure(config)
        if error_msg != "Processing failed due to an unexpected error. Check input files and system resources.":
            return error_msg
        
        # Check system dependencies
        dependency_error = ErrorContext.check_system_dependencies()
        if dependency_error:
            return dependency_error
        
        return ""  # No issues found
    
    def _progress_callback(self, phase: str, current: int, total: int, description: str = ""):
        """Callback function to update progress from the processor.
        
        Args:
            phase: Current processing phase (e.g., 'extraction', 'sharpness')
            current: Current progress count within the phase
            total: Total expected items for this phase (0 if unknown)
            description: Human-readable description of current operation
            
        Note:
            This method is thread-safe and can be called from worker threads.
            Progress updates are scheduled on the main UI thread.
        """
        # Thread-safe state check
        with self._state_lock:
            if self._processing_cancelled or self._processing_complete:
                return
        
        self.current_phase = phase
        
        # Calculate overall progress across all phases
        phase_mapping = {
            ProcessingPhases.DEPENDENCIES: 0,
            ProcessingPhases.EXTRACTION: 1, 
            ProcessingPhases.LOADING: 1,  # Same as extraction phase
            ProcessingPhases.SHARPNESS: 2,
            ProcessingPhases.SELECTION: 3,
            ProcessingPhases.SAVING: 4
        }
        
        current_phase_num = phase_mapping.get(phase, 0)
        
        # Calculate progress within current phase (0-20% per phase)
        phase_progress = 0
        if total > 0:
            phase_progress = (current / total) * 20  # Each phase is 20%
        
        # Calculate total progress (current phase * 20% + progress within phase)
        total_progress = (current_phase_num * 20) + phase_progress
        total_progress = min(100, max(0, total_progress))  # Clamp between 0-100
        
        # Schedule UI update on main thread with thread-safe state
        self.app.call_from_thread(self._update_progress_ui, phase, current, total, total_progress, description)
    
    def _update_progress_ui(self, phase: str, current: int, total: int, total_progress: float, description: str):
        """Update the UI with progress information."""
        try:
            # Thread-safe state check
            with self._state_lock:
                if self._processing_complete or self._processing_cancelled:
                    return
                
            status_text = self.query_one("#status-text")
            phase_text = self.query_one("#phase-text")
            progress_bar = self.query_one("#progress-bar")
            
            # Update phase information
            phase_names = {
                ProcessingPhases.DEPENDENCIES: "Checking Dependencies",
                ProcessingPhases.EXTRACTION: "Extracting Frames",
                ProcessingPhases.LOADING: "Loading Images", 
                ProcessingPhases.SHARPNESS: "Calculating Sharpness",
                ProcessingPhases.SELECTION: "Selecting Frames",
                ProcessingPhases.SAVING: "Saving Results"
            }
            
            phase_name = phase_names.get(phase, phase.title())
            phase_num = ["dependencies", "extraction", "loading", "sharpness", "selection", "saving"].index(phase) + 1
            
            if phase == "loading":
                phase_num = 2  # Loading is phase 2, same as extraction conceptually
            
            status_text.update(f"🔄 {phase_name}...")
            
            if total > 0:
                phase_text.update(f"Phase {phase_num}/5: {description} ({current}/{total})")
            else:
                phase_text.update(f"Phase {phase_num}/5: {description}")
            
            # Update progress bar
            progress_bar.update(progress=total_progress)
            
        except Exception as e:
            # Fail silently if UI update fails to avoid breaking processing
            pass
    
    def _process_frames(self) -> bool:
        """Worker function that runs the actual processing."""
        # Import here to avoid circular imports
        from ...processing.minimal_progress import MinimalProgressSharpFrames
        
        try:
            # Create a custom SharpFrames processor with progress callback
            processor_config = self.config.copy()
            processor_config['progress_callback'] = self._progress_callback
            
            # Update UI with config info for debugging
            self.app.call_from_thread(self._update_debug_info, f"Creating processor...")
            
            try:
                # Remove progress_callback from config to avoid duplicate argument
                clean_config = {k: v for k, v in processor_config.items() if k != 'progress_callback'}
                # Pass app instance for signal handling on macOS
                self.processor = MinimalProgressSharpFrames(
                    progress_callback=self._progress_callback, 
                    app_instance=self.app,
                    **clean_config
                )
                self.app.call_from_thread(self._update_debug_info, f"Using progress-enabled SharpFrames processor with macOS compatibility")
            except Exception as init_error:
                self.last_error = init_error
                error_msg = ErrorContext.analyze_processing_failure(self.config, init_error)
                self.app.call_from_thread(self._update_debug_info, f"Failed to create processor: {error_msg}")
                raise init_error
            
            # Run the processing
            self.app.call_from_thread(self._update_debug_info, f"Starting processing...")
            
            success = self.processor.run()
            
            if not success:
                error_msg = ErrorContext.analyze_processing_failure(self.config)
                self.app.call_from_thread(self._update_debug_info, f"Processing failed: {error_msg}")
            
            return success
            
        except KeyboardInterrupt:
            self.app.call_from_thread(self._update_debug_info, "Processing cancelled by user")
            self.processing_cancelled = True
            return False
        except Exception as e:
            self.last_error = e
            # Analyze error and provide user-friendly message
            error_msg = ErrorContext.analyze_processing_failure(self.config, e)
            self.app.call_from_thread(self._update_debug_info, error_msg)
            # Re-raise the exception to be caught by worker error handler
            raise e
    
    def _update_debug_info(self, message: str):
        """Update UI with debug information."""
        try:
            phase_text = self.query_one("#phase-text")
            phase_text.update(f"Debug: {message}")
        except:
            pass  # Fail silently if UI update fails
    
    def on_worker_state_changed(self, event) -> None:
        """Handle worker state changes."""
        if event.worker.name == WorkerNames.FRAME_PROCESSOR:
            status_text = self.query_one("#status-text")
            progress_bar = self.query_one("#progress-bar")
            phase_text = self.query_one("#phase-text")
            
            if event.worker.is_running:
                # Keep current progress display while running
                pass
            elif event.worker.is_finished:
                # Thread-safe state update
                self.processing_complete = True
                
                if event.worker.result:
                    status_text.update("✅ Processing completed successfully!")
                    phase_text.update("All phases complete!")
                    progress_bar.display = False  # Hide the progress bar when complete
                else:
                    # Thread-safe state check
                    if self.processing_cancelled:
                        status_text.update("⚠️ Processing cancelled by user.")
                        phase_text.update("Processing was cancelled.")
                    else:
                        # Worker finished but returned False - provide detailed error analysis
                        status_text.update("❌ Processing failed")
                        
                        # Use ErrorContext to provide better error messages
                        if self.last_error:
                            error_msg = ErrorContext.analyze_processing_failure(self.config, self.last_error)
                        else:
                            error_msg = ErrorContext.analyze_processing_failure(self.config)
                        
                        phase_text.update(error_msg)
                        
                    progress_bar.update(progress=0)  # Show failed state without animation
                
                # Change button to close
                self.query_one("#cancel-processing").label = "Close"
            elif event.worker.is_cancelled:
                # Thread-safe state update
                self.processing_complete = True
                status_text.update("⚠️ Processing cancelled.")
                phase_text.update("Processing was cancelled.")
                progress_bar.update(progress=0)  # Show cancelled state without animation
                self.query_one("#cancel-processing").label = "Close"
    
    def on_worker_state_error(self, event) -> None:
        """Handle worker errors."""
        if event.worker.name == WorkerNames.FRAME_PROCESSOR:
            # Thread-safe state update
            self.processing_complete = True
            
            # Analyze error and provide user-friendly message
            error_msg = "Unknown error occurred"
            if event.error:
                self.last_error = event.error
                error_msg = ErrorContext.analyze_processing_failure(self.config, event.error)
                
                # Log detailed error for debugging
                if hasattr(event.error, '__traceback__'):
                    import traceback
                    error_details = ''.join(traceback.format_exception(type(event.error), event.error, event.error.__traceback__))
                    print(f"Detailed error:\n{error_details}")
            
            self.query_one("#status-text").update("❌ Processing Error")
            self.query_one("#phase-text").update(error_msg)
            self.query_one("#progress-bar").update(progress=0)  # Show error state without animation
            self.query_one("#cancel-processing").label = "Close"
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel-processing":
            if event.button.label == "Cancel":
                self.action_cancel()
            else:
                # Close button
                self.app.exit(result="completed")
    
    def action_cancel(self) -> None:
        """Cancel processing."""
        # Thread-safe state update
        self.processing_cancelled = True
        
        # Cancel the worker if it's running
        workers = self.workers
        for worker in workers:
            if worker.name == WorkerNames.FRAME_PROCESSOR and not worker.is_finished:
                worker.cancel()
                break
        
        # If no worker was cancelled, just exit
        if not any(w.name == WorkerNames.FRAME_PROCESSOR for w in workers):
            self.app.exit(result="cancelled") 