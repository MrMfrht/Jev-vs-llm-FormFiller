from dataclasses import asdict

from finder.memory import Observation, RunMemory
from open_router.luna.answer import Answer, AnswerMode, Source, answer_from_sources

from .trace import RunTrace


def final_answer(memory: RunMemory, current: Observation, mode: AnswerMode, trace: RunTrace) -> Answer:
    snapshots = {item.id: item for item in memory.snapshots}
    evidence = [(snapshots[step.snapshot_id], block)
                for step in memory.steps for block in step.remembered_blocks]
    evidence.extend((current, block) for block in current.evidence.blocks)
    sources = {
        (snap.id, b.id): Source(snap.id, b.id, snap.page.url, b.text, b.context)
        for snap, b in evidence
    }
    step = len(memory.steps)
    trace.write(step, "answer", "input", {"goal": memory.goal, "mode": mode,
                "sources": [asdict(source) for source in sources.values()]})
    answer = answer_from_sources(memory.goal, tuple(sources.values()), mode)
    trace.write(step, "answer", "output", asdict(answer))
    return answer
