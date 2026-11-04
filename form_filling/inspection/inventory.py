"""Shared DOM inventory format and decoding for inspection and target binding."""

from dataclasses import dataclass
from functools import cache
from pathlib import Path

from playwright.sync_api import Frame


@dataclass(frozen=True, slots=True)
class Option:
    label: str
    value: str | None
    selected: bool
    disabled: bool
    hidden: bool
    group: str


@dataclass(frozen=True, slots=True)
class Field:
    id: str
    kind: str
    label: str
    name: str
    html_id: str
    placeholder: str
    form: str
    section: str
    required: bool
    multiple: bool
    hidden: bool
    disabled: bool
    read_only: bool
    fillable_now: bool
    value: str | bool | tuple[str, ...] | None
    options: tuple[Option, ...]
    options_source: str
    nearby_label: str = ""
    help_text: str = ""


@dataclass(frozen=True, slots=True)
class DocumentFields:
    frame_id: str
    url: str
    fields: tuple[Field, ...]
    error: str | None = None


@cache
def field_inventory_script() -> str:
    return Path(__file__).with_name("inspect_fields.js").read_text(encoding="utf-8")


def is_frame_hidden(frame: Frame) -> bool:
    while frame.parent_frame is not None:
        owner = frame.frame_element()
        try:
            if not owner.is_visible() or owner.evaluate("el => !!el.closest('[inert],[aria-hidden=true]')"):
                return True
        finally:
            owner.dispose()
        frame = frame.parent_frame
    return False

def parse_field(frame_id: str, index: int, raw: dict) -> Field:
    value = raw["value"]
    return Field(**{**raw, "id": f"{frame_id}.f{index}",
                    "value": tuple(value) if isinstance(value, list) else value,
                    "options": tuple(Option(**item) for item in raw["options"])})
