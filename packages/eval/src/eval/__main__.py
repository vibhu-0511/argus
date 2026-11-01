"""python -m eval metrics <dir> [--glob PATTERN] [--json]"""

from __future__ import annotations

import argparse
from pathlib import Path

from eval.metrics import format_summary, load_dir, summarize


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="eval")
    sub = parser.add_subparsers(dest="command", required=True)
    metrics = sub.add_parser("metrics", help="print trajectory metrics for a directory")
    metrics.add_argument("directory", type=Path)
    metrics.add_argument("--glob", default="**/trajectory.jsonl", help="pattern under the directory")
    metrics.add_argument("--json", action="store_true", help="print the summary as JSON")
    args = parser.parse_args(argv)

    summary = summarize(load_dir(args.directory, args.glob))
    print(summary.model_dump_json(indent=2) if args.json else format_summary(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
