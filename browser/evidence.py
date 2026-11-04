"""Fine-grained evidence from one rendered document. IDs are local to the observation."""

from dataclasses import dataclass
from functools import cache
from pathlib import Path
from uuid import uuid4

from playwright.sync_api import Page


@dataclass(frozen=True, slots=True)
class EvidenceBlock:
    id: str
    kind: str
    text: str
    context: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvidenceSnapshot:
    id: str
    url: str
    blocks: tuple[EvidenceBlock, ...]


@cache
def evidence_script() -> str:
    return Path(__file__).with_name("evidence_dom.js").read_text(encoding="utf-8")


def parse_evidence(data: dict) -> EvidenceSnapshot:
    blocks = tuple(
        EvidenceBlock(f"b{i}", item["kind"], item["text"], tuple(item["context"]))
        for i, item in enumerate(data["blocks"], start=1)
    )
    return EvidenceSnapshot(uuid4().hex, data["url"], blocks)


def read_evidence(page: Page) -> EvidenceSnapshot:
    return parse_evidence(page.evaluate(evidence_script()))
