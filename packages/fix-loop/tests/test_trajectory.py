"""P3-T08: a run writes one JSONL file that validates, including a rejected call."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from argus_core.client import Completion, Usage
from argus_core.ledger import Ledger, ModelQuota
from argus_core.types import Trajectory
from jsonschema import Draft202012Validator

from fix_loop.loop import run_fix

_SCHEMA = Path(__file__).resolve().parents[3] / "packages" / "argus-core" / "schemas" / "trajectory.schema.json"


def test_run_validates_and_a_rejected_call_keeps_its_raw_response(tmp_path: Path):
    raw = "not a tool call"
    replies = iter([
        Completion(raw, Usage(4, 5, 6), {}),
        Completion(json.dumps({"tool": "submit", "arguments": {}}), Usage(1, 1, 0), {}),
    ])
    result = run_fix(
        worktree=tmp_path / "work",
        model="fake",
        ledger=Ledger(tmp_path / "ledger.json", {"fake": ModelQuota(100, 10**9, 100, 10**9, False)}),
        complete=lambda _messages: next(replies),
        out_dir=tmp_path / "out",
        step_cap=4,
        token_cap=1000,
        run_id="run-1",
        host="test",
        git_commit="abc",
        task_id="bug-17",
        system="system",
        user="fix it",
    )
    text = result.trajectory_path.read_text(encoding="utf-8")
    trajectory = Trajectory.from_jsonl(text)
    Draft202012Validator(json.loads(_SCHEMA.read_text(encoding="utf-8"))).validate(
        trajectory.model_dump(mode="json")
    )
    rejected = trajectory.steps[0]
    assert rejected.raw_response == raw
    assert rejected.tool_error == "failed"
    assert rejected.tokens_in == 4
    assert rejected.tokens_out == 5
    assert rejected.tokens_cached == 6
    lines = [line for line in text.splitlines() if line.strip()]
    step = json.loads(lines[1])
    del step["tokens_cached"]
    again = Trajectory.from_jsonl(lines[0] + "\n" + json.dumps(step) + "\n")
    assert again.steps[0].tokens_cached == 0
