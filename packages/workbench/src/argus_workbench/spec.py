"""The P10 design spec, packaged. `spec.json` is a copy of `docs/notes/p10-spec.json` (a test keeps the two equal as JSON).

The page shows the SPEC label of each screen (`screens[].built.label`) and, next to it, the honest P10 status line.
The spec labels describe what existed when the design was drawn; the workbench itself is local and scripted, and
the status line says so, so the page cannot be read as a claim that a hosted product exists.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

SPEC_PATH = Path(__file__).with_name("spec.json")
P10_STATUS = "local, scripted"  # shown next to every label; no run on any screen is a model result


@lru_cache(maxsize=1)
def load_spec() -> dict:
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


def scenario_ids() -> tuple[str, ...]:
    return tuple(s["id"] for s in load_spec()["scenarios"])


def tabs() -> list[dict]:
    """The five tabs in screen order, with the spec label verbatim and the P10 status line."""
    return [
        {
            "id": s["id"],
            "n": s["n"],
            "title": s["title"],
            "short": s["short"],
            "purpose": s["purpose"],
            "label": s["built"]["label"],
            "level": s["built"]["level"],
            "detail": s["built"]["detail"],
            "status": P10_STATUS,
        }
        for s in sorted(load_spec()["screens"], key=lambda s: s["n"])
    ]
