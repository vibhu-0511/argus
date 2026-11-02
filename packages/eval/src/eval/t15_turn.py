"""P5.5-T15 break-it driver: the P5.5-T04 train-mutant run (`eval.t14_turn`, variant T) with skills turned on.

    T15_ARM=real5|plus-any python -m eval.t15_turn start T mut-0190     (and show, answer, status, as in t14_turn)
    python -m eval.t15_turn rescore real5 plus-any                       score the stored diffs again (writes rescore.json)
    python -m eval.t15_turn summary real5 plus-any                       tokens and skills-loaded count per run, from the stored files

Two arms, each its own run folder under `runs/p55-t15/<arm>` and its own skills directory:

- `real5`: the 5 reviewed skills, with a copy of the real lock.
- `plus-any`: the same 5 plus `use-for-any-task` (a description that matches every ticket), pinned in a throwaway lock.

Both directories are built under `runs/p55-t15/_skills/<arm>/` and are never `packages/skills/skills` or the real
`skills.lock.json`. This module patches `t14_turn.TRAIN_RUNS` and `fix_loop.loop.run_fix` and changes nothing else in the
driver, so a run is the T04 run plus `skills=`. Tokens are chars/4 estimates of the messages, as in T04.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from functools import partial
from pathlib import Path

from eval import t14_turn
from fix_loop import loop
from fix_loop.skills import LOCK_NAME, content_hash, loaded_names

PACKAGES = Path(__file__).resolve().parents[3]
REAL = PACKAGES / "skills" / "skills"
ALWAYS = PACKAGES / "skills" / "tests" / "fixtures" / "always-matching" / "use-for-any-task"
ROOT = Path(__file__).resolve().parents[2] / "runs" / "p55-t15"
ARMS = ("real5", "plus-any")


def build_skills(arm: str, root: Path = ROOT) -> Path:
    """The skills directory of an arm, with its lock one level up (where the loader looks)."""
    base = root / "_skills" / arm
    skills = base / "skills"
    if skills.exists():  # built once per arm: a later start must not rewrite files an earlier run is reading
        return skills
    shutil.copytree(REAL, skills)
    lock = json.loads((REAL.parent / LOCK_NAME).read_text(encoding="utf-8"))
    if arm == "plus-any":
        shutil.copytree(ALWAYS, skills / ALWAYS.name)
        raw = (ALWAYS / "SKILL.md").read_bytes()
        lock["skills"][ALWAYS.name] = {"reviewed": True, "reviewed_by": "throwaway T15 lock", "reviewed_on": "2026-11-02", "sha256": content_hash(raw)}
    (base / LOCK_NAME).write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    return skills


def summary(arms: list[str]) -> int:
    from argus_core.types import Trajectory

    print("| arm | task | verdict | steps | tokens in | tokens out | skills loaded |\n|---|---|---|---|---|---|---|")
    for arm in arms:
        for run in sorted((ROOT / arm).glob("mut-*")):
            verdict = json.loads((run / "verdict.json").read_text(encoding="utf-8")) if (run / "verdict.json").exists() else {"verdict": "no verdict"}
            path = run / "fix" / "trajectory.jsonl"
            steps = Trajectory.from_jsonl(path.read_text(encoding="utf-8")).steps if path.exists() else []
            tin, tout, _, _ = t14_turn._totals([path]) if path.exists() else (0, 0, 0, 0)
            names = loaded_names(steps)
            print(f"| {arm} | {run.name} | {verdict['verdict']} | {len(steps)} | {tin} | {tout} | {len(names)} ({', '.join(names) or 'none'}) |")
    return 0


def rescore(arms: list[str]) -> int:
    """Score each finished run's stored `diff.patch` again on a fresh tree (HEAD + `bug.patch` + the diff) and write
    `rescore.json` next to the run's `verdict.json`, which is left as it was. Used when the scorer could not run (exit 2)."""
    import subprocess
    import tempfile

    from argus_bench.golden import platform_repo
    from fix_loop import worktree

    for arm in arms:
        for run in sorted((ROOT / arm).glob("mut-*")):
            task = t14_turn.MUTATED / run.name
            with tempfile.TemporaryDirectory() as scratch:
                tree = worktree.create(platform_repo(), run.name, "HEAD", root=Path(scratch))
                try:
                    for patch in (task / "bug.patch", run / "diff.patch"):
                        lf = Path(scratch) / f"{patch.stem}.lf.patch"  # a CRLF checkout of bug.patch would not apply: write LF bytes, as turn._reset does
                        lf.write_bytes(patch.read_text(encoding="utf-8").encode("utf-8"))
                        applied = subprocess.run(["git", "-c", "core.autocrlf=false", "-C", str(tree), "apply", str(lf)], capture_output=True, text=True)
                        if applied.returncode:
                            raise RuntimeError(f"{patch} did not apply: {applied.stderr.strip()}")
                    code = subprocess.run([sys.executable, "-m", "argus_bench.cli", "score", str(task), "--tree", str(tree)], capture_output=True, text=True, encoding="utf-8").returncode
                finally:
                    worktree.destroy(platform_repo(), tree)
            verdict = "excluded" if code == 2 else "resolved" if code == 0 else "unresolved"
            (run / "rescore.json").write_text(json.dumps({"task_id": run.name, "score_exit": code, "verdict": verdict}) + "\n", encoding="utf-8")
            print(arm, run.name, verdict)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "summary":
        return summary(args[1:] or list(ARMS))
    if args and args[0] == "rescore":
        return rescore(args[1:] or list(ARMS))
    arm = os.environ.get("T15_ARM", "")
    if arm not in ARMS:
        raise SystemExit(f"set T15_ARM to one of {ARMS}")
    t14_turn.TRAIN_RUNS = ROOT / arm
    loop.run_fix = partial(loop.run_fix, skills=build_skills(arm))
    return t14_turn.main(args)


if __name__ == "__main__":
    raise SystemExit(main())
