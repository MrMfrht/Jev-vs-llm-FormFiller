"""Applicable native form and document-scroll actions for one captured page."""

from dataclasses import dataclass

from playwright.sync_api import Error as BrowserError

from .click import ClickResult, ClickStatus
from .snapshot import PageSnapshot
from .targets import CapturedPage


@dataclass(frozen=True)
class Action:
    kind: str
    label: str
    target: str = ""
    option_index: int = -1
    value: str = ""


def available_actions(page: PageSnapshot, fill_values: tuple[str, ...]) -> dict[str, Action]:
    actions = {}
    for control in page.controls:
        if control.disabled:
            continue
        for option in control.options:
            if option.disabled or (option.selected and not control.multiple):
                continue
            verb = "Deselect" if option.selected else "Select"
            label = f"{verb} {option.label!r} in {control.name or control.id}"
            actions[f"select_{control.id}_{option.index}"] = Action("select", label, control.id, option.index)
        if control.editable:
            for index, value in enumerate(fill_values):
                label = f"Fill {control.name or control.id} with {value!r}"
                actions[f"fill_{control.id}_{index}"] = Action("fill", label, control.id, value=value)
    if page.scroll_y > 0:
        actions["scroll_up"] = Action("scroll", "Scroll the document up one viewport.", value="up")
    if page.scroll_y < page.scroll_max:
        actions["scroll_down"] = Action("scroll", "Scroll the document down one viewport to reveal more content.", value="down")
    return actions


def execute_action(capture: CapturedPage, action: Action) -> ClickResult:
    page = capture.page
    stale = ClickResult(ClickStatus.STALE, "Target or document changed; take a fresh observation.")
    try:
        if action.kind == "scroll":
            y = capture.targets.evaluate("""(capture, direction) => {
                if (location.href !== capture.snapshot.url || Math.round(scrollY) !== capture.snapshot.scroll_y) return null;
                window.scrollBy({top: (direction === 'down' ? 1 : -1) * innerHeight, behavior:'instant'});
                return Math.round(scrollY);
            }""", action.value)
            if y is None:
                return stale
            status = ClickStatus.CHANGED if y != capture.snapshot.scroll_y else ClickStatus.NO_CHANGE
            return ClickResult(status, f"Document scroll position: {y}px.")
        if action.kind == "select":
            # Verify the captured option's identity before changing it, including
            # duplicate labels or values. Multi-select keeps other selections.
            selected = capture.targets.evaluate("""(capture, [id, index]) => {
                const option = capture.resolveOption(id, index);
                if (!option) return false;
                const field = capture.resolve(id);
                option.selected = field.multiple ? !option.selected : true;
                field.dispatchEvent(new Event('input', {bubbles:true}));
                field.dispatchEvent(new Event('change', {bubbles:true}));
                return true;
            }""", [action.target, action.option_index])
            return ClickResult(ClickStatus.CHANGED, action.label) if selected else stale
        handle = capture.targets.evaluate_handle("(capture, id) => capture.resolve(id)", action.target)
        try:
            element = handle.as_element()
            if element is None:
                return stale
            element.fill(action.value, timeout=2000)
            return ClickResult(ClickStatus.CHANGED, action.label)
        finally:
            handle.dispose()
    except BrowserError:
        return ClickResult(ClickStatus.UNCONFIRMED, f"Could not confirm {action.kind}; no automatic retry.")
