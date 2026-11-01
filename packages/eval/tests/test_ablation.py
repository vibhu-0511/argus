"""P5-T14: policies, the table and the runner's dollars hook. Hand-built trajectories, no pipeline, no model call."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from argus_core.ledger import load_quotas
from argus_core.prices import dollar_equivalent
from argus_core.router import ROUTING_PATH, load_policy
from argus_core.types import Check, CheckType, Task, TaskMeta, Ticket, Trajectory, TrajectoryMeta, TrajectoryStep

from eval.ablation import QUOTAS, STRONG_ONLY, table
from eval.runner import AgentConfig, Outcome, run_eval

NOW = datetime(2026, 11, 1, tzinfo=UTC)
STRONG, CHEAP = "openai/gpt-oss-120b", "openai/gpt-oss-20b"


def _task(i: int) -> Task:
    return Task(
        id=f"t{i}", ticket=Ticket(id=f"t{i}", text="x"), bug_patch="b", golden_patch="g",
        checks=[Check(type=CheckType.pixel_diff)], meta=TaskMeta(source="seeded", archetype="a", tier="easy"),
    )


def test_variant_a_is_all_strong_with_the_same_strong_route_as_routing_yaml():
    a, b = load_policy(STRONG_ONLY), load_policy(ROUTING_PATH)
    assert set(a.stages.values()) == {"strong"} and set(a.stages) == set(b.stages)
    assert a.tiers["strong"] == b.tiers["strong"]  # the copy in policies/ must not drift
    assert b.stages == {"repro": "cheap", "localize": "cheap", "fix": "strong"}


def _steps(tmp: Path, task: str, stage: str, rows: list[tuple[str, str, int, int, int]]) -> Path:
    steps = [
        TrajectoryStep(index=i, tokens_in=a, tokens_out=b, tokens_cached=c, tier=tier, host="groq", model=model)
        for i, (tier, model, a, b, c) in enumerate(rows)
    ]
    meta = TrajectoryMeta(run_id=task, task_id=task, model="m", host="h", prompt_hash="p", git_commit="c")
    path = tmp / task / stage / "trajectory.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text(Trajectory(meta=meta, steps=steps).to_jsonl(), encoding="utf-8")
    return path


def _variant(tmp: Path, name: str, repro_tier: str, repro_model: str, *, stub: bool = False, drop_repro: bool = False) -> Path:
    tmp = tmp / name

    def agent(task: Task) -> Outcome:
        repro = _steps(tmp, task.id, "repro", [(repro_tier, repro_model, 100, 50, 0)])
        fix = _steps(tmp, task.id, "fix", [("strong", STRONG, 1950, 100, 200)])
        if drop_repro:
            repro.unlink()
        dollars = dollar_equivalent(repro_model, 100, 50, 0) + dollar_equivalent(STRONG, 1950, 100, 200)
        return Outcome("resolved" if task.id == "t0" else "unresolved", tokens_in=2050, tokens_out=150, tokens_cached=200,
                       latency_s=10.0, trajectory=str(fix), dollars=dollars)

    config = AgentConfig(name=name, model="not-in-prices", factory="x:y", params={"stub": stub})
    results = run_eval([_task(0), _task(1)], agent, config, now=NOW)
    out = tmp / "results.json"
    out.write_text(results.to_json(), encoding="utf-8")
    return out


def test_runner_uses_the_agents_dollars_and_never_prices_the_config_model():
    results = run_eval([_task(0)], lambda t: Outcome("resolved", tokens_in=10, tokens_out=1, dollars=0.5), AgentConfig(name="n", model="not-in-prices", factory="x:y"), now=NOW)
    assert results.dollar_equivalent == 0.5
    unknown = run_eval([_task(0), _task(1)], lambda t: Outcome("resolved", tokens_in=10, tokens_out=1, dollars=0.5 if t.id == "t0" else None), AgentConfig(name="n", model="not-in-prices", factory="x:y"), now=NOW)
    assert unknown.dollar_equivalent is None  # one task the agent could not price: the total is unknown, not half of it


def test_table_splits_tokens_by_tier_and_prices_each_model(tmp_path: Path):
    a = _variant(tmp_path, "A", "strong", STRONG)
    b = _variant(tmp_path, "B", "cheap", CHEAP)
    out = table(a, b)
    assert "STUB" not in out
    row_a, row_b = [line for line in out.splitlines() if line.startswith(("| A", "| B"))]
    # per bug: in 2050 / out 150 / cached 200; resolve 1/2; Wilson 95% for 1/2 is [9.5%, 90.5%]
    assert "50.0% (1/2) [9.5%, 90.5%]" in row_a and "2,050 / 150 / 200" in row_a
    cost_a = (dollar_equivalent(STRONG, 100, 50, 0) + dollar_equivalent(STRONG, 1950, 100, 200))
    cost_b = (dollar_equivalent(CHEAP, 100, 50, 0) + dollar_equivalent(STRONG, 1950, 100, 200))
    assert f"${cost_a:.4f}" in row_a and f"${cost_b:.4f}" in row_b and cost_b < cost_a
    # ledger rule: cached tokens do not count. A: strong charged (150 + 1850) * 2 = 4000 of 200000 over 2 bugs = 1.0%.
    # B: strong 1850 * 2 / 400000 = 0.925% binds, cheap is 0.075%.
    assert " 1.0% |" in row_a and " 0.9% |" in row_b
    assert f"cheap    {CHEAP}: 200 / 100 / 0, 2 calls" in out  # B: repro on the cheap model
    assert f"strong   {STRONG}: 4,100 / 300 / 400, 4 calls" in out  # A: repro and fix both on the strong model
    assert f"strong   {STRONG}: 3,900 / 200 / 400, 2 calls" in out  # B: fix only


def test_a_missing_stage_trajectory_is_a_dash_not_a_smaller_number(tmp_path: Path):
    a = _variant(tmp_path, "A", "strong", STRONG, drop_repro=True)
    b = _variant(tmp_path, "B", "cheap", CHEAP)
    row_a = next(line for line in table(a, b).splitlines() if line.startswith("| A"))
    cells = [c.strip() for c in row_a.strip("|").split("|")]
    assert cells[4] == "—"  # quota share
    assert "(stage trajectories missing" in table(a, b)


def test_a_stub_run_is_labelled(tmp_path: Path):
    out = table(_variant(tmp_path, "A", "strong", STRONG, stub=True), _variant(tmp_path, "B", "cheap", CHEAP))
    assert out.startswith("**STUB RUN")


def test_quotas_file_is_the_one_the_ledger_reads():
    assert STRONG in load_quotas(QUOTAS) and CHEAP in load_quotas(QUOTAS)
