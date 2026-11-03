"""P8-T11: planner emits sub-tasks, subagents run on their own budgets, and the ledger total is the sum over all agents. Scripted model, no LLM call."""

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
from fix_loop.planner import PlanError, parse_plan, run_planned, select
from fix_loop.tools import ToolResult


def _plan(*titles: str) -> str:
    return json.dumps({"subtasks": [{"title": t, "instructions": f"do {t}"} for t in titles]})


def _tool(name: str) -> str:
    return json.dumps({"tool": name, "arguments": {}})


class Script:
    """Replies in order. `usage[i]` is the (in, out, cached) of reply i; the default is (10, 2, 4)."""

    def __init__(self, replies: list[str], usage: dict[int, tuple[int, int, int]] | None = None):
        self.replies, self.usage, self.seen = replies, usage or {}, []

    def complete(self, *args) -> Completion:
        messages = args[-1]
        i = len(self.seen)
        self.seen.append((messages[0]["role"], len(messages), str(messages[1]["content"])))
        return Completion(self.replies[i], Usage(*self.usage.get(i, (10, 2, 4))), {})


def _ledger(tmp_path: Path) -> Ledger:
    return Ledger(tmp_path / "ledger.json", {"fake": ModelQuota(1000, 10**9, 1000, 10**9, False)})


def _run(tmp_path: Path, script: Script, *, token_cap: int = 1000, step_cap: int = 30, **kwargs):
    return run_planned(
        worktree=tmp_path, model="fake", ledger=_ledger(tmp_path), complete=script.complete, out_dir=tmp_path / "out",
        step_cap=step_cap, token_cap=token_cap, run_id="run-1", host="test", git_commit="abc", task_id="bug-1",
        system="system", user="fix it", execute=lambda name, payload: ToolResult(tool=name, text="ok"), **kwargs,
    )


def _bucket(tmp_path: Path) -> dict:
    return json.loads((tmp_path / "ledger.json").read_text(encoding="utf-8"))["models"]["fake"]


def test_planner_emits_subtasks_and_each_subagent_has_its_own_history(tmp_path: Path):
    # planner, then list_dir + submit for each of three sub-tasks
    script = Script([_plan("a", "b", "c")] + [_tool("list_dir"), _tool("submit")] * 3)
    result = _run(tmp_path, script, context="src/ has two files")
    assert result.stop_reason is StopReason.submit
    assert [a.agent for a in result.agents] == ["planner", "sub-1", "sub-2", "sub-3"]
    assert "src/ has two files" in script.seen[0][2]
    firsts = [s for s in script.seen[1:] if s[1] == 2]  # a subagent's first call sees only system + user
    assert len(firsts) == 3
    assert [("sub-task (%d of 3)" % n) in f[2] for n, f in enumerate(firsts, 1)] == [True] * 3
    assert all(len(s[2]) and "do b" not in firsts[0][2] for s in firsts[:1])  # sub-task 1 never sees sub-task 2's text


def test_ledger_total_is_the_sum_over_planner_and_subagents(tmp_path: Path):
    script = Script([_plan("a", "b")] + [_tool("list_dir"), _tool("submit")] * 2, usage={0: (30, 6, 0)})
    result = _run(tmp_path, script)
    bucket = _bucket(tmp_path)
    assert bucket["requests"] == 5  # 1 planner call + 4 subagent calls, each counted once
    assert result.subagent_calls == 4
    assert (result.tokens_in, result.tokens_out, result.tokens_cached) == (30 + 4 * 10, 6 + 4 * 2, 4 * 4)
    assert bucket["tokens"] == result.tokens_in + result.tokens_out - result.tokens_cached  # the quota's charge rule: cached do not count
    assert bucket["cached"] == result.tokens_cached
    by_agent = {a.agent: (a.tokens_in, a.tokens_out, a.tokens_cached, a.calls) for a in result.agents}
    assert by_agent == {"planner": (30, 6, 0, 1), "sub-1": (20, 4, 8, 2), "sub-2": (20, 4, 8, 2)}
    assert json.loads((tmp_path / "out" / "agents.json").read_text(encoding="utf-8"))[1]["agent"] == "sub-1"


def test_every_agent_trajectory_carries_the_run_id_and_the_merged_one_sums_all(tmp_path: Path):
    result = _run(tmp_path, Script([_plan("a", "b")] + [_tool("submit")] * 2))
    out = tmp_path / "out"
    for name in ("planner", "sub-1", "sub-2", "."):
        meta = Trajectory.from_jsonl((out / name / "trajectory.jsonl").read_text(encoding="utf-8")).meta
        assert (meta.run_id, meta.task_id) == ("run-1", "bug-1")
    merged = Trajectory.from_jsonl(result.trajectory_path.read_text(encoding="utf-8")).steps
    assert [s.index for s in merged] == [0, 1, 2]
    assert sum(s.tokens_in + s.tokens_out for s in merged) == result.tokens_in + result.tokens_out


def test_a_subagent_that_hits_its_budget_does_not_stop_the_others(tmp_path: Path):
    # token_cap 100, planner 12 -> 88 // 3 = 29 each. Reply 2 (sub-2's first) costs 50, over its own cap.
    script = Script([_plan("a", "b", "c"), _tool("submit"), _tool("list_dir"), _tool("list_dir"), _tool("submit")], usage={2: (50, 0, 0)})
    result = _run(tmp_path, script, token_cap=100)
    reasons = {a.agent: a.stop_reason for a in result.agents}
    assert reasons == {"planner": None, "sub-1": "submit", "sub-2": "token-cap", "sub-3": "submit"}
    assert result.stop_reason is StopReason.token_cap  # the bug is not cleanly done, but sub-3 still ran
    assert _bucket(tmp_path)["requests"] == 5  # planner, sub-1 once, sub-2 once, sub-3 twice


def test_quota_refusal_ends_the_whole_run(tmp_path: Path):
    script = Script([_plan("a", "b")] + [_tool("submit")] * 2)
    ledger = Ledger(tmp_path / "ledger.json", {"fake": ModelQuota(2, 10**9, 1000, 10**9, False)})  # planner + sub-1, then refused
    result = run_planned(
        worktree=tmp_path, model="fake", ledger=ledger, complete=script.complete, out_dir=tmp_path / "out", step_cap=20,
        token_cap=1000, run_id="r", host="h", git_commit="c", task_id="t", system="s", user="u",
        execute=lambda name, payload: ToolResult(tool=name, text="ok"),
    )
    assert result.stop_reason is StopReason.quota_exceeded
    assert [a.agent for a in result.agents] == ["planner", "sub-1", "sub-2"]
    assert len(script.seen) == 2


@pytest.mark.parametrize(
    "reply",
    ["no json at all", "[]", '{"subtasks": []}', _plan(*"abcdef"), '{"subtasks": [{"title": "a"}]}', '{"subtasks": [{"title": "a", "instructions": "b", "x": 1}]}'],
)
def test_a_malformed_plan_is_a_typed_error_and_the_planner_call_is_still_counted(tmp_path: Path, reply: str):
    with pytest.raises(PlanError) as error:
        _run(tmp_path, Script([reply]))
    assert error.value.raw == reply
    assert _bucket(tmp_path)["requests"] == 1
    assert (tmp_path / "out" / "planner" / "trajectory.jsonl").exists()
    assert not (tmp_path / "out" / "sub-1").exists()


def test_a_fenced_plan_parses():
    assert [t.title for t in parse_plan("```json\n" + _plan("a", "b") + "\n```").subtasks] == ["a", "b"]


def test_through_a_router_the_planner_and_subagents_land_in_one_ledger(tmp_path: Path):
    policy = load_policy()
    models = {r.model for t in policy.tiers.values() for r in (t.primary, t.fallback) if r}
    ledger = Ledger(tmp_path / "ledger.json", {m: ModelQuota(100, 10**6, 100, 10**6, False) for m in models})
    script = Script([_plan("a", "b")] + [_tool("submit")] * 2)
    router = Router(policy, ledger, {"groq": script, "mistral": script, "ollama": script})
    result = run_planned(
        worktree=tmp_path, model="routed", router=router, out_dir=tmp_path / "out", step_cap=10, token_cap=1000, run_id="r",
        host="routed", git_commit="c", task_id="t", system="s", user="u", execute=lambda name, payload: ToolResult(tool=name, text="ok"),
    )
    strong = policy.tiers["strong"].primary.model
    assert result.stop_reason is StopReason.submit
    assert ledger._state["models"][strong]["requests"] == 3
    assert {s.model for s in Trajectory.from_jsonl(result.trajectory_path.read_text(encoding="utf-8")).steps} == {strong}


def test_select_picks_the_runner_by_name():
    assert select("single") is run_fix and select("planner") is run_planned
    with pytest.raises(ValueError, match="variant must be one of"):
        select("swarm")
