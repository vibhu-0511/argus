"""One git worktree per task, at that task's base commit."""

from __future__ import annotations

import subprocess
from pathlib import Path


def create(repo: Path, task_id: str, commit: str, *, root: Path) -> Path:
    """Add a detached worktree of `repo` at `commit`. The tree is clean."""
    repo = repo.resolve()
    dest = _dest(root, task_id)
    dest.parent.mkdir(parents=True, exist_ok=True)
    proc = _git(repo, "worktree", "add", "--detach", str(dest), commit)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "worktree add failed").strip())
    return dest


def destroy(repo: Path, path: Path) -> None:
    """Remove the worktree. `git worktree list` must not name it afterwards."""
    repo = repo.resolve()
    path = path.resolve()
    proc = _git(repo, "worktree", "remove", "--force", str(path))
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "worktree remove failed").strip())
    if path in _listed(repo):
        raise RuntimeError(f"worktree still listed: {path}")


def _dest(root: Path, task_id: str) -> Path:
    if not task_id or Path(task_id).name != task_id or task_id in {".", ".."}:
        raise ValueError("task id must be a single path segment")
    root = root.resolve()
    dest = (root / task_id).resolve()
    if dest.parent != root:
        raise ValueError("task id must be a single path segment")
    return dest


def _listed(repo: Path) -> list[Path]:
    proc = _git(repo, "worktree", "list")
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "worktree list failed").strip())
    found: list[Path] = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        found.append(Path(line.split()[0]).resolve())
    return found


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", "core.autocrlf=false", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
