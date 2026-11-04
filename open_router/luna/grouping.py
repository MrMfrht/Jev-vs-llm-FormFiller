"""Run an optional grouping pass over one caller-selected section of a snapshot."""

import json
from collections.abc import Sequence
from dataclasses import asdict

from open_router.client import OpenRouterError, request_chat
from browser.evidence import EvidenceBlock

from .contract import FORMAT, INSTRUCTIONS
from .references import Fact, resolve_facts


def group_blocks(blocks: Sequence[EvidenceBlock]) -> tuple[Fact, ...]:
    """Return validated source spans and context links; an invalid model response raises."""
    if not blocks:
        return ()
    if len({block.id for block in blocks}) != len(blocks):
        raise ValueError("Provide unique IDs from a single evidence snapshot.")
    result = request_chat({
        "model": "openai/gpt-6-luna",
        "messages": [
            {"role": "system", "content": INSTRUCTIONS},
            {"role": "user", "content": json.dumps([asdict(block) for block in blocks], ensure_ascii=False)},
        ],
        "reasoning": {"effort": "minimal"},
        "response_format": FORMAT,
    })
    try:
        message = result["choices"][0]["message"]["content"]
        return resolve_facts(blocks, json.loads(message))
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise OpenRouterError(f"Invalid Luna evidence grouping: {exc}") from exc
