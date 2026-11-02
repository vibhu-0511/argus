"""P5.5-T03 train and held-out split. The committed result is `packages/skills/split.json`.

Later tasks read that file and nothing else: T04 (collect trajectories) runs the `train` ids in order, T08 (ablation)
runs the `held_out` ids whose `runnable` flag is true. Never pick tasks any other way.

    uv run python -m skills.split split    # rewrite split.json from the task folders
    uv run python -m skills.split check    # exit 1 on a shared id, a shared (file, operator) pair, or a stale file

Held-out: every directory in `packages/bench/tasks/seeded` (30; `bug-17` no longer applies to platform HEAD, so 29
are flagged runnable, as in `eval.ablation tasks`). Train: generated mutants in `packages/bench/tasks/mutated`.

A task's pairs are the (source file, operator) combinations its `bug.patch` makes. Mutant `meta.json` records the
archetype but not the operator, and seeded tasks record neither, so both are derived from the patch (`pairs`):
the declaration a hunk changes names the operator, and an unreadable hunk falls back to every operator of the
task's archetype (docs/bug-archetypes.md, bugsmith `OPERATOR_ARCHETYPE`). The check is strict: a train candidate
that shares any pair with any held-out task is dropped before selection.

ponytail: the operator is read from the patch text, not from the generator. A pure deletion reads as `delete-rule`,
which can over-claim a pair (safe for an overlap check). Upgrade path: have `argus_bench.mutate` write `operator`
into meta.json.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from itertools import zip_longest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
TASKS = ROOT / "packages" / "bench" / "tasks"
SPLIT = ROOT / "packages" / "skills" / "split.json"
NOT_RUNNABLE = ("bug-17",)  # no longer applies to platform HEAD (docs/notes/p4-finish.md)
PER_ARCHETYPE = 20  # 2 archetypes exist among mutants today, so 40 train tasks
TIERS = ("easy", "medium", "hard")

# bugsmith OPERATOR_ARCHETYPE, inverted (packages/bugsmith/src/index.ts)
ARCHETYPE_OPERATORS = {
    "missing-style": ("delete-rule", "remove-class"),
    "font-size": ("change-unit",),
    "flex-direction": ("swap-flex-direction",),
    "overflow": ("overflow",),
    "z-index": ("z-index",),
    "wrong-element": ("drop-prop", "change-element"),
}
RULE = (
    f"train = {PER_ARCHETYPE} mutants per archetype, spread over source files (files take turns, each file's picks "
    "evenly spaced by id), only mutants sharing no (file, operator) pair with any held-out task; ordered by tier "
    "then interleaved by archetype; held-out = all seeded tasks. No randomness."
)
_DECL = re.compile(r"([\w-]+)\s*:\s*([^;{}]+)")
_PX = re.compile(r"^\d+(?:\.\d+)?px$")


def _hunks(patch: str):
    """Yield (file, removed lines, added lines) for each hunk of a unified diff."""
    path, minus, plus = None, [], []
    for line in patch.splitlines():
        if line.startswith(("+++ ", "@@")):
            if minus or plus:
                yield path, minus, plus
            minus, plus = [], []
            if line.startswith("+++ "):
                path = line[4:].removeprefix("b/")
        elif line.startswith("-") and not line.startswith("---"):
            minus.append(line[1:])
        elif line.startswith("+"):
            plus.append(line[1:])
    if minus or plus:
        yield path, minus, plus


def _decls(lines: list[str]) -> Counter:
    return Counter((m[1], m[2].strip()) for line in lines for m in _DECL.finditer(line))


def _hunk_operators(minus: list[str], plus: list[str], archetype: str) -> set[str]:
    fallback = set(ARCHETYPE_OPERATORS[archetype])
    if not any(line.strip() for line in plus):
        return {"delete-rule"}
    old, new = _decls(minus), _decls(plus)
    gone, came = old - new, new - old
    ops: set[str] = set()
    for prop in {p for p, _ in gone} | {p for p, _ in came}:
        values = [v for p, v in (*gone, *came) if p == prop]
        if prop == "z-index":
            ops.add("z-index")
        elif prop.startswith("overflow"):
            ops.add("overflow")
        elif prop == "flex-direction":
            ops.add("swap-flex-direction")
        elif all(_PX.match(v) for v in values):
            ops.add("change-unit")
        else:
            ops |= fallback
    return ops or fallback


def pairs(task_dir: Path) -> set[tuple[str, str]]:
    archetype = json.loads((task_dir / "meta.json").read_text(encoding="utf-8"))["archetype"]
    patch = (task_dir / "bug.patch").read_text(encoding="utf-8")
    return {(path, op) for path, minus, plus in _hunks(patch) for op in _hunk_operators(minus, plus, archetype)}


def _select(candidates: dict[str, dict]) -> list[str]:
    """candidates: id -> {archetype, tier, file}. Deterministic: a fixed rule, no random calls."""
    groups: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for task_id, c in sorted(candidates.items()):
        groups[c["archetype"]][c["file"]].append(task_id)
    picked: dict[str, list[str]] = {}
    for archetype, files in sorted(groups.items()):
        quota, left = dict.fromkeys(files, 0), PER_ARCHETYPE
        while left and any(quota[f] < len(files[f]) for f in files):
            for f in sorted(files):
                if left and quota[f] < len(files[f]):
                    quota[f] += 1
                    left -= 1
        picked[archetype] = sorted(
            ids[j * len(ids) // quota[f]] for f, ids in files.items() for j in range(quota[f])
        )
    order = [i for row in zip_longest(*(picked[a] for a in sorted(picked))) for i in row if i]
    return sorted(order, key=lambda i: TIERS.index(candidates[i]["tier"]))  # stable: easy first


def build(tasks: Path = TASKS) -> dict:
    seeded = sorted(d for d in (tasks / "seeded").iterdir() if (d / "meta.json").is_file())
    held_pairs = {d.name: pairs(d) for d in seeded}
    shared = set().union(*held_pairs.values())
    candidates, dropped = {}, []
    for d in sorted(p for p in (tasks / "mutated").iterdir() if (p / "meta.json").is_file()):
        p = pairs(d)
        if p & shared:
            dropped.append(d.name)
            continue
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        candidates[d.name] = {"archetype": meta["archetype"], "tier": meta["tier"], "file": sorted(p)[0][0]}
    train = _select(candidates)
    train_pairs = sorted({q for i in train for q in pairs(tasks / "mutated" / i)})
    return {
        "rule": RULE,
        "held_out": [{"id": d.name, "runnable": d.name not in NOT_RUNNABLE} for d in seeded],
        "train": train,
        "pairs": {"held_out": [list(q) for q in sorted(shared)], "train": [list(q) for q in train_pairs]},
        "counts": {
            "held_out": len(seeded),
            "held_out_runnable": sum(d.name not in NOT_RUNNABLE for d in seeded),
            "train": len(train),
            "mutants": len(candidates) + len(dropped),
            "mutants_dropped_for_shared_pair": len(dropped),
            "train_by_archetype": dict(Counter(candidates[i]["archetype"] for i in train)),
            "train_by_tier": dict(Counter(candidates[i]["tier"] for i in train)),
            "train_by_file": dict(Counter(candidates[i]["file"] for i in train)),
        },
    }


def problems(doc: dict, tasks: Path = TASKS) -> list[str]:
    """Why the split is not clean. Empty list = clean. Recomputes pairs from the task folders, not from the doc."""
    held = [h["id"] for h in doc["held_out"]]
    train = list(doc["train"])
    both = set(held) & set(train)
    out = [f"task id in both sets: {i}" for i in sorted(both)]
    out += [f"duplicate id: {i}" for i, n in Counter(held + train).items() if n > 1 and i not in both]
    missing = [
        f"{i}: no task folder under tasks/{kind}"
        for ids, kind in ((held, "seeded"), (train, "mutated"))
        for i in ids
        if not (tasks / kind / i / "bug.patch").is_file()
    ]
    if missing:
        return out + missing
    held_pairs = {q: i for i in held for q in pairs(tasks / "seeded" / i)}
    for i in train:
        out += [
            f"{i} shares pair {q[0]} + {q[1]} with {held_pairs[q]}"
            for q in sorted(pairs(tasks / "mutated" / i))
            if q in held_pairs
        ]
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="skills.split")
    parser.add_argument("command", choices=("split", "check"))
    command = parser.parse_args(argv).command
    fresh = build()
    if command == "split":
        SPLIT.write_text(json.dumps(fresh, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps(fresh["counts"]))
        return 0
    doc = json.loads(SPLIT.read_text(encoding="utf-8"))
    found = problems(doc)
    if doc != fresh:
        found.append("split.json is stale: run `python -m skills.split split` and commit it")
    for line in found:
        print(line, file=sys.stderr)
    print("split clean" if not found else f"{len(found)} problem(s)")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
