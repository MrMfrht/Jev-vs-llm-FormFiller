"""Use a remembered salary to choose a destination on a live paginated table, then report it with citations."""

from pathlib import Path
from uuid import uuid4

from finder.automation.retention import select_luna_memories
from finder.automation.runner import run_task
from browser.session import browser_page


URL = "https://datatables.net/examples/basic_init/zero_configuration.html"
GOAL = (
    "On page 1 of the employee table, remember Airi Satou's salary. Visit page 2 first. "
    "From page 2, use the remembered salary: if it exceeds $150,000, go to page 3; "
    "otherwise go to page 4. Use the table's 'Showing' range to recognize the active page: "
    "page 2 shows 11 to 20, page 3 shows 21 to 30, and page 4 shows 31 to 40. "
    "Choose done as soon as the destination range is visible and the salary is remembered. "
    "Retain the employee name and salary from the same row. "
    "Report the salary and how far above or below $150,000 it is."
)


def main():
    with browser_page() as page:
        page.goto(URL)
        table = page.locator("#example")
        salary = table.locator("tbody tr").filter(has_text="Airi Satou").locator("td").last.inner_text()
        destination = "3" if int(salary.replace("$", "").replace(",", "")) > 150_000 else "4"

        def verified(current, memory):
            visited_second = any("Showing 11 to 20" in snap.page.html for snap in memory.snapshots)
            retained = {b.text for step in memory.steps for b in step.remembered_blocks}
            start = (int(destination) - 1) * 10 + 1
            at_destination = f"Showing {start} to {start + 9}" in current.page.html
            return visited_second and at_destination and salary in retained

        path = Path("artifacts") / f"employees-{uuid4().hex}.jsonl"
        result = run_task(page, GOAL, path, verify_done=verified, memory_selector=select_luna_memories,
                          answer_mode="summary")
        for step in result.memory.steps:
            print(step.selected_id, step.outcome)
            for block in step.remembered_blocks:
                print(f"  Luna remembered: {block.text}")
        print(result.memory.status, result.reason, path.resolve())
        if result.answer:
            print(result.answer.text)
            for source in result.answer.sources:
                print(f"  {source.url} [{source.block_id}]: {source.text}")
        if result.memory.status != "completed":
            raise SystemExit(1)


if __name__ == "__main__":
    main()
