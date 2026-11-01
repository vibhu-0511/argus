"""P3-T09: the budget manager reports a step and calls a strategy at 80%."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from argus_core.client import Completion, Usage
from argus_core.ledger import Ledger, ModelQuota
from argus_core.types import StopReason

from fix_loop.budget import StepUsage, apply_budget
from fix_loop.loop import run_fix


def test_strategy_is_called_at_80_percent_and_not_before():
    calls: list[int] = []

    def strategy(messages, used, budget):
        calls.append(used)
        assert budget == 10
        return [*messages, {"role": "user", "content": "shrunk"}]

    messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]
    assert apply_budget(messages, used=7, budget=10, strategy=strategy) == messages
    assert calls == []
    changed = apply_budget(messages, used=8, budget=10, strategy=strategy)
    assert calls == [8]
    assert changed[-1]["content"] == "shrunk"


def test_step_usage_reports_in_out_and_cached():
    usage = StepUsage(3, 2, 1)
    assert usage.tokens_in == 3
    assert usage.tokens_out == 2
    assert usage.tokens_cached == 1
    assert usage.total == 6


def test_fake_model_sees_the_strategy_on_the_next_call(tmp_path: Path):
    seen: list[list[dict]] = []
    replies = iter([
        _completion("read_file", {"path": "a.txt"}, tokens_in=5, tokens_out=3),
        _completion("submit", {}),
    ])

    def strategy(messages, used, budget):
        del messages, used, budget
        return [{"role": "system", "content": "kept"}, {"role": "user", "content": "budget hit"}]

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
        execute=lambda name, _payload: __import__("fix_loop.tools", fromlist=["ToolResult"]).ToolResult(tool=name, text="ok"),
        context_budget=10,
        strategy=strategy,
    )
    assert result.stop_reason is StopReason.submit
    assert seen[1][0]["content"] == "kept"
    assert seen[1][1]["content"] == "budget hit"


def _completion(tool: str, arguments: dict, *, tokens_in: int = 1, tokens_out: int = 1) -> Completion:
    content = json.dumps({"tool": tool, "arguments": arguments})
    return Completion(content, Usage(tokens_in, tokens_out, 0), {})
