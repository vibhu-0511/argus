"""Calibration pairs. Labels stay null until a person fills them in, before any judge output."""

from __future__ import annotations

import json
from pathlib import Path

from verify.png import encode_png, fill, solid

MIX = ("correct",) * 40 + ("wrong",) * 30 + ("collateral",) * 30
GRAY = (180, 180, 180)
RED = (200, 40, 40)
BLUE = (40, 40, 200)


def load_tickets(root: Path) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for path in sorted(root.glob("*/ticket.json")):
        body = json.loads(path.read_text(encoding="utf-8"))
        found.append((str(body["id"]), str(body["text"])))
    if not found:
        raise ValueError(f"no tickets under {root}")
    return found


def generate(dest: Path, tickets: list[tuple[str, str]]) -> None:
    if len(MIX) != 100:
        raise ValueError("calibration set is 100 pairs")
    dest.mkdir(parents=True, exist_ok=True)
    labels = []
    for index, kind in enumerate(MIX):
        ticket_id, text = tickets[index % len(tickets)]
        pair_id = f"{index:03d}"
        folder = dest / pair_id
        folder.mkdir(exist_ok=True)
        before, after = _shots(kind)
        (folder / "before.png").write_bytes(encode_png(before))
        (folder / "after.png").write_bytes(encode_png(after))
        (folder / "ticket.txt").write_text(text, encoding="utf-8")
        meta = {
            "id": pair_id,
            "ticket_id": ticket_id,
            "constructed_as": kind,
            "shot_source": "synthetic",
            "label": None,
        }
        (folder / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        labels.append({"id": pair_id, "label": None})
    (dest / "labels.json").write_text(json.dumps({"pairs": labels}, indent=2) + "\n", encoding="utf-8")


def _shots(kind: str):
    base = solid(16, 16, GRAY)
    defect = fill(base, 2, 2, 4, 4, RED)
    collateral = fill(base, 10, 10, 4, 4, BLUE)
    if kind == "correct":
        return defect, base
    if kind == "wrong":
        return defect, defect
    if kind == "collateral":
        return defect, collateral
    raise ValueError(kind)
