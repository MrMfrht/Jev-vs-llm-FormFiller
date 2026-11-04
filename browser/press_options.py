"""Build Jev choice criteria from an existing page observation."""

from .snapshot import PageSnapshot


# Text entry belongs to a separate action. Pressing a combobox can open it.
PRESS_ROLES = frozenset({
    "button", "link", "checkbox", "radio", "combobox", "switch", "tab", "menuitem",
    "menuitemcheckbox", "menuitemradio", "option", "treeitem",
    "date-picker", "datetime-local-picker", "month-picker", "week-picker",
    "time-picker", "color-picker", "file-picker",
})


def press_options(snapshot: PageSnapshot) -> dict[str, str]:
    """Map snapshot-local IDs to choices. Use the snapshot HTML for context."""
    return {
        control.id: f"{control.role}: {control.name or '(unlabeled)'}"
        for control in snapshot.controls
        if control.role in PRESS_ROLES and not control.disabled
    }
