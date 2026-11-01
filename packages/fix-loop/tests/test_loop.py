"""P3-T06: each stop reason is stored on the trajectory."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from argus_core.client import Completion, Usage
from argus_core.ledger import Ledger, ModelQuota
from argus_core.types import StopReason, Trajectory

from fix_loop.loop import run_fix
from fix_loop.tools import ToolError, ToolResult, call


def _quota(tmp_path: Path, **overrides: int) -> Ledger:
    fields = {
        "requests_per_day": 100,
        "tokens_per_day": 10**9,
        "requests_per_minute": 100,
        "tokens_per_minute": 10**9,
        "cached_counts": False,
    }
    fields.update(overrides)
    return Ledger(tmp_path / "ledger.json", {"fake": ModelQuota(**fields)})


def _completion(tool: str, arguments: dict, *, tokens_in: int = 1, tokens_out: int = 1) -> Completion:
    content = json.dumps({"tool": tool, "arguments": arguments})
    return Completion(content, Usage(tokens_in, tokens_out, 0), {"choices": [{"message": {"content": content}}]})


def _run(tmp_path: Path, complete, execute, *, step_cap: int = 5, token_cap: int = 1000, ledger: Ledger | None = None):
    root = tmp_path / "work"
    root.mkdir()
    (root / "a.txt").write_text("one\n", encoding="utf-8", newline="\n")
    return run_fix(
        worktree=root,
        model="fake",
        ledger=ledger or _quota(tmp_path),
        complete=complete,
        out_dir=tmp_path / "out",
        step_cap=step_cap,
        token_cap=token_cap,
        run_id="run-1",
        host="test",
        git_commit="abc",
        task_id="bug-17",
        system="system",
        user="fix it",
        execute=execute,
    )


def _reason(result) -> StopReason:
    trajectory = Trajectory.from_jsonl(result.trajectory_path.read_text(encoding="utf-8"))
    assert trajectory.steps[-1].stop_reason is result.stop_reason
    return result.stop_reason


def test_submit_stops_and_is_in_the_trajectory(tmp_path: Path):
    result = _run(tmp_path, lambda _messages: _completion("submit", {}), lambda _name, _payload: ToolResult(tool="submit", text="submitted"))
    assert _reason(result) is StopReason.submit


def test_step_cap_stops(tmp_path: Path):
    result = _run(
        tmp_path,
        lambda _messages: _completion("read_file", {"path": "a.txt"}),
        lambda _name, _payload: ToolResult(tool="read_file", text="one\n"),
        step_cap=2,
    )
    assert _reason(result) is StopReason.step_cap
    assert len(Trajectory.from_jsonl(result.trajectory_path.read_text(encoding="utf-8")).steps) == 2


def test_token_cap_stops_before_the_tool(tmp_path: Path):
    called = []

    def execute(name, payload):
        called.append(name)
        return ToolResult(tool=name, text="")

    result = _run(
        tmp_path,
        lambda _messages: _completion("read_file", {"path": "a.txt"}, tokens_in=3, tokens_out=2),
        execute,
        token_cap=4,
    )
    assert _reason(result) is StopReason.token_cap
    assert called == []


def test_quota_exceeded_stops_without_a_model_call(tmp_path: Path):
    def complete(_messages):
        raise AssertionError("model was called")

    result = _run(
        tmp_path,
        complete,
        lambda _name, _payload: ToolResult(tool="submit", text="submitted"),
        ledger=_quota(tmp_path, requests_per_day=0),
    )
    assert _reason(result) is StopReason.quota_exceeded


def test_stuck_stops_on_three_identical_calls(tmp_path: Path):
    result = _run(
        tmp_path,
        lambda _messages: _completion("read_file", {"path": "a.txt"}),
        lambda _name, _payload: ToolResult(tool="read_file", text="one\n"),
    )
    trajectory = Trajectory.from_jsonl(result.trajectory_path.read_text(encoding="utf-8"))
    assert result.stop_reason is StopReason.stuck
    assert trajectory.steps[-1].stop_reason is StopReason.stuck
    assert len(trajectory.steps) == 3


def test_three_timeouts_stop_as_consecutive_timeout_not_stuck(tmp_path: Path):
    result = _run(
        tmp_path,
        lambda _messages: _completion("run_cmd", {"command": "sleep 9"}),
        lambda _name, _payload: ToolError(error="timeout", message="command timed out after 30s"),
    )
    assert _reason(result) is StopReason.consecutive_timeout
    assert result.stop_reason is not StopReason.stuck


def test_interactive_command_is_rejected(tmp_path: Path):
    root = tmp_path / "work"
    replies = iter([
        _completion("run_cmd", {"command": "vim a.txt"}),
        _completion("submit", {}),
    ])
    result = run_fix(
        worktree=root,
        model="fake",
        ledger=_quota(tmp_path),
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
        execute=lambda name, payload: call(name, payload, root),
    )
    trajectory = Trajectory.from_jsonl(result.trajectory_path.read_text(encoding="utf-8"))
    assert trajectory.steps[0].tool_error == "not-allowed"
    assert trajectory.steps[0].message["text"] == "interactive command rejected"
    assert result.stop_reason is StopReason.submit
