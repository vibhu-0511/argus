"""Run the judge over a calibration directory. Resumable, with a progress file, so a long CPU run survives the turn.

    python -m verify.judge_run --pairs fixtures/calibration --out runs/judge-<run id>.jsonl --run-id <run id>
        [--limit N] [--ids 000,001 | --ids-file split.json:dev] [--order forward|reverse|both] [--rubric path]
        [--prompt v1|v2] [--num-ctx 8192]

One JSON line per (pair, order): id, order, label, seconds, tokens, raw. `forward` is before then after, the order α uses.
A pair already in the output file is skipped, so re-running the same command continues the job. Labels here are the
judge's. They are not scored against anything in this file.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from verify.judge import GEMMA_MODEL, judge_pair, ollama_backend, rubric_text


def done_keys(out: Path) -> set[tuple[str, str]]:
    if not out.exists():
        return set()
    keys = set()
    for line in out.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            keys.add((row["id"], row["order"]))
    return keys


def run(args: argparse.Namespace) -> int:
    pairs = Path(args.pairs)
    if args.ids_file:  # "<json file>:<key>", e.g. runs/split-seed0.json:dev
        path, key = args.ids_file.rsplit(":", 1)
        ids = json.loads(Path(path).read_text(encoding="utf-8"))[key]
    else:
        ids = args.ids.split(",") if args.ids else sorted(p.name for p in pairs.iterdir() if (p / "before.png").exists())
    if args.limit:
        ids = ids[: args.limit]
    orders = ["forward", "reverse"] if args.order == "both" else [args.order]
    jobs = [(i, o) for o in orders for i in ids]
    rubric = Path(args.rubric).read_text(encoding="utf-8") if args.rubric else rubric_text()
    out, progress = Path(args.out), Path(args.out).with_suffix(".progress.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    seen = done_keys(out)
    todo = [job for job in jobs if job not in seen]
    backend = ollama_backend(args.model, num_ctx=args.num_ctx)
    started = time.perf_counter()
    spent = 0.0
    state = {"run_id": args.run_id, "model": args.model, "prompt": args.prompt, "rubric": args.rubric or "rubric.md", "pairs": args.pairs, "num_ctx": args.num_ctx, "total": len(jobs),
             "started_utc": datetime.now(timezone.utc).isoformat(), "status": "running"}

    def write(status: str, last: str | None, finished: int) -> None:
        remaining = len(jobs) - len(seen) - finished
        mean = spent / finished if finished else None
        progress.write_text(json.dumps({**state, "status": status, "done": len(seen) + finished, "last": last,
                                        "mean_seconds_per_job": mean, "eta_seconds": mean * remaining if mean else None,
                                        "updated_utc": datetime.now(timezone.utc).isoformat()}, indent=1), encoding="utf-8")

    write("running", None, 0)
    finished = 0
    for pair_id, order in todo:
        folder = pairs / pair_id
        before, after = (folder / "before.png").read_bytes(), (folder / "after.png").read_bytes()
        if order == "reverse":
            before, after = after, before
        ticket = (folder / "ticket.txt").read_text(encoding="utf-8")
        result = judge_pair(backend, ticket, before, after, rubric, args.prompt)
        row = {"id": pair_id, "order": order, "label": result.label, "flagged": result.flagged, "seconds": round(result.seconds, 2),
               "tokens_in": result.tokens_in, "tokens_out": result.tokens_out, "raw": result.raw[:600], "run_id": args.run_id}
        with out.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")
        spent += result.seconds
        finished += 1
        write("running", f"{pair_id}/{order}", finished)
    write("finished", None, finished)
    print(f"{finished} judged this call, {len(seen) + finished}/{len(jobs)} in {out}; wall {time.perf_counter() - started:.0f}s")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pairs", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--model", default=GEMMA_MODEL)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--ids", default="")
    ap.add_argument("--ids-file", default="")
    ap.add_argument("--prompt", choices=["v1", "v2"], default="v1")
    ap.add_argument("--order", choices=["forward", "reverse", "both"], default="forward")
    ap.add_argument("--rubric", default="")
    ap.add_argument("--num-ctx", type=int, default=8192)
    return run(ap.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
