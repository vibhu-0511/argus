"""Exit status for one stored screenshot pair. No model call."""

from __future__ import annotations

import json
from pathlib import Path

from verify.checks import pixel_diff
from verify.png import decode_png


def check_dir(directory: Path) -> int:
    verdict_path = directory / "verdict.json"
    if not verdict_path.is_file():
        return 1
    try:
        verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return 1
    if not isinstance(verdict, dict) or "ok" not in verdict:
        return 1
    try:
        before = decode_png((directory / "before.png").read_bytes())
        after = decode_png((directory / "after.png").read_bytes())
    except (OSError, ValueError):
        return 1
    if not pixel_diff(before, after).ok:
        return 1
    if verdict["ok"] is not True:
        return 1
    return 0
