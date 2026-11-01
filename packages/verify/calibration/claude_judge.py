"""Claude as the judge: same rubric (rubrics/v2.md) and prompt (v2) as judge_run, one pair per call. No model call here.

    python claude_judge.py show <id> <forward|reverse>     print the prompt and two neutral image paths (first, second)
    python claude_judge.py record <id> <forward|reverse>   read the judge's reply on stdin, append one row
    python claude_judge.py todo <forward|reverse>          held-out ids with no row yet

Rows go to runs/judge-p4-judge-claude-v2-heldout.jsonl in judge_run's format, so score_split.py reads them.
The model is a Claude subagent that sees only the prompt and the two images (not meta.json, labels or other pairs).
`seconds` and the token counts are not measured here and are written as 0.
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG / "src"))
from verify.judge import build_prompt, injection_flag, parse_label  # noqa: E402

RUN_ID = "p4-judge-claude-v2-heldout"
OUT = PKG / "runs" / f"judge-{RUN_ID}.jsonl"
PAIRS = PKG / "fixtures" / "calibration"


def done() -> set[tuple[str, str]]:
    if not OUT.exists():
        return set()
    rows = [json.loads(line) for line in OUT.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {(r["id"], r["order"]) for r in rows}


def show(pair_id: str, order: str) -> None:
    folder = PAIRS / pair_id
    first, second = folder / "before.png", folder / "after.png"
    if order == "reverse":
        first, second = second, first
    dest = Path(tempfile.gettempdir()) / f"claude-judge-{pair_id}-{order}"
    dest.mkdir(exist_ok=True)
    shutil.copy(first, dest / "first.png")
    shutil.copy(second, dest / "second.png")
    ticket = (folder / "ticket.txt").read_text(encoding="utf-8")
    print(build_prompt((PKG / "rubrics" / "v2.md").read_text(encoding="utf-8"), ticket, "v2"))
    print("FIRST IMAGE (before):", dest / "first.png")
    print("SECOND IMAGE (after):", dest / "second.png")


def record(pair_id: str, order: str, raw: str) -> None:
    if (pair_id, order) in done():
        raise SystemExit(f"{pair_id}/{order} already recorded")
    ticket = (PAIRS / pair_id / "ticket.txt").read_text(encoding="utf-8")
    row = {"id": pair_id, "order": order, "label": parse_label(raw), "flagged": injection_flag(ticket), "seconds": 0,
           "tokens_in": 0, "tokens_out": 0, "raw": raw[:600], "run_id": RUN_ID}
    with OUT.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row) + chr(10))
    print(f"recorded {pair_id}/{order}: {row['label']} ({len(done())} rows)")


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[0] == "show":
        show(argv[1], argv[2])
    elif len(argv) == 3 and argv[0] == "record":
        record(argv[1], argv[2], sys.stdin.read())
    elif len(argv) == 2 and argv[0] == "todo":
        ids = json.loads((PKG / "runs" / "split-seed0.json").read_text(encoding="utf-8"))["held_out"]
        print(" ".join(i for i in ids if (i, argv[1]) not in done()))
    else:
        print(__doc__, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
