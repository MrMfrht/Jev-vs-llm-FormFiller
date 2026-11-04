"""Pursue FINDER_GOAL from FINDER_URL, then print a cited answer. Configure it in .env."""

import sys
from uuid import uuid4

from playwright.sync_api import Error as BrowserError

from browser.session import browser_page
from open_router.client import OpenRouterError
from settings import FinderSettings

from .automation.retention import MEMORY_SELECTORS
from .automation.runner import run_task


def main() -> None:
    try:
        config = FinderSettings.from_env()
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    with browser_page() as page:
        try:
            page.goto(config.url, wait_until="load", timeout=45000)
        except BrowserError as exc:
            raise SystemExit(f"Could not open {config.url}: {exc}") from None
        path = config.trace_dir / f"finder-{uuid4().hex[:8]}.jsonl"
        print(f"Trace: {path}", file=sys.stderr, flush=True)
        try:
            result = run_task(page, config.goal, path, max_steps=config.max_steps,
                              memory_selector=MEMORY_SELECTORS[config.memory],
                              answer_mode=config.answer_mode)
        except OpenRouterError as exc:
            raise SystemExit(f"Provider failure: {exc}") from None
        for step in result.memory.steps:
            action = step.selected_id if step.selected_id in ("done", "blocked") else step.selected_label
            print(f"{action} -> {step.outcome}")
            for block in step.remembered_blocks:
                print(f"  remembered [{block.id}]: {block.text}")
        print(result.memory.status, result.reason)
        if result.answer:
            print(result.answer.text)
            for source in result.answer.sources:
                print(f"  {source.url} [{source.block_id}]: {source.text}")
    if result.memory.status != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
