"""Browser-level checks of the path from a snapshot-local choice to an observed outcome."""

import os
import unittest
from unittest.mock import patch

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from finder.memory import Observation, RunMemory
from browser.click import ClickStatus, click_selected
from browser.evidence import read_evidence
from browser.targets import capture_page


ROWS = """
<table>
<tr><td>North</td><td><button onclick="this.closest('tr').cells[0].textContent='North chosen'">Choose</button></td></tr>
<tr><td>South</td><td><button onclick="this.closest('tr').cells[0].textContent='South chosen'">Choose</button></td></tr>
</table>
"""


class VerifiedClickTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_dotenv()
        cls.pw = sync_playwright().start()
        cls.addClassCleanup(cls.pw.stop)
        cls.browser = cls.pw.chromium.launch(channel=os.getenv("PLAYWRIGHT_CHANNEL") or None)
        cls.addClassCleanup(cls.browser.close)

    def setUp(self):
        self.page = self.browser.new_page()
        self.addCleanup(self.page.close)
        self.page.set_content(ROWS)

    @patch("finder.memory.run.choose_browser_action", return_value="c2")
    def test_duplicate_labels_click_only_selected_row_and_record_outcome(self, _classify):
        with capture_page(self.page) as capture:
            run = RunMemory("Choose South", Observation(capture.snapshot, read_evidence(self.page)))
            result = click_selected(capture, run.choose())
        self.assertEqual(result.status, ClickStatus.CHANGED)
        self.assertEqual(self.page.locator("td:first-child").all_text_contents(), ["North", "South chosen"])
        run.record_outcome(result.outcome, next_observation=Observation(result.after, read_evidence(self.page)))
        self.assertEqual(run.steps[0].outcome, result.outcome)
        self.assertEqual(run.snapshots[-1].page, result.after)

    def test_replaced_target_requires_fresh_decision(self):
        with capture_page(self.page) as capture:
            self.page.locator("button").last.evaluate("el => el.replaceWith(el.cloneNode(true))")
            result = click_selected(capture, "c2")
        self.assertEqual(result.status, ClickStatus.STALE)
        self.assertEqual(self.page.locator("td:first-child").all_text_contents(), ["North", "South"])

    def test_repurposed_row_requires_fresh_decision(self):
        with capture_page(self.page) as capture:
            self.page.locator("td:first-child").last.evaluate("el => el.textContent = 'East'")
            result = click_selected(capture, "c2")
        self.assertEqual(result.status, ClickStatus.STALE)
        self.assertEqual(self.page.locator("td:first-child").last.inner_text(), "East")

    def test_navigation(self):
        self.page.route("https://example.test/**", lambda route: route.fulfill(
            content_type="text/html", body='<a href="/next">Continue</a>'))
        self.page.goto("https://example.test/start")
        with capture_page(self.page) as capture:
            result = click_selected(capture, "c1")
        self.assertEqual(result.status, ClickStatus.NAVIGATED)
        self.assertEqual(result.after.url, "https://example.test/next")

    def test_overlay_blocks_input(self):
        self.page.evaluate("""() => {
            const cover = document.createElement('div');
            cover.style = 'position:fixed; inset:0; z-index:100';
            document.body.append(cover);
        }""")
        with capture_page(self.page) as capture:
            result = click_selected(capture, "c2", timeout_ms=250)
        self.assertEqual(result.status, ClickStatus.BLOCKED)
        self.assertEqual(self.page.locator("td:first-child").all_text_contents(), ["North", "South"])

    def test_no_visible_effect(self):
        self.page.set_content("<button>OK</button>")
        with capture_page(self.page) as capture:
            result = click_selected(capture, "c1", observe_ms=100)
        self.assertEqual(result.status, ClickStatus.NO_CHANGE)
