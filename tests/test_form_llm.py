import json
import unittest
from dataclasses import replace

from form_filling.inspection.inventory import DocumentFields, Field
from form_filling.matching.llm import FillPlan, build_llm_requests, estimated_prompt_tokens, match_fields_with_llm
from form_filling.matching.requests import read_facts
from open_router.client import OpenRouterError


def field(number, **overrides):
    seed = Field(id=f"frame1.f{number}", kind="text", label=f"Label {number}", name="", html_id="", placeholder="",
                 form="quote", section="Vehicle", required=False, multiple=False, hidden=False, disabled=False,
                 read_only=False, fillable_now=True, value="PRIVATE", options=(), options_source="none")
    return replace(seed, **overrides)


def doc(*fields):
    return DocumentFields("frame1", "https://example.test", fields)


def reply(assignments):
    content = json.dumps({"assignments": assignments})
    return {"choices": [{"message": {"content": content}}], "usage": {"prompt_tokens": 10, "completion_tokens": 5}}


class LlmMatcherTests(unittest.TestCase):
    facts = read_facts({"vehicle.make": "Toyota", "seats": 5, "newsletter": True,
                        "delivery": ["Email notice", "Paperless inbox"]})

    def test_request_carries_fields_facts_and_strict_schema(self):
        documents = [doc(field(1, label="Make"), field(2, kind="select", multiple=True, label="Delivery"),
                         field(3, kind="password"), field(4, fillable_now=False))]
        [request] = build_llm_requests(documents, self.facts, resolved_ids={"frame1.f1"})
        payload = request["payload"]
        self.assertEqual(set(request["fields"]), {"frame1.f2"})
        self.assertIn("multi-select", request["fields"]["frame1.f2"])
        self.assertEqual(payload["model"], "openai/gpt-6-luna")
        self.assertEqual(payload["usage"], {"include": True})
        self.assertTrue(payload["response_format"]["json_schema"]["strict"])
        self.assertEqual(payload["response_format"]["json_schema"]["schema"], FillPlan.model_json_schema())
        user = json.loads(payload["messages"][1]["content"])
        self.assertEqual(user["fields"], request["fields"])
        self.assertEqual(user["facts"][1], {"name": "seats", "value": 5})
        self.assertIn("EXACTLY", payload["messages"][0]["content"])
        self.assertNotIn("PRIVATE", json.dumps(payload))

    def test_fields_split_to_fit_the_budget_but_facts_never_do(self):
        documents = [doc(*(field(i) for i in range(1, 9)))]
        [single] = build_llm_requests([doc(field(1))], self.facts)
        one_field = estimated_prompt_tokens(single["payload"])
        requests = build_llm_requests(documents, self.facts, max_tokens=one_field + 40)
        self.assertGreater(len(requests), 1)
        self.assertCountEqual([f for r in requests for f in r["fields"]], [f"frame1.f{i}" for i in range(1, 9)])
        for request in requests:
            self.assertLessEqual(estimated_prompt_tokens(request["payload"]), one_field + 40)
            self.assertEqual(len(json.loads(request["payload"]["messages"][1]["content"])["facts"]), 5)
        with self.assertRaises(ValueError):
            build_llm_requests([doc(field(1))], self.facts, max_tokens=one_field - 1)

    def test_exact_values_become_proposals_and_everything_else_is_reported(self):
        documents = [doc(field(1, label="Make"), field(2, label="Seats"), field(3, label="News"),
                         field(4, kind="select", multiple=True, label="Delivery"), field(5, label="Confirm make"),
                         field(6, label="Untouched"), field(7, label="Loose copy"), field(8, label="Two values"))]
        requests = build_llm_requests(documents, self.facts)
        answer = reply([
            {"field_id": "frame1.f1", "values": ["Toyota"]},
            {"field_id": "frame1.f2", "values": ["5"]},
            {"field_id": "frame1.f3", "values": [True]},
            {"field_id": "frame1.f4", "values": ["Paperless inbox", "Email notice", "Email notice"]},
            {"field_id": "frame1.f5", "values": ["Toyota"]},
            {"field_id": "frame1.f7", "values": ["toyota"]},
            {"field_id": "frame1.f8", "values": ["Toyota", "Email notice"]},
            {"field_id": "frame1.f99", "values": ["Toyota"]},
        ])
        with self.assertLogs("form_filling.matching.llm", level="WARNING"):
            records = match_fields_with_llm(requests, self.facts, send=lambda payload: answer)
        by_field = {}
        for record in records:
            by_field.setdefault(record["field_id"], []).append(record)
        self.assertEqual([(r["status"], r["fact"], r["value"]) for r in by_field["frame1.f1"]],
                         [("proposed", "vehicle.make", "Toyota")])
        self.assertEqual(by_field["frame1.f2"][0]["value"], 5)
        self.assertEqual(by_field["frame1.f3"][0]["value"], True)
        self.assertEqual([r["value"] for r in by_field["frame1.f4"]], ["Paperless inbox", "Email notice"])
        self.assertEqual(by_field["frame1.f5"][0]["status"], "proposed")
        self.assertEqual(by_field["frame1.f6"][0]["status"], "unmatched")
        self.assertEqual(by_field["frame1.f7"][0]["status"], "needs_review")
        self.assertEqual(by_field["frame1.f8"][0]["status"], "needs_review")
        self.assertNotIn("frame1.f99", by_field)
        self.assertTrue(all(r["match_method"] == "llm" for r in records))

    def test_invalid_plans_are_rejected(self):
        requests = build_llm_requests([doc(field(1))], self.facts)
        for content in ('{"assignments": [{"field_id": "frame1.f1"}]}', '{"plan": []}', "not json",
                        '{"assignments": [{"field_id": "frame1.f1", "values": [null]}]}'):
            with self.subTest(content=content), self.assertRaises(OpenRouterError):
                match_fields_with_llm(requests, self.facts,
                                      send=lambda payload: {"choices": [{"message": {"content": content}}]})
        with self.assertRaises(ValueError):
            match_fields_with_llm(requests, self.facts, max_workers=0, send=lambda payload: {})
