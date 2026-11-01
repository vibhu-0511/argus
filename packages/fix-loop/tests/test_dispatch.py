"""P3-T07: five bad inputs return a typed error. They do not raise."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from argus_core.client import Completion, Usage
from argus_core.ledger import Ledger, ModelQuota
from argus_core.types import StopReason, Trajectory

from fix_loop.loop import run_fix
from fix_loop.tools import ToolError, ToolErrorCode, call


def _tree(tmp_path: Path) -> Path:
    root = tmp_path / "work"
    root.mkdir()
    (root / "a.txt").write_text("alpha\nbeta\nalpha\n", encoding="utf-8", newline="\n")
    (root / "wide.txt").write_text("a  b\n", encoding="utf-8", newline="\n")
    return root


def test_five_bad_inputs_are_typed_errors(tmp_path: Path):
    root = _tree(tmp_path)
    not_unique = call("edit", {"path": "a.txt", "old": "alpha", "new": "x"}, root)
    missing = call("edit", {"path": "a.txt", "new": "x"}, root)
    wrong_type = call("edit", {"path": 1, "old": "alpha", "new": "x"}, root)
    unknown = call("write_file", {"path": "a.txt", "text": "nope"}, root)
    outside = call("read_file", {"path": "../secret.txt"}, root)
    results = (not_unique, missing, wrong_type, unknown, outside)
    assert all(isinstance(item, ToolError) for item in results)
    assert not_unique.error == "not-unique"
    assert not_unique.message == "a.txt matches lines 1, 3"
    assert (root / "a.txt").read_text(encoding="utf-8") == "alpha\nbeta\nalpha\n"
    assert missing.error == "failed"
    assert wrong_type.error == "failed"
    assert unknown.error == "not-allowed"
    assert outside.error == "outside-worktree"
    assert "stuck" not in {item.value for item in ToolErrorCode}
    flex = call("edit", {"path": "wide.txt", "old": "a b", "new": "ab"}, root)
    assert flex.error == "not-found"
    assert (root / "wide.txt").read_text(encoding="utf-8") == "a  b\n"


def test_tool_error_is_a_normal_step_the_model_can_read(tmp_path: Path):
    root = _tree(tmp_path)
    seen: list[list[dict]] = []
    replies = iter([
        _completion("edit", {"path": "a.txt", "new": "x"}),
        _completion("submit", {}),
    ])

    def complete(messages):
        seen.append(messages)
        return next(replies)

    result = run_fix(
        worktree=root,
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
        execute=lambda name, payload: call(name, payload, root),
    )
    trajectory = Trajectory.from_jsonl(result.trajectory_path.read_text(encoding="utf-8"))
    assert trajectory.steps[0].tool_error == "failed"
    assert trajectory.steps[0].stop_reason is None
    assert result.stop_reason is StopReason.submit
    assert "failed:" in seen[1][-1]["content"]


def _completion(tool: str, arguments: dict) -> Completion:
    content = json.dumps({"tool": tool, "arguments": arguments})
    return Completion(content, Usage(1, 1, 0), {})
