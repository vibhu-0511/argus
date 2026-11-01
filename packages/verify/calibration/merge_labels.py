"""Merge the owner's exported labels with Claude's drafts into fixtures/calibration/labels.json.

    python merge_labels.py <exported labels.json> --accept-rest

The export is the file `review.html` downloads. A pair the owner labelled keeps the owner's label, even when it differs
from the draft. With --accept-rest, each pair the owner left blank takes Claude's draft, because the owner said to go
ahead with the drafts. Nothing is overwritten silently:

- `labels.json` gets the merged labels (the file alpha is scored against).
- `labels.provenance.json` records, per pair, `owner` or `owner-accepted-draft`, so a later alpha can say how many of the
  100 labels are the owner's own and how many are drafts the owner adopted.
- `labels.claude-draft.json` keeps its draft labels; only each pair's `human_review` field is updated.

Refuses to run if `labels.json` already has labels, so a second run cannot overwrite a finished file.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

CAL = Path(__file__).resolve().parents[1] / "fixtures" / "calibration"
LABELS = {"pass", "fail", "collateral"}


def main(export: Path, accept_rest: bool) -> None:
    current = json.loads((CAL / "labels.json").read_text(encoding="utf-8"))
    if any(p["label"] is not None for p in current["pairs"]):
        raise SystemExit("labels.json already has labels; not overwriting")
    owner = {p["id"]: p["label"] for p in json.loads(export.read_text(encoding="utf-8"))["pairs"] if p["label"] is not None}
    bad = {i: v for i, v in owner.items() if v not in LABELS}
    if bad:
        raise SystemExit(f"unknown labels in the export: {bad}")
    draft_file = json.loads((CAL / "labels.claude-draft.json").read_text(encoding="utf-8"))
    draft = {p["id"]: p for p in draft_file["pairs"]}
    ids = sorted(draft)
    if not set(owner) <= set(ids):
        raise SystemExit("export has ids that are not in the set")
    blank = [i for i in ids if i not in owner]
    if blank and not accept_rest:
        raise SystemExit(f"{len(blank)} pairs have no owner label; pass --accept-rest to take the drafts for them")
    merged, source, disagree = [], {}, []
    for i in ids:
        if i in owner:
            label, source[i] = owner[i], "owner"
            draft[i]["human_review"] = "reviewed-agrees" if owner[i] == draft[i]["label"] else "reviewed-disagrees"
            if owner[i] != draft[i]["label"]:
                disagree.append(i)
        else:
            label, source[i] = draft[i]["label"], "owner-accepted-draft"
            draft[i]["human_review"] = "accepted-by-owner-without-individual-review"
        merged.append({"id": i, "label": label})
    (CAL / "labels.json").write_text(json.dumps({"pairs": merged}, indent=2) + "\n", encoding="utf-8")
    (CAL / "labels.provenance.json").write_text(
        json.dumps({"note": "owner = the owner labelled this pair; owner-accepted-draft = the owner told Claude to use the draft.",
                    "counts": dict(Counter(source.values())), "owner_disagreed_with_draft": disagree, "source": source}, indent=1) + "\n",
        encoding="utf-8")
    (CAL / "labels.claude-draft.json").write_text(json.dumps(draft_file, indent=1, ensure_ascii=False), encoding="utf-8")
    agree = len(owner) - len(disagree)
    print(f"owner labelled {len(owner)}; agreed with the draft on {agree}, disagreed on {len(disagree)} {disagree}")
    print(f"drafts adopted for {len(blank)} pairs; merged labels: {dict(Counter(p['label'] for p in merged))}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), "--accept-rest" in sys.argv)
