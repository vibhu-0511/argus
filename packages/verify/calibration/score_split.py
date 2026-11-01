"""Score a judge run over one split of the calibration set against labels.json (Claude drafts adopted by the owner).

    python score_split.py <judge jsonl> <dev|held_out>

Uses the ids in runs/split-seed0.json. Refuses to print an alpha unless every pair of the split has a forward judgement.
The order-disagreement rate needs the reverse-order half as well; without it the rate is reported as not computed.
Writes `<jsonl stem>.<split>.scored.json` beside the input.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from verify.alpha import bootstrap_alpha, false_accept_rate, order_disagreement_rate  # noqa: E402

PKG = Path(__file__).resolve().parents[1]
STATUS = "vs labels.json = Claude drafts adopted by the owner (not independently human-labelled)"


def main(path: Path, split: str) -> None:
    ids = json.loads((PKG / "runs" / "split-seed0.json").read_text(encoding="utf-8"))[split]
    labels = {p["id"]: p["label"] for p in json.loads((PKG / "fixtures" / "calibration" / "labels.json").read_text(encoding="utf-8"))["pairs"]}
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    fwd = {r["id"]: r for r in rows if r["order"] == "forward"}
    rev = {r["id"]: r for r in rows if r["order"] == "reverse"}
    if not set(ids) <= set(fwd):
        raise SystemExit(f"incomplete: {len(set(ids) & set(fwd))}/{len(ids)} forward judgements. No alpha from a run that did not finish.")
    human = [labels[i] for i in ids]
    judge = [fwd[i]["label"] for i in ids]
    point, low, high = bootstrap_alpha(human, judge, iterations=1000, seed=0)
    out = {
        "status": STATUS, "judge_run": path.name, "split": split, "pairs": len(ids),
        "alpha": round(point, 4), "bootstrap95": [round(low, 4), round(high, 4)],
        "agreement": f"{sum(a == b for a, b in zip(human, judge, strict=True))}/{len(ids)}",
        "false_accept_rate_vs_non_pass_labels": round(false_accept_rate(human, judge), 4),
        "judge_labels": dict(Counter(judge)), "labels": dict(Counter(human)),
        "confusion_label_to_judge": {f"{a}->{b}": n for (a, b), n in sorted(Counter(zip(human, judge, strict=True)).items())},
        "error_count": judge.count("error"),
        "mean_seconds_per_pair": round(sum(fwd[i]["seconds"] for i in ids) / len(ids), 1),
    }
    if set(ids) <= set(rev):
        out["order_disagreement_rate"] = round(order_disagreement_rate(judge, [rev[i]["label"] for i in ids]), 4)
    else:
        out["order_disagreement_rate"] = f"not computed: {len(set(ids) & set(rev))}/{len(ids)} reverse-order judgements"
    Path(str(path).replace(".jsonl", f".{split}.scored.json")).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(Path(sys.argv[1]), sys.argv[2])
