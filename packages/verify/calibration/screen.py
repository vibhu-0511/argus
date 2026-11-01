"""Which seeded bugs show up in a screenshot at all?

Renders HEAD (the fixed tree) and each task's buggy tree (HEAD + bug.patch) on every view and records the changed-pixel
ratio. A bug with ratio 0 on every view cannot be judged from screenshots, so it cannot go in the calibration set.

    python screen.py <work dir>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from common import SEEDED, VIEWS, apply_patches, css_cache, pixel_ratios, render


def main(work: Path) -> None:
    cache = work / "css"
    shots = work / "shots"
    shots.mkdir(parents=True, exist_ok=True)
    head_css_files = css_cache(apply_patches([]), cache)
    jobs = [{"out": str(shots / f"head_{view}.png"), "view": view, "css": head_css_files} for view in VIEWS]
    pairs = []
    skipped = {}
    for task in sorted(SEEDED.iterdir()):
        tree = apply_patches([(task / "bug.patch").read_text(encoding="utf-8")])
        if tree is None:
            skipped[task.name] = "bug.patch does not apply to platform HEAD"
            continue
        css = css_cache(tree, cache)
        for view in VIEWS:
            out = str(shots / f"{task.name}_{view}.png")
            jobs.append({"out": out, "view": view, "css": css})
            pairs.append((task.name, view, out))
    report = render([j for j in jobs if not Path(j["out"]).exists()], work)  # shots are deterministic: reuse
    errors = [r for r in report if r["errors"]]
    ratios = pixel_ratios([[str(shots / f"head_{view}.png"), out] for _, view, out in pairs])
    table: dict[str, dict[str, float]] = {}
    for (name, view, _), ratio in zip(pairs, ratios, strict=True):
        table.setdefault(name, {})[view] = round(ratio, 6)
    (work / "screening.json").write_text(
        json.dumps({"skipped": skipped, "page_errors": len(errors), "changed_ratio": table}, indent=1), encoding="utf-8"
    )
    for name, row in table.items():
        print(name, row)
    print("skipped", skipped, "page errors", len(errors))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
