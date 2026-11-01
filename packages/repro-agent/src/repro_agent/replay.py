"""Replay a stored trajectory from its recorded reply. No model call."""

from __future__ import annotations

from pathlib import Path

from argus_core.client import Completion, Usage
from argus_core.ledger import Ledger, ModelQuota
from argus_core.types import Ticket, Trajectory

from repro_agent.loop import TreeRun, run_repro


def replay(fixture: Path, out_dir: Path) -> Trajectory:
    ticket = Ticket.model_validate_json((fixture / "ticket.json").read_text(encoding="utf-8"))
    reply = (fixture / "reply.txt").read_text(encoding="utf-8")
    stored = Trajectory.from_jsonl((fixture / "trajectory.jsonl").read_text(encoding="utf-8"))
    ledger = Ledger(
        out_dir / "ledger.json",
        {
            stored.meta.model: ModelQuota(
                requests_per_day=10,
                tokens_per_day=1000,
                requests_per_minute=10,
                tokens_per_minute=1000,
                cached_counts=False,
            )
        },
    )

    def complete(_messages: list[dict]) -> Completion:
        return Completion(reply, Usage(1, 1, 0), {})

    result = run_repro(
        ticket=ticket,
        task_dir=out_dir,
        model=stored.meta.model,
        ledger=ledger,
        complete=complete,
        run_trees=lambda _script: TreeRun(True, True),
        out_dir=out_dir,
        cap=1,
        run_id=stored.meta.run_id,
        host=stored.meta.host,
        git_commit=stored.meta.git_commit,
        mode="text",
    )
    return Trajectory.from_jsonl(result.trajectory_path.read_text(encoding="utf-8"))
