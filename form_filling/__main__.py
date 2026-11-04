"""Fill and verify the current step of FORM_URL from FORM_FACTS. Configure it in .env."""

import json
import sys
from collections import Counter
from dataclasses import asdict

from playwright.sync_api import Error as BrowserError

from browser.session import browser_page
from open_router.client import OpenRouterError
from settings import FormSettings

from .navigation import open_form_link
from .matching.requests import read_facts
from .workflow import run_form_step


def main() -> None:
    try:
        config = FormSettings.from_env()
        facts = read_facts(json.loads(config.facts_path.read_text(encoding="utf-8-sig")))
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from None
    with browser_page(watch_delay_ms=0) as page:
        try:
            page.goto(config.url, wait_until="commit", timeout=45000)
            if config.open_link:
                page.wait_for_load_state("domcontentloaded", timeout=45000)
                open_form_link(page, config.open_link)
        except BrowserError as exc:
            raise SystemExit(f"Could not open {config.url}: {exc}") from None
        try:
            result = run_form_step(page, facts, **asdict(config.matching))
        except (ValueError, OpenRouterError) as exc:
            raise SystemExit(str(exc)) from None
        print(json.dumps(result.records, ensure_ascii=True, indent=2))
        statuses = dict(Counter(record["status"] for record in result.records))
        print(f"Jev calls: {result.decision_calls}, {result.input_tokens} input tokens, ${result.cost:.4f}. "
              f"Statuses: {statuses}", file=sys.stderr)


if __name__ == "__main__":
    main()
