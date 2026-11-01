"""P3-T15: a failed gate is a message, and the loop continues."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from argus_core.client import Completion, Usage
from argus_core.ledger import Ledger, ModelQuota
from argus_core.types import StopReason

from fix_loop.gates import GateResult
from fix_loop.loop import run_fix
from fix_loop.tools import ToolResult


def test_failed_gate_names_the_gate_and_the_first_error(tmp_path: Path):
    seen: list[list[dict]] = []
    replies = iter([
        _completion("submit", {}),
        _completion("submit", {}),
    ])
    passes = {"n": 0}

    def gates():
        passes["n"] += 1
        if passes["n"] == 1:
            return [GateResult("typecheck", False, "error TS2322\nnext line")]
        return [GateResult("typecheck", True, "")]

    def complete(messages):
        seen.append(messages)
        return next(replies)

    result = run_fix(
        worktree=tmp_path / "work",
        model="fake",
        ledger=Ledger(tmp_path / "ledger.json", {"fake": ModelQuota(100, 10**9, 100, 10**9, False)}),
        complete=complete,
        out_dir=tmp_path / "out",
        step_cap=4,
        token_cap=1000,
        run_id="run-1",
        host="test",
        git_commit="abc",
        task_id="bug-17",
        system="system",
        user="fix it",
        execute=lambda name, _payload: ToolResult(tool=name, text="submitted"),
        gates=gates,
    )
    assert result.stop_reason is StopReason.submit
    assert len(seen) == 2
    feedback = json.loads(seen[1][-1]["content"])
    assert feedback["gate"] == "typecheck"
    assert feedback["error"] == "error TS2322"


def _completion(tool: str, arguments: dict) -> Completion:
    content = json.dumps({"tool": tool, "arguments": arguments})
    return Completion(content, Usage(1, 1, 0), {})
