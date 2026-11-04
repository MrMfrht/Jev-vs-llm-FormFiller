from contextlib import ExitStack

from playwright.sync_api import Page

from finder.memory import Observation
from browser.evidence import evidence_script, parse_evidence
from browser.snapshot import parse_snapshot, snapshot_script
from browser.targets import CapturedPage

from .trace import RunTrace


def observe(page: Page, resources: ExitStack, trace: RunTrace, step: int) -> tuple[CapturedPage, Observation]:
    """Replace the previous capture. Read targets and evidence in one browser turn."""
    resources.close()
    trace.write(step, "observe", "input", {"url": page.url})
    script = f"() => ({{targets: ({snapshot_script()})(true), evidence: ({evidence_script()})()}})"
    handle = page.evaluate_handle(script)
    resources.callback(handle.dispose)
    targets = handle.get_property("targets")
    resources.callback(targets.dispose)
    snapshot = parse_snapshot(targets.evaluate("t => t.snapshot"))
    evidence = parse_evidence(handle.evaluate("s => s.evidence"))
    observation = Observation(snapshot, evidence)
    trace.write(step, "observe", "output", {"id": observation.id, "url": snapshot.url,
        "title": snapshot.title, "html": snapshot.html, "evidence_blocks": len(evidence.blocks)})
    return CapturedPage(page, snapshot, targets), observation
