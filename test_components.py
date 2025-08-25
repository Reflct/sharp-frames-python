#!/usr/bin/env python
"""Test the two-phase Sharp Frames components."""

import sys
import asyncio
from sharp_frames.ui.app_v2 import TwoPhaseSharpFramesApp
from sharp_frames.ui.screens.configuration_v2 import TwoPhaseConfigurationForm


def test_configuration_form():
    """Test that configuration form can be created."""
    print("Testing configuration form creation...")
    try:
        form = TwoPhaseConfigurationForm()
        print(f"✓ Configuration form created successfully")
        print(f"  - Steps: {form.steps}")
        print(f"  - Current step: {form.current_step}")
        print(f"  - Step handlers: {list(form.step_handlers.keys())}")
        return True
    except Exception as e:
        print(f"✗ Failed to create configuration form: {e}")
        return False


def test_app_creation():
    """Test that app can be created."""
    print("\nTesting app creation...")
    try:
        app = TwoPhaseSharpFramesApp()
        print(f"✓ App created successfully")
        print(f"  - Title: {app.TITLE}")
        print(f"  - Has CSS: {app.CSS is not None}")
        return True
    except Exception as e:
        print(f"✗ Failed to create app: {e}")
        return False


def test_step_handlers():
    """Test that step handlers are working."""
    print("\nTesting step handlers...")
    from sharp_frames.ui.components.v2_step_handlers import (
        InputTypeStepHandler,
        InputPathStepHandler,
        OutputDirStepHandler,
        FpsStepHandler,
        OutputFormatStepHandler,
        WidthStepHandler,
        ForceOverwriteStepHandler,
        ConfirmStepHandler
    )
    
    handlers = [
        ("InputType", InputTypeStepHandler),
        ("InputPath", InputPathStepHandler),
        ("OutputDir", OutputDirStepHandler),
        ("Fps", FpsStepHandler),
        ("OutputFormat", OutputFormatStepHandler),
        ("Width", WidthStepHandler),
        ("ForceOverwrite", ForceOverwriteStepHandler),
        ("Confirm", ConfirmStepHandler)
    ]
    
    all_good = True
    for name, handler_class in handlers:
        try:
            handler = handler_class()
            assert hasattr(handler, 'get_title')
            assert hasattr(handler, 'get_description')
            assert hasattr(handler, 'render')
            assert hasattr(handler, 'validate')
            assert hasattr(handler, 'get_data')
            print(f"  ✓ {name}StepHandler: {handler.get_title()}")
        except Exception as e:
            print(f"  ✗ {name}StepHandler failed: {e}")
            all_good = False
    
    return all_good


def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing Two-Phase Sharp Frames Components")
    print("=" * 60)
    
    results = []
    results.append(test_configuration_form())
    results.append(test_app_creation())
    results.append(test_step_handlers())
    
    print("\n" + "=" * 60)
    if all(results):
        print("✓ All tests passed!")
        print("\nYou can now run the app with:")
        print("  python test_two_phase.py")
        return 0
    else:
        print("✗ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())