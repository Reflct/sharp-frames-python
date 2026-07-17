"""Shared keyboard behavior for interactive option controls."""

from textual.actions import SkipAction
from textual.widget import Widget
from textual.widgets import Checkbox, OptionList, RadioButton, RadioSet, Select


class OptionSelect(Select):
    """A small option menu where Space selects instead of type-searching."""

    def on_mount(self) -> None:
        """Keep Space available to the screen-level selection binding."""
        overlay = self.query_one(OptionList)
        if hasattr(overlay, "_type_to_search"):
            overlay._type_to_search = False


def select_focused_option(focused: Widget | None) -> None:
    """Select or toggle the option represented by the focused control.

    Raising ``SkipAction`` lets unrelated controls, such as text inputs and
    buttons, keep their normal Space-key behavior.
    """
    if isinstance(focused, Select):
        focused.action_show_overlay()
        return

    if isinstance(focused, OptionList):
        focused.action_select()
        return

    if isinstance(focused, (Checkbox, RadioButton)):
        focused.toggle()
        return

    if isinstance(focused, RadioSet):
        focused.action_toggle_button()
        return

    raise SkipAction
