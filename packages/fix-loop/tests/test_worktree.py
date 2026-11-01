"""P3-T04: create a clean worktree at a commit, then destroy it."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fix_loop.worktree import create, destroy


def _git(repo: Path, *args: str, identity: bool = False) -> subprocess.CompletedProcess[str]:
    cmd = ["git", "-c", "core.autocrlf=false"]
    if identity:
        cmd += ["-c", "user.email=dev@example.com", "-c", "user.name=dev"]
    cmd += ["-C", str(repo), *args]
    return subprocess.run(cmd, check=True, capture_output=True, text=True, encoding="utf-8")


def _listed(repo: Path) -> list[Path]:
    text = _git(repo, "worktree", "list").stdout
    return [Path(line.split()[0]).resolve() for line in text.splitlines() if line.strip()]


def test_create_is_clean_at_base_commit_and_destroy_unlists_it(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    (repo / "a.txt").write_text("one\n", encoding="utf-8", newline="\n")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "-m", "one", identity=True)
    base = _git(repo, "rev-parse", "HEAD").stdout.strip()
    (repo / "a.txt").write_text("two\n", encoding="utf-8", newline="\n")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "-m", "two", identity=True)
    (repo / "a.txt").write_text("dirty\n", encoding="utf-8", newline="\n")

    path = create(repo, "bug-17", base, root=tmp_path / "work")

    assert _git(path, "rev-parse", "HEAD").stdout.strip() == base
    assert _git(path, "status", "--porcelain").stdout == ""
    assert _git(path, "show", "HEAD:a.txt").stdout == "one\n"
    assert (repo / "a.txt").read_text(encoding="utf-8") == "dirty\n"
    assert path.resolve() in _listed(repo)

    destroy(repo, path)

    assert path.resolve() not in _listed(repo)
    assert not path.exists()


def test_task_id_cannot_escape_the_root(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    (repo / "a.txt").write_text("one\n", encoding="utf-8", newline="\n")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "-m", "one", identity=True)
    base = _git(repo, "rev-parse", "HEAD").stdout.strip()
    with pytest.raises(ValueError):
        create(repo, "../elsewhere", base, root=tmp_path / "work")
