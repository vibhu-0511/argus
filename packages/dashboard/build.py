"""Build data.js for the static dashboard from results JSON files (schema: packages/eval/schemas/results.schema.json).

Browsers block fetch() of local JSON from file://, so the data goes into a script tag file instead.
Usage: python packages/dashboard/build.py [results.json ...] [--out DIR]
No files given: the real results files in the repo (DEFAULT_FILES).
Files are kept in the order given; the page reads the last real run as "this phase" and the one before as "previous".
"""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
# The real runs, oldest first. The page reads the last two real runs as "previous" and "this phase", so the P5 ablation (A, then B) goes last.
# T20 is a different task set (14 multimodal tasks); it is charted beside the others, labelled by run id.
DEFAULT_FILES = [
    "packages/eval/results/baseline.json",  # P3 variant A, 29 seeded tasks
    "packages/eval/results/p5-t20-multimodal.json",  # T20 baseline, one plain subagent per task
    "packages/eval/results/p5-t20-multimodal-argus.json",  # T20 with the argus fix loop
    "packages/eval/results/breakit-C.json",  # T27 break-it: fix on the cheap model
    "packages/eval/results/ablation-A.json",  # T14 all strong
    "packages/eval/results/ablation-B.json",  # T14 routed
]
# Kept to exercise the delta and the "made up" labels in the tests; not shown by default.
FIXTURE_FILES = ["packages/eval/fixtures/gate/baseline.json", "packages/eval/fixtures/gate/worse.json"]
KEEP = ("run_id", "created_at", "agent", "counts", "resolve_rate", "tokens", "latency_s", "trajectory_metrics", "$_equivalent")


def load_run(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise SystemExit(f"{path}: schema_version {data.get('schema_version')!r}, this dashboard reads 1")
    run = {k: data[k] for k in KEEP}  # KeyError names the missing field; the per-task rows stay in the source file
    try:
        run["source"] = path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        run["source"] = path.as_posix()
    # ponytail: text match on the run id and agent config; the fixtures say "made up" there. A schema field would be firmer.
    text = (data["run_id"] + json.dumps(data["agent"])).lower()
    run["made_up"] = "made up" in text or "made-up" in text
    return run


def build(files: list[str], out: Path) -> Path:
    runs = [load_run(Path(f) if Path(f).is_absolute() else ROOT / f) for f in files]
    out.mkdir(parents=True, exist_ok=True)
    target = out / "data.js"
    target.write_text("window.ARGUS_RUNS = " + json.dumps(runs, indent=1) + ";\n", encoding="utf-8")
    return target


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("files", nargs="*", default=DEFAULT_FILES)
    ap.add_argument("--out", type=Path, default=HERE)
    args = ap.parse_args()
    print(build(args.files, args.out))
