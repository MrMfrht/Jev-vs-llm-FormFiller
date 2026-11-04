"""Offer browser Back only within the current Chromium tab's run history."""

from contextlib import contextmanager
from dataclasses import dataclass

from playwright.sync_api import CDPSession, Error as BrowserError, Page

from .click import ClickResult, ClickStatus


@dataclass(frozen=True)
class BackTarget:
    current_id: int
    previous_id: int
    url: str


class RunHistory:
    def __init__(self, page: Page, session: CDPSession):
        self.page = page
        self.session = session
        history = session.send("Page.getNavigationHistory")
        self.outside_run = {
            entry["id"] for index, entry in enumerate(history["entries"])
            if index != history["currentIndex"]
        }

    def back_target(self) -> BackTarget | None:
        history = self.session.send("Page.getNavigationHistory")
        index = history["currentIndex"]
        if index < 1:
            return None
        current, previous = history["entries"][index], history["entries"][index - 1]
        if current["id"] in self.outside_run or previous["id"] in self.outside_run:
            return None
        return BackTarget(current["id"], previous["id"], previous["url"])

    def go_back(self, target: BackTarget) -> ClickResult:
        if target != self.back_target():
            return ClickResult(ClickStatus.STALE, "Tab history changed; take a fresh observation.")
        try:
            # The history index can change before the new document commits.
            with self.page.expect_navigation(wait_until="domcontentloaded", timeout=5000):
                self.session.send("Page.navigateToHistoryEntry", {"entryId": target.previous_id})
            history = self.session.send("Page.getNavigationHistory")
            if history["entries"][history["currentIndex"]]["id"] == target.previous_id:
                return ClickResult(ClickStatus.NAVIGATED, f"Browser Back returned to {self.page.url}.")
        except BrowserError:
            pass
        return ClickResult(ClickStatus.UNCONFIRMED, "Browser Back could not be confirmed.")


@contextmanager
def run_history(page: Page):
    session = page.context.new_cdp_session(page)
    try:
        yield RunHistory(page, session)
    finally:
        session.detach()
