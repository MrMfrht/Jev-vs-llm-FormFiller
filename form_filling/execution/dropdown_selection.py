"""Resolve supplied values exactly and verify the resulting selection."""

from playwright.sync_api import ElementHandle, Error as BrowserError

from .targets import FieldTarget
from .selection import Selection, normalized
from .widgets import select_custom_option


def _select_native_option(node: ElementHandle, value: str) -> Selection:
    state = node.evaluate("""el => ({multiple:el.multiple, options:Array.from(el.options, o => ({
        value:o.value, label:o.label, disabled:o.matches(':disabled') || !!o.closest('[hidden],[inert],[aria-disabled=true]'),
        selected:o.selected
    }))})""")
    options = state["options"]
    hits = [i for i, o in enumerate(options) if normalized(value) in (normalized(o["value"]), normalized(o["label"])) and not o["disabled"]]
    if not hits:
        return Selection("unavailable", "No enabled native option has that label or value.")
    if len(hits) != 1:
        return Selection("needs_review", "Several enabled options match.")
    idx = hits[0]
    keep = [i for i,o in enumerate(options) if state["multiple"] and o["selected"]]
    desired = sorted(set([*keep, idx]))
    if not options[idx]["selected"]:
        # Capture exact nodes to avoid selecting a different row if indices shift.
        handles = []
        try:
            for i in desired:
                opt = node.evaluate_handle("(el,i)=>el.options[i]", i)
                handles.append(opt)
                if not opt.as_element() or not opt.evaluate("(o, expected) => o.value===expected.value && o.label===expected.label", options[i]):
                    return Selection("needs_review", "Options changed during selection.")
            node.select_option(element=[opt.as_element() for opt in handles], timeout=2000)
        finally:
            for opt in handles:
                opt.dispose()
    expected = [(options[i]["value"], options[i]["label"]) for i in desired]
    actual = node.evaluate("el=>el.isConnected ? Array.from(el.selectedOptions,o=>[o.value,o.label]) : null")
    if actual != [list(pair) for pair in expected]:
        return Selection("needs_review", "The selected values did not survive readback.")
    return Selection("matched", options[idx]["label"])


def select_dropdown(target: FieldTarget, value: str) -> Selection:
    try:
        node = target.node
        if not target.is_current() or not node.is_visible():
            return Selection("needs_review", "Field is no longer available.")
        if target.field.kind == "select":
            return _select_native_option(node, value)
        if target.field.options_source == "suggestions":
            values = node.evaluate("""el=>Array.from(el.list?.options || [], o=>({
                label:o.label, value:o.value, disabled:o.matches(':disabled') || !!o.closest('[hidden]')
            }))""")
            hits = [o for o in values if not o["disabled"] and normalized(value) in
                    (normalized(o["label"]), normalized(o["value"]))]
            if len(hits) != 1:
                return Selection("needs_review", "No unique matching suggestion.")
            node.fill(hits[0]["value"], timeout=2000)
            if node.input_value() == hits[0]["value"]:
                return Selection("matched", hits[0]["label"])
            return Selection("needs_review", "Suggestion did not survive readback.")
        return select_custom_option(node, value)
    except BrowserError:
        return Selection("needs_review", "The widget changed or its selection could not be confirmed.")
