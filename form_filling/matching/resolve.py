"""Resolve field matches using the original field and section descriptions."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from collections.abc import Callable, Sequence

from open_router.client import OpenRouterError, request_decision

from .requests import DEFAULT_TOKEN_BUDGET, MAX_FACT_CHOICES, NO_MATCH, Fact, build_match_request, estimated_input_tokens, describe_field, eligible_fields

DEFAULT_CONCURRENCY = 4
# A multi-select fact is chosen at or above this yes-probability.
DEFAULT_MULTI_SELECT_THRESHOLD = 0.6
# Below this, a single-value choice is reported instead of written.
DEFAULT_SINGLE_VALUE_MIN_CONFIDENCE = 0.6


def exact_name_matches(documents, facts, *, include_deferred: bool = False):
    """Only bypass inference for a literal name unique on both sides."""
    fields = list(eligible_fields(documents, include_deferred=include_deferred))
    field_counts = Counter(field.name for _, field in fields)
    fact_counts = Counter(fact.name for fact in facts)
    unique_facts = {fact.name: fact for fact in facts if fact_counts[fact.name] == 1}
    matches = {}
    for frame_id, field in fields:
        fact = unique_facts.get(field.name)
        if fact is not None and field_counts[field.name] == 1 and not field.multiple:
            matches[field.id] = {
                "field_id": field.id, "field": describe_field(frame_id, field),
                "fact": fact.name, "value": fact.value, "status": "proposed",
                "match_method": "exact_name",
            }
    return matches


def _probability(value, key: str) -> float:
    if type(value) not in (int, float) or not 0 <= value <= 1:
        raise OpenRouterError(f"Invalid Jev probability for {key}.")
    return float(value)


def _request_answers(request: dict, send: Callable) -> dict[str, tuple[str, float]]:
    """Map each question to (choice, confidence). A noul question's choice is its fact ID."""
    response = send(request)
    answers = {}
    for key, question in request["questions"].items():
        try:
            answer = response["answers"][key]
            if question["type"] == "noul":
                answers[key] = (key.partition(":")[2], _probability(answer["noul"], key))
                continue
            choice = answer["choice"]
            if not isinstance(choice, str) or choice not in question["criteria"]:
                raise OpenRouterError(f"Invalid Jev choice for {key}.")
            confidence = answer.get("confidence")
            if confidence is None:
                confidence = answer["probabilities"][choice]
            answers[key] = (choice, _probability(confidence, key))
        except (TypeError, KeyError) as exc:
            raise OpenRouterError(f"Missing Jev answer for {key}.") from exc
    return answers


def match_fields(requests: Sequence[dict], facts: Sequence[Fact], *,
                 max_tokens: int = DEFAULT_TOKEN_BUDGET, max_workers: int = DEFAULT_CONCURRENCY,
                 multi_select_threshold: float = DEFAULT_MULTI_SELECT_THRESHOLD,
                 single_value_min_confidence: float = DEFAULT_SINGLE_VALUE_MIN_CONFIDENCE,
                 send: Callable = request_decision) -> list[dict]:
    if max_workers < 1:
        raise ValueError("max_workers must be positive.")
    if not 0 <= multi_select_threshold <= 1 or not 0 <= single_value_min_confidence <= 1:
        raise ValueError("Thresholds must be between 0 and 1.")
    facts_by_id = {fact.id: fact for fact in facts}
    multiple_field_ids = set()
    descriptions = {}
    candidates = {}
    ask = partial(_request_answers, send=send)
    with ThreadPoolExecutor(max_workers=max_workers) as workers:
        for request, answers in zip(requests, workers.map(ask, requests), strict=True):
            descriptions.update(request["state"]["fields"])
            for question_id, (choice, confidence) in answers.items():
                field_id = question_id.partition(":")[0]
                nominations = candidates.setdefault(field_id, [])
                if request["questions"][question_id]["type"] == "noul":
                    multiple_field_ids.add(field_id)
                    if confidence >= multi_select_threshold:
                        nominations.append((facts_by_id[choice], confidence))
                elif choice != NO_MATCH:
                    nominations.append((facts_by_id[choice], confidence))

        def resolve(field_id):
            field = {"field_id": field_id, "field": descriptions[field_id]}
            nominees = candidates[field_id]
            if len(nominees) > 1 and field_id not in multiple_field_ids:
                comparison = build_match_request([(field_id, descriptions[field_id])], [f for f, _ in nominees])
                if len(nominees) > MAX_FACT_CHOICES or estimated_input_tokens(comparison) > max_tokens:
                    return [{**field, "status": "needs_review", "candidate_ids": [f.id for f, _ in nominees]}]
                winner, confidence = ask(comparison)[field_id]
                nominees = [] if winner == NO_MATCH else [(facts_by_id[winner], confidence)]
            if not nominees:
                return [{**field, "status": "unmatched", "fact": None, "value": None}]
            if field_id not in multiple_field_ids and nominees[0][1] < single_value_min_confidence:
                fact, confidence = nominees[0]
                return [{**field, "status": "needs_review", "fact": fact.name, "value": fact.value,
                         "confidence": confidence,
                         "detail": f"Jev's confidence {confidence:.2f} is below {single_value_min_confidence}; nothing written."}]
            return [{**field, "fact": fact.name, "value": fact.value, "confidence": confidence, "status": "proposed"}
                    for fact, confidence in nominees]

        return [record for records in workers.map(resolve, candidates) for record in records]
