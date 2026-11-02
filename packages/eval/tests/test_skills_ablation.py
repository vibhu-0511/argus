"""P5.5-T08 report: counts, Wilson interval, paired cells and skills-loaded read from hand-built run folders. No model."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp", reason="run with: uv run --all-packages python -m pytest packages/eval/tests/test_skills_ablation.py")
for src in ("eval", "fix-loop"):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / src / "src"))

from argus_core.types import Trajectory, TrajectoryMeta, TrajectoryStep

from eval import skills_ablation as sa

SONNET = "claude-sonnet-5-5"


def _run(root: Path, task: str, verdict: str, *, load: str | None = None, steps: int = 2) -> None:
    rows = [TrajectoryStep(index=i, tokens_in=100, tokens_out=10, tier="strong", host="claude-session", model=SONNET, tool_name="search") for i in range(steps)]
    if load:
        rows[0] = TrajectoryStep(index=0, tokens_in=100, tokens_out=10, tier="strong", host="claude-session", model=SONNET, tool_name="load_skill",
                                 message={"text": f'<skill_content name="{load}">\nbody\n</skill_content>'})
    meta = TrajectoryMeta(run_id="r", task_id=task, model=SONNET, host="claude-session", prompt_hash="p", git_commit="c")
    folder = root / task
    (folder / "fix").mkdir(parents=True)
    (folder / "fix" / "trajectory.jsonl").write_text(Trajectory(meta=meta, steps=rows).to_jsonl(), encoding="utf-8")
    (folder / "verdict.json").write_text(
        json.dumps({"verdict": verdict, "stop_reason": "submit", "wall_s": 10.0, "model_turns": steps + 3, "turns_by_stage": {"repro": 3, "fix": steps}}), encoding="utf-8")


def test_counts_interval_pairs_and_loaded_come_from_the_stored_files(tmp_path: Path):
    a, b = tmp_path / "a", tmp_path / "b"
    for task, va, vb in [("t1", "resolved", "resolved"), ("t2", "unresolved", "unresolved"), ("t3", "resolved", "unresolved"),
                         ("t4", "unresolved", "resolved"), ("t5", "excluded", "resolved")]:
        _run(a, task, va)
        _run(b, task, vb, load="css-rule-missing-for-class" if task == "t4" else None)
    tasks = ["t1", "t2", "t3", "t4", "t5", "t6"]  # t6 has no run in either row
    without, with_skills = sa.read_row(a, tasks), sa.read_row(b, tasks)
    assert with_skills["t4"].loaded == ("css-rule-missing-for-class",) and with_skills["t1"].loaded == () and with_skills["t6"] is None
    counts, cells = sa.paired(without, with_skills)
    assert dict(counts) == {"both": 1, "neither": 1, "without only": 1, "with only": 1}  # t5 is excluded in `without`, so it is not paired
    text = sa.report(without, with_skills)
    assert "50.0% (2/4)" in text and "[15.0%, 85.0%]" in text  # without: 2 of 4 scored; Wilson 95%
    assert "75.0% (3/4)" not in text and "css-rule-missing-for-class 1" in text and "Without a verdict" in text and "'t6'" in text


def test_held_out_is_the_runnable_ids_only(tmp_path: Path):
    split = tmp_path / "split.json"
    split.write_text(json.dumps({"held_out": [{"id": "bug-17", "runnable": False}, {"id": "seed-e01", "runnable": True}]}), encoding="utf-8")
    assert sa.held_out(split) == ["seed-e01"]
    assert len(sa.held_out()) == 29
