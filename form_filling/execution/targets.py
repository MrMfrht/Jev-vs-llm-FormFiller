"""Bind matching IDs to the original field elements before sending the model request."""

from collections.abc import Iterator, Sequence
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass

from playwright.sync_api import ElementHandle, Error as BrowserError, Page

from ..inspection.inventory import DocumentFields, Field, field_inventory_script, is_frame_hidden, parse_field


@dataclass(frozen=True)
class FieldTarget:
    field: Field
    node: ElementHandle

    def is_current(self) -> bool:
        describe = f"""el => {{
          if (!el.isConnected) return null;
          const scan = ({field_inventory_script()})(false, true);
          return scan.fields[scan.nodes.indexOf(el)] ?? null;
        }}"""
        live = self.node.evaluate(describe)
        return bool(live and live["fillable_now"] and all(
            live[key] == getattr(self.field, key) for key in
            ("kind", "form", "section", "name", "label", "html_id", "nearby_label", "multiple")
        ))


@contextmanager
def capture_targets(page: Page, documents: Sequence[DocumentFields]) -> Iterator[dict[str, FieldTarget]]:
    targets = {}
    with ExitStack() as resources:
        for doc, frame in zip(documents, page.frames):
            try:
                capture = frame.evaluate_handle(f"hidden => ({field_inventory_script()})(hidden, true)", is_frame_hidden(frame))
                resources.callback(capture.dispose)
                data = capture.evaluate("s => ({url:s.url, fields:s.fields})")
                if doc.url != data["url"] or len(doc.fields) != len(data["fields"]):
                    continue
                for i, field in enumerate(doc.fields):
                    if not field.fillable_now or not (is_dropdown(field) or field.kind in TEXT_KINDS
                                                      or field.kind == "checkbox"):
                        continue
                    if parse_field(doc.frame_id, i + 1, data["fields"][i]) != field:
                        continue
                    handle = capture.evaluate_handle("(s, i) => s.nodes[i]", i)
                    resources.callback(handle.dispose)
                    if handle.as_element() is not None:
                        targets[field.id] = FieldTarget(field, handle.as_element())
            except BrowserError:
                continue  # Missing or navigating frame: absent targets require fresh inspection.
        yield targets


TEXT_KINDS = {"text", "textarea", "number", "date", "email", "tel", "url", "month", "time", "week", "datetime-local"}


def is_dropdown(field: Field) -> bool:
    return field.kind in {"select", "combobox", "listbox"} or field.options_source == "suggestions"
