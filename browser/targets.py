"""Retain exact DOM targets only while a decision is being made and executed."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from playwright.sync_api import JSHandle, Page

from .snapshot import PageSnapshot, parse_snapshot, snapshot_script


@dataclass(frozen=True, slots=True)
class CapturedPage:
    page: Page
    snapshot: PageSnapshot
    targets: JSHandle


@contextmanager
def capture_page(page: Page) -> Iterator[CapturedPage]:
    handle = page.evaluate_handle(snapshot_script(), True)
    try:
        snapshot = parse_snapshot(handle.evaluate("capture => capture.snapshot"))
        yield CapturedPage(page, snapshot, handle)
    finally:
        handle.dispose()
