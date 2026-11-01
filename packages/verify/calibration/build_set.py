"""Build the real calibration set: real Canvas screens, before/after trees from the seeded bench tasks and P3 runs.

    python build_set.py candidates <work dir> <screening.json>   render every candidate after-tree
    python build_set.py select <work dir> <dest dir>             pick pairs (40/30/30) and write the fixtures

Trees (all are the four CSS files, applied to platform HEAD):
  before   HEAD + the task's bug.patch
  correct  HEAD (the golden fix). A resolved P3 run has an empty diff, so its tree is HEAD too.
  wrong    an unresolved P3 run's diff; one bug hunk left unfixed (partial); or no fix at all
  collateral  HEAD plus one regression hunk taken from a different task's bug.patch

`constructed_as` records how a pair was built. It is not the label. The owner labels each pair by eye.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from common import RUNS, SEEDED, VIEWS, apply_patches, css_cache, pixel_ratios, render

MIN_VISIBLE = 0.0003  # changed-pixel ratio below which a change is not visible in a 1280x800 shot (a 20px to 8px text is about 0.0004)
MAX_CHANGED = 0.5  # above this a render is treated as broken, not as a design change
SHARE = {"correct": 0.4, "wrong": 0.3, "collateral": 0.3}
WORKERS = 4


def split_hunks(patch: str) -> list[tuple[str, str]]:
    """[(file, one-hunk patch text)] for a unified diff."""
    out: list[tuple[str, str]] = []
    file = None
    hunk: list[str] = []

    def flush() -> None:
        if hunk and file:
            out.append((file, f"--- a/{file}\n+++ b/{file}\n" + "\n".join(hunk) + "\n"))
        hunk.clear()

    for line in patch.splitlines():
        if line.startswith("+++ b/"):
            flush()
            file = line[6:]
        elif line.startswith(("diff --git", "index ", "--- ")):
            flush()
        elif line.startswith("@@"):
            flush()
            hunk.append(line)
        elif hunk:
            hunk.append(line)
    flush()
    return out


def hunk_span(text: str) -> tuple[int, int]:
    m = re.search(r"@@ -(\d+)(?:,(\d+))? ", text)
    return int(m.group(1)), int(m.group(1)) + int(m.group(2) or 1)


def overlaps(a: tuple[str, str], b: tuple[str, str]) -> bool:
    if a[0] != b[0]:
        return False
    (a0, a1), (b0, b1) = hunk_span(a[1]), hunk_span(b[1])
    return a0 <= b1 + 3 and b0 <= a1 + 3


def p3_runs() -> dict[str, list[dict]]:
    """task -> runs that have a non-empty diff (a tree different from HEAD)."""
    table = json.loads((RUNS / "p3-a-claude-results.json").read_text(encoding="utf-8"))
    out: dict[str, list[dict]] = defaultdict(list)
    for row in table:
        diff = RUNS / row["run"] / "diff.patch"
        if row["verdict"] == "excluded" or not diff.exists():
            continue
        text = diff.read_text(encoding="utf-8")
        out[row["task"]].append({"run": row["run"], "verdict": row["verdict"], "patch": text})
    for scored in sorted(RUNS.glob("p4-t20-*/verdict.rescored.json")):  # the P4-T20 pilot draws, scored again from diff.patch
        row = json.loads(scored.read_text(encoding="utf-8"))
        out[row["task_id"]].append({"run": row["run_id"], "verdict": row["verdict"], "patch": (scored.parent / "diff.patch").read_text(encoding="utf-8")})
    return out


def candidates(work: Path, screening: Path) -> None:
    screen = json.loads(screening.read_text(encoding="utf-8"))["changed_ratio"]
    cache, shots = work / "css", work / "cand"
    shots.mkdir(parents=True, exist_ok=True)
    runs = p3_runs()
    bug_hunks = {t.name: split_hunks((t / "bug.patch").read_text(encoding="utf-8")) for t in SEEDED.iterdir() if t.name in screen}
    visible = {t: {v: r for v, r in row.items() if r >= MIN_VISIBLE} for t, row in screen.items()}
    visible = {t: row for t, row in visible.items() if row}
    cands: list[dict] = []

    def add(task: str, view: str, kind: str, source: str, patches: list[str]) -> None:
        tree = apply_patches(patches)
        if tree is None:
            return
        cid = f"{task}__{view}__{kind}"
        cands.append({"id": cid, "task": task, "view": view, "constructed_as": kind.split(":")[0], "variant": kind, "source": source,
                      "css": css_cache(tree, cache), "out": str(shots / f"{cid.replace(':', '_')}.png")})

    donors = [(t, h) for t in visible for h in bug_hunks[t] if hunk_span(h[1])]
    for task, row in visible.items():
        bug = (SEEDED / task / "bug.patch").read_text(encoding="utf-8")
        views = sorted(row, key=row.get, reverse=True)
        for view in views:
            add(task, view, "before", f"{task}/bug.patch on platform HEAD", [bug])
            add(task, view, "correct:golden", f"platform HEAD ({task}/golden.patch result)", [])
            add(task, view, "wrong:nofix", f"{task}/bug.patch left in place", [bug])
            for index in range(len(bug_hunks[task])) if len(bug_hunks[task]) > 1 else []:
                rest = [h[1] for i, h in enumerate(bug_hunks[task]) if i != index]
                add(task, view, f"wrong:partial{index}", f"{task}: bug hunk {index} left in place, the other fixed", rest)
            for run in runs.get(task, []):
                if run["patch"].strip():
                    kind = "correct" if run["verdict"] == "resolved" else "wrong"
                    add(task, view, f"{kind}:{run['run']}", f"P3 run {run['run']} ({run['verdict']}) diff on platform HEAD", [run["patch"]])
            plus = 0
            for donor, hunk in donors:  # the bug stays and something else regresses: still wrong
                if donor == task or any(overlaps(hunk, mine) for mine in bug_hunks[task]):
                    continue
                if plus >= 2:
                    break
                plus += 1
                add(task, view, f"wrong:bugplus-{donor}-h{bug_hunks[donor].index(hunk)}", f"{task} bug left in place, plus a regression from {donor}", [bug, hunk[1]])
            used = 0
            for donor, hunk in donors:
                if donor == task or any(overlaps(hunk, mine) for mine in bug_hunks[task]):
                    continue
                if used >= 4:
                    break
                used += 1
                add(task, view, f"collateral:{donor}-h{bug_hunks[donor].index(hunk)}", f"HEAD plus a regression from {donor}", [hunk[1]])
    for c in cands:
        c["css"] = {k: v for k, v in c["css"].items()}
    for attempt in range(4):  # a worker's browser sometimes dies under load; shots already written are kept
        todo = [c for c in cands if not Path(c["out"]).exists()]
        if not todo:
            break
        chunks = [todo[i::WORKERS] for i in range(WORKERS)]

        def one(args):
            index, chunk = args
            if not chunk:
                return
            try:
                render([{"out": c["out"], "view": c["view"], "css": c["css"]} for c in chunk], work / f"w{index}")
            except subprocess.CalledProcessError:
                pass

        with ThreadPoolExecutor(WORKERS) as pool:
            list(pool.map(one, enumerate(chunks)))
    # ratios against the task's own before and against the golden render on the same view
    by_key = {(c["task"], c["view"], c["variant"]): c for c in cands}
    pairs = []
    for c in cands:
        before = by_key[(c["task"], c["view"], "before")]
        golden = by_key[(c["task"], c["view"], "correct:golden")]
        pairs += [[c["out"], before["out"]], [c["out"], golden["out"]]]
    ratios = pixel_ratios(pairs)
    for i, c in enumerate(cands):
        c["vs_before"], c["vs_golden"] = round(ratios[2 * i], 6), round(ratios[2 * i + 1], 6)
    (work / "candidates.json").write_text(json.dumps(cands, indent=1), encoding="utf-8")
    print(len(cands), "candidates;", sum(Path(c["out"]).exists() for c in cands), "rendered")


def select(work: Path, dest: Path) -> None:
    cands = json.loads((work / "candidates.json").read_text(encoding="utf-8"))
    keyed = {(c["task"], c["view"], c["variant"]): c for c in cands}
    pool: dict[str, list[dict]] = {k: [] for k in SHARE}
    seen: set[tuple[str, str, str]] = set()
    for c in cands:
        kind = c["constructed_as"]
        if kind not in SHARE:
            continue
        before = keyed[(c["task"], c["view"], "before")]
        if max(c["vs_before"], c["vs_golden"], before["vs_golden"]) > MAX_CHANGED:
            continue  # a broken render, not a design change
        if kind == "correct":
            if c["variant"] != "correct:golden" and c["vs_golden"] < MIN_VISIBLE:
                continue  # same picture as the golden pair
            if c["vs_before"] < MIN_VISIBLE:
                continue
        elif kind == "collateral":
            if c["vs_golden"] < MIN_VISIBLE or c["vs_before"] < MIN_VISIBLE:
                continue  # the regression is not visible on this screen
        elif kind == "wrong":
            if c["variant"] != "wrong:nofix" and c["vs_golden"] < MIN_VISIBLE:
                continue  # a "wrong" tree that renders like the golden fix is not wrong on this screen
        sig = (c["task"], c["view"], hashlib.sha256(Path(c["out"]).read_bytes()).hexdigest())
        if sig in seen:
            continue
        seen.add(sig)
        pool[kind].append({**c, "before": before["out"]})
    for kind in pool:  # nofix pairs are trivial; keep a few. Round-robin across tasks so no ticket dominates.
        by_task: dict[str, list[dict]] = defaultdict(list)
        for c in pool[kind]:
            by_task[c["task"]].append(c)
        order = []
        while any(by_task.values()):
            for t in sorted(by_task):
                if by_task[t]:
                    order.append(by_task[t].pop(0))
        pool[kind] = order
    nofix_cap = 4
    kept_wrong, nofix = [], 0
    for c in pool["wrong"]:
        if c["variant"] == "wrong:nofix":
            if nofix >= nofix_cap:
                continue
            nofix += 1
        kept_wrong.append(c)
    pool["wrong"] = kept_wrong
    n = min(100, min(int(len(pool[k]) / SHARE[k]) for k in SHARE))
    take = {k: round(n * SHARE[k]) for k in SHARE}
    chosen = [c for k in ("correct", "wrong", "collateral") for c in pool[k][: take[k]]]
    chosen.sort(key=lambda c: (c["task"], c["view"], c["variant"]))
    # interleave the classes so ids carry no class order
    import random

    random.Random(0).shuffle(chosen)
    if dest.exists():
        raise SystemExit(f"{dest} exists; move it away first")
    dest.mkdir(parents=True)
    labels = []
    for index, c in enumerate(chosen):
        pid = f"{index:03d}"
        folder = dest / pid
        folder.mkdir()
        shutil.copyfile(c["before"], folder / "before.png")
        shutil.copyfile(c["out"], folder / "after.png")
        ticket = json.loads((SEEDED / c["task"] / "ticket.json").read_text(encoding="utf-8"))
        (folder / "ticket.txt").write_text(ticket["text"], encoding="utf-8")
        meta = {
            "id": pid, "ticket_id": c["task"], "view": c["view"], "constructed_as": c["constructed_as"],
            "shot_source": "real-canvas-mocked-api", "after_variant": c["variant"], "after_source": c["source"],
            "changed_ratio_vs_before": c["vs_before"], "changed_ratio_vs_golden": c["vs_golden"], "label": None,
        }
        (folder / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        labels.append({"id": pid, "label": None})
    (dest / "labels.json").write_text(json.dumps({"pairs": labels}, indent=2) + "\n", encoding="utf-8")
    summary = {
        "pairs": len(chosen), "target": 100, "mix_target": SHARE,
        "mix_built": {k: sum(c["constructed_as"] == k for c in chosen) for k in SHARE},
        "available_before_cap": {k: len(pool[k]) for k in SHARE},
        "distinct_tickets": len({c["task"] for c in chosen}),
        "views": sorted({c["view"] for c in chosen}),
        "viewport": "1280x800", "min_visible_changed_ratio": MIN_VISIBLE,
    }
    (dest / "manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    if sys.argv[1] == "candidates":
        candidates(Path(sys.argv[2]), Path(sys.argv[3]))
    elif sys.argv[1] == "select":
        select(Path(sys.argv[2]), Path(sys.argv[3]))
    else:
        raise SystemExit(__doc__)
