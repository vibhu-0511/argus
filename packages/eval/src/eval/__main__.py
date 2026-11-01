"""python -m eval metrics <dir> | run --tasks F --agent F --out F | schema"""

from __future__ import annotations

import argparse
from pathlib import Path

from eval.gate import gate_main
from eval.metrics import format_summary, load_dir, summarize
from eval.report import report_files
from eval.results import schema_json
from eval.runner import AgentConfig, load_agent, load_tasks, run_eval


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="eval")
    sub = parser.add_subparsers(dest="command", required=True)

    metrics = sub.add_parser("metrics", help="print trajectory metrics for a directory")
    metrics.add_argument("directory", type=Path)
    metrics.add_argument("--glob", default="**/trajectory.jsonl", help="pattern under the directory")
    metrics.add_argument("--json", action="store_true", help="print the summary as JSON")

    run = sub.add_parser("run", help="run an agent over a task list and write one results JSON")
    run.add_argument("--tasks", type=Path, required=True, help="JSON array of argus_core Task objects")
    run.add_argument("--agent", type=Path, required=True, help="JSON agent config (name, model, factory, params)")
    run.add_argument("--out", type=Path, required=True)
    run.add_argument("--run-id", help="default: the agent name")

    report = sub.add_parser("report", help="print the phase report table from <previous.json> <this.json>")
    report.add_argument("files", type=Path, nargs="*", help="none: empty template; one: this phase; two: previous, this")

    sub.add_parser("schema", help="print the results JSON Schema")

    gate = sub.add_parser("gate", help="compare a results file with a baseline; exit 1 on a regression")
    gate.add_argument("results", type=Path)
    gate.add_argument("--baseline", type=Path, required=True)
    gate.add_argument("--config", type=Path, help="default: packages/eval/gate.toml")

    args = parser.parse_args(argv)
    if args.command == "gate":
        return gate_main(args.results, args.baseline, args.config)
    if args.command == "schema":
        print(schema_json(), end="")
    elif args.command == "report":
        print(report_files(args.files), end="")
    elif args.command == "run":
        config = AgentConfig.model_validate_json(args.agent.read_text(encoding="utf-8"))
        results = run_eval(load_tasks(args.tasks), load_agent(config), config, run_id=args.run_id)
        args.out.write_text(results.to_json(), encoding="utf-8")
        rate = results.resolve_rate
        print(f"{results.run_id}: {rate.successes}/{rate.total} resolved, wrote {args.out}")
    else:
        summary = summarize(load_dir(args.directory, args.glob))
        print(summary.model_dump_json(indent=2) if args.json else format_summary(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
