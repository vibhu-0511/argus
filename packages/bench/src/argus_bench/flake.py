"""Quarantine a task when repeated scores disagree or hit infra."""

from __future__ import annotations

import contextlib
import io
import shutil
import subprocess
import tempfile
from pathlib import Path

_BENCH = Path(__file__).resolve().parents[2]
_RUNS = 5


def flake_all(score=None, *, tasks=None, buggy=None, golden=None, quarantine=None) -> int:
    dest = _BENCH / "quarantine" if quarantine is None else Path(quarantine)
    if score is not None and tasks is not None and buggy is not None and golden is not None:
        return _given(tasks, score, buggy, golden, dest)
    return _repo(dest)


def _given(tasks, score, buggy, golden, dest: Path) -> int:
    moved = False
    for task in tasks:
        path = Path(task)
        buggy_codes = [score(task, buggy) for _ in range(_RUNS)]
        golden_codes = [score(task, golden) for _ in range(_RUNS)]
        moved |= _take(path, buggy_codes, golden_codes, dest)
    return int(moved)


def _take(task: Path, buggy_codes: list[int], golden_codes: list[int], dest: Path) -> bool:
    flaky = (
        len(set(buggy_codes)) != 1
        or len(set(golden_codes)) != 1
        or any(code == 2 for code in (*buggy_codes, *golden_codes))
    )
    if not flaky:
        return False
    dest.mkdir(parents=True, exist_ok=True)
    shutil.move(task, dest / task.name)
    print(task.name)
    return True


def _repo(dest: Path) -> int:
    from argus_bench.golden import platform_repo, task_dirs
    from argus_bench.score import score_task

    repo = platform_repo()
    work = Path(tempfile.mkdtemp(prefix="argus-flake-"))
    added = subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "--detach", str(work), "HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if added.returncode != 0:
        print(added.stderr or added.stdout, end="")
        return 2
    moved = False
    try:
        for task in task_dirs():
            buggy_codes = _times(work, task, buggy=True, score=score_task)
            golden_codes = _times(work, task, buggy=False, score=score_task)
            moved |= _take(task, buggy_codes, golden_codes, dest)
    finally:
        subprocess.run(["git", "-C", str(repo), "worktree", "remove", "--force", str(work)], check=False)
    return int(moved)


def _times(work: Path, task: Path, *, buggy: bool, score) -> list[int]:
    if not _place(work, task, buggy=buggy):
        return [2] * _RUNS
    codes: list[int] = []
    for _ in range(_RUNS):
        with contextlib.redirect_stdout(io.StringIO()):
            codes.append(score(str(task), work))
    return codes


def _place(work: Path, task: Path, *, buggy: bool) -> bool:
    subprocess.run(["git", "-C", str(work), "checkout", "--", "."], check=False, capture_output=True)
    bug = (task / "bug.patch").read_text(encoding="utf-8")
    golden = (task / "golden.patch").read_text(encoding="utf-8")
    if _apply(work, bug, check=True):
        if not buggy:
            return True
        return _apply(work, bug, check=False)
    if not _apply(work, golden, check=True):
        return False
    if buggy:
        return True
    return _apply(work, golden, check=False)


def _apply(work: Path, patch: str, check: bool) -> bool:
    cmd = ["git", "-C", str(work), "apply"]
    if check:
        cmd.append("--check")
    proc = subprocess.run(cmd, input=patch, text=True, capture_output=True, encoding="utf-8")
    return proc.returncode == 0
