"""Live acceptance run on a self-contained three-page fixture. FINDER_MEMORY picks jev or luna memory."""

from pathlib import Path
from uuid import uuid4

import settings
from finder.automation.runner import run_task
from finder.automation.retention import MEMORY_SELECTORS
from browser.session import browser_page

GOAL = "Select the monthly plan under $25 and reach its confirmation page."
PAGES = {
    "/prices": "<h1>Monthly prices</h1><p>Harbor: $19 per month</p><p>Cedar: $35 per month</p>"
               "<a href='/choose'>Continue to plan selection</a>",
    "/choose": "<h1>Select a plan</h1><a href='/cedar'>Choose Cedar</a> <a href='/harbor'>Choose Harbor</a>",
    "/harbor": "<h1>Confirmed: Harbor monthly plan</h1>",
    "/cedar": "<h1>Confirmed: Cedar monthly plan</h1>",
}


def open_fixture(page):
    def serve(route):
        path = route.request.url.removeprefix("https://plans.test")
        route.fulfill(status=200 if path in PAGES else 404, content_type="text/html", body=PAGES.get(path, "Missing"))
    page.route("https://plans.test/**", serve)
    page.goto("https://plans.test/prices")


def verified(current, memory):
    prices = [b.text for step in memory.steps for b in step.remembered_blocks]
    return (current.page.url == "https://plans.test/harbor" and
            "Confirmed: Harbor monthly plan" in current.page.html and
            "Harbor: $19 per month" in prices)


def main():
    try:
        memory = settings.finder_memory()
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    with browser_page() as page:
        open_fixture(page)
        path = Path("artifacts") / f"plan-{uuid4().hex}.jsonl"
        result = run_task(page, GOAL, path, verify_done=verified, max_steps=6,
                          memory_selector=MEMORY_SELECTORS[memory])
        for step in result.memory.steps:
            print(step.selected_label, "->", step.outcome)
            for block in step.remembered_blocks:
                print(f"  {memory} remembered [{block.id}]: {block.text}")
        print(result.memory.status, result.reason, path.resolve())
        if result.memory.status != "completed":
            raise SystemExit(1)


if __name__ == "__main__":
    main()
