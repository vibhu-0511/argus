"""P5-T14: the fix loop takes a Router. Each step records the tier, host and model that served it, and the ledger counts each call once."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from argus_core.client import Completion, Usage
from argus_core.ledger import Ledger, ModelQuota
from argus_core.router import Router, load_policy
from argus_core.types import StopReason, Trajectory

from fix_loop.loop import run_fix
from fix_loop.tools import ToolResult


class Stub:
    def __init__(self, replies: list[str]):
        self.replies = replies
        self.models: list[str] = []

    def complete(self, model: str, messages: list[dict]) -> Completion:
        self.models.append(model)
        return Completion(self.replies[len(self.models) - 1], Usage(10, 2, 4), {})


def _router(tmp_path: Path, replies: list[str]) -> tuple[Router, Stub, Ledger]:
    policy = load_policy()
    models = {r.model for t in policy.tiers.values() for r in (t.primary, t.fallback) if r}
    quota = ModelQuota(100, 10**6, 100, 10**6, False)
    ledger = Ledger(tmp_path / "ledger.json", {m: quota for m in models})
    stub = Stub(replies)
    return Router(policy, ledger, {"groq": stub, "mistral": stub, "ollama": stub}), stub, ledger


def _call(tool: str) -> str:
    return json.dumps({"tool": tool, "arguments": {}})


def _run(tmp_path: Path, **kwargs):
    return run_fix(
        worktree=tmp_path, model="routed", out_dir=tmp_path / "out", step_cap=5, token_cap=1000, run_id="r", host="routed",
        git_commit="abc", task_id="t", system="system", user="fix it",
        execute=lambda name, payload: ToolResult(tool=name, text="ok"), **kwargs,
    )


def test_steps_record_who_served_them_and_the_ledger_counts_each_call_once(tmp_path: Path):
    router, stub, ledger = _router(tmp_path, [_call("list_dir"), _call("submit")])
    result = _run(tmp_path, router=router)
    assert result.stop_reason is StopReason.submit
    steps = Trajectory.from_jsonl(result.trajectory_path.read_text(encoding="utf-8")).steps
    strong = load_policy().tiers["strong"].primary
    assert [(s.tier, s.host, s.model) for s in steps] == [("strong", strong.host, strong.model)] * 2
    assert stub.models == [strong.model] * 2
    bucket = ledger._state["models"][strong.model]
    assert bucket["requests"] == 2  # a second ledger call in the loop would make this 4
    assert bucket["cached"] == 8


def test_stage_picks_the_tier(tmp_path: Path):
    router, stub, _ = _router(tmp_path, [_call("submit")])
    _run(tmp_path, router=router, stage="repro")
    assert stub.models == [load_policy().tiers["cheap"].primary.model]


def test_without_a_router_nothing_is_recorded_and_ledger_and_complete_are_needed(tmp_path: Path):
    ledger = Ledger(tmp_path / "l.json", {"m": ModelQuota(10, 10**6, 10, 10**6, False)})
    result = _run(tmp_path, ledger=ledger, complete=lambda _m: Completion(_call("submit"), Usage(1, 1, 0), {}))
    step = Trajectory.from_jsonl(result.trajectory_path.read_text(encoding="utf-8")).steps[0]
    assert (step.tier, step.host, step.model) == (None, None, None)
    with pytest.raises(ValueError, match="ledger and complete, or a router"):
        _run(tmp_path)
