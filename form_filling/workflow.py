"""Inspect one form step, map supplied facts, then fill and verify every supported field."""

import logging
from threading import Lock
from dataclasses import dataclass
from time import perf_counter

from playwright.sync_api import Page

from open_router.client import request_decision, request_fill_plan

from .execution.apply import apply_matches
from .inspection import FormInspector
from .matching.llm import DEFAULT_LLM_MODEL, build_llm_requests, match_fields_with_llm
from .matching.resolve import (DEFAULT_CONCURRENCY, DEFAULT_MULTI_SELECT_THRESHOLD,
                               DEFAULT_SINGLE_VALUE_MIN_CONFIDENCE, exact_name_matches, match_fields)
from .matching.requests import DEFAULT_TOKEN_BUDGET, Fact, FormRequestBuilder
from .execution.targets import capture_targets

MATCHERS = ("jev", "llm")
logger = logging.getLogger(__name__)


@dataclass
class FormStepResult:
    records: list[dict]
    model_calls: int = 0
    input_tokens: int = 0   # billed, as reported by OpenRouter
    output_tokens: int = 0  # as reported by OpenRouter (free for Jev)
    cost: float = 0.0       # USD, as reported by OpenRouter

    @property
    def decision_calls(self) -> int:
        return self.model_calls


class _Usage:
    """Thread-safe totals taken from each response's usage object."""

    def __init__(self):
        self.lock = Lock()
        self.calls = self.input_tokens = self.output_tokens = 0
        self.cost = 0.0

    def start(self) -> int:
        with self.lock:
            self.calls += 1
            return self.calls

    def record(self, response: dict, input_key: str, output_key: str) -> None:
        usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
        with self.lock:
            self.input_tokens += usage.get(input_key) if isinstance(usage.get(input_key), int) else 0
            self.output_tokens += usage.get(output_key) if isinstance(usage.get(output_key), int) else 0
            self.cost += usage.get("cost") if isinstance(usage.get("cost"), (int, float)) else 0


def run_form_step(
    page: Page,
    facts: list[Fact],
    *,
    matcher: str = "jev",
    llm_model: str = DEFAULT_LLM_MODEL,
    concurrency: int = DEFAULT_CONCURRENCY,
    facts_per_request: int | None = None,
    token_budget: int = DEFAULT_TOKEN_BUDGET,
    multi_select_threshold: float = DEFAULT_MULTI_SELECT_THRESHOLD,
    single_value_min_confidence: float = DEFAULT_SINGLE_VALUE_MIN_CONFIDENCE,
) -> FormStepResult:
    """Run the whole pipeline on the current step. It never submits the form."""
    if matcher not in MATCHERS:
        raise ValueError(f"matcher must be one of {', '.join(MATCHERS)}.")
    usage = _Usage()

    def send_decision(payload: dict) -> dict:
        number = usage.start()
        logger.info("Jev request %d sent (%d questions)...", number, len(payload["questions"]))
        started = perf_counter()
        response = request_decision(payload)
        usage.record(response, "input_tokens", "output_tokens")
        logger.info("Jev request %d answered in %.1f s", number, perf_counter() - started)
        return response

    def send_chat(payload: dict) -> dict:
        number = usage.start()
        logger.info("%s request %d sent...", llm_model, number)
        started = perf_counter()
        response = request_fill_plan(payload)
        usage.record(response, "prompt_tokens", "completion_tokens")
        logger.info("%s request %d answered in %.1f s", llm_model, number, perf_counter() - started)
        return response

    builder = FormRequestBuilder(token_budget, facts_per_request=facts_per_request)

    def build_requests(documents, resolved_ids):
        if matcher == "llm":
            return build_llm_requests(documents, facts, resolved_ids=resolved_ids, model=llm_model,
                                      max_tokens=token_budget, include_deferred=True)
        return builder.build(documents, facts, resolved_ids=resolved_ids, include_deferred=True)

    def infer(requests):
        if not requests:
            return []
        if matcher == "llm":
            return match_fields_with_llm(requests, facts, max_workers=concurrency, send=send_chat)
        return match_fields(requests, facts, max_tokens=token_budget, max_workers=concurrency,
                            multi_select_threshold=multi_select_threshold,
                            single_value_min_confidence=single_value_min_confidence, send=send_decision)

    def identity(doc, field):
        return (doc.url, field.id, field.html_id, field.name, field.kind, field.form, field.section, field.label)

    # One matching pass covers every field, including those that are disabled until another field is
    # filled. Their values are kept and written once the field unlocks, without asking the model again.
    documents = FormInspector().inspect_when_ready(page)
    fields_by_id = {field.id: (doc, field) for doc in documents for field in doc.fields}
    order = {field_id: index for index, field_id in enumerate(fields_by_id)}
    exact_matches = exact_name_matches(documents, facts, include_deferred=True)
    requests = build_requests(documents, exact_matches)
    deferred = sum(not field.fillable_now and not field.hidden for _, field in fields_by_id.values())
    logger.info("Inspected %d fields (%d disabled for now); %d matched by exact name; %d %s requests to send, %d at a time",
                len(fields_by_id), deferred, len(exact_matches), len(requests), matcher, concurrency)

    # Bind the inspected elements before inference so rerenders cannot redirect writes.
    with capture_targets(page, documents) as targets:
        ready, pending, records = [], {}, []
        for record in [*exact_matches.values(), *infer(requests)]:
            doc, field = fields_by_id[record["field_id"]]
            if field.fillable_now:
                ready.append(record)
            elif record["status"] == "proposed":
                pending.setdefault(identity(doc, field), []).append(record)
            else:
                records.append(record)
        logger.info("Matching done; writing %d values now, %d waiting for fields to unlock",
                    sum(r["status"] == "proposed" for r in ready), sum(len(rows) for rows in pending.values()))
        applied = apply_matches(ready, targets)
        records.extend(applied)

    processed = {field_id for field_id, (_, field) in fields_by_id.items() if field.fillable_now}
    while pending and any(row["status"] == "matched" for row in applied):
        documents = FormInspector().inspect(page)
        ready = []
        for doc in documents:
            for field in doc.fields:
                key = identity(doc, field)
                if field.fillable_now and field.id not in processed and key in pending:
                    processed.add(field.id)
                    ready.extend({**row, "field_id": field.id} for row in pending.pop(key))
        if not ready:
            break
        logger.info("%d field(s) unlocked; writing their values", len(ready))
        with capture_targets(page, documents) as targets:
            applied = apply_matches(ready, targets)
            records.extend(applied)
    for rows in pending.values():
        records.extend({**row, "status": "skipped", "detail": "The field never became editable; nothing written."}
                       for row in rows)
    records.sort(key=lambda record: order.get(record["field_id"], len(order)))
    return FormStepResult(records, usage.calls, usage.input_tokens, usage.output_tokens, usage.cost)
