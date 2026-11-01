"""System and user text for one fix run."""

from __future__ import annotations

from pathlib import Path

_AGENTS = Path(__file__).resolve().parents[2] / "AGENTS.md"


def system_message(instruction: str) -> str:
    return _AGENTS.read_text(encoding="utf-8") + "\n" + instruction


def user_message(task: dict) -> str:
    locate = task["locate"]
    return (
        f"Ticket:\n{task['ticket']}\n\n"
        f"Repro: {task['repro']}\n"
        f"Locate: {locate['file']}:{locate['line']}\n"
    )
