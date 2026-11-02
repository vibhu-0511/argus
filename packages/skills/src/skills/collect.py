"""P5.5-T04: copy the finished train runs into the committed data folder and write the ledger.

    python -m skills.collect [--runs packages/eval/runs/p55-t04] [--out packages/skills/trajectories]

Reads each run folder `eval.t14_turn` wrote for variant T (`verdict.json`, `fix/trajectory.jsonl`, `diff.patch`) and the
task folder it names (`ticket.json`, `meta.json`). A RESOLVED run is copied to `<out>/<task id>/` (trajectory, verdict, diff,
ticket text). Any other verdict keeps only its `verdict.json`, in `<out>/_unresolved/<task id>/`, so the success rate stays
honest. `<out>/ledger.json` has one row per finished run. A run with no `verdict.json` (stuck) is listed under `no_verdict`
and not copied. Tokens are the chars/4 estimates stored in the trajectory; there is no provider usage for Claude sessions.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
RUNS = ROOT / "packages" / "eval" / "runs" / "p55-t04"
OUT = ROOT / "packages" / "skills" / "trajectories"
# Mirrors eval.t14_turn.SELF_IMPOSED (300 requests, 10 million tokens per model). Not a provider limit: none exists for Claude sessions.
SELF_IMPOSED = {"requests": 300, "tokens": 10_000_000, "source": "eval.t14_turn.SELF_IMPOSED, not a provider limit"}


def _steps(trajectory: Path) -> tuple[int, int, int]:
    steps = [json.loads(line) for line in trajectory.read_text(encoding="utf-8").splitlines() if line]
    steps = [s for s in steps if s.get("kind") == "step"]
    return len(steps), sum(s["tokens_in"] for s in steps), sum(s["tokens_out"] for s in steps)


def collect(runs: Path, out: Path) -> dict:
    rows, no_verdict = [], []
    for run in sorted(runs.glob("mut-*")):
        if not (run / "task.json").is_file():
            continue
        if not (run / "verdict.json").is_file():
            no_verdict.append(run.name)
            continue
        verdict = json.loads((run / "verdict.json").read_text(encoding="utf-8"))
        task = Path(json.loads((run / "task.json").read_text(encoding="utf-8"))["task"])
        trajectory = run / "fix" / "trajectory.jsonl"
        steps, tin, tout = _steps(trajectory) if trajectory.is_file() else (0, 0, 0)
        rows.append({
            "task_id": run.name, "archetype": json.loads((task / "meta.json").read_text(encoding="utf-8")).get("archetype"),
            "verdict": verdict["verdict"], "stop_reason": verdict["stop_reason"], "steps": steps, "model_turns": verdict["model_turns"],
            "tokens_in": tin, "tokens_out": tout, "tokens_cached": 0, "wall_s": verdict.get("wall_s"),
        })
        if verdict["verdict"] == "resolved":
            dest = out / run.name
            dest.mkdir(parents=True, exist_ok=True)
            for name, src in (("trajectory.jsonl", trajectory), ("verdict.json", run / "verdict.json"), ("diff.patch", run / "diff.patch")):
                shutil.copyfile(src, dest / name)
            ticket = json.loads((task / "ticket.json").read_text(encoding="utf-8"))["text"]
            (dest / "ticket.txt").write_text(ticket + "\n", encoding="utf-8", newline="\n")
        else:
            dest = out / "_unresolved" / run.name
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(run / "verdict.json", dest / "verdict.json")
    tin, tout = sum(r["tokens_in"] for r in rows), sum(r["tokens_out"] for r in rows)
    ledger = {
        "token_source": "chars/4 estimate of the messages; excludes each subagent's harness overhead; no provider usage exists for Claude sessions",
        "self_imposed_budget": SELF_IMPOSED, "model": "claude-sonnet-5-5 (subagent model sonnet)",
        "runs": rows, "no_verdict": no_verdict,
        "totals": {
            "finished": len(rows), "resolved": sum(r["verdict"] == "resolved" for r in rows), "steps": sum(r["steps"] for r in rows),
            "tokens_in": tin, "tokens_out": tout, "share_of_self_imposed_tokens": round((tin + tout) / SELF_IMPOSED["tokens"], 4),
            "requests": sum(r["model_turns"] for r in rows),
        },
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "ledger.json").write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8", newline="\n")
    return ledger


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="skills.collect")
    parser.add_argument("--runs", type=Path, default=RUNS)
    parser.add_argument("--out", type=Path, default=OUT)
    ns = parser.parse_args(argv)
    totals = collect(ns.runs, ns.out)["totals"]
    print(json.dumps(totals))
    return 0


if __name__ == "__main__":
    sys.exit(main())
