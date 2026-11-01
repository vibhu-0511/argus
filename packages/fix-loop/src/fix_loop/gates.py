"""Gates that run before submit. Each one returns pass or fail on its own."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

NAMES = ("build", "typecheck", "lint", "unit", "bench")


@dataclass(frozen=True)
class GateResult:
    name: str
    ok: bool
    text: str


def canvas_commands() -> dict[str, list[str]]:
    """npm scripts for the Canvas app. Bench is the Argus scorer, supplied by the caller."""
    return {
        "build": ["npm", "run", "build"],
        "typecheck": ["npm", "run", "typecheck"],
        "lint": ["npm", "run", "lint"],
        "unit": ["npm", "run", "test"],
        "bench": ["bench"],
    }


def gate_message(result: GateResult) -> str:
    first = result.text.splitlines()[0] if result.text else "failed"
    return json.dumps({"error": first, "gate": result.name}, sort_keys=True)


def run_gates(tree: Path, commands: dict[str, list[str]]) -> list[GateResult]:
    missing = [name for name in NAMES if name not in commands]
    if missing:
        raise ValueError(f"missing gates: {', '.join(missing)}")
    results: list[GateResult] = []
    for name in NAMES:
        proc = subprocess.run(
            commands[name],
            cwd=tree,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        text = (proc.stdout + proc.stderr).strip()
        results.append(GateResult(name, proc.returncode == 0, text))
    return results
