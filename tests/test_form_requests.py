import json
import unittest

import tiktoken
from threading import Barrier, Lock
from dataclasses import replace

from form_filling.inspection.inventory import DocumentFields, Field
from form_filling.matching.resolve import exact_name_matches, match_fields
from form_filling.matching.requests import (CHOICE_OPTION_TOKENS, FormRequestBuilder, NO_MATCH, read_facts,
                                            estimated_input_tokens)
from open_router.client import OpenRouterError


def field(number, section="Vehicle", **overrides):
    seed = Field(id=f"frame1.f{number}", kind="text", label="Year", name="year", html_id="year",
                 placeholder="", form="quote", section=section, required=True, multiple=False,
                 hidden=False, disabled=False, read_only=False, fillable_now=True,
                 value="EXISTING_PRIVATE_VALUE", options=(), options_source="none")
    return replace(seed, **overrides)


def doc(*fields):
    return DocumentFields("frame1", "https://example.test", fields)


def picked(choice, confidence=0.9):
    return {"choice": choice, "confidence": confidence}


class RequestTests(unittest.TestCase):
    def test_exact_name_requires_unique_field_and_unique_fact(self):
        fields = [field(1, name="asset_001_serial"), field(2, name="year"),
                  field(3, name="year"), field(4, name="hobby"), field(5, name="confirm_serial")]
        facts = read_facts({"asset_001_serial": "S1", "year": 2025, "hobby": ["reading", "skiing"]})
        exact = exact_name_matches([doc(*fields)], facts)
        self.assertEqual(list(exact), ["frame1.f1"])
        self.assertEqual(exact["frame1.f1"]["value"], "S1")
        requests = FormRequestBuilder().build([doc(*fields)], facts, resolved_ids=exact)
        questions = requests[0]["questions"]
        self.assertEqual(set(questions), {f.id for f in fields[1:]})
        self.assertIn(facts[0].id, questions["frame1.f5"]["criteria"])

    def test_fact_batches_preserve_all_options_for_each_field(self):
        for count, expected in [(254, [254]), (255, [128, 127]), (509, [170, 170, 169])]:
            facts = read_facts({f"key{i}": i for i in range(count)})
            requests = FormRequestBuilder().build([doc(field(1), field(2))], facts)
            for target in ["frame1.f1", "frame1.f2"]:
                groups = [r["questions"][target]["criteria"] for r in requests if target in r["questions"]]
                self.assertEqual([len(group)-1 for group in groups], expected)
                self.assertCountEqual([key for group in groups for key in group if key != NO_MATCH],
                                      [fact.id for fact in facts])

    def test_size_budget_and_private_fields(self):
        fields = [field(i) for i in range(30)]
        facts = read_facts({"x": 42, "y": 12})
        requests = FormRequestBuilder(2500).build([doc(*fields, field(30, kind="password"))], facts)
        self.assertGreater(len(requests), 1)
        self.assertLess(len(requests), len(fields))
        for r in requests:
            self.assertEqual(set(r["state"]["fields"]), set(r["questions"]))
            self.assertLessEqual(estimated_input_tokens(r), 2500)
            self.assertNotIn("EXISTING_PRIVATE_VALUE", json.dumps(r))
        self.assertCountEqual([key for r in requests for key in r["questions"]], [f.id for f in fields])

    def test_estimate_adds_overhead_for_each_choice_option(self):
        facts = read_facts({f"key{i}": i for i in range(9)})
        single, multi = FormRequestBuilder().build([doc(field(1), field(2), field(3, kind="select", multiple=True))], facts)
        encoder = tiktoken.get_encoding("cl100k_base")
        base = lambda request: len(encoder.encode_ordinary(json.dumps(request, ensure_ascii=True)))
        self.assertEqual(estimated_input_tokens(single) - base(single), CHOICE_OPTION_TOKENS * 2 * 10)
        self.assertEqual(estimated_input_tokens(multi), base(multi))

    def test_reuse_competing_groups_and_unused_field(self):
        facts = read_facts({"contact.email": "alex@example.com", "work.email": "work@example.com"})
        requests = FormRequestBuilder(facts_per_request=1).build([doc(field(1), field(2), field(3))], facts)
        both_started = Barrier(2)
        def decide(req):
            if len(next(iter(req["questions"].values()))["criteria"]) == 2:
                both_started.wait(timeout=3)
            return {"answers": {key: picked(NO_MATCH if key == "frame1.f3" else next(iter(q["criteria"])))
                                for key, q in req["questions"].items()}}
        results = match_fields(requests, facts, send=decide)
        self.assertEqual([r["value"] for r in results], ["alex@example.com", "alex@example.com", None])

    def test_concurrency_limit(self):
        facts = read_facts({"a": "1", "b": "2", "c": "3"})
        requests = FormRequestBuilder(facts_per_request=1).build([doc(field(1))], facts)
        self.assertEqual(len(requests), 3)
        for workers in (1, 3):
            active = peak = 0
            lock = Lock()
            all_started = Barrier(workers)
            def decide(req):
                nonlocal active, peak
                with lock:
                    active += 1
                    peak = max(peak, active)
                all_started.wait(timeout=3)
                with lock:
                    active -= 1
                return {"answers": {key: picked(NO_MATCH) for key in req["questions"]}}
            match_fields(requests, facts, max_workers=workers, send=decide)
            self.assertEqual(peak, workers)
        with self.assertRaises(ValueError):
            match_fields(requests, facts, max_workers=0, send=decide)

    def test_multi_select_asks_one_noul_per_fact_and_applies_threshold(self):
        facts = read_facts({"hobbies": ["skiing", "reading"], "city": "Rome"})
        requests = FormRequestBuilder().build([doc(field(1, kind="select", multiple=True))], facts)
        self.assertEqual(len(requests), 1)
        state, questions = requests[0]["state"], requests[0]["questions"]
        self.assertEqual(set(questions), {"frame1.f1:q1", "frame1.f1:q2", "frame1.f1:q3"})
        self.assertTrue(all(q["type"] == "noul" and "criteria" not in q for q in questions.values()))
        self.assertEqual(state["fact_q1"], 'hobbies = "skiing"')
        self.assertEqual(json.dumps(requests[0]).count("skiing"), 1)
        yes = {"q1": 0.97, "q2": 0.7, "q3": 0.05}
        def decide(req):
            return {"answers": {key: {"noul": yes[key.partition(":")[2]]} for key in req["questions"]}}
        result = match_fields(requests, facts, send=decide)
        self.assertEqual([(r["value"], r["confidence"]) for r in result], [("skiing", 0.97)])
        result = match_fields(requests, facts, multi_select_threshold=0.6, send=decide)
        self.assertEqual([r["value"] for r in result], ["skiing", "reading"])
        result = match_fields(requests, facts, multi_select_threshold=0.99, send=decide)
        self.assertEqual([r["status"] for r in result], ["unmatched"])

    def test_single_value_minimum_confidence(self):
        facts = read_facts({"year": 2025, "other": 1999})
        requests = FormRequestBuilder().build([doc(field(1))], facts)
        def decide(confidence):
            return lambda req: {"answers": {key: picked("q1", confidence) for key in req["questions"]}}
        [sure] = match_fields(requests, facts, send=decide(0.9))
        self.assertEqual((sure["status"], sure["value"], sure["confidence"]), ("proposed", 2025, 0.9))
        [unsure] = match_fields(requests, facts, send=decide(0.4))
        self.assertEqual((unsure["status"], unsure["value"]), ("needs_review", 2025))
        self.assertIn("0.40", unsure["detail"])
        [allowed] = match_fields(requests, facts, single_value_min_confidence=0, send=decide(0.4))
        self.assertEqual(allowed["status"], "proposed")
        fallback = lambda req: {"answers": {key: {"choice": "q1", "probabilities": {"q1": 0.3}}
                                            for key in req["questions"]}}
        self.assertEqual(match_fields(requests, facts, send=fallback)[0]["status"], "needs_review")

    def test_invalid_answers_and_unfit_values(self):
        facts = read_facts({"note": "x"*2000})
        with self.assertRaises(ValueError):
            FormRequestBuilder(150).build([doc(field(1))], facts)
        requests = FormRequestBuilder().build([doc(field(1))], facts)
        with self.assertRaises(OpenRouterError):
            match_fields(requests, facts, send=lambda req: {"answers": {}})
        for answer in ({"choice": "q1"}, {"choice": "q1", "confidence": 1.5}, {"choice": "q9", "confidence": 1}):
            with self.subTest(answer=answer), self.assertRaises(OpenRouterError):
                match_fields(requests, facts, send=lambda req: {"answers": {k: answer for k in req["questions"]}})
        multi = FormRequestBuilder().build([doc(field(2, kind="select", multiple=True))], facts)
        with self.assertRaises(OpenRouterError):
            match_fields(multi, facts, send=lambda req: {"answers": {k: {"noul": "yes"} for k in req["questions"]}})
        with self.assertRaises(ValueError):
            match_fields(requests, facts, multi_select_threshold=2, send=lambda req: {})
