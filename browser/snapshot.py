"""Read the current page without navigating or activating any controls."""

from dataclasses import dataclass
from pathlib import Path
from functools import cache

from playwright.sync_api import Page


@dataclass(frozen=True, slots=True)
class SelectOption:
    index: int
    label: str
    selected: bool
    disabled: bool


@dataclass(frozen=True, slots=True)
class Control:
    id: str
    role: str
    name: str
    disabled: bool
    href: str | None
    options: tuple[SelectOption, ...] = ()
    multiple: bool = False
    editable: bool = False


@dataclass(frozen=True, slots=True)
class PageSnapshot:
    url: str
    title: str
    html: str
    controls: tuple[Control, ...]
    scroll_y: int = 0
    scroll_max: int = 0


@cache
def snapshot_script() -> str:
    return Path(__file__).with_name("compact_dom.js").read_text(encoding="utf-8")


def parse_snapshot(data: dict) -> PageSnapshot:
    return PageSnapshot(
        url=data["url"],
        title=data["title"],
        html=data["html"],
        controls=tuple(Control(**{**item, "options": tuple(SelectOption(**option)
                       for option in item.get("options", ()))}) for item in data["controls"]),
        scroll_y=data.get("scroll_y", 0), scroll_max=data.get("scroll_max", 0),
    )


def read_page(page: Page) -> PageSnapshot:
    """Generate both views in one DOM traversal so their IDs agree."""
    return parse_snapshot(page.evaluate(snapshot_script()))
