"""Execute one verified click without looking up a replacement by name or ordinal."""

from dataclasses import dataclass
from enum import StrEnum
from time import monotonic, sleep

from playwright.sync_api import Error as BrowserError

from .press_options import press_options
from .snapshot import PageSnapshot, read_page
from .targets import CapturedPage


class ClickStatus(StrEnum):
    STALE = "stale"
    BLOCKED = "blocked"
    UNCONFIRMED = "unconfirmed"
    NAVIGATED = "navigated"
    CHANGED = "changed"
    NO_CHANGE = "no_change"


@dataclass(frozen=True, slots=True)
class ClickResult:
    status: ClickStatus
    outcome: str
    after: PageSnapshot | None = None


def _verify_and_click(capture: CapturedPage, target_id: str, timeout_ms: int) -> ClickResult | None:
    still_current = "(capture, id) => capture.resolve(id) !== null"
    stale = ClickResult(ClickStatus.STALE, "Target changed or disappeared; take a fresh snapshot.")
    try:
        handle = capture.targets.evaluate_handle("(capture, id) => capture.resolve(id)", target_id)
    except BrowserError:
        return stale  # The captured document may have navigated.
    try:
        element = handle.as_element()
        if element is None:
            return stale
        try:
            element.click(trial=True, timeout=timeout_ms)
        except BrowserError:
            if not capture.targets.evaluate(still_current, target_id):
                return stale
            return ClickResult(ClickStatus.BLOCKED, "Target did not pass Playwright's click checks.")
        # Scrolling into view can rerender a virtual list. Recheck after the trial.
        if not capture.targets.evaluate(still_current, target_id):
            return stale
        try:
            element.click(timeout=timeout_ms)
        except BrowserError:
            # Input may already have been dispatched. Never replay it automatically.
            return ClickResult(ClickStatus.UNCONFIRMED, "Click completion could not be confirmed.")
        return None
    except BrowserError:
        return stale
    finally:
        handle.dispose()


def _observe_click(capture: CapturedPage, observe_ms: int) -> ClickResult:
    deadline = monotonic() + observe_ms / 1000
    while True:
        try:
            after = read_page(capture.page)
        except BrowserError:
            after = None  # Navigation can replace the execution context while reading.
        if after is not None:
            if after.url != capture.snapshot.url:
                return ClickResult(ClickStatus.NAVIGATED, f"Navigated to {after.url}.", after)
            if after != capture.snapshot:
                return ClickResult(ClickStatus.CHANGED, f"Observed a page change at {after.url}.", after)
        remaining = deadline - monotonic()
        if remaining <= 0:
            if after is None:
                return ClickResult(ClickStatus.UNCONFIRMED, "Clicked; could not observe the resulting page.")
            return ClickResult(ClickStatus.NO_CHANGE, "Clicked; no page change observed within the observation window.", after)
        sleep(min(0.05, remaining))


def click_selected(capture: CapturedPage, target_id: str, *, timeout_ms: int = 2000,
                   observe_ms: int = 750) -> ClickResult:
    """Verify the snapshot-local ID, click its original element, then observe the result."""
    if timeout_ms <= 0 or observe_ms < 0:
        raise ValueError("Click timeout must be positive; observation window cannot be negative.")
    if target_id not in press_options(capture.snapshot):
        raise ValueError("The selected ID was not a press option in this snapshot.")
    failure = _verify_and_click(capture, target_id, timeout_ms)
    if failure is not None:
        return failure
    return _observe_click(capture, observe_ms)
