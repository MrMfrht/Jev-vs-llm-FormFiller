"""Fill every benchmark form with both matchers and compare the results.

Run from the repository root with uv run python -m examples.form_filling.benchmark.run (billed).
BENCHMARK_MATCHERS=jev or =llm runs only one matcher; BENCHMARK_FORMS=visa_application,checkout runs
only those forms. BROWSER_WATCH=true shows the browser. The FORM_* matching settings in .env apply,
except FORM_MATCHER. Results are also written as JSON under artifacts/.
"""
import json
import logging
import os
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path
from time import perf_counter

from browser.session import browser_page
from form_filling.matching.requests import read_facts
from form_filling.workflow import run_form_step
from open_router.client import OpenRouterError
from settings import MATCHERS, ROOT, MatchingSettings

from .generate import FORMS

DIRECTORY = Path(__file__).parent


def read_controls(page):
    """Every control's final value by id: inputs, selects, textareas and the custom ARIA widgets."""
    values = {}
    for frame in page.frames:
        for field_id, value in frame.locator("input, select, textarea, [data-check]").evaluate_all("""
            fields => fields.map(el => [el.id,
                el.matches('[data-multilistbox]') ? Array.from(el.querySelectorAll('[aria-selected=true]'), o => o.textContent) :
                el.matches('[data-check]') ? el.textContent.trim() :
                el.type === 'checkbox' ? el.checked :
                el.multiple ? Array.from(el.selectedOptions, o => o.value) : el.value])
        """):
            if field_id in values:
                raise ValueError(f"Duplicate control id: {field_id}")
            values[field_id] = value
    return values


def run_one(folder: str, matching: MatchingSettings) -> dict:
    target = DIRECTORY / folder
    facts = read_facts(json.loads((target / "facts.json").read_text(encoding="utf-8")))
    expected = json.loads((target / "expected.json").read_text(encoding="utf-8"))
    result = {"form": folder, "matcher": matching.matcher, "fields": len(expected)}
    with browser_page() as page:
        page.goto((target / "form.html").resolve().as_uri())
        page.wait_for_load_state("load")
        started = perf_counter()
        try:
            run = run_form_step(page, facts, **asdict(matching))
        except (OpenRouterError, ValueError) as exc:
            return {**result, "error": f"{type(exc).__name__}: {exc}", "seconds": round(perf_counter() - started, 1)}
        result["seconds"] = round(perf_counter() - started, 1)
        actual = read_controls(page)
    if actual.keys() != expected.keys():
        raise ValueError(f"{folder}: fixture schema mismatch: {sorted(actual.keys() ^ expected.keys())}")
    wrong = {k: {"expected": v, "actual": actual[k]} for k, v in expected.items() if actual[k] != v}
    rows = {r["field_id"]: r for r in run.records}
    result.update({
        "correct": len(expected) - len(wrong), "wrong": wrong,
        "calls": run.model_calls, "input_tokens": run.input_tokens, "output_tokens": run.output_tokens,
        "cost": round(run.cost, 5),
        "statuses": {status: sum(r["status"] == status for r in run.records) for status in
                     sorted({r["status"] for r in run.records})},
        "needs_review": [{"field": r["field"], "value": r.get("value"), "detail": r.get("detail")}
                         for r in rows.values() if r["status"] == "needs_review"],
    })
    return result


def main():
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    matchers = [m.strip() for m in os.environ.get("BENCHMARK_MATCHERS", ",".join(MATCHERS)).split(",") if m.strip()]
    unknown = set(matchers) - set(MATCHERS)
    if unknown:
        raise SystemExit(f"BENCHMARK_MATCHERS must be among {', '.join(MATCHERS)}, not {', '.join(sorted(unknown))}.")
    forms = [f.strip() for f in os.environ.get("BENCHMARK_FORMS", ",".join(FORMS)).split(",") if f.strip()]
    unknown = set(forms) - set(FORMS)
    if unknown:
        raise SystemExit(f"BENCHMARK_FORMS must be among {', '.join(FORMS)}, not {', '.join(sorted(unknown))}.")
    try:
        base = MatchingSettings.from_env()
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    results = []
    for folder in forms:
        for matcher in matchers:
            print(f"{folder} / {matcher} ...", flush=True)
            outcome = run_one(folder, replace(base, matcher=matcher))
            results.append(outcome)
            if "error" in outcome:
                print(f"  FAILED: {outcome['error']}")
            else:
                print(f"  {outcome['correct']}/{outcome['fields']} correct, {outcome['calls']} calls, "
                      f"{outcome['input_tokens']} in + {outcome['output_tokens']} out tokens, ${outcome['cost']:.4f}, "
                      f"{outcome['seconds']} s")
                for field_id, err in outcome["wrong"].items():
                    print(f"    wrong {field_id}: expected {err['expected']!r}, got {err['actual']!r}")
                for row in outcome["needs_review"]:
                    print(f"    needs_review {row['field'][-50:]}: {row['detail']}")

    print("\n| Form | Fields | Matcher | Correct | Calls | Tokens in / out | Cost | Time |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in results:
        if "error" in r:
            print(f"| {r['form']} | {r['fields']} | {r['matcher']} | failed | | | | {r['seconds']} s |")
        else:
            print(f"| {r['form']} | {r['fields']} | {r['matcher']} | {r['correct']}/{r['fields']} | {r['calls']} | "
                  f"{r['input_tokens']:,} / {r['output_tokens']:,} | ${r['cost']:.4f} | {r['seconds']} s |")
    for matcher in matchers:
        done = [r for r in results if r["matcher"] == matcher and "error" not in r]
        if done:
            print(f"| **Total {matcher}** | {sum(r['fields'] for r in done)} | | "
                  f"**{sum(r['correct'] for r in done)}/{sum(r['fields'] for r in done)}** | "
                  f"{sum(r['calls'] for r in done)} | {sum(r['input_tokens'] for r in done):,} / "
                  f"{sum(r['output_tokens'] for r in done):,} | **${sum(r['cost'] for r in done):.4f}** | "
                  f"{sum(r['seconds'] for r in done):.0f} s |")

    out = ROOT / "artifacts" / f"benchmark-{datetime.now():%Y%m%d-%H%M%S}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nDetails: {out}")
    raise SystemExit(any("error" in r or r["wrong"] for r in results))


if __name__ == "__main__":
    main()
