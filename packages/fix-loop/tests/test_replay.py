"""P3-T27: replay applies stored edits and does not run the shell."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from argus_core.client import Completion, Usage
from argus_core.ledger import Ledger, ModelQuota
from argus_core.types import Trajectory, TrajectoryStep

from fix_loop.loop import run_fix
from fix_loop.replay import observations_for, replay
from fix_loop.tools import call


def _git(repo: Path, *args: str, identity: bool = False) -> subprocess.CompletedProcess[str]:
    cmd = ["git", "-c", "core.autocrlf=false"]
    if identity:
        cmd += ["-c", "user.email=dev@example.com", "-c", "user.name=dev"]
    cmd += ["-C", str(repo), *args]
    return subprocess.run(cmd, check=True, capture_output=True, text=True, encoding="utf-8")


def _diff(repo: Path) -> str:
    return _git(repo, "diff").stdout


def test_replay_reproduces_the_patch_and_does_not_run_the_shell(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    (repo / "a.txt").write_text("alpha\n", encoding="utf-8", newline="\n")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "-m", "one", identity=True)
    replies = iter([
        _completion("edit", {"path": "a.txt", "old": "alpha", "new": "beta"}),
        _completion("submit", {}),
    ])
    result = run_fix(
        worktree=repo,
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
        execute=lambda name, payload: call(name, payload, repo),
    )
    expected = _diff(repo)
    assert "beta" in expected
    _git(repo, "checkout", "--", "a.txt")
    stored = Trajectory.from_jsonl(result.trajectory_path.read_text(encoding="utf-8"))
    shell = TrajectoryStep(
        index=9,
        raw_response=json.dumps({"tool": "run_cmd", "arguments": {"command": "echo x > planted.txt"}}),
        tool_name="run_cmd",
        message={"text": "ran"},
    )
    mixed = Trajectory(meta=stored.meta, steps=[*stored.steps, shell])
    path = tmp_path / "trajectory.jsonl"
    path.write_text(mixed.to_jsonl(), encoding="utf-8")
    again = replay(path, repo)
    assert again == expected
    assert not (repo / "planted.txt").exists()
    assert observations_for(stored.steps[0])[0]["raw_response"] == stored.steps[0].raw_response


def test_tool_call_ids_have_one_observation_each():
    step = TrajectoryStep(
        index=0,
        raw_response=json.dumps(
            {
                "tool_calls": [
                    {"id": "call-1", "function": {"name": "edit", "arguments": "{}"}},
                    {"id": "call-2", "function": {"name": "edit", "arguments": "{}"}},
                ]
            }
        ),
        message={"observations": [{"id": "call-1", "text": "one"}, {"id": "call-2", "text": "two"}]},
    )
    rows = observations_for(step)
    assert [row["id"] for row in rows] == ["call-1", "call-2"]
    assert [row["observation"]["text"] for row in rows] == ["one", "two"]


def _completion(tool: str, arguments: dict) -> Completion:
    content = json.dumps({"tool": tool, "arguments": arguments})
    return Completion(content, Usage(1, 1, 0), {})
