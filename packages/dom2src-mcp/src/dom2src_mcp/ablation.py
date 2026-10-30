"""The P2-T12 ablation: three retrievers over the seeded tasks, with the raw per-task ranks.

    uv run python -m dom2src_mcp.ablation --reindex --out-dir docs/notes/results

Needs the pgvector container and ARGUS_PLATFORM_REPO (README). No model API is called.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime
import io
import math
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

from dom2src_mcp.embed import index_canvas
from dom2src_mcp.harness import _golden_paths, score
from dom2src_mcp.repo_map import platform_repo
from dom2src_mcp.retrievers import embed_files, locate_files, repo_map_files, seeded_tasks

VARIANTS: dict[str, Callable[[Path], list[str]]] = {"A": repo_map_files, "B": embed_files, "C": locate_files}


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


def _percentile(sorted_seconds: list[float], p: int) -> float:
    # nearest rank: index ceil(p/100*n)-1
    return sorted_seconds[math.ceil(p / 100 * len(sorted_seconds)) - 1]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="dom2src-ablation")
    parser.add_argument("--reindex", action="store_true", help="rebuild the pgvector table before scoring")
    parser.add_argument("--out-dir", type=Path, help="also write the output to <out-dir>/<run id>.txt")
    args = parser.parse_args(argv)

    out: list[str] = []

    def emit(line: str = "") -> None:
        print(line, flush=True)
        out.append(line)

    here = Path(__file__).resolve().parents[4]
    started = datetime.datetime.now(datetime.timezone.utc)
    run_id = "p2-abl-" + started.strftime("%Y%m%dT%H%M%SZ")
    dirty = bool(_git(here, "status", "--porcelain", "--", "packages", "TASKS.md"))
    emit(f"run id: {run_id}")
    emit("command: " + " ".join(["python", "-m", "dom2src_mcp.ablation", *(argv if argv is not None else sys.argv[1:])]))
    emit(f"argus: {_git(here, 'rev-parse', 'HEAD')}{' (working tree has uncommitted changes)' if dirty else ''}")
    emit(f"platform: {_git(platform_repo(), 'rev-parse', 'HEAD')}")
    if args.reindex:
        emit(f"reindexed files: {index_canvas()}")

    tasks = seeded_tasks()
    emit(f"tasks: {len(tasks)}")
    for name, retriever in VARIANTS.items():
        emit()
        emit(f"== variant {name}: {retriever.__name__}")
        retriever(tasks[0])  # one warmup call, not timed
        seconds: list[float] = []
        for task in tasks:
            begin = time.perf_counter()
            ranked = retriever(task)
            seconds.append(time.perf_counter() - begin)
            golden = ", ".join(sorted(_golden_paths(task)))
            emit(f"{task.name}: golden [{golden}] top3 {ranked[:3]}")
        seconds.sort()
        emit(f"latency p50 {_percentile(seconds, 50):.6f}s p95 {_percentile(seconds, 95):.6f}s over {len(seconds)} timed calls")
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            score(tasks, retriever)  # runs the retriever again and prints the accuracy line
        emit(buffer.getvalue().strip())
    if args.out_dir:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        (args.out_dir / f"{run_id}.txt").write_text("\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
