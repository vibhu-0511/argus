"""Top-1 and top-3 file accuracy against the files a golden patch touches."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

# repro-agent is a workspace member, not a dependency of this package.
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "packages" / "repro-agent" / "src"))

from repro_agent.batch import rate_label, wilson_interval


class Accuracy(NamedTuple):
    top1: int
    top3: int
    total: int


def _golden_paths(task_dir: Path) -> set[str]:
    found: list[str] = []
    patch = (task_dir / "golden.patch").read_text(encoding="utf-8")
    for line in patch.splitlines():
        if not line.startswith("+++ b/"):
            continue
        path = line[6:].split("\t", 1)[0].strip()
        if not path or path == "/dev/null" or path in found:
            continue
        found.append(path)
    if not found:
        raise ValueError(f"no golden path in {task_dir / 'golden.patch'}")
    return set(found)


def _label(successes: int, total: int) -> str:
    low, high = wilson_interval(successes, total)
    label = rate_label(successes, total)
    if label != f"{successes}/{total} [{low:.6f}, {high:.6f}]":
        raise RuntimeError(label)
    return label


def score(tasks: list[Path], retriever: Callable[[Path], list[str]]) -> Accuracy:
    """Score `retriever` on each task dir. Prints top-1 and top-3, and returns the counts."""
    top1 = 0
    top3 = 0
    for task in tasks:
        golden = _golden_paths(task)
        ranked = retriever(task)
        if ranked and ranked[0] in golden:
            top1 += 1
        if any(path in golden for path in ranked[:3]):
            top3 += 1
    total = len(tasks)
    print(f"top-1 {_label(top1, total)} top-3 {_label(top3, total)}")
    return Accuracy(top1, top3, total)
