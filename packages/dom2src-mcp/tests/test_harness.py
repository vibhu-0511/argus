import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "packages" / "repro-agent" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dom2src_mcp.harness import score

GOLDEN = "apps/canvas/src/ops/radar.css"
_DECOYS = (
    "apps/canvas/src/screens/Landing.tsx",
    "apps/canvas/src/screens/UserAdmin.tsx",
    "apps/canvas/src/ops/ops.css",
)


def _task(root: Path, name: str, patch: str) -> Path:
    task = root / name
    task.mkdir()
    (task / "golden.patch").write_text(patch, encoding="utf-8")
    return task


def test_stub_retriever_top1_and_top3(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    patch = f"--- a/{GOLDEN}\n+++ b/{GOLDEN}\n"
    tasks = [_task(tmp_path, f"task-{index}", patch) for index in (1, 2, 3)]
    # Rank 1, rank 2, and rank 4 (1-based) for the three tasks.
    ranks = {tasks[0]: 0, tasks[1]: 1, tasks[2]: 3}

    def retriever(task_dir: Path) -> list[str]:
        ranked = list(_DECOYS)
        ranked.insert(ranks[task_dir], GOLDEN)
        return ranked

    result = score(tasks, retriever)
    assert (result.top1, result.top3, result.total) == (1, 2, 3)
    printed = capsys.readouterr().out
    assert any("1/3" in line and "2/3" in line for line in printed.splitlines())


def test_golden_patch_without_a_path_raises(tmp_path: Path) -> None:
    task = _task(tmp_path, "deleted", "--- a/apps/canvas/src/ops/radar.css\n+++ b//dev/null\n")
    with pytest.raises(ValueError):
        score([task], lambda _task: [GOLDEN])
