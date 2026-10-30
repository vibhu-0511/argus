"""Text-only pass over the seeded tasks. One crash does not stop the next task."""

from __future__ import annotations

import json
from pathlib import Path

from argus_core.client import Completion, Usage
from argus_core.ledger import Ledger, load_quotas
from argus_core.types import Ticket, Trajectory

from repro_agent.browser import ToolUnavailable
from repro_agent.loop import TreeRun, run_repro
from repro_agent.verify import verify

_REPO = Path(__file__).resolve().parents[4]
_SEEDED = _REPO / "packages" / "bench" / "tasks" / "seeded"
MODEL = "openai/gpt-oss-20b"
CRASH_TASK = "seed-e01"
LOOSE_TASK = "seed-h01"

VALID = """
await page.getByRole("button", { name: "Sign in" }).click();
await expect(page.getByRole("heading", { name: "Welcome" })).toBeVisible();
"""
LOOSE = """
await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
"""


def seeded_tickets(root: Path | None = None) -> list[tuple[str, Ticket]]:
    base = root or _SEEDED
    found: list[tuple[str, Ticket]] = []
    for path in sorted(p for p in base.iterdir() if (p / "ticket.json").is_file()):
        ticket = Ticket.model_validate_json((path / "ticket.json").read_text(encoding="utf-8"))
        found.append((path.name, ticket))
    return found


def run_text_only(out_dir: Path, *, ledger: Ledger | None = None) -> Path:
    """Write one verdict and one trajectory per seeded task. Text mode only."""
    out_dir.mkdir(parents=True, exist_ok=True)
    book = ledger or Ledger(out_dir / "ledger.json", load_quotas(_REPO / "docs" / "quotas.md"))
    for name, ticket in seeded_tickets():
        task_out = out_dir / name
        result = run_repro(
            ticket=ticket,
            task_dir=_SEEDED / name,
            model=MODEL,
            ledger=book,
            complete=_complete(name),
            run_trees=_trees(name),
            out_dir=task_out,
            cap=1,
            run_id=name,
            host="fixture",
            git_commit="text-only",
            mode="text",
        )
        trajectory = Trajectory.from_jsonl(result.trajectory_path.read_text(encoding="utf-8"))
        verdict = _verdict(name, result.script, result.stop_reason.value, trajectory)
        (task_out / "verdict.json").write_text(
            json.dumps({"task_id": ticket.id, "verdict": verdict, "stop_reason": result.stop_reason.value}) + "\n",
            encoding="utf-8",
        )
    return book.path


def _complete(name: str):
    text = LOOSE if name == LOOSE_TASK else VALID

    def complete(_messages: list[dict]) -> Completion:
        return Completion(text, Usage(1, 1, 0), {})

    return complete


def _trees(name: str):
    def run_trees(script: str) -> TreeRun:
        if name == CRASH_TASK:
            raise ToolUnavailable("server exited")
        if "Welcome" in script:
            return TreeRun(failed_on_buggy=True, passed_on_golden=True)
        return TreeRun(failed_on_buggy=False, passed_on_golden=True)

    return run_trees


def _verdict(name: str, script: str | None, stop: str, trajectory: Trajectory) -> str:
    if stop == "tool-unavailable" or name == CRASH_TASK:
        return "error"
    body = script or (trajectory.steps[-1].raw_response if trajectory.steps else "") or ""
    if "Welcome" in body:
        return verify(body, "fail", "pass").value
    return verify(body, "pass", "pass").value
