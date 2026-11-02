"""P5.5-T16: the T14 Claude-session driver (variant T, fix stage only) with a stale test skill loaded.

    python -m eval.t16_turn prep <natural|insistent>     copy the fixture skill to runs/p55-t16/skills-<name>/ and pin it in a throwaway lock
    T16_VARIANT=<name> python -m eval.t16_turn start T mut-0003 | show T-mut-0003 | answer T-mut-0003 | status T-mut-0003

Every other command is `eval.t14_turn`'s. Two things change: the runs go under runs/p55-t16/<name>/ (so the T04 run of the same task
is not touched), and `run_fix` gets `skills=` the throwaway directory, so the model sees the catalog and can call `load_skill`.
The real `packages/skills/skills/` and `skills.lock.json` are not read or written; the lock pinned here lives next to the copy.
"""

from __future__ import annotations

import functools
import os
import shutil
import sys
from pathlib import Path

import fix_loop.loop as loop

from eval import t14_turn

ROOT = Path(__file__).resolve().parents[2] / "runs" / "p55-t16"
FIXTURES = Path(__file__).resolve().parents[4] / "packages" / "skills" / "tests" / "fixtures" / "stale-skills"


def prep(name: str) -> None:
    from skills.pin import pin  # the skills package is not a dependency of eval; `uv run --all-packages` has it

    target = ROOT / f"skills-{name}"
    shutil.rmtree(target, ignore_errors=True)
    shutil.copytree(FIXTURES / name, target / "skills")
    for folder in (target / "skills").iterdir():
        problem = pin(folder.name, "t16 throwaway", target / "skills", target / "skills.lock.json")
        if problem:
            raise SystemExit(problem)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) == 2 and args[0] == "prep":
        prep(args[1])
        return 0
    name = os.environ["T16_VARIANT"]
    t14_turn.TRAIN_RUNS = ROOT / name
    loop.run_fix = functools.partial(loop.run_fix, skills=ROOT / f"skills-{name}" / "skills")
    return t14_turn.main(args)


if __name__ == "__main__":
    raise SystemExit(main())
