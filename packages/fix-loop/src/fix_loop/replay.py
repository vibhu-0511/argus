"""Replay stored model messages. Edits are applied. The shell is not run."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from argus_core.types import Trajectory, TrajectoryStep

from fix_loop.tools import call


def replay(path: Path, worktree: Path) -> str:
    trajectory = Trajectory.from_jsonl(path.read_text(encoding="utf-8"))
    for step in trajectory.steps:
        action = _action(step.raw_response)
        if action is None or action[0] != "edit":
            continue
        call("edit", action[1], worktree)
    return _diff(worktree)


def observations_for(step: TrajectoryStep) -> list[dict]:
    body = _json(step.raw_response)
    calls = body.get("tool_calls") if isinstance(body, dict) else None
    if isinstance(calls, list) and calls and all(isinstance(item, dict) and item.get("id") for item in calls):
        observations = (step.message or {}).get("observations") or []
        rows = []
        for index, item in enumerate(calls):
            observation = observations[index] if index < len(observations) else step.message
            rows.append({"id": item["id"], "observation": observation})
        return rows
    return [{"raw_response": step.raw_response, "observation": step.message}]


def _action(raw: str | None) -> tuple[str, dict] | None:
    body = _json(raw)
    if not isinstance(body, dict) or not isinstance(body.get("arguments"), dict) or "tool" not in body:
        return None
    return str(body["tool"]), body["arguments"]


def _json(raw: str | None) -> dict:
    try:
        body = json.loads(raw or "")
    except json.JSONDecodeError:
        return {}
    return body if isinstance(body, dict) else {}


def _diff(worktree: Path) -> str:
    proc = subprocess.run(
        ["git", "-c", "core.autocrlf=false", "-C", str(worktree), "diff"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return proc.stdout
