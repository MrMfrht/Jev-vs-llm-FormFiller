"""Immutable records for the observations and decisions in one browser run."""

from dataclasses import dataclass
from enum import StrEnum

from browser.evidence import EvidenceBlock, EvidenceSnapshot
from browser.snapshot import PageSnapshot


class RunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    STOPPED = "stopped"


@dataclass(frozen=True, slots=True)
class Observation:
    page: PageSnapshot
    evidence: EvidenceSnapshot

    def __post_init__(self):
        if self.page.url != self.evidence.url:
            raise ValueError("Page and evidence must come from the same URL.")

    @property
    def id(self) -> str:
        return self.evidence.id


@dataclass(frozen=True, slots=True)
class Step:
    snapshot_id: str
    available_actions: tuple[tuple[str, str], ...]
    selected_id: str
    selected_label: str
    outcome: str | None = None
    next_snapshot_id: str | None = None
    remembered_blocks: tuple[EvidenceBlock, ...] = ()
