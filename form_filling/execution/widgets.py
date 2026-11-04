"""Bounded discovery for custom widgets exposing ARIA options."""

from functools import cache
from pathlib import Path
from time import monotonic, sleep

from playwright.sync_api import ElementHandle

from .selection import Selection, normalized


@cache
def _menu_script() -> str:
    return Path(__file__).with_name("widget_menu.js").read_text(encoding="utf-8")


def select_custom_option(field: ElementHandle, value: str) -> Selection:
    menu = _menu_script()
    if not field.evaluate(menu, "open") and field.get_attribute("role") != "listbox":
        field.evaluate("el => el.scrollIntoView({block:'center', behavior:'instant'})")
        field.click(timeout=2000)
    search = field.evaluate_handle(menu, "search")
    try:
        if search.as_element() is not None:
            search.as_element().fill(value, timeout=2000)
    finally:
        search.dispose()

    # Keep polling across delayed filtering, lazy loading and recycled DOM rows.
    deadline = monotonic() + 5
    scrolls = 0
    while monotonic() < deadline:
        rows = field.evaluate(menu, "rows")
        hits = [i for i,row in enumerate(rows) if not row["disabled"] and
                normalized(value) in {normalized(row["label"]), normalized(row["value"] or "")}]
        if len(hits) > 1:
            return Selection("needs_review", "Several visible options match.")
        if hits:
            idx = hits[0]
            handle = field.evaluate_handle(menu, {"index": idx})
            try:
                element = handle.as_element()
                if element is None or field.evaluate(menu, "rows") != rows:
                    continue
                label = rows[idx]["label"]
                already_selected = (field.get_attribute("aria-multiselectable") == "true" and
                                    label in field.evaluate(menu, "selected"))
                if not already_selected:
                    focused = field.evaluate_handle("el => el.ownerDocument.activeElement")
                    try:
                        editor = focused.as_element()
                        # A filtered popup can highlight its exact match for keyboard
                        # selection, even when a sticky header covers its mouse target.
                        active_id = editor.get_attribute("aria-activedescendant") if editor else None
                        if editor and active_id and active_id == element.get_attribute("id"):
                            editor.press("Enter", timeout=1500)
                        else:
                            element.click(timeout=1500)
                    finally:
                        focused.dispose()
            finally:
                handle.dispose()
            return _verify_custom(field, label)
        if scrolls < 30 and field.evaluate(menu, "scroll"):
            scrolls += 1
        sleep(0.1)
    return Selection("needs_review", "No unique match in the inspected menu within the search budget.")


def _verify_custom(field: ElementHandle, label: str) -> Selection:
    deadline = monotonic() + 1
    while monotonic() < deadline:
        selected = field.evaluate(_menu_script(), "selected")
        display = field.evaluate("""el => el.isConnected && el.getAttribute('aria-expanded') === 'false'
            && !el.matches('input,textarea') ? el.innerText.trim() : null""")
        if display == label or (display is None and label in selected):
            return Selection("matched", label)
        sleep(0.05)
    return Selection("needs_review", "Option was clicked, but the widget did not expose a confirmed selection.")
