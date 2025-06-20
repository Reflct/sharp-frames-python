#!/usr/bin/env python3
"""
Textual-based user interface for Sharp Frames interactive mode.

This is the main entry point for the Sharp Frames textual interface.
All UI components have been modularized into the ui package.
"""

from .ui import SharpFramesApp


def run_textual_interface() -> bool:
    """Run the Textual interface and return success status."""
    try:
        app = SharpFramesApp()
        result = app.run()
        return result != "cancelled"
    except Exception as e:
        print(f"Error running Textual interface: {e}")
        return False


if __name__ == "__main__":
    run_textual_interface() 