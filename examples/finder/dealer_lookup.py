"""Find the Thunderbird in the dealer inventory and report its advertised price."""

from pathlib import Path
from uuid import uuid4

from finder.automation.retention import select_luna_memories
from finder.automation.runner import run_task
from browser.session import browser_page


def main():
    with browser_page() as page:
        page.goto("https://grclassics.com/cars-for-sale", wait_until="commit")
        listing = page.get_by_role("link", name="1960 Ford Thunderbird (Black)", exact=True).first
        listing.wait_for(state="visible", timeout=45000)
        expected_url = listing.evaluate("a => a.href")

        def verified(current, _memory):
            return (current.page.url.rstrip("/") == expected_url.rstrip("/")
                    and "1960 Ford Thunderbird" in current.page.html
                    and "$34,990" in current.page.html)

        path = Path("artifacts") / f"dealer-watch-{uuid4().hex[:8]}.jsonl"
        print(f"Trace: {path.resolve()}", flush=True)
        result = run_task(page, "Find the black 1960 Ford Thunderbird. Open its individual vehicle "
                          "detail page and report its advertised price. Browse listings only; "
                          "do not contact the dealer.", path, max_steps=8,
                          memory_selector=select_luna_memories, verify_done=verified, answer_mode="summary")
        for step in result.memory.steps:
            print(step.selected_id, step.outcome)
        print(result.memory.status, result.reason)
        if result.answer:
            print(result.answer.text)
        if result.memory.status != "completed":
            raise SystemExit(1)


if __name__ == "__main__":
    main()
