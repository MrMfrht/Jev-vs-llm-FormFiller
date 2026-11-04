"""Inspect one form step, map supplied facts, then fill and verify every supported field."""

from threading import Lock
from dataclasses import dataclass

from playwright.sync_api import Page

from open_router.client import request_decision

from .execution.apply import apply_matches
from .inspection import FormInspector
from .matching.resolve import (DEFAULT_CONCURRENCY, DEFAULT_MULTI_SELECT_THRESHOLD,
                               DEFAULT_SINGLE_VALUE_MIN_CONFIDENCE, exact_name_matches, match_fields)
from .matching.requests import DEFAULT_TOKEN_BUDGET, Fact, FormRequestBuilder
from .execution.targets import capture_targets


@dataclass
class FormStepResult:
    records: list[dict]
    decision_calls: int = 0
    input_tokens: int = 0  # billed, as reported by OpenRouter
    cost: float = 0.0      # USD, as reported by OpenRouter


def run_form_step(
    page: Page,
    facts: list[Fact],
    *,
    concurrency: int = DEFAULT_CONCURRENCY,
    facts_per_request: int | None = None,
    token_budget: int = DEFAULT_TOKEN_BUDGET,
    multi_select_threshold: float = DEFAULT_MULTI_SELECT_THRESHOLD,
    single_value_min_confidence: float = DEFAULT_SINGLE_VALUE_MIN_CONFIDENCE,
) -> FormStepResult:
    """Run the whole pipeline on the current step. It never submits the form."""
    documents = FormInspector().inspect_when_ready(page)
    exact_matches = exact_name_matches(documents, facts)
    builder = FormRequestBuilder(token_budget, facts_per_request=facts_per_request)
    requests = builder.build(documents, facts, resolved_ids=exact_matches)

    count_lock = Lock()
    decision_calls = input_tokens = 0
    cost = 0.0

    def send_decision(payload: dict) -> dict:
        nonlocal decision_calls, input_tokens, cost
        with count_lock:
            decision_calls += 1
        response = request_decision(payload)
        usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
        with count_lock:
            input_tokens += usage.get("input_tokens", 0) if isinstance(usage.get("input_tokens"), int) else 0
            cost += usage.get("cost", 0) if isinstance(usage.get("cost"), (int, float)) else 0
        return response

    def resolve_matches():
        inferred = match_fields(requests, facts, max_tokens=token_budget, max_workers=concurrency,
                                multi_select_threshold=multi_select_threshold,
                                single_value_min_confidence=single_value_min_confidence,
                                send=send_decision) if requests else []
        records = [*exact_matches.values(), *inferred]
        field_ids = (field.id for doc in documents for field in doc.fields)
        order = {field_id: index for index, field_id in enumerate(field_ids)}
        return sorted(records, key=lambda record: order[record["field_id"]])

    # Bind the inspected elements before inference so rerenders cannot redirect writes.
    processed = {field.id for doc in documents for field in doc.fields if field.fillable_now}
    records = []
    while True:
        with capture_targets(page, documents) as targets:
            matches = resolve_matches()
            applied = apply_matches(matches, targets)
            records.extend(applied)
        # Only revisit fields that changed from unavailable to editable on this page.
        def identity(doc, field):
            return (doc.url, field.id, field.html_id, field.name, field.kind, field.form, field.section, field.label)

        inactive = {identity(doc, field) for doc in documents for field in doc.fields
                    if not field.fillable_now and field.kind not in {"password", "file"}}
        if not inactive or not any(row["status"] == "matched" for row in applied):
            break
        documents = FormInspector().inspect(page)
        newly_enabled = {field.id for doc in documents for field in doc.fields
                         if field.fillable_now and identity(doc, field) in inactive and field.id not in processed}
        if not newly_enabled:
            break
        processed.update(newly_enabled)
        exact_matches = {k: v for k, v in exact_name_matches(documents, facts).items() if k in newly_enabled}
        exclude = {field.id for doc in documents for field in doc.fields if field.id not in newly_enabled}
        requests = builder.build(documents, facts, resolved_ids=exclude.union(exact_matches))
    return FormStepResult(records, decision_calls, input_tokens, cost)
