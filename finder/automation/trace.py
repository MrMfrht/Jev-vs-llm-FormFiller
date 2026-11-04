"""One flushed JSON record for each stage input, output, or failure."""

import json
from pathlib import Path


class RunTrace:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=False)

    def write(self, step: int, stage: str, phase: str, data: object) -> None:
        record = {"step": step, "stage": stage, "phase": phase, "data": data}
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
