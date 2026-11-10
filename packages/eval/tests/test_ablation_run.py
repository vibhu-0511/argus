"""P5-T14: both variants over the same tasks through `python -m eval run`, with stub models only. Needs the repro agent's
dependencies (mcp), so it is skipped in the plain root environment: `uv run --package repro-agent pytest packages/eval/tests/test_ablation_run.py -v`."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp", reason="run with: uv run --package repro-agent pytest packages/eval/tests/test_ablation_run.py")
for src in ("eval", "fix-loop", "repro-agent"):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / src / "src"))

from argus_core.client import Completion, Usage
from argus_core.ledger import load_quotas
from argus_core.prices import dollar_equivalent
from argus_core.types import Check, CheckType, Task, TaskMeta, Ticket, Trajectory

from eval.__main__ import main
from eval.ablation import QUOTAS, Measured, quota_share, subagent_calls, table, tier_usage
from eval.results import Results

STRONG, CHEAP = "openai/gpt-oss-120b", "openai/gpt-oss-20b"


def _task(i: int) -> Task:
    return Task(
        id=f"t{i}", ticket=Ticket(id=f"t{i}", text="The Sign in button does nothing."), bug_patch="b", golden_patch="g",
        checks=[Check(type=CheckType.pixel_diff)], meta=TaskMeta(source="seeded", archetype="a", tier="easy"),
    )


def _run(tmp_path: Path, variant: str, factory: str) -> tuple[Results, Path]:
    tasks = tmp_path / "tasks.json"
    tasks.write_text(json.dumps([_task(i).model_dump(mode="json") for i in range(4)]), encoding="utf-8")
    out = tmp_path / variant
    agent = tmp_path / f"{variant}.json"
    agent.write_text(json.dumps({
        "name": variant, "model": STRONG, "host": "groq", "factory": factory,
        "params": {"stub": True, "out_dir": str(out), "resolve": ["t0", "t1"]},
    }), encoding="utf-8")
    assert main(["run", "--tasks", str(tasks), "--agent", str(agent), "--out", str(out / "results.json")]) == 0
    return Results.model_validate_json((out / "results.json").read_text(encoding="utf-8")), out / "results.json"


def _steps(results: Results):
    for row in results.tasks:
        fix = Path(row.trajectory)
        for file in sorted(fix.parent.parent.glob("*/trajectory.jsonl")):
            for step in Trajectory.from_jsonl(file.read_text(encoding="utf-8")).steps:
                yield file.parent.name, step


def test_both_variants_run_the_same_tasks_and_split_by_tier(tmp_path: Path):
    a, path_a = _run(tmp_path, "A", "eval.ablation:strong_only")
    b, path_b = _run(tmp_path, "B", "eval.ablation:routed")
    assert [r.task_id for r in a.tasks] == [r.task_id for r in b.tasks] == ["t0", "t1", "t2", "t3"]
    assert (a.counts.resolved, b.counts.resolved) == (2, 2)

    tiers_a = {(stage, s.tier, s.model) for stage, s in _steps(a)}
    tiers_b = {(stage, s.tier, s.model) for stage, s in _steps(b)}
    assert tiers_a == {("repro", "strong", STRONG), ("fix", "strong", STRONG)}
    assert tiers_b == {("repro", "cheap", CHEAP), ("fix", "strong", STRONG)}

    for results in (a, b):
        total = results.tokens.total
        steps = [s for _, s in _steps(results)]
        assert total.tokens_cached == sum(s.tokens_cached for s in steps) > 0  # cached is counted apart from fresh
        assert total.tokens_in == sum(s.tokens_in for s in steps)
        dollars = sum(dollar_equivalent(s.model, s.tokens_in, s.tokens_out, s.tokens_cached) for s in steps)
        assert results.dollar_equivalent == pytest.approx(dollars, abs=1e-6)  # the results file rounds to 6 decimals
    assert b.dollar_equivalent < a.dollar_equivalent  # same tokens, repro priced on the 20b model in B

    quotas = load_quotas(QUOTAS)
    for results, variant in ((a, "A"), (b, "B")):
        use = tier_usage(results, tmp_path, quotas)
        assert use is not None
        ledger = json.loads((tmp_path / variant / "ledger.json").read_text(encoding="utf-8"))["models"]
        for (_, model), u in use.items():
            assert u.charged == ledger[model]["tokens"]  # the trajectory rule and the ledger agree
            assert u.calls == ledger[model]["requests"]
            assert u.tokens_cached == ledger[model]["cached"]
        assert quota_share(Measured(results, use), quotas) == pytest.approx(max(u.charged / 200_000 / 4 for u in use.values()))

    out = table(path_a, path_b)
    assert out.startswith("**STUB RUN")
    assert "—" not in "\n".join(line for line in out.splitlines() if line.startswith(("| A", "| B")))


def test_live_run_without_a_tree_runner_is_refused_before_any_task(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ARGUS_MODEL_API_KEY", "dummy-not-a-key")
    from eval.ablation import routed
    from eval.runner import AgentConfig

    config = AgentConfig(name="B", model=STRONG, host="groq", factory="eval.ablation:routed", params={"out_dir": str(tmp_path)})
    with pytest.raises(ValueError, match="no live repro tree runner"):
        routed(config)


def test_the_planner_variant_runs_from_the_same_config_and_every_agent_is_counted(tmp_path: Path):
    """P8-T11: `params.variant = planner` switches the fix stage to planner plus subagents; the results file still sums every call."""
    tasks = tmp_path / "tasks.json"
    tasks.write_text(json.dumps([_task(i).model_dump(mode="json") for i in range(2)]), encoding="utf-8")
    out = tmp_path / "P"
    agent = tmp_path / "P.json"
    agent.write_text(json.dumps({
        "name": "P", "model": STRONG, "host": "groq", "factory": "eval.ablation:strong_only",
        "params": {"stub": True, "out_dir": str(out), "resolve": ["t0"], "variant": "planner"},
    }), encoding="utf-8")
    assert main(["run", "--tasks", str(tasks), "--agent", str(agent), "--out", str(out / "results.json")]) == 0
    results = Results.model_validate_json((out / "results.json").read_text(encoding="utf-8"))
    assert (results.counts.resolved, results.resolve_rate.total) == (1, 2)
    seen_in = seen_cached = 0
    for row in results.tasks:
        agents = json.loads((Path(row.trajectory).parent / "agents.json").read_text(encoding="utf-8"))
        assert [a["agent"] for a in agents] == ["planner", "sub-1"]
        assert agents[1]["calls"] == 2  # list_dir, then submit
        repro = Trajectory.from_jsonl((Path(row.trajectory).parent.parent / "repro" / "trajectory.jsonl").read_text(encoding="utf-8")).steps
        seen_in += sum(a["tokens_in"] for a in agents) + sum(s.tokens_in for s in repro)
        seen_cached += sum(a["tokens_cached"] for a in agents) + sum(s.tokens_cached for s in repro)
    assert (results.tokens.total.tokens_in, results.tokens.total.tokens_cached) == (seen_in, seen_cached)
    ledger = json.loads((out / "ledger.json").read_text(encoding="utf-8"))["models"][STRONG]
    assert ledger["cached"] == seen_cached


# --- P8-T12: the local-model ablation pieces, stub models only ----------------------------------------------------

LOCAL = "gemma4:e4b"


def bad_plan_clients():
    """A client that answers the planner with text that is not a plan and everything else like the stub."""
    from eval.ablation import StubClient

    class BadPlan(StubClient):
        def complete(self, model, messages):
            if "split a bug ticket" in str(messages[0]["content"]):
                return Completion("I would start by looking at the CSS.", Usage(40, 9, 0), {})
            return super().complete(model, messages)

    return {"ollama": BadPlan()}


def _local_run(tmp_path: Path, name: str, variant: str, extra: dict | None = None) -> tuple[Results, Path]:
    tasks = tmp_path / "tasks.json"
    tasks.write_text(json.dumps([_task(i).model_dump(mode="json") for i in range(3)]), encoding="utf-8")
    out = tmp_path / name
    agent = tmp_path / f"{name}.json"
    params = {"stub": True, "out_dir": str(out), "resolve": ["t0", "t1"], "variant": variant, **(extra or {})}
    agent.write_text(json.dumps({"name": name, "model": LOCAL, "host": "ollama", "factory": "eval.ablation:local", "params": params}), encoding="utf-8")
    assert main(["run", "--tasks", str(tasks), "--agent", str(agent), "--out", str(out / "results.json")]) == 0
    return Results.model_validate_json((out / "results.json").read_text(encoding="utf-8")), out / "results.json"


def test_local_model_runs_both_variants_with_no_price_and_the_table_counts_subagent_calls(tmp_path: Path):
    a, path_a = _local_run(tmp_path, "A", "single")
    b, path_b = _local_run(tmp_path, "B", "planner")
    assert [r.task_id for r in a.tasks] == [r.task_id for r in b.tasks]
    assert a.dollar_equivalent is None and b.dollar_equivalent is None  # gemma4:e4b has no list price: a dash, not a failure and not 0
    assert {s.model for _, s in _steps(b)} == {LOCAL}
    assert b.tokens.total.tokens_in > a.tokens.total.tokens_in  # the planner call and the subagent's own prompt are counted too
    lines = [ln for ln in table(path_a, path_b).splitlines() if ln.startswith(("| A", "| B"))]
    assert lines[0].endswith("| 0.00 |")  # single agent: no subagents
    assert lines[1].endswith("| 2.00 |")  # list_dir, then submit, in the one subagent
    assert lines[0].split("|")[4].strip() == "—" == lines[1].split("|")[4].strip()  # $-equivalent


def test_a_malformed_plan_is_an_unresolved_bug_that_still_costs_its_tokens(tmp_path: Path):
    results, path = _local_run(tmp_path, "P", "planner", {"clients": "test_ablation_run:bad_plan_clients"})
    assert (results.counts.resolved, results.counts.unresolved, results.counts.error) == (0, 3, 0)
    row = results.tasks[0]
    assert row.stop_reason is None and row.reason.startswith("PlanError: not a valid plan")
    repro = Trajectory.from_jsonl((Path(row.trajectory).parent.parent / "repro" / "trajectory.jsonl").read_text(encoding="utf-8")).steps
    assert row.tokens.tokens_in == 40 + sum(s.tokens_in for s in repro)  # the planner's 40 prompt tokens are in the row
    assert subagent_calls(results, path.parent) == 0


def test_task_list_picks_the_same_evenly_spaced_20_every_time():
    from eval.ablation import task_list

    first, second = task_list(count=20), task_list(count=20)
    ids = [t["id"] for t in first]
    assert ids == [t["id"] for t in second] and len(set(ids)) == 20 and ids == sorted(ids)
    assert {i[:6] for i in ids} == {"seed-e", "seed-m", "seed-h"}  # easy, medium and hard all stay in
    with pytest.raises(ValueError, match="count must be between"):
        task_list(count=99)


def test_the_two_t12_configs_load_and_differ_only_in_the_variant(tmp_path: Path):
    """The ablation is one flipped param: same model, caps, strategy and tasks. Nothing here calls Ollama (building the agent opens no connection)."""
    from eval.ablation import local
    from eval.runner import AgentConfig

    policies = Path(__file__).resolve().parents[1] / "policies"
    a, b = (json.loads((policies / f"p8-t12-{v}.agent.json").read_text(encoding="utf-8")) for v in "AB")
    pa, pb = a.pop("params"), b.pop("params")
    assert (a["model"], a["host"], a["factory"]) == (b["model"], b["host"], b["factory"]) == (LOCAL, "ollama", "eval.ablation:local")
    assert {k for k in pa if pa[k] != pb[k]} == {"out_dir", "variant"} and (pa["variant"], pb["variant"]) == ("single", "planner")
    for config in (a, b):
        callable_agent = local(AgentConfig(**config, params={**pa, "out_dir": str(tmp_path / config["name"])}))
        assert callable(callable_agent)
