"""Browser lifecycle for command-line runs."""

import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager, suppress

from playwright.sync_api import Page, sync_playwright

import settings

VIDEO_SIZE = {"width": 1280, "height": 720}


@contextmanager
def browser_page(*, watch: bool | None = None, watch_delay_ms: int | None = None) -> Iterator[Page]:
    """Launch Chromium. BROWSER_WATCH shows it, BROWSER_SLOW_MO_MS slows it, BROWSER_VIDEO_DIR records it."""
    if watch is None:
        watch = settings.browser_watch()
    if watch_delay_ms is None:
        watch_delay_ms = settings.browser_slow_mo()
    video_dir = settings.browser_video_dir()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            channel=os.getenv("PLAYWRIGHT_CHANNEL") or None,
            headless=not watch,
            args=[f"--window-size={VIDEO_SIZE['width']},{VIDEO_SIZE['height'] + 90}"] if watch else [],
            slow_mo=watch_delay_ms if watch else 0,
        )
        try:
            if video_dir:
                page = browser.new_page(viewport=VIDEO_SIZE, record_video_dir=str(video_dir), record_video_size=VIDEO_SIZE)
                print(f"Recording video to {video_dir}", file=sys.stderr, flush=True)
            else:
                page = browser.new_page(no_viewport=watch)
            yield page
            if watch and sys.stdin.isatty() and not page.is_closed():
                with suppress(EOFError):
                    input("Run finished. Press Enter to close the browser. ")
            if video_dir and not page.is_closed():
                path = page.video.path()
                page.close()
                print(f"Video saved: {path}", file=sys.stderr, flush=True)
        finally:
            browser.close()
