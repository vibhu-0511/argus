"""P5.5-T04 collect: resolved runs are copied whole, other verdicts keep only verdict.json, a stuck run is listed and not copied."""

from __future__ import annotations

import json
from pathlib import Path

from skills.collect import collect


def _run(runs: Path, tasks: Path, name: str, verdict: str | None) -> None:
    task = tasks / name
    task.mkdir(parents=True)
    (task / "meta.json").write_text(json.dumps({"archetype": "font-size"}), encoding="utf-8")
    (task / "ticket.json").write_text(json.dumps({"id": name, "text": f"ticket for {name}"}), encoding="utf-8")
    run = runs / name
    (run / "fix").mkdir(parents=True)
    (run / "task.json").write_text(json.dumps({"task": str(task)}), encoding="utf-8")
    if verdict is None:
        return
    rows = [{"kind": "meta"}, {"kind": "step", "tokens_in": 100, "tokens_out": 10}, {"kind": "step", "tokens_in": 200, "tokens_out": 20}]
    (run / "fix" / "trajectory.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    (run / "verdict.json").write_text(json.dumps({"verdict": verdict, "stop_reason": "submit", "model_turns": 2, "wall_s": 5.0}), encoding="utf-8")
    (run / "diff.patch").write_text("--- a\n", encoding="utf-8")


def test_collect_copies_resolved_keeps_unresolved_verdict_and_lists_stuck(tmp_path: Path):
    runs, tasks, out = tmp_path / "runs", tmp_path / "tasks", tmp_path / "out"
    _run(runs, tasks, "mut-0001", "resolved")
    _run(runs, tasks, "mut-0002", "unresolved")
    _run(runs, tasks, "mut-0003", None)
    ledger = collect(runs, out)
    assert sorted(p.name for p in (out / "mut-0001").iterdir()) == ["diff.patch", "ticket.txt", "trajectory.jsonl", "verdict.json"]
    assert (out / "mut-0001" / "ticket.txt").read_text(encoding="utf-8") == "ticket for mut-0001\n"
    assert [p.name for p in (out / "_unresolved" / "mut-0002").iterdir()] == ["verdict.json"] and not (out / "mut-0002").exists()
    assert ledger["no_verdict"] == ["mut-0003"] and not (out / "mut-0003").exists()
    row = ledger["runs"][0]
    assert (row["steps"], row["tokens_in"], row["tokens_out"]) == (2, 300, 30) and ledger["totals"]["resolved"] == 1
    assert json.loads((out / "ledger.json").read_text(encoding="utf-8")) == ledger
