"""Bench commands. validate, score, golden, flake, baseline, and mutate."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pydantic import ValidationError

from argus_bench.baseline import baseline_task
from argus_bench.flake import flake_all
from argus_bench.golden import golden_all
from argus_bench.mutate import mutate_all
from argus_bench.score import score_task
from argus_bench.task_dir import load_task_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bench")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="check a task directory against the Task schema")
    validate.add_argument("directory")
    score = sub.add_parser("score", help="run a task's checks against a tree")
    score.add_argument("task")
    score.add_argument("--tree", required=True)
    golden = sub.add_parser("golden", help="apply each golden patch and score it")
    golden.add_argument("--all", action="store_true")
    flake = sub.add_parser("flake", help="repeat checks and quarantine mixed results")
    flake.add_argument("--all", action="store_true")
    baseline = sub.add_parser("baseline", help="one model call from the ticket and file text")
    baseline.add_argument("task")
    baseline.add_argument("--tree", required=True)
    mutate = sub.add_parser("mutate", help="write validated CSS mutants for one seed")
    mutate.add_argument("--seed", type=int, required=True)
    args = parser.parse_args(argv)
    if args.command == "validate":
        return _validate(Path(args.directory))
    if args.command == "score":
        return score_task(args.task, Path(args.tree))
    if args.command == "golden":
        if not args.all:
            print("golden needs --all", file=sys.stderr)
            return 2
        return golden_all()
    if args.command == "flake":
        if not args.all:
            print("flake needs --all", file=sys.stderr)
            return 2
        return flake_all()
    if args.command == "baseline":
        return baseline_task(args.task, Path(args.tree))
    if args.command == "mutate":
        return mutate_all(args.seed)
    return 2


def _validate(directory: Path) -> int:
    try:
        load_task_dir(directory)
    except (OSError, ValidationError, ValueError, KeyError) as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"valid {directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
