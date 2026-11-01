"""Tally the stateless context ablation from run files. Run: PYTHONPATH=src python swarm/tally.py (as turn.sh sets it).

Only verdict.json and trajectory.jsonl are read. Tokens are chars/4 estimates from the trajectory step rows;
the summary strategy's own summarizer calls are not step rows, so its tokens are an undercount.
"""

import json
from collections import Counter
from pathlib import Path

from fix_loop.baseline import _wilson, rate_label

RUNS = Path(__file__).resolve().parents[1] / "runs"
STRATEGIES = ["none", "cap", "offload", "summary"]
TASKS = [f"{k}{i:02d}" for k, n in (("e", 10), ("m", 9), ("h", 10)) for i in range(1, n + 1)]
PILOT = {  # runs from the earlier pilot, different ids
    ("none", "e07"): "p4b-pilot-none2-e07", ("cap", "e07"): "p4b-pilot-cap-e07",
    ("offload", "e07"): "p4b-pilot-offload-e07", ("summary", "e07"): "p4b-pilot-summary3-e07",
}
STEP_ESTIMATE = 70_000  # subagent tokens per step; an estimate, not measured here


def run_id(strategy: str, task: str) -> str:
    if (strategy, task) in PILOT:
        return PILOT[(strategy, task)]
    if task in ("e05", "e08"):
        return f"p4b-pilot2-{strategy}-{task}"
    return f"p4b-full-{strategy}-{task}"


def mini_id(task: str) -> str:
    return "p4b-mini-e08b" if task == "e08" else f"p4b-mini-{task}"  # e08: p4b-mini-e08 is an aborted first attempt


def load(strategy: str, task: str) -> dict:
    folder = RUNS / (mini_id(task) if strategy == "mini" else run_id(strategy, task))
    verdict = json.loads((folder / "verdict.json").read_text(encoding="utf-8"))
    steps = [d for d in (json.loads(x) for x in (folder / "trajectory.jsonl").read_text(encoding="utf-8").splitlines() if x)
             if d.get("kind") == "step"]
    verdict["loop_steps"] = len(steps)
    verdict["tin"] = sum(s["tokens_in"] for s in steps)
    verdict["tout"] = sum(s["tokens_out"] for s in steps)
    verdict["tcached"] = sum(s["tokens_cached"] for s in steps)
    verdict["peak"] = max((s["tokens_in"] for s in steps), default=0)
    return verdict


def main() -> None:
    data = {(s, t): load(s, t) for s in STRATEGIES for t in TASKS}
    print(f"tasks {len(TASKS)}, runs {len(data)}")
    for s in STRATEGIES:
        rows = [data[(s, t)] for t in TASKS]
        kinds = Counter(r["verdict"] for r in rows)
        res, unres = kinds["resolved"], kinds["unresolved"]
        n = len(rows)
        print(f"\n{s}: resolved {res}, unresolved {unres}, excluded {kinds['excluded']}; "
              f"rate over resolved+unresolved {rate_label(res, res + unres)}")
        print(f"  mean model turns {sum(r['model_turns'] for r in rows) / n:.2f}, "
              f"mean loop steps {sum(r['loop_steps'] for r in rows) / n:.2f}, total model turns {sum(r['model_turns'] for r in rows)}")
        print(f"  stop reasons {dict(Counter(r['stop_reason'] for r in rows))}")
        print(f"  mean est. loop tokens per task: in {sum(r['tin'] for r in rows) / n:.0f}, out {sum(r['tout'] for r in rows) / n:.0f}, cached {sum(r['tcached'] for r in rows) / n:.0f}; "
              f"peak prompt mean {sum(r['peak'] for r in rows) / n:.0f}, max {max(r['peak'] for r in rows)}")
    turns = sum(r["model_turns"] for r in data.values())
    print(f"\ntotal model turns {turns}; estimate {turns} x about {STEP_ESTIMATE} = about {turns * STEP_ESTIMATE / 1e6:.0f}M subagent tokens (estimate)")
    print("\ntasks where the strategies disagree (none cap offload summary; R resolved, U unresolved, X excluded):")
    code = {"resolved": "R", "unresolved": "U", "excluded": "X"}
    for t in TASKS:
        row = [code[data[(s, t)]["verdict"]] for s in STRATEGIES]
        if len(set(row)) > 1:
            print(f"  {t}: {' '.join(row)}  turns {[data[(s, t)]['model_turns'] for s in STRATEGIES]}")
    print("\nexcluded runs:", [run_id(s, t) for (s, t), r in data.items() if r["verdict"] == "excluded"])
    mini()
    oneshot(data)


def mini() -> None:
    """Variant E (mini-swe-agent through the relay), 29 tasks, next to the stateless none row (variant A)."""
    rows = {t: load("mini", t) for t in TASKS}
    none = {t: load("none", t) for t in TASKS}
    kinds = Counter(r["verdict"] for r in rows.values())
    res, unres, n = kinds["resolved"], kinds["unresolved"], len(rows)
    turns = sum(r["model_turns"] for r in rows.values())
    print(f"{chr(10)}mini (variant E): resolved {res}, unresolved {unres}, excluded {kinds['excluded']}; rate {rate_label(res, res + unres)}")
    print(f"  mean model turns {turns / n:.2f}, total {turns}; stop reasons {dict(Counter(r['stop_reason'] for r in rows.values()))}")
    print(f"  mean est. loop tokens per task: in {sum(r['tin'] for r in rows.values()) / n:.0f}, out {sum(r['tout'] for r in rows.values()) / n:.0f}; "
          f"peak prompt mean {sum(r['peak'] for r in rows.values()) / n:.0f}, max {max(r['peak'] for r in rows.values())}")
    pair = Counter((none[t]["verdict"], rows[t]["verdict"]) for t in TASKS)
    print("  paired with none (A), (A, E): " + ", ".join(f"{a[0]}{e[0]}={c}" for (a, e), c in sorted(pair.items())) + "  (r resolved, u unresolved, e excluded)")
    print("  tasks where E differs from none (A):", {t: (none[t]["verdict"], rows[t]["verdict"]) for t in TASKS if none[t]["verdict"] != rows[t]["verdict"]})
    print("  tasks whose model_turns differs from the request files:", [t for t in TASKS if len(list((RUNS / mini_id(t) / "mini").glob("req-*.json"))) != rows[t]["model_turns"]])
    print(f"  estimate: {turns} turns x about {STEP_ESTIMATE} = about {turns * STEP_ESTIMATE / 1e6:.0f}M subagent tokens (estimate)")




def oneshot_id(task: str, lenient: bool) -> str:
    base = "p0c-oneshot-e02-rescore" if task == "e02" else f"p0c-oneshot-{task}"  # e02: first run failed git apply on a context-free diff, same reply re-scored
    return f"{base}-lenient" if lenient and (RUNS / f"{base}-lenient").is_dir() else base


def oneshot(data: dict) -> None:
    """P0-T28 one-shot baseline redone with claude-session: one call, no tools, 29 tasks, with the loop variants' deltas."""
    print()
    rows = {}
    for name, lenient in (("git apply", False), ("git apply, then GNU patch", True)):
        rows[name] = {t: json.loads((RUNS / oneshot_id(t, lenient) / "verdict.json").read_text(encoding="utf-8")) for t in TASKS}
        k = Counter(r["verdict"] for r in rows[name].values())
        n = len(rows[name])
        fails = [t for t, r in rows[name].items() if not r["applied"]]
        print(f"one-shot ({name}): resolved {k['resolved']}, unresolved {k['unresolved']}, excluded {k['excluded']}; rate {rate_label(k['resolved'], k['resolved'] + k['unresolved'])}; "
              f"diff did not apply: {fails}; mean est. tokens in {sum(r['tokens_in'] for r in rows[name].values()) / n:.0f}, out {sum(r['tokens_out'] for r in rows[name].values()) / n:.0f}")
    base = rows["git apply, then GNU patch"]
    res, att = sum(r["verdict"] == "resolved" for r in base.values()), sum(r["verdict"] != "excluded" for r in base.values())
    lo, hi = _wilson(res, att)
    print(f"deltas against the one-shot row (GNU patch fallback) {res}/{att} = {100 * res / att:.1f}%:")
    variants = {f"{s}": [data[(s, t)]["verdict"] for t in TASKS] for s in STRATEGIES}
    variants["mini"] = [load("mini", t)["verdict"] for t in TASKS]
    for name, verdicts in variants.items():
        r2, a2 = verdicts.count("resolved"), len(verdicts) - verdicts.count("excluded")
        l2, h2 = _wilson(r2, a2)
        both = sum(1 for t, v in zip(TASKS, verdicts) if v == "resolved" and base[t]["verdict"] == "resolved")
        only_loop = sum(1 for t, v in zip(TASKS, verdicts) if v == "resolved" and base[t]["verdict"] != "resolved")
        only_one = sum(1 for t, v in zip(TASKS, verdicts) if v != "resolved" and base[t]["verdict"] == "resolved")
        print(f"  {name}: {r2}/{a2} = {100 * r2 / a2:.1f}%, delta {100 * r2 / a2 - 100 * res / att:+.1f} points; intervals overlap: {not (l2 > hi or lo > h2)}; "
              f"both resolved {both}, only {name} {only_loop}, only one-shot {only_one}")


if __name__ == "__main__":
    main()
