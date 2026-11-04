import json
import unittest
from unittest.mock import patch

from finder.memory import Observation, RunMemory, RunStatus
from browser.evidence import EvidenceBlock, EvidenceSnapshot
from browser.snapshot import Control, PageSnapshot


def observation(id_, name, html, action, blocks=()):
    url = f"https://example.test/{name}"
    page = PageSnapshot(url, name, html, (Control("c1", "button", action, False, None),))
    return Observation(page, EvidenceSnapshot(id_, url, tuple(blocks)))


class RunMemoryTest(unittest.TestCase):
    def setUp(self):
        self.block = EvidenceBlock("b1", "text", "17:30", ("Train 82", "Departure"))
        self.first = observation("s1", "schedule", "OLD PAGE ONLY", "Continue", [self.block])
        self.second = observation("s2", "platforms", "CURRENT PAGE", "Check platform",
                                  [EvidenceBlock("b1", "text", "Platform 4", ())])
        self.goal = "  Find the departure and platform for Train 82.  "
        self.run = RunMemory(self.goal, self.first, result_schema={"required": ["departure", "platform"]})

    @patch("open_router.jev.classifier.request_decision")
    def test_next_request_carries_prior_evidence(self, transport):
        transport.return_value = {"answers": {"classification": {"choice": "c1"}}}
        self.run.choose()
        self.run.record_outcome("Opened platforms page.", next_observation=self.second, remember_ids=["b1"])
        self.run.choose()
        payload = transport.call_args.args[0]
        context = json.loads(payload["state"])
        self.assertEqual(context["goal"], self.goal)
        self.assertEqual(context["recent_actions"], [
            {"snapshot_id": "s1", "action": "button: Continue", "outcome": "Opened platforms page."}
        ])
        self.assertEqual(context["remembered_blocks"], [
            {"snapshot_id": "s1", "url": self.first.page.url, "id": "b1", "kind": "text",
             "text": "17:30", "context": ["Train 82", "Departure"]}
        ])
        self.assertEqual(context["result_schema"]["required"], ["departure", "platform"])
        self.assertEqual(context["current_page"]["html"], "CURRENT PAGE")
        self.assertNotIn("OLD PAGE ONLY", payload["state"])
        self.assertEqual(payload["questions"]["classification"]["criteria"], {"c1": "button: Check platform"})
        self.assertEqual(self.run.snapshots, (self.first, self.second))
        self.assertEqual(self.run.steps[0].next_snapshot_id, "s2")
        self.assertIsNone(self.run.steps[1].outcome)

    @patch("finder.memory.run.choose_browser_action", return_value="c1")
    def test_failed_action_can_be_recorded_without_navigation(self, classify):
        self.run.choose()
        with self.assertRaises(ValueError):
            self.run.choose()
        with self.assertRaises(ValueError):
            self.run.record_outcome("Click failed", remember_ids=["unknown"])
        self.assertIsNone(self.run.steps[0].outcome)
        self.run.record_outcome("Click failed: dialog covered target.")
        self.run.finish(RunStatus.BLOCKED)
        self.assertEqual(self.run.status, RunStatus.BLOCKED)
        with self.assertRaises(ValueError):
            self.run.choose()
        classify.assert_called_once()

    @patch("finder.memory.run.choose_browser_action", return_value="c1")
    def test_evidence_outlives_recent_action_window(self, classify):
        self.run.choose()
        self.run.record_outcome("Moved.", next_observation=self.second, remember_ids=["b1"])
        for i in range(20):
            self.run.choose()
            self.run.record_outcome(f"Attempt {i} failed.")
        self.run.choose()
        context = json.loads(classify.call_args.args[0])
        self.assertEqual(len(context["recent_actions"]), 20)
        self.assertEqual(context["recent_actions"][0]["outcome"], "Attempt 0 failed.")
        self.assertEqual(context["remembered_blocks"][0]["text"], "17:30")
        self.assertEqual(len(self.run.steps), 22)
