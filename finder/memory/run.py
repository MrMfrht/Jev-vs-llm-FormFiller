"""In-process history and decision context for one browser task."""

import json
from collections.abc import Callable, Iterable, Mapping
from copy import deepcopy
from dataclasses import asdict, replace

from open_router.jev.classifier import choose_browser_action
from browser.press_options import press_options

from .models import Observation, RunStatus, Step

RECENT_ACTION_LIMIT = 20


class RunMemory:
    def __init__(self, goal: str, first: Observation, *, result_schema: dict | None = None):
        if not goal.strip():
            raise ValueError("A run requires a goal.")
        self._goal = goal
        self._result_schema = deepcopy(result_schema)
        self._status = RunStatus.RUNNING
        self._snapshots = {first.id: first}
        self._current = first
        self._steps: list[Step] = []

    @property
    def goal(self) -> str:
        return self._goal

    @property
    def status(self) -> RunStatus:
        return self._status

    @property
    def snapshots(self) -> tuple[Observation, ...]:
        return tuple(self._snapshots.values())

    @property
    def steps(self) -> tuple[Step, ...]:
        return tuple(self._steps)

    def decision_context(self) -> str:
        recent = [
            {"snapshot_id": step.snapshot_id, "action": step.selected_label, "outcome": step.outcome}
            for step in self._steps[-RECENT_ACTION_LIMIT:]
        ]
        evidence = [
            {"snapshot_id": step.snapshot_id, "url": self._snapshots[step.snapshot_id].page.url,
             **asdict(block)}
            for step in self._steps for block in step.remembered_blocks
        ]
        page = self._current.page
        return json.dumps({
            "goal": self.goal, "result_schema": self._result_schema, "recent_actions": recent,
            "remembered_blocks": evidence,
            "current_page": {"snapshot_id": self._current.id, "url": page.url,
                             "title": page.title, "html": page.html},
        }, ensure_ascii=False)

    def choose(self, options: Mapping[str, str] | None = None, *,
               chooser: Callable[[str, dict[str, str]], str] | None = None) -> str:
        """Ask Jev once, then record its selection without claiming it was executed."""
        if self.status != RunStatus.RUNNING:
            raise ValueError("The run has ended.")
        if self._steps and self._steps[-1].outcome is None:
            raise ValueError("Record the previous outcome before choosing again.")
        actions = dict(options) if options is not None else press_options(self._current.page)
        selected = (chooser or choose_browser_action)(self.decision_context(), actions)
        self._steps.append(Step(self._current.id, tuple(actions.items()), selected, actions[selected]))
        return selected

    def record_outcome(
        self, outcome: str, *, next_observation: Observation | None = None,
        remember_ids: Iterable[str] = (),
    ) -> None:
        """Complete the pending step. IDs always refer to the page before the action."""
        if self.status != RunStatus.RUNNING or not self._steps or self._steps[-1].outcome is not None:
            raise ValueError("No pending action.")
        if not outcome.strip():
            raise ValueError("Describe what the browser actually observed.")
        step = self._steps[-1]
        requested = set(remember_ids)
        blocks = self._current.evidence.blocks
        if requested.difference(block.id for block in blocks):
            raise ValueError("Unknown evidence ID for the source snapshot.")
        if next_observation and next_observation.id in self._snapshots:
            raise ValueError("New observations need distinct snapshot IDs.")
        completed = replace(
            step, outcome=outcome, next_snapshot_id=next_observation.id if next_observation else None,
            remembered_blocks=tuple(block for block in blocks if block.id in requested),
        )
        self._steps[-1] = completed
        if next_observation:
            self._snapshots[next_observation.id] = next_observation
            self._current = next_observation

    def finish(self, status: RunStatus = RunStatus.COMPLETED) -> None:
        status = RunStatus(status)
        if self.status != RunStatus.RUNNING or status == RunStatus.RUNNING:
            raise ValueError("Expected a running task and a terminal status.")
        if self._steps and self._steps[-1].outcome is None:
            raise ValueError("Record the pending outcome first.")
        self._status = status
