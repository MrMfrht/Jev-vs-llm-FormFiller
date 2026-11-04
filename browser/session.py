"""Browser lifecycle for command-line runs."""

import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager, suppress

from playwright.sync_api import Page, sync_playwright

import settings


@contextmanager
def browser_page(*, watch: bool | None = None, watch_delay_ms: int = 150) -> Iterator[Page]:
    """Launch Chromium. Without an explicit watch, BROWSER_WATCH decides whether it is visible."""
    if watch is None:
        watch = settings.browser_watch()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            channel=os.getenv("PLAYWRIGHT_CHANNEL") or None,
            headless=not watch,
            args=["--window-size=960,720"] if watch else [],
            slow_mo=watch_delay_ms if watch else 0,
        )
        try:
            page = browser.new_page(no_viewport=watch)
            yield page
            if watch and sys.stdin.isatty() and not page.is_closed():
                with suppress(EOFError):
                    input("Run finished. Press Enter to close the browser. ")
        finally:
            browser.close()
