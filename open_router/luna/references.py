"""Validate model references against the original source. Never accept rewritten text."""

from collections.abc import Sequence
from dataclasses import dataclass

from browser.evidence import EvidenceBlock


@dataclass(frozen=True, slots=True)
class SourceSpan:
    block_id: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class Fact:
    parts: tuple[SourceSpan, ...]
    context_ids: tuple[str, ...]


def resolve_facts(blocks: Sequence[EvidenceBlock], document: dict) -> tuple[Fact, ...]:
    index = 0
    offset = 0
    ids = {block.id for block in blocks}
    facts = []
    for raw in document["facts"]:
        parts = []
        for part in raw["parts"]:
            if index >= len(blocks) or part["id"] != blocks[index].id:
                raise ValueError("Missing, reordered, or unknown source block.")
            block = blocks[index]
            quote = part["quote"]
            if not isinstance(quote, str):
                raise ValueError("Invalid source quote.")
            start = offset
            # A boundary between quotes may omit whitespace, but no source words.
            if quote and not block.text.startswith(quote, start):
                start += len(block.text[start:]) - len(block.text[start:].lstrip())
            source = quote or block.text
            if not block.text.startswith(source, start):
                raise ValueError("Source quote differs from the original fragment.")
            offset = start + len(source)
            parts.append(SourceSpan(block.id, start, offset))
            if not block.text[offset:].strip():
                index += 1
                offset = 0
        context = raw["context_ids"]
        if not parts or not isinstance(context, list) or not set(context) <= ids:
            raise ValueError("Empty fact or unknown context.")
        if set(context).intersection(p.block_id for p in parts):
            raise ValueError("Self-referential context.")
        facts.append(Fact(tuple(parts), tuple(context)))
    if index != len(blocks):
        raise ValueError("Luna omitted source text.")
    return tuple(facts)
