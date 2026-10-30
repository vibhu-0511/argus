"""A bench task is a directory: ticket.json, bug.patch, golden.patch, checks.json, meta.json.

`golden.patch` applies to the buggy tree. `bug.patch` is its inverse and applies to the fixed tree.
"""

from __future__ import annotations

import json
from pathlib import Path

from argus_core.types import Task


def load_task_dir(directory: Path) -> Task:
    directory = Path(directory)
    ticket = _read_json(directory / "ticket.json")
    checks = _read_json(directory / "checks.json")
    meta = _read_json(directory / "meta.json")
    bug_patch = _read_text(directory / "bug.patch")
    golden_patch = _read_text(directory / "golden.patch")
    shot = (ticket.get("screenshot") or {}).get("path")
    if shot and not (directory / shot).is_file():
        raise ValueError(f"screenshot not found: {shot}")
    return Task.model_validate(
        {
            "id": ticket["id"],
            "ticket": ticket,
            "bug_patch": bug_patch,
            "golden_patch": golden_patch,
            "checks": checks,
            "meta": meta,
        }
    )


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"missing {path.name}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path.name} is not JSON") from exc


def _read_text(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ValueError(f"missing {path.name}") from exc
    if not text.strip():
        raise ValueError(f"{path.name} is empty")
    return text
