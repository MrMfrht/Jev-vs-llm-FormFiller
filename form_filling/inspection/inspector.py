"""Read-only inventory of fields in each currently attached document."""

from time import monotonic, sleep

from playwright.sync_api import Error as BrowserError, Page

from .inventory import DocumentFields, field_inventory_script, is_frame_hidden, parse_field

class FormInspector:
    def inspect_when_ready(self, page: Page, *, timeout: float = 12) -> tuple[DocumentFields, ...]:
        """Wait for a nonempty, briefly stable inventory, or return the latest snapshot."""
        deadline = monotonic() + timeout
        previous = None
        stable_since = monotonic()
        while True:
            documents = self.inspect(page)
            now = monotonic()
            if documents != previous:
                previous, stable_since = documents, now
            if (any(doc.fields for doc in documents) and not any(doc.error for doc in documents)
                    and now - stable_since >= 1):
                return documents
            if now >= deadline:
                return documents
            sleep(min(0.25, deadline - now))

    def inspect(self, page: Page) -> tuple[DocumentFields, ...]:
        """IDs identify fields within this inspection. Inspect again after a form changes."""
        documents = []
        for index, frame in enumerate(page.frames, start=1):
            frame_id = f"frame{index}"
            url = frame.url
            try:
                data = frame.evaluate(field_inventory_script(), is_frame_hidden(frame))
                fields = tuple(parse_field(frame_id, i, raw) for i, raw in enumerate(data["fields"], 1))
                documents.append(DocumentFields(frame_id, data["url"], fields))
            except BrowserError as exc:
                documents.append(DocumentFields(frame_id, url, (), str(exc)))
        return tuple(documents)
