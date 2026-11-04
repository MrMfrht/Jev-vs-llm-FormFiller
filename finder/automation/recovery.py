"""Read-only recovery and snapshot-local alternatives to a stale browser target."""

from contextlib import ExitStack
from time import monotonic, sleep

from playwright.sync_api import Error as BrowserError, Page

from finder.memory import Observation
from browser.snapshot import Control, PageSnapshot, read_page

from .observation import observe
from .trace import RunTrace


def matching_controls(control: Control, page: PageSnapshot) -> set[str]:
    """Match the same link destination, or role and label for non-links."""
    return {
        candidate.id for candidate in page.controls
        if candidate.role == control.role and (
            candidate.href == control.href if control.href else candidate.name == control.name
        )
    }


def reconcile(page: Page, resources: ExitStack, trace: RunTrace, step: int, before: Observation):
    """Wait briefly for a document or visible state transition, without sending browser input."""
    deadline = monotonic() + 4
    while True:
        try:
            latest = read_page(page)
            if latest != before.page or monotonic() >= deadline:
                capture, observed = observe(page, resources, trace, step)
                break
        except BrowserError:
            if page.is_closed() or monotonic() >= deadline:
                raise
        sleep(0.1)
    if observed.page.url != before.page.url:
        outcome = f"After uncertain input, observed navigation to {observed.page.url}."
    elif observed.page != before.page:
        outcome = "After uncertain input, observed a changed page; verify the requested effect."
    else:
        outcome = "Input not confirmed; the page appears unchanged. Do not repeat this action."
    trace.write(step, "recover", "output", {"snapshot_id": observed.id, "outcome": outcome})
    return capture, observed, outcome
