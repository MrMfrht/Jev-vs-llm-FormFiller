import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from finder.automation.runner import run_task
from examples.finder.plan_lookup import GOAL, open_fixture, verified
from browser.history import run_history
from browser.click import ClickResult, ClickStatus, click_selected


class RunnerTest(unittest.TestCase):
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
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.log = Path(tmp.name) / "run.jsonl"
        open_fixture(self.page)

    @patch("finder.automation.retention.should_remember")
    @patch("finder.memory.run.choose_browser_action", side_effect=["c1", "c2", "done"])
    def test_full_run(self, classify, remember):
        remember.side_effect = lambda prompt, blocks: {k: "$19" in v for k,v in blocks.items()}
        result = run_task(self.page, GOAL, self.log, verify_done=verified)
        self.assertEqual(result.memory.status, "completed")
        records = [json.loads(line) for line in self.log.read_text().splitlines()]
        self.assertTrue(all(any(r["stage"] == stage and r["phase"] == phase for r in records)
                            for stage in ("observe","decide","click","remember","verify","run")
                            for phase in ("input","output")))
        context = json.loads(classify.call_args_list[1].args[0])
        self.assertIn("Harbor: $19 per month", [b["text"] for b in context["remembered_blocks"]])
        self.assertNotIn("$19", context["current_page"]["html"])
        self.assertEqual(result.memory.steps[-1].selected_id, "done")

    @patch("finder.automation.retention.should_remember", return_value={})
    @patch("finder.memory.run.choose_browser_action", side_effect=["done", "blocked"])
    def test_premature_done_is_reconsidered(self, choose, _):
        result = run_task(self.page, GOAL, self.log, verify_done=verified)
        self.assertEqual(result.memory.status, "blocked")
        self.assertEqual(self.page.url, "https://plans.test/prices")
        self.assertNotIn("done", choose.call_args.args[1])
        self.assertIn("Completion rejected", choose.call_args.args[0])

    @patch("finder.automation.retention.should_remember", return_value={})
    @patch("finder.memory.run.choose_browser_action", side_effect=["c1", "done"])
    def test_uncertain_click_that_navigated_is_not_replayed(self, *_):
        def uncertain(capture, selected):
            click_selected(capture, selected)
            return ClickResult(ClickStatus.UNCONFIRMED, "Timed out after input.")
        with patch("finder.automation.runner.click_selected", side_effect=uncertain) as click:
            result = run_task(self.page, "Open the selection page", self.log,
                              verify_done=lambda cur, _: cur.page.url.endswith("/choose"))
        click.assert_called_once()
        self.assertEqual(result.memory.status, "completed")
        self.assertIn("observed navigation", result.memory.steps[0].outcome)

    @patch("finder.automation.retention.should_remember", return_value={})
    @patch("finder.memory.run.choose_browser_action", side_effect=["c1", "blocked"])
    def test_uncertain_unchanged_link_cannot_be_replayed(self, choose, _):
        with patch("finder.automation.runner.click_selected",
                   return_value=ClickResult(ClickStatus.UNCONFIRMED, "Unknown")) as click:
            result = run_task(self.page, GOAL, self.log)
        click.assert_called_once()
        self.assertNotIn("c1", choose.call_args_list[1].args[1])
        self.assertIn("unchanged", result.memory.steps[0].outcome)
        self.assertEqual(result.memory.status, "blocked")

    @patch("finder.automation.retention.should_remember", return_value={})
    @patch("finder.memory.run.choose_browser_action", side_effect=["c1", "c2", "done"])
    def test_stale_link_is_reselected_by_destination_with_new_id(self, choose, _):
        def replace_link(capture, selected):
            if capture.page.locator("#unrelated").count() == 0:
                capture.page.evaluate("""() => {
                  const a=document.querySelector('a');
                  a.replaceWith(a.cloneNode(true));
                  document.body.insertAdjacentHTML('afterbegin','<button id="unrelated">Other</button>');
                }""")
            return click_selected(capture, selected)
        with patch("finder.automation.runner.click_selected", side_effect=replace_link):
            result = run_task(self.page, "Open the selection page", self.log,
                              verify_done=lambda cur, _: cur.page.url.endswith("/choose"))
        self.assertNotIn("c1", choose.call_args_list[1].args[1])
        self.assertIn("fresh IDs", choose.call_args_list[1].args[0])
        self.assertEqual(result.memory.status, "completed")

    @patch("finder.automation.retention.should_remember", return_value={})
    @patch("finder.memory.run.choose_browser_action", return_value="c1")
    def test_step_budget(self, *_):
        result = run_task(self.page, GOAL, self.log, max_steps=1)
        self.assertEqual(result.memory.status, "stopped")
        self.assertEqual(len(result.memory.steps), 1)

    @patch("finder.memory.run.choose_browser_action", side_effect=["c1", "go_back", "c2", "done"])
    def test_back_tracks_real_history_and_keeps_rejected_price(self, classify):
        pages = {
            "offers": "<a href='/expensive'>Preview A</a><a href='/cheap'>Preview B</a>",
            "expensive": "<p>Offer A costs $120</p>", "cheap": "<p>Offer B costs $60</p>",
        }
        self.page.route("https://offers.test/**", lambda r: r.fulfill(
            content_type="text/html", body=pages[r.request.url.rsplit("/", 1)[1]]))
        self.page.goto("https://offers.test/offers")
        def remember(goal, source, action, outcome, trace, step):
            return [b.id for b in source.evidence.blocks if "$120" in b.text]
        result = run_task(self.page, "Find an offer under $100", self.log, memory_selector=remember,
                          verify_done=lambda current, _: current.page.url.endswith("/cheap"))
        self.assertEqual(result.memory.status, "completed")
        calls = classify.call_args_list
        self.assertNotIn("go_back", calls[0].args[1])  # Do not leave the run for plans.test.
        self.assertIn("go_back", calls[1].args[1])
        self.assertNotIn("go_back", calls[2].args[1])
        ctx = json.loads(calls[2].args[0])
        self.assertEqual(ctx["remembered_blocks"][0]["text"], "Offer A costs $120")
        self.assertIn("Browser Back", ctx["recent_actions"][-1]["outcome"])

    def test_same_url_push_creates_back_option_but_dom_change_does_not(self):
        with run_history(self.page) as history:
            self.page.evaluate("document.body.append('Modal open')")
            self.assertIsNone(history.back_target())
            self.page.evaluate("history.pushState({view: 2}, '')")
            target = history.back_target()
            self.assertIsNotNone(target)
            self.page.evaluate("history.pushState({view: 3}, '')")
            self.assertEqual(history.go_back(target).status, "stale")
            self.assertEqual(history.go_back(history.back_target()).status, "navigated")
            self.assertEqual(self.page.evaluate("history.state.view"), 2)
