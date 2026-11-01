"""P4-T22: one retry with the verdict reason, then stop."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from argus_core.client import Completion, Usage
from argus_core.ledger import Ledger, ModelQuota
from argus_core.types import StopReason, Trajectory
from jsonschema import Draft202012Validator

from fix_loop.loop import run_fix
from fix_loop.tools import ToolResult

_SCHEMA = Path(__file__).resolve().parents[3] / "packages" / "argus-core" / "schemas" / "trajectory.schema.json"


class _Verdict:
    def __init__(self, ok: bool):
        self.ok = ok
        self.first_failure = None if ok else "pixel shifted"
        self.failed_check = None if ok else "pixel"


def _completion() -> Completion:
    content = json.dumps({"tool": "submit", "arguments": {}})
    return Completion(content, Usage(1, 1, 0), {})


def _run(tmp_path: Path, replies: list[Completion], verify):
    seen: list[list[dict]] = []

    def complete(messages):
        seen.append(messages)
        return replies[len(seen) - 1]

    result = run_fix(
        worktree=tmp_path / "work",
        model="fake",
        ledger=Ledger(tmp_path / "ledger.json", {"fake": ModelQuota(100, 10**9, 100, 10**9, False)}),
        complete=complete,
        out_dir=tmp_path / "out",
        step_cap=4,
        token_cap=1000,
        run_id="run-1",
        host="test",
        git_commit="abc",
        task_id="bug-17",
        system="system",
        user="fix it",
        execute=lambda name, _payload: ToolResult(tool=name, text="submitted"),
        verify=verify,
    )
    return result, seen


def test_accept(tmp_path: Path):
    result, seen = _run(tmp_path, [_completion()], lambda: _Verdict(True))
    assert result.stop_reason is StopReason.submit
    assert len(seen) == 1


def test_reject_then_accept(tmp_path: Path):
    state = {"n": 0}

    def verify():
        state["n"] += 1
        return _Verdict(state["n"] > 1)

    result, seen = _run(tmp_path, [_completion(), _completion()], verify)
    assert result.stop_reason is StopReason.submit
    feedback = json.loads(seen[1][-1]["content"])
    assert feedback["verify"] == "pixel"
    assert feedback["error"] == "pixel shifted"


def test_reject_twice(tmp_path: Path):
    result, seen = _run(tmp_path, [_completion(), _completion(), _completion()], lambda: _Verdict(False))
    assert result.stop_reason is StopReason.verify_reject
    assert len(seen) == 2
    trajectory = Trajectory.from_jsonl(result.trajectory_path.read_text(encoding="utf-8"))
    assert trajectory.steps[-1].stop_reason is StopReason.verify_reject
    assert "pixel shifted" in trajectory.steps[-1].message["text"]
    Draft202012Validator(json.loads(_SCHEMA.read_text(encoding="utf-8"))).validate(trajectory.model_dump(mode="json"))
