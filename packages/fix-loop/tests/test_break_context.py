"""P3-T29 and P3-T30: a 5 MB read is shrunk, and repeated bad arguments stop."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from argus_core.client import Completion, Usage
from argus_core.ledger import Ledger, ModelQuota
from argus_core.types import StopReason, Trajectory

from fix_loop.loop import run_fix
from fix_loop.strategies import OUTPUT_CAP, cap_strategy
from fix_loop.tools import ToolResult, call

_FIVE_MB = 5 * 1024 * 1024


def _ledger(tmp_path: Path) -> Ledger:
    return Ledger(tmp_path / "ledger.json", {"fake": ModelQuota(100, 10**9, 100, 10**9, False)})


def _run(tmp_path: Path, complete, **kwargs):
    root = tmp_path / "work"
    root.mkdir()
    return root, run_fix(
        worktree=root,
        model="fake",
        ledger=_ledger(tmp_path),
        complete=complete,
        out_dir=tmp_path / "out",
        step_cap=6,
        token_cap=1000,
        run_id="run-1",
        host="test",
        git_commit="abc",
        task_id="bug-17",
        system="system",
        user="fix it",
        **kwargs,
    )


def test_five_megabyte_read_is_shrunk_before_the_next_call(tmp_path: Path):
    root = tmp_path / "work"
    root.mkdir()
    (root / "big.txt").write_text("x" * _FIVE_MB, encoding="utf-8", newline="\n")
    seen: list[list[dict]] = []
    replies = iter([
        Completion(json.dumps({"tool": "read_file", "arguments": {"path": "big.txt"}}), Usage(1, 1, 0), {}),
        Completion(json.dumps({"tool": "submit", "arguments": {}}), Usage(1, 1, 0), {}),
    ])

    def complete(messages):
        seen.append(messages)
        return next(replies)

    result = run_fix(
        worktree=root,
        model="fake",
        ledger=_ledger(tmp_path),
        complete=complete,
        out_dir=tmp_path / "out",
        step_cap=4,
        token_cap=10**9,
        run_id="run-1",
        host="test",
        git_commit="abc",
        task_id="bug-17",
        system="system",
        user="fix it",
        execute=lambda name, payload: call(name, payload, root),
        context_budget=10,
        strategy=cap_strategy,
    )
    assert result.stop_reason is StopReason.submit
    shown = seen[1][-1]["content"]
    assert len(shown) == OUTPUT_CAP
    assert shown.endswith("[truncated]")
    assert len(shown) < _FIVE_MB


def test_repeated_malformed_arguments_stop_as_retry_cap(tmp_path: Path):
    root = tmp_path / "work"
    root.mkdir()
    (root / "a.txt").write_text("alpha\n", encoding="utf-8", newline="\n")
    seen: list[list[dict]] = []
    replies = iter([
        Completion(json.dumps({"tool": "edit", "arguments": {"path": "a.txt", "new": "x"}}), Usage(1, 1, 0), {}),
        Completion(json.dumps({"tool": "edit", "arguments": {"path": 1, "old": "a", "new": "b"}}), Usage(1, 1, 0), {}),
        Completion(json.dumps({"tool": "edit", "arguments": {}}), Usage(1, 1, 0), {}),
        Completion(json.dumps({"tool": "submit", "arguments": {}}), Usage(1, 1, 0), {}),
    ])

    def complete(messages):
        seen.append([dict(item) for item in messages])
        return next(replies)

    result = run_fix(
        worktree=root,
        model="fake",
        ledger=_ledger(tmp_path),
        complete=complete,
        out_dir=tmp_path / "out",
        step_cap=6,
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
    assert result.stop_reason is StopReason.retry_cap
    assert result.stop_reason is not StopReason.stuck
    assert trajectory.steps[-1].stop_reason is StopReason.retry_cap
    assert "failed:" in seen[1][-1]["content"]
    assert "old" in seen[1][-1]["content"]


def test_provider_payload_missing_choices_is_a_typed_error(tmp_path: Path):
    replies = iter([
        Completion("", Usage(1, 1, 0), {"id": "resp-1"}),
        Completion(json.dumps({"tool": "submit", "arguments": {}}), Usage(1, 1, 0), {}),
    ])
    _root, result = _run(
        tmp_path,
        lambda _messages: next(replies),
        execute=lambda name, _payload: ToolResult(tool=name, text="submitted"),
    )
    trajectory = Trajectory.from_jsonl(result.trajectory_path.read_text(encoding="utf-8"))
    assert trajectory.steps[0].tool_error == "failed"
    assert "choices" in trajectory.steps[0].message["error"]
    assert result.stop_reason is StopReason.submit
