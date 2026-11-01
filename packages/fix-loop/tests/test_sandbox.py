"""P3-T05: the sandbox has no network, and the checks directory is read-only."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fix_loop.sandbox import build_image, run
from fix_loop.worktree import create, destroy


def _git(repo: Path, *args: str, identity: bool = False) -> subprocess.CompletedProcess[str]:
    cmd = ["git", "-c", "core.autocrlf=false"]
    if identity:
        cmd += ["-c", "user.email=dev@example.com", "-c", "user.name=dev"]
    cmd += ["-C", str(repo), *args]
    return subprocess.run(cmd, check=True, capture_output=True, text=True, encoding="utf-8")


def test_sandbox_blocks_network_and_checks_writes(tmp_path: Path):
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
    try:
        network = run(work, checks, ["wget", "-q", "-T", "2", "-O", "-", "http://example.com"])
        assert network.returncode != 0
        denied = run(work, checks, ["sh", "-c", "echo x > /checks/keep.txt"])
        assert denied.returncode != 0
        assert (checks / "keep.txt").read_text(encoding="utf-8") == "same\n"
        wrote = run(work, checks, ["sh", "-c", "echo hi > /work/note.txt"])
        assert wrote.returncode == 0, wrote.stderr
        assert "hi" in (work / "note.txt").read_text(encoding="utf-8")
    finally:
        destroy(repo, work)
