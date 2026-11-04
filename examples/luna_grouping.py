"""Live smoke experiment. Run from the repo with uv run python -m examples.luna_grouping."""

import os
from time import perf_counter

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from open_router.client import OpenRouterError
from open_router.luna import group_blocks
from browser.evidence import read_evidence


def run_case(name, blocks, expected_links=(), expected_join=None, split_id=None):
    start = perf_counter()
    try:
        facts = group_blocks(blocks)
    except OpenRouterError as exc:
        print(name, f"{perf_counter() - start:.2f}s", exc)
        return False
    elapsed = perf_counter() - start
    links = {(p.block_id, c) for fact in facts for p in fact.parts for c in fact.context_ids}
    joined = [tuple(p.block_id for p in fact.parts) for fact in facts]
    checks = [(f"{child} -> {parent}", (child, parent) in links) for child, parent in expected_links]
    if expected_join:
        checks.append(("join split phrase", expected_join in joined))
    if split_id:
        checks.append(("split compound text", sum(split_id in ids for ids in joined) > 1))
    print(name, f"{elapsed:.2f}s", len(blocks), "blocks", len(facts), "facts", checks)
    return all(ok for _, ok in checks)


def main():
    load_dotenv()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel=os.getenv("PLAYWRIGHT_CHANNEL") or None)
        try:
            page = browser.new_page()
            page.set_content("""<div><span>Basic</span><span>$10/month</span><span>Cancel anytime</span></div>
                <div><span>Pro</span><span>$20/month</span><span>Priority</span><span> support</span></div>""")
            ok = run_case("Pricing cards", read_evidence(page).blocks,
                          expected_links=(("b2","b1"),("b3","b1"),("b5","b4")), expected_join=("b6","b7"))
            page.set_content("<div>Price: $15. Availability: In stock.</div>")
            ok &= run_case("Compound fragment", read_evidence(page).blocks, split_id="b1")
            page.set_content("<section><h2>Inspection</h2><p>Inspector: Reed. Status: Passed.</p></section>")
            ok &= run_case("Inspection record", read_evidence(page).blocks, split_id="b2")
            page.goto("https://books.toscrape.com/")
            blocks = read_evidence(page).blocks
            start = next(i for i, block in enumerate(blocks) if block.text == "Sharp Objects" and block.kind == "heading")
            sample = blocks[start:start + 4]
            ok &= run_case("Live catalog", sample, expected_links=((sample[1].id, sample[0].id),))
        finally:
            browser.close()
    if not ok:
        raise SystemExit("One or more semantic checks failed.")


if __name__ == "__main__":
    main()
