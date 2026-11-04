from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
import re

from playwright.sync_api import Error as BrowserError, Page

from finder.memory import Observation, RunMemory, RunStatus
from open_router.client import OpenRouterError
from open_router.jev.limits import MAX_CHOICE_OPTIONS
from open_router.jev.classifier import choose_browser_action
from open_router.luna.answer import Answer, AnswerMode
from browser.click import ClickStatus, click_selected
from browser.history import RunHistory, run_history
from browser.interactions import available_actions, execute_action

from .observation import observe
from .answering import final_answer
from .policy import decision_options
from .menu import choose_from_menu
from .retention import select_memories
from .recovery import matching_controls, reconcile
from .trace import RunTrace


@dataclass(frozen=True)
class RunResult:
    memory: RunMemory
    reason: str
    trace_path: Path
    answer: Answer | None = None


def run_task(page: Page, goal: str, trace_path: Path, *, max_steps: int = 10,
             memory_selector: Callable = select_memories,
             answer_mode: AnswerMode | None = None,
             fill_values: tuple[str, ...] | None = None,
             verify_done: Callable[[Observation, RunMemory], bool] | None = None) -> RunResult:
    """Run on an already-open page. A supplied verifier must approve completion."""
    if max_steps < 1:
        raise ValueError("max_steps must be positive.")
    if answer_mode not in (None, "summary", "extract"):
        raise ValueError("answer_mode must be summary, extract, or None.")
    trace = RunTrace(trace_path)
    trace.write(0, "run", "input", {"goal": goal, "max_steps": max_steps, "url": page.url})
    with run_history(page) as history, ExitStack() as resources:
        try:
            values = fill_values if fill_values is not None else tuple(re.findall(r'"([^"\n]+)"', goal))
            return _run_decision_loop(page, goal, trace, max_steps, verify_done, resources, memory_selector, answer_mode, history, values)
        except Exception as exc:
            trace.write(0, "run", "error", {"type": type(exc).__name__, "message": str(exc)})
            raise


def _filter_recovery_options(options, current, rejected_page, uncertain_actions, stale_control):
    """Suppress rejected or uncertain actions and prioritize a stale target's replacement."""
    if rejected_page == current.page:
        options.pop("done")
    for url, key, control in uncertain_actions:
        if current.page.url == url:
            forbidden = matching_controls(control, current.page) if control else {key}
            for item in forbidden:
                options.pop(item, None)
    if stale_control:
        matches = matching_controls(stale_control, current.page).intersection(options)
        if matches:
            options = {k: v for k, v in options.items() if k in matches or k in ("done", "blocked")}
    return options


def _choose_next_action(memory: RunMemory, options: dict[str, str], trace: RunTrace, step: int) -> str:
    trace.write(step, "decide", "input", {"prompt": memory.decision_context(), "options": options})
    if len(options) > MAX_CHOICE_OPTIONS:
        def ask_menu(prompt, menu):
            trace.write(step, "menu", "input", {"options": menu})
            choice = choose_browser_action(prompt, menu)
            trace.write(step, "menu", "output", {"id": choice})
            return choice
        selected = memory.choose(options, chooser=lambda prompt, menu: choose_from_menu(prompt, menu, ask_menu))
    else:
        selected = memory.choose(options)
    trace.write(step, "decide", "output", {"id": selected, "label": options[selected]})
    return selected


def _run_decision_loop(page: Page, goal: str, trace: RunTrace, max_steps: int,
         verify_done: Callable[[Observation, RunMemory], bool] | None,
         resources: ExitStack, memory_selector: Callable, answer_mode: AnswerMode | None,
         history: RunHistory, fill_values: tuple[str, ...]) -> RunResult:
    capture, current = observe(page, resources, trace, 0)
    memory = RunMemory(goal, current)
    attempted = set()
    rejected_page = None
    stale_control = None
    uncertain_actions = []
    reason = "Decision budget exhausted."
    status = RunStatus.STOPPED
    for step in range(1, max_steps + 1):
        try:
            back = history.back_target()
            browser_actions = available_actions(current.page, fill_values)
            options = decision_options(current.page, back.url if back else None, browser_actions)
            options = _filter_recovery_options(options, current, rejected_page, uncertain_actions, stale_control)
            stale_control = None
        except ValueError as exc:
            status, reason = RunStatus.BLOCKED, str(exc)
            break
        selected = _choose_next_action(memory, options, trace, step)

        if selected in ("done", "blocked"):
            accepted = False
            if selected == "done":
                trace.write(step, "verify", "input", {"snapshot_id": current.id, "independent": verify_done is not None})
                accepted = verify_done(current, memory) if verify_done else True
                trace.write(step, "verify", "output", {"accepted": accepted})
            if selected == "blocked":
                reason = "Agent reported no way forward."
            elif not accepted:
                feedback = ("Completion rejected: at least one requested condition is still unmet. "
                            "Recheck the goal and choose the missing action, or blocked if impossible.")
                capture, fresh = observe(page, resources, trace, step)
                memory.record_outcome(feedback, next_observation=fresh)
                rejected_page = current.page
                current = fresh
                continue
            else:
                reason = "Completion verified." if verify_done else "Agent reported completion (no independent verifier)."
            status = RunStatus.COMPLETED if accepted else RunStatus.BLOCKED
            ids = [] if accepted and answer_mode else memory_selector(goal, current, selected, reason, trace, step)
            memory.record_outcome(reason, remember_ids=ids)
            break

        attempt = (current.page, selected, back if selected == "go_back" else None)
        if attempt in attempted:
            reason = "Repeated choice on an unchanged page; click was not replayed."
            memory.record_outcome(reason)
            break
        stage = browser_actions[selected].kind if selected in browser_actions else ("back" if selected == "go_back" else "click")
        trace.write(step, stage, "input", {"snapshot_id": current.id, "target": selected, "label": options[selected]})
        if selected in browser_actions:
            action_result = execute_action(capture, browser_actions[selected])
        elif selected == "go_back":
            action_result = history.go_back(back)
        else:
            action_result = click_selected(capture, selected)
        trace.write(step, stage, "output", {"status": action_result.status, "outcome": action_result.outcome})
        original = next((c for c in current.page.controls if c.id == selected), None)
        outcome = action_result.outcome
        if action_result.status == ClickStatus.UNCONFIRMED:
            uncertain_actions.append((current.page.url, selected, original))
            trace.write(step, "recover", "input", {"snapshot_id": current.id, "target": selected})
            try:
                capture, following, outcome = reconcile(page, resources, trace, step, current)
            except BrowserError:
                reason = "Could not obtain a fresh observation after uncertain input."
                memory.record_outcome(reason)
                break
        else:
            capture, following = observe(page, resources, trace, step)
        if action_result.status == ClickStatus.STALE:
            stale_control = original
            outcome += f" Reconsider {options[selected]} using fresh IDs. Nothing was dispatched."
        else:
            attempted.add(attempt)
        try:
            ids = [] if action_result.status == ClickStatus.STALE else memory_selector(goal, current, options[selected], outcome, trace, step)
        except OpenRouterError as exc:
            memory.record_outcome(outcome, next_observation=following)
            reason = f"Memory selection failed after the click: {exc}"
            break
        memory.record_outcome(outcome, next_observation=following, remember_ids=ids)
        current = following
    answer = None
    if status == RunStatus.COMPLETED and answer_mode:
        answer = final_answer(memory, current, answer_mode, trace)
        if not answer.supported:
            status, reason = RunStatus.BLOCKED, "Insufficient evidence for the requested answer."
    memory.finish(status)
    trace.write(len(memory.steps), "run", "output", {"status": status, "reason": reason,
        "steps": len(memory.steps), "retained": sum(len(s.remembered_blocks) for s in memory.steps)})
    return RunResult(memory, reason, trace.path, answer)
