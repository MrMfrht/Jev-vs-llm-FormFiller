"""Fill the whole synthetic banking form and compare every control with expected.json.

Run from the repository root with uv run python -m examples.form_filling.banking.check.
FORM_CONCURRENCY, FORM_FACTS_PER_REQUEST and FORM_TOKEN_BUDGET apply here too.
"""
import json
import logging
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

from settings import MatchingSettings
from open_router.client import OpenRouterError
from browser.session import browser_page
from form_filling.matching.requests import read_facts
from form_filling.workflow import run_form_step

DIRECTORY = Path(__file__).parent


def read_json(filename):
    return json.loads((DIRECTORY / filename).read_text(encoding="utf-8"))


def read_controls(page):
    values = {}
    for frame in page.frames:
        for field_id, value in frame.locator("input, select, textarea").evaluate_all("""
            fields => fields.map(el => [el.id, el.type === 'checkbox' ? el.checked :
                el.multiple ? Array.from(el.selectedOptions, o => o.value) : el.value])
        """):
            if field_id in values:
                raise ValueError(f"Duplicate control id: {field_id}")
            values[field_id] = value
    return values


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        matching = MatchingSettings.from_env()
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    with browser_page() as page:
        page.goto((DIRECTORY / "form.html").resolve().as_uri())
        page.frame_locator("#broker").locator("input").wait_for()
        started = perf_counter()
        try:
            run = run_form_step(page, read_facts(read_json("facts.json")), **asdict(matching))
            print(f"{matching.matcher} calls {run.model_calls}, {run.input_tokens} input + {run.output_tokens} output "
                  f"tokens, ${run.cost:.4f}, {perf_counter() - started:.0f} s; "
                  f"app statuses {dict(Counter(r['status'] for r in run.records))}")
            print("Verified field-value selections by source:", dict(Counter(
                r.get("match_method", "jev") for r in run.records if r["status"] == "matched")))
        except OpenRouterError as exc:
            raise SystemExit(f"Provider failure: {exc}") from None
        actual = read_controls(page)
        expected = read_json("expected.json")
        if actual.keys() != expected.keys():
            raise ValueError(f"Fixture schema mismatch: {actual.keys() ^ expected.keys()}")
        errors = {k: {"expected": v, "actual": actual[k]} for k, v in expected.items() if actual[k] != v}
        print(f"Correct final values: {len(expected)-len(errors)}/{len(expected)}")
        for field_id, error in errors.items():
            print(field_id, error)
    raise SystemExit(bool(errors))


if __name__ == "__main__":
    main()
