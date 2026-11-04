"""Apply proposed matches to bound fields and verify each result."""

from collections import Counter

from playwright.sync_api import Error as BrowserError

from .dropdown_selection import select_dropdown
from .selection import Selection
from .targets import FieldTarget, is_dropdown


def _fill_text(target: FieldTarget, value: str) -> Selection:
    try:
        if not target.is_current():
            return Selection("needs_review", "Field is no longer available.")
        node = target.node
        node.fill(value, timeout=2000)
        node.evaluate("el => el.blur()")
        if node.input_value() == value and node.evaluate("el => el.isConnected && el.checkValidity() && el.getAttribute('aria-invalid') !== 'true'"):
            return Selection("matched", value)
        return Selection("needs_review", "The value did not pass readback or field validation.")
    except BrowserError:
        return Selection("needs_review", "Could not confirm the value after input.")


def apply_matches(matches: list[dict], targets: dict[str, FieldTarget]) -> list[dict]:
    proposals_per_field = Counter(match["field_id"] for match in matches if match["status"] == "proposed")
    output = []
    for match in matches:
        if match["status"] != "proposed":
            output.append(match)
            continue
        target = targets.get(match["field_id"])
        if not target:
            selection = Selection("skipped", "No supported field bound in this mode.")
        elif proposals_per_field[match["field_id"]] > 1 and not target.field.multiple:
            selection = Selection("needs_review", "Multiple facts map to one single-value field.")
        elif target.field.kind == "checkbox":
            value = match["value"]
            selection = Selection("needs_review", "Checkbox requires a boolean and a current native input.")
            if isinstance(value, bool) and target.is_current() and target.node.evaluate("el => el.matches('input[type=checkbox]')"):
                try:
                    target.node.set_checked(value, timeout=2000)
                    if target.node.is_checked() == value:
                        selection = Selection("matched", str(value))
                except BrowserError:
                    pass
        else:
            fill = select_dropdown if is_dropdown(target.field) else _fill_text
            selection = fill(target, str(match["value"]))
        output.append({**match, "status": selection.status, "detail": selection.detail})
    return output
