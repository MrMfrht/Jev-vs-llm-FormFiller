"""Print everything the agents see on READER_URL. Run with uv run python -m browser."""

import json
from dataclasses import asdict

import settings

from .evidence import read_evidence
from .press_options import press_options
from .session import browser_page
from .snapshot import read_page


def main() -> None:
    try:
        url = settings.reader_url()
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    with browser_page() as page:
        page.goto(url, wait_until="load")
        snapshot = read_page(page)
        output = {"snapshot": asdict(snapshot), "press_options": press_options(snapshot),
                  "evidence": asdict(read_evidence(page))}
        print(json.dumps(output, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
