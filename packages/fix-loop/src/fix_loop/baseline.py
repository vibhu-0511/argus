"""No-compaction baseline. One trajectory and one verdict per seeded task.

The live fixer is not called from here. Pass `complete`. Exit 2 and a crashed
task stay out of the Wilson denominator. A passing score whose checks were
touched is not resolved.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from pathlib import Path

from argus_core.client import Completion
from argus_core.ledger import Ledger

from fix_loop.loop import run_fix

Score = Callable[[str, Path], tuple[int, bool]]


def seeded_subset(root: Path) -> list[Path]:
    quarantine = root.parent.parent / "quarantine"
    skipped = {item.name for item in quarantine.iterdir()} if quarantine.is_dir() else set()
    return sorted(
        path
        for path in root.iterdir()
        if path.is_dir() and (path / "meta.json").is_file() and path.name not in skipped
    )


def run_baseline(
    *,
    tasks: list[Path],
    out_dir: Path,
    ledger: Ledger,
    complete: Callable[[list[dict]], Completion],
    score: Score,
    prepare: Callable[[Path], Path],
    model: str,
    host: str,
    git_commit: str,
    step_cap: int,
    token_cap: int,
    compaction: str = "none",
) -> str:
    if compaction != "none":
        raise ValueError("the baseline is no compaction")
    out_dir.mkdir(parents=True, exist_ok=True)
    resolved = 0
    unresolved = 0
    for task in tasks:
        task_id, text = _ticket(task)
        task_out = out_dir / task.name
        task_out.mkdir(parents=True, exist_ok=True)
        try:
            tree = prepare(task)
            tree.mkdir(parents=True, exist_ok=True)
            result = run_fix(
                worktree=tree,
                model=model,
                ledger=ledger,
                complete=complete,
                out_dir=task_out,
                step_cap=step_cap,
                token_cap=token_cap,
                run_id=task.name,
                host=host,
                git_commit=git_commit,
                task_id=task_id,
                system="Fix the ticket.",
                user=f"Ticket:\n{text}\n\nRepro: not-run\nLocate: none\n",
            )
            code, touched = score(task_id, tree)
            kind = _kind(code, touched)
            reason = result.stop_reason.value
        except Exception as exc:
            kind = "error"
            reason = str(exc)
        if kind == "resolved":
            resolved += 1
        elif kind == "unresolved":
            unresolved += 1
        (task_out / "verdict.json").write_text(
            json.dumps({"task_id": task_id, "verdict": kind, "stop_reason": reason}) + "\n",
            encoding="utf-8",
        )
    attempted = resolved + unresolved
    label = rate_label(resolved, attempted) if attempted else "0/0"
    (out_dir / "rate.txt").write_text(label + "\n", encoding="utf-8")
    return label


def rate_label(successes: int, total: int) -> str:
    low, high = _wilson(successes, total)
    return f"{successes}/{total} [{low:.6f}, {high:.6f}]"


def _kind(code: int, checks_touched: bool) -> str:
    if code == 2:
        return "excluded"
    if code == 0 and not checks_touched:
        return "resolved"
    return "unresolved"


def _wilson(successes: int, total: int) -> tuple[float, float]:
    """Wilson score interval at 95%. z = 1.96 formats the P0 0/10 cell as [0.000000, 0.277540]."""
    if total < 1:
        raise ValueError("total must be at least 1")
    z = 1.96
    phat = successes / total
    z2 = z * z
    denom = 1 + z2 / total
    center = (phat + z2 / (2 * total)) / denom
    margin = z * math.sqrt(phat * (1 - phat) / total + z2 / (4 * total * total)) / denom
    return max(0.0, center - margin), min(1.0, center + margin)


def _ticket(path: Path) -> tuple[str, str]:
    data = json.loads((path / "ticket.json").read_text(encoding="utf-8"))
    return str(data.get("id") or path.name), str(data.get("text") or "")
