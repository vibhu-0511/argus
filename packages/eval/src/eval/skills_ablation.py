"""P5.5-T08: the with-skills vs without-skills table, read only from stored run folders.

    python -m eval.skills_ablation <without dir> <with dir> [--split packages/skills/split.json]

Each directory holds one folder per task with `verdict.json` and `fix/trajectory.jsonl` (the shape `eval.t14_turn` writes).
Both rows are measured on the fix stage only: the repro stage of variant A found nothing in 29 of 29 runs and its turns never
reached the fix prompt, so they are left out of the tokens and steps of both rows (the stored A total is printed too).
A run the scorer could not score (`excluded`) is out of the denominators and out of the paired comparison. `loaded` is
`fix_loop.skills.loaded_names` on the stored trajectory. Nothing here calls a model.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from argus_core.types import Trajectory

from eval.ablation import _totals
from eval.stats import percentile, wilson
from fix_loop.skills import loaded_names

SPLIT = Path(__file__).resolve().parents[3] / "skills" / "split.json"


@dataclass(frozen=True)
class Run:
    task: str
    verdict: str
    steps: int
    tokens_in: int
    tokens_out: int
    dollars: float | None
    wall_s: float | None
    loaded: tuple[str, ...]
    stop: str
    turns_total: int  # every model turn of the run, repro stage included
    fix_turns: int  # worker steps of the fix stage (the answers, a few more than the trajectory steps when a reply was rejected)


def held_out(split: Path = SPLIT) -> list[str]:
    return [t["id"] for t in json.loads(split.read_text(encoding="utf-8"))["held_out"] if t["runnable"]]


def read_run(folder: Path) -> Run | None:
    """None when the run has no verdict.json (it did not finish)."""
    try:
        verdict = json.loads((folder / "verdict.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    path = folder / "fix" / "trajectory.jsonl"
    steps = Trajectory.from_jsonl(path.read_text(encoding="utf-8")).steps
    tin, tout, _cached, dollars = _totals([path])
    return Run(
        folder.name, verdict["verdict"], len(steps), tin, tout, dollars, verdict.get("wall_s"), tuple(loaded_names(steps)), verdict["stop_reason"],
        verdict["model_turns"], verdict["turns_by_stage"].get("fix", 0),
    )


def read_row(root: Path, tasks: list[str]) -> dict[str, Run | None]:
    return {t: read_run(root / t) for t in tasks}


def _scored(row: dict[str, Run | None]) -> dict[str, Run]:
    return {t: r for t, r in row.items() if r is not None and r.verdict != "excluded"}


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def summary(name: str, row: dict[str, Run | None]) -> list[str]:
    runs = [r for r in row.values() if r is not None]
    scored = _scored(row)
    resolved = sum(r.verdict == "resolved" for r in scored.values())
    low, high = wilson(resolved, len(scored))
    loads = [len(r.loaded) for r in runs]
    wall = [r.wall_s for r in runs if r.wall_s is not None]
    return [
        f"| {name} | {resolved / len(scored):.1%} ({resolved}/{len(scored)}) [{low:.1%}, {high:.1%}] "
        f"| {_mean([r.tokens_in for r in scored.values()]):,.0f} / {_mean([r.tokens_out for r in scored.values()]):,.0f} / 0 "
        f"| {_mean([r.steps for r in scored.values()]):.1f} "
        f"| {'${:.4f}'.format(_mean([r.dollars for r in scored.values()])) if all(r.dollars is not None for r in scored.values()) else '-'} "
        f"| {percentile(wall, 50):,.0f} s / {percentile(wall, 95):,.0f} s | {sum(loads)} in {sum(1 for n in loads if n)} of {len(runs)} runs |"
    ]


def paired(a: dict[str, Run | None], b: dict[str, Run | None]) -> tuple[Counter, dict[str, list[str]]]:
    sa, sb = _scored(a), _scored(b)
    cells: dict[str, list[str]] = {"both": [], "neither": [], "without only": [], "with only": []}
    for t in sorted(set(sa) & set(sb)):
        ra, rb = sa[t].verdict == "resolved", sb[t].verdict == "resolved"
        cells["both" if ra and rb else "neither" if not ra and not rb else "without only" if ra else "with only"].append(t)
    return Counter({k: len(v) for k, v in cells.items()}), cells


def report(without: dict[str, Run | None], with_skills: dict[str, Run | None]) -> str:
    out = [
        "| Row | Resolve rate (95% CI, Wilson) | Tokens/bug in / out / cached (fix stage, chars/4) | Fix steps/bug | $-equivalent/bug | p50 / p95 wall | Skills loaded |",
        "|---|---|---|---|---|---|---|",
        *summary("without skills (P5-T14 variant A, stored)", without),
        *summary("with skills (variant S)", with_skills),
        "",
    ]
    counts, cells = paired(without, with_skills)
    out.append(f"Paired on {sum(counts.values())} tasks scored in both rows: " + ", ".join(f"{k} {v}" for k, v in counts.items()))
    for key, tasks in cells.items():
        if key in ("without only", "with only") and tasks:
            out.append(f"- {key}: {', '.join(tasks)}")
    excluded = {n: sorted(t for t, r in row.items() if r is not None and r.verdict == "excluded") for n, row in (("without", without), ("with", with_skills))}
    unfinished = {n: sorted(t for t, r in row.items() if r is None) for n, row in (("without", without), ("with", with_skills))}
    out.append(f"Excluded by the scorer (exit 2): {excluded}. Without a verdict: {unfinished}.")
    out.append(f"Worker steps (model turns): fix stage without {sum(r.fix_turns for r in without.values() if r)}, with {sum(r.fix_turns for r in with_skills.values() if r)}; "
               f"all stages incl. repro without {sum(r.turns_total for r in without.values() if r)}, with {sum(r.turns_total for r in with_skills.values() if r)}. "
               f"Trajectory steps: without {sum(r.steps for r in without.values() if r)}, with {sum(r.steps for r in with_skills.values() if r)}.")
    names = Counter(n for r in with_skills.values() if r for n in r.loaded)
    out += ["", "Skills loaded, runs that loaded each (row with skills): " + (", ".join(f"{k} {v}" for k, v in sorted(names.items())) or "none"), "",
            "| Task | Without | With | Steps without / with | Skills loaded (with) | Stop (with) |", "|---|---|---|---|---|---|"]
    for t in sorted(set(without) | set(with_skills)):
        a, b = without.get(t), with_skills.get(t)
        out.append(f"| {t} | {a.verdict if a else 'no verdict'} | {b.verdict if b else 'no verdict'} | {a.steps if a else '-'} / {b.steps if b else '-'} "
                   f"| {', '.join(b.loaded) if b and b.loaded else 'none'} | {b.stop if b else '-'} |")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="eval.skills_ablation")
    parser.add_argument("without", type=Path)
    parser.add_argument("with_skills", type=Path)
    parser.add_argument("--split", type=Path, default=SPLIT)
    args = parser.parse_args(argv)
    tasks = held_out(args.split)
    print(f"held-out runnable tasks: {len(tasks)}")
    print(report(read_row(args.without, tasks), read_row(args.with_skills, tasks)), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
