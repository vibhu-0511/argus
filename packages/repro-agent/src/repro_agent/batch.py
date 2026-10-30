"""Seeded-task passes. One crash does not stop the next task. Replies are recorded, so neither pass calls a provider."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Literal

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
    return run_seeded(out_dir, mode="text", ledger=ledger)


def run_with_screenshot(out_dir: Path, *, ledger: Ledger | None = None) -> Path:
    """Same 30 tasks and the same model as text-only. The ticket image is attached once when the task has one."""
    return run_seeded(out_dir, mode="image", ledger=ledger)


def run_seeded(out_dir: Path, *, mode: Literal["text", "image"], ledger: Ledger | None = None) -> Path:
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
            git_commit="text-only" if mode == "text" else "text-plus-image",
            mode=mode,
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


def valid_count(run_dir: Path) -> tuple[int, int]:
    files = sorted(run_dir.glob("*/verdict.json"))
    valid = 0
    for path in files:
        if json.loads(path.read_text(encoding="utf-8"))["verdict"] == "valid":
            valid += 1
    return valid, len(files)


def wilson_interval(successes: int, total: int) -> tuple[float, float]:
    """Wilson score interval at 95%. z = 1.96 formats the P0 0/10 cell as [0.000000, 0.277540]."""
    z = 1.96
    phat = successes / total
    z2 = z * z
    denom = 1 + z2 / total
    center = (phat + z2 / (2 * total)) / denom
    margin = z * math.sqrt(phat * (1 - phat) / total + z2 / (4 * total * total)) / denom
    return max(0.0, center - margin), min(1.0, center + margin)


def rate_label(successes: int, total: int) -> str:
    low, high = wilson_interval(successes, total)
    return f"{successes}/{total} [{low:.6f}, {high:.6f}]"


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="repro")
    parser.add_argument("command", choices=("text-only", "text-plus-image"))
    args = parser.parse_args(argv)
    out = _REPO / "packages" / "repro-agent" / "runs" / args.command
    if args.command == "text-only":
        run_text_only(out)
    else:
        run_with_screenshot(out)
    print(out)
    return 0
