import json
from time import perf_counter

from finder.memory import Observation
from open_router.jev import should_remember
from open_router.luna.memory import select_memory_ids

from .trace import RunTrace


def select_luna_memories(goal: str, source: Observation, action: str, outcome: str,
                         trace: RunTrace, step: int) -> list[str]:
    if action == "done" and outcome == "Completion verified.":
        trace.write(step, "remember", "skipped", {"reason": outcome})
        return []
    task = {"goal": goal, "source_url": source.page.url, "action": action, "outcome": outcome}
    blocks = {b.id: {"context": b.context, "text": b.text} for b in source.evidence.blocks}
    trace.write(step, "remember", "input", {"model": "luna", "task": task, "blocks": blocks})
    started = perf_counter()
    ids = select_memory_ids(task, blocks)
    trace.write(step, "remember", "output", {"ids": ids, "seconds": perf_counter() - started})
    return ids


def select_memories(goal: str, source: Observation, action: str, outcome: str,
                    trace: RunTrace, step: int) -> list[str]:
    prompt = json.dumps({"goal": goal, "source_url": source.page.url, "action": action,
                         "observed_outcome": outcome}, ensure_ascii=False)
    retained = []
    blocks = source.evidence.blocks
    for start in range(0, len(blocks), 24):
        batch = {b.id: json.dumps({"context": b.context, "text": b.text}, ensure_ascii=False)
                 for b in blocks[start:start + 24]}
        trace.write(step, "remember", "input", {"prompt": prompt, "blocks": batch})
        flags = should_remember(prompt, batch)
        trace.write(step, "remember", "output", flags)
        retained.extend(key for key, keep in flags.items() if keep)
    return retained


# FINDER_MEMORY names, see settings.py.
MEMORY_SELECTORS = {"jev": select_memories, "luna": select_luna_memories}
