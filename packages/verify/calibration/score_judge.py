"""Score a finished judge run against `fixtures/calibration/labels.json`: Claude's draft labels, adopted by the owner.

    python score_judge.py <judge jsonl> [--dev-seed 0]

Refuses to print an alpha unless all 100 forward judgements are in the file. Every number is labelled as agreement with
adopted Claude drafts (`labels.provenance.json`): the labels were not produced independently by a person.
Writes `<jsonl stem>.scored.json` beside the input.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from verify.alpha import (  # noqa: E402
    alphas_on_split,
    bootstrap_alpha,
    false_accept_rate,
    order_disagreement_rate,
    split_dev_held_out,
)

CAL = Path(__file__).resolve().parents[1] / "fixtures" / "calibration"
PROVISIONAL = "vs labels.json = Claude drafts adopted by the owner (not independently human-labelled)"


def main(path: Path, dev_seed: int) -> None:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    draft = {p["id"]: p["label"] for p in json.loads((CAL / "labels.json").read_text(encoding="utf-8"))["pairs"]}
    if any(label is None for label in draft.values()):
        raise SystemExit("labels.json has null labels")
    ids = sorted(draft)
    fwd = {r["id"]: r for r in rows if r["order"] == "forward"}
    rev = {r["id"]: r for r in rows if r["order"] == "reverse"}
    if set(fwd) != set(ids):
        raise SystemExit(f"incomplete: {len(fwd)}/100 forward judgements. No alpha is computed from a run that did not finish.")
    human_like = [draft[i] for i in ids]
    judge = [fwd[i]["label"] for i in ids]  # an unparsed reply is the label `error` and stays in the denominator
    point, low, high = bootstrap_alpha(human_like, judge, iterations=1000, seed=0)
    dev, _held = split_dev_held_out(len(ids), seed=dev_seed)
    dev_alpha, held_alpha = alphas_on_split(human_like, judge, dev)
    out = {
        "status": PROVISIONAL, "judge_run": path.name, "pairs": len(ids),
        "alpha": round(point, 4), "bootstrap95": [round(low, 4), round(high, 4)],
        "dev_alpha": round(dev_alpha, 4), "held_out_alpha": round(held_alpha, 4), "split": f"seed {dev_seed}, 50/50 by position",
        "false_accept_rate_vs_non_pass_labels": round(false_accept_rate(human_like, judge), 4),
        "judge_labels": dict(Counter(judge)), "labels": dict(Counter(human_like)),
        "confusion_draft_to_judge": {f"{a}->{b}": n for (a, b), n in sorted(Counter(zip(human_like, judge, strict=True)).items())},
        "error_count": judge.count("error"),
        "mean_seconds_per_pair": round(sum(r["seconds"] for r in fwd.values()) / len(fwd), 1),
    }
    if set(rev) == set(ids):
        out["order_disagreement_rate"] = round(order_disagreement_rate(judge, [rev[i]["label"] for i in ids]), 4)
    else:
        out["order_disagreement_rate"] = f"not computed: {len(rev)}/100 reverse-order judgements"
    Path(str(path).replace(".jsonl", ".scored.json")).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(Path(sys.argv[1]), int(sys.argv[sys.argv.index("--dev-seed") + 1]) if "--dev-seed" in sys.argv else 0)
