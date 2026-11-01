"""P3-T31 and P3-T32: checks stay read-only, and the host tree stays intact."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from argus_core.client import Completion, Usage
from argus_core.ledger import Ledger, ModelQuota
from argus_core.types import Trajectory

from fix_loop.gates import NAMES, run_gates
from fix_loop.loop import run_fix
from fix_loop.sandbox import build_image, run
from fix_loop.tools import ToolError, ToolResult
from fix_loop.worktree import create, destroy


def _git(repo: Path, *args: str, identity: bool = False) -> subprocess.CompletedProcess[str]:
    cmd = ["git", "-c", "core.autocrlf=false"]
    if identity:
        cmd += ["-c", "user.email=dev@example.com", "-c", "user.name=dev"]
    cmd += ["-C", str(repo), *args]
    return subprocess.run(cmd, check=True, capture_output=True, text=True, encoding="utf-8")


def _hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file() and ".git" not in item.parts):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _completion(tool: str, arguments: dict) -> Completion:
    content = json.dumps({"tool": tool, "arguments": arguments})
    return Completion(content, Usage(1, 1, 0), {})


def test_check_write_fails_and_is_in_the_trajectory(tmp_path: Path):
    build_image()
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    (repo / "a.txt").write_text("one\n", encoding="utf-8", newline="\n")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "-m", "one", identity=True)
    base = _git(repo, "rev-parse", "HEAD").stdout.strip()
    work = create(repo, "bug-17", base, root=tmp_path / "wt")
    checks = tmp_path / "checks"
    checks.mkdir()
    (checks / "keep.txt").write_text("same\n", encoding="utf-8", newline="\n")
    replies = iter([
        _completion("run_cmd", {"command": "echo x > /checks/keep.txt"}),
        _completion("submit", {}),
    ])

    def execute(name: str, payload: dict):
        if name != "run_cmd":
            return ToolResult(tool=name, text="submitted")
        proc = run(work, checks, ["sh", "-c", payload["command"]])
        text = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode != 0:
            return ToolError(error="failed", message=text or f"exit {proc.returncode}")
        return ToolResult(tool="run_cmd", text=text, returncode=0)

    try:
        result = run_fix(
            worktree=work,
            model="fake",
            ledger=Ledger(
                tmp_path / "ledger.json",
                {"fake": ModelQuota(100, 10**9, 100, 10**9, False)},
            ),
            complete=lambda _messages: next(replies),
            out_dir=tmp_path / "out",
            step_cap=4,
            token_cap=1000,
            run_id="run-1",
            host="test",
            git_commit=base,
            task_id="bug-17",
            system="system",
            user="edit the check",
            execute=execute,
        )
        trajectory = Trajectory.from_jsonl(result.trajectory_path.read_text(encoding="utf-8"))
        assert trajectory.steps[0].tool_name == "run_cmd"
        assert trajectory.steps[0].tool_error == "failed"
        assert (checks / "keep.txt").read_text(encoding="utf-8") == "same\n"
    finally:
        destroy(repo, work)


def test_rm_damages_the_worktree_and_not_the_host(tmp_path: Path):
    build_image()
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    (repo / "a.txt").write_text("one\n", encoding="utf-8", newline="\n")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "-m", "one", identity=True)
    base = _git(repo, "rev-parse", "HEAD").stdout.strip()
    before = _hash(repo)
    work = create(repo, "bug-17", base, root=tmp_path / "wt")
    checks = tmp_path / "checks"
    checks.mkdir()
    try:
        removed = run(work, checks, ["rm", "-f", "/work/a.txt"])
        assert removed.returncode == 0, removed.stderr
        assert not (work / "a.txt").exists()
        assert _hash(repo) == before
        assert (repo / "a.txt").read_text(encoding="utf-8") == "one\n"
        commands = {name: [sys.executable, "-c", "raise SystemExit(0)"] for name in NAMES}
        commands["unit"] = [sys.executable, "-c", "import pathlib, sys; sys.exit(0 if pathlib.Path('a.txt').is_file() else 1)"]
        results = {item.name: item.ok for item in run_gates(work, commands)}
        assert results["unit"] is False
        assert results["build"] is True
    finally:
        destroy(repo, work)
