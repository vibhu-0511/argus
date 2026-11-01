"""Score fix-loop runs again from their saved diff.patch.

    python rescore_runs.py <run id> [<run id> ...]

`fix_loop.turn` scores the worktree it just edited, then deletes it. When that score crashed (exit 2) the tree is gone,
but `diff.patch` (the final tree against platform HEAD) is kept. This applies it to a fresh worktree of platform HEAD and
runs `bench score` on that. The original `verdict.json` is left as it was; the result goes to `verdict.rescored.json`.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from common import PLATFORM, RUNS, SEEDED

BENCH = Path(r"C:\Users\vibha\Downloads\data\personal\argus\.venv\Scripts\bench.exe")


def rescore(run: str) -> dict:
    out = RUNS / run
    task = json.loads((out / "task.json").read_text(encoding="utf-8"))["task"]
    task_dir = SEEDED / Path(task).name
    diff = (out / "diff.patch").read_bytes()
    with tempfile.TemporaryDirectory() as tmp:
        tree = Path(tmp) / "wt"
        subprocess.run(["git", "-C", str(PLATFORM), "worktree", "add", "--detach", str(tree), "HEAD"], check=True, capture_output=True)
        try:
            if diff.strip():
                (Path(tmp) / "d.patch").write_bytes(diff)
                subprocess.run(["git", "-C", str(tree), "apply", str(Path(tmp) / "d.patch")], check=True, capture_output=True)
            done = subprocess.run([str(BENCH), "score", str(task_dir), "--tree", str(tree)], capture_output=True, text=True, cwd=RUNS.parents[2])
        finally:
            subprocess.run(["git", "-C", str(PLATFORM), "worktree", "remove", "--force", str(tree)], capture_output=True)
    verdict = json.loads((out / "verdict.json").read_text(encoding="utf-8"))
    result = {
        "run_id": run, "task_id": verdict["task_id"], "stop_reason": verdict["stop_reason"], "model_turns": verdict["model_turns"],
        "score_exit": done.returncode, "verdict": "excluded" if done.returncode == 2 else "resolved" if done.returncode == 0 else "unresolved",
        "empty_diff": not diff.strip(), "model": verdict["model"],
        "note": "rescored from diff.patch on a fresh platform worktree; the original verdict.json came from a scorer that could not find @playwright/test in this checkout",
    }
    (out / "verdict.rescored.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    for run_id in sys.argv[1:]:
        print(json.dumps(rescore(run_id)))
