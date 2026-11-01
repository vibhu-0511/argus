"""P4-T20 pilot table: best-of-k, k = 1, 3, 5, from stored fix-loop runs.

    python t20_results.py <run id> [all] > packages/fix-loop/runs/<run id>.json   (`all`: every P3 task, not the 3-task pilot)

Draw 1 of each task is the P3 variant A run; draws 2 to 5 are the `p4-t20-<task>-d<n>` runs. Every draw is one Claude
session as the model (`claude-session`). The verifier handed to `best_of_k` is the task's own scorer (`bench score`),
so the selection is by an oracle: this measures what extra draws buy when the selector is perfect, not how good the
judge-plus-checks selector is. The judge was not used.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from common import RUNS

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from verify.alpha import wilson  # noqa: E402
from verify.best_of_k import UsageLedger, best_of_k  # noqa: E402
from verify.pipeline import CheckResult, Verdict  # noqa: E402

P3_TABLE = json.loads((RUNS / "p3-a-claude-results.json").read_text(encoding="utf-8"))
TIER = {row["task"]: row["tier"] for row in P3_TABLE}
P3_RUN = {row["task"]: row["run"] for row in P3_TABLE if row["verdict"] != "excluded"}
TASKS = tuple(sorted(P3_RUN)) if len(sys.argv) > 2 and sys.argv[2] == "all" else ("seed-e03", "seed-e05", "seed-e06")


def draw_runs(task: str) -> list[str]:
    """Draw 1 is the P3 run. Draws 2 to 5 are the T20 runs. A `-retry` is used only when the original has no verdict
    (a retry for a run that did finish would be a resample, which favours the result)."""
    runs = [P3_RUN[task]]
    for n in (2, 3, 4, 5):
        base = f"p4-t20-{task}-d{n}"
        retry = f"{base}-retry"
        runs.append(base if (RUNS / base / "verdict.json").exists() or not (RUNS / retry / "verdict.json").exists() else retry)
    return runs


def load(run: str) -> dict:
    out = RUNS / run
    verdict = json.loads((out / ("verdict.rescored.json" if (out / "verdict.rescored.json").exists() else "verdict.json")).read_text(encoding="utf-8"))
    steps = [json.loads(line) for line in (out / "trajectory.jsonl").read_text(encoding="utf-8").splitlines() if '"kind":"step"' in line.replace(" ", "")]
    return {
        "run_id": run, "verdict": verdict["verdict"], "stop_reason": verdict["stop_reason"], "model_turns": verdict["model_turns"],
        "tokens_in": sum(s["tokens_in"] for s in steps), "tokens_out": sum(s["tokens_out"] for s in steps),
        "tokens_cached": sum(s["tokens_cached"] for s in steps),
        "patch": (out / "diff.patch").read_text(encoding="utf-8"),
        "scored_from": "verdict.rescored.json" if (out / "verdict.rescored.json").exists() else "verdict.json",
    }


def main(run_id: str) -> None:
    draws = {task: [load(r) for r in draw_runs(task)] for task in TASKS}
    per_k = {}
    for k in (1, 3, 5):
        solved, tokens, selections = 0, [], {}
        for task in TASKS:
            ledger = UsageLedger()
            rows = draws[task]

            def draw(i: int, rows=rows):
                row = rows[i]
                return row["patch"] or f"<empty diff: tree equals platform HEAD> {row['run_id']}", (row["tokens_in"], row["tokens_out"], row["tokens_cached"])

            def verify(patch: str, rows=rows, task=task) -> Verdict:
                row = next(r for r in rows if (r["patch"] or f"<empty diff: tree equals platform HEAD> {r['run_id']}") == patch)
                ok = row["verdict"] == "resolved"
                return Verdict(ok, (CheckResult("bench-score", ok, True, row["verdict"]),), None if ok else row["verdict"], None if ok else "bench-score")

            picked = best_of_k(k, draw=draw, verify=verify, judge=lambda _patch: "pass", ledger=ledger)
            solved += picked.selected is not None
            tokens.append(sum(r["tokens_in"] + r["tokens_out"] for r in ledger.rows))
            selections[task] = {"selected_index": None if picked.selected is None else picked.selected.index, "reason": picked.reason}
        p, low, high = wilson(solved, len(TASKS))
        tiers = {}
        for tier in ("easy", "medium", "hard"):
            members = [t for t in TASKS if TIER[t] == tier]
            if members:
                hit = sum(selections[t]["selected_index"] is not None for t in members)
                tiers[tier] = f"{hit}/{len(members)}"
        per_k[str(k)] = {"by_tier": tiers, "resolved": solved, "tasks": len(TASKS), "rate": round(p, 4), "wilson95": [round(low, 4), round(high, 4)],
                         "mean_loop_tokens_in_plus_out_per_task": round(sum(tokens) / len(tokens)), "selections": selections}
    every = [d for rows in draws.values() for d in rows]
    single = sum(d["verdict"] == "resolved" for d in every)
    out = {
        "run_id": run_id, "model": "claude-session", "tasks": list(TASKS),
        "selector": "task scorer (oracle); the judge was not used",
        "draws": {t: [{k: v for k, v in d.items() if k != "patch"} for d in rows] for t, rows in draws.items()},
        "all_draws_resolved": f"{single}/{len(every)}",
        "best_of_k": per_k,
        "token_source": "chars/4 estimate of the loop's messages, not provider usage",
    }
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
