"""Apply each golden patch and score the restored tree."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from argus_bench.score import score_task

_BENCH = Path(__file__).resolve().parents[2]
_REPO = _BENCH.parents[1]


def platform_repo(root: Path | None = None) -> Path:
    text = ((root or _REPO) / "config" / "platform.md").read_text(encoding="utf-8")
    for line in text.splitlines():
        if not line.startswith("| Repo |"):
            continue
        start = line.find("`")
        end = line.find("`", start + 1)
        if start < 0 or end < 0:
            break
        return Path(line[start + 1 : end])
    raise FileNotFoundError("config/platform.md has no Repo path")


def task_dirs(root: Path | None = None) -> list[Path]:
    base = root or (_BENCH / "tasks")
    found: list[Path] = []
    for kind in ("seeded", "mutated"):
        directory = base / kind
        if directory.is_dir():
            found.extend(sorted(path for path in directory.iterdir() if path.is_dir()))
    return found


def golden_all(tree: Path | None = None, tasks: list[Path] | None = None) -> int:
    repo = tree or platform_repo()
    found = list(tasks) if tasks is not None else task_dirs()
    if not found:
        print("0/0")
        return 1
    work = Path(tempfile.mkdtemp(prefix="argus-golden-"))
    added = subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "--detach", str(work), "HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if added.returncode != 0:
        print(added.stderr or added.stdout, end="")
        return 2
    passed = 0
    try:
        for task in found:
            if _one(work, task) == 0:
                passed += 1
                print(f"pass {task.name}")
            else:
                print(f"fail {task.name}")
    finally:
        subprocess.run(["git", "-C", str(repo), "worktree", "remove", "--force", str(work)], check=False)
    print(f"{passed}/{len(found)}")
    return 0 if passed == len(found) else 1


def _apply(work: Path, patch: str, check: bool) -> bool:
    cmd = ["git", "-C", str(work), "apply"]
    if check:
        cmd.append("--check")
    proc = subprocess.run(cmd, input=patch, text=True, capture_output=True, encoding="utf-8")
    return proc.returncode == 0


def _one(work: Path, task: Path) -> int:
    subprocess.run(["git", "-C", str(work), "checkout", "--", "."], check=False, capture_output=True)
    bug = (task / "bug.patch").read_text(encoding="utf-8")
    golden = (task / "golden.patch").read_text(encoding="utf-8")
    if _apply(work, bug, check=True):
        if not _apply(work, bug, check=False):
            return 2
        if not _apply(work, golden, check=False):
            return 2
    elif _apply(work, golden, check=True):
        if not _apply(work, golden, check=False):
            return 2
    else:
        return 2
    code = score_task(str(task), work)
    if code == 2:
        code = score_task(str(task), work)
    return code
