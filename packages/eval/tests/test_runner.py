"""P5-T04: the runner on a stub agent. No model call, no network."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from argus_core.types import Check, CheckType, Task, TaskMeta, Ticket

from eval.__main__ import main
from eval.results import Results, schema_json
from eval.runner import AgentConfig, Outcome, run_eval
from eval.stats import percentile, wilson

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = Path(__file__).resolve().parents[1] / "schemas" / "results.schema.json"
WORKED = ROOT / "packages" / "fix-loop" / "runs" / "p4b-full-summary-h10" / "trajectory.jsonl"
NOW = datetime(2026, 11, 1, 12, 0, 0, tzinfo=UTC)
CONFIG = AgentConfig(name="stub", model="stub-model", host="local", factory="eval.stub:make")


def _task(i: int, tier: str = "easy") -> Task:
    return Task(
        id=f"t{i:02d}",
        ticket=Ticket(id=f"t{i:02d}", text="the button overflows"),
        bug_patch="bug",
        golden_patch="gold",
        checks=[Check(type=CheckType.pixel_diff)],
        meta=TaskMeta(source="seeded", archetype="overflow", tier=tier),
    )


def test_wilson_reproduces_the_p3_cell():
    low, high = wilson(20, 29)
    assert (round(low, 6), round(high, 6)) == (0.507695, 0.827246)  # packages/fix-loop/runs/README.md


def test_percentile_interpolates():
    values = [float(i) for i in range(1, 11)]
    assert percentile(values, 50) == 5.5
    assert percentile(values, 95) == 9.55
    assert percentile([], 50) is None
    assert percentile([3.0], 95) == 3.0


def test_stub_run_aggregates():
    tasks = [_task(i, "easy" if i < 5 else "hard") for i in range(10)]

    def agent(task: Task) -> Outcome:
        i = int(task.id[1:])
        return Outcome(
            "resolved" if i < 7 else "unresolved",
            stop_reason="submit",
            steps=i + 1,
            tokens_in=100,
            tokens_out=10,
            tokens_cached=40,
            latency_s=float(i + 1),
        )

    r = run_eval(tasks, agent, CONFIG, now=NOW)
    assert r.counts.model_dump() == {"resolved": 7, "unresolved": 3, "excluded": 0, "error": 0}
    assert (r.resolve_rate.successes, r.resolve_rate.total, r.resolve_rate.rate) == (7, 10, 0.7)
    assert (r.resolve_rate.ci_low, r.resolve_rate.ci_high) == tuple(round(x, 6) for x in wilson(7, 10))
    assert r.tokens.total.model_dump() == {"tokens_in": 1000, "tokens_out": 100, "tokens_cached": 400}
    assert r.tokens.per_task.model_dump() == {"tokens_in": 100.0, "tokens_out": 10.0, "tokens_cached": 40.0}
    assert (r.latency_s.p50, r.latency_s.p95, r.latency_s.n) == (5.5, 9.55, 10)
    assert [t.tier for t in r.tasks] == ["easy"] * 5 + ["hard"] * 5
    assert r.created_at == "2026-11-01T12:00:00Z"
    assert r.trajectory_metrics is None
    assert r.dollar_equivalent is None


def test_excluded_stays_out_and_error_counts_against():
    tasks = [_task(0), _task(1), _task(2), _task(3)]

    outcomes = {
        "t00": Outcome("resolved", tokens_in=10, latency_s=1.0),
        "t01": Outcome("excluded", reason="bug.patch does not apply", tokens_in=999),
        "t02": Outcome("unresolved", tokens_in=10, latency_s=3.0),
    }

    def agent(task: Task) -> Outcome:
        if task.id not in outcomes:
            raise RuntimeError("sandbox died")
        return outcomes[task.id]

    r = run_eval(tasks, agent, CONFIG, now=NOW)
    assert r.counts.model_dump() == {"resolved": 1, "unresolved": 1, "excluded": 1, "error": 1}
    assert (r.resolve_rate.successes, r.resolve_rate.total) == (1, 3)
    assert r.tokens.total.tokens_in == 20  # the excluded row's tokens are not summed
    by_id = {t.task_id: t for t in r.tasks}
    assert by_id["t01"].reason == "bug.patch does not apply" and by_id["t01"].latency_s is None
    assert by_id["t03"].verdict == "error" and by_id["t03"].reason == "RuntimeError: sandbox died"
    assert len(r.tasks) == 4  # nothing is dropped from the rows


def test_wall_time_is_used_when_the_agent_gives_none():
    ticks = iter([0.0, 2.5, 10.0, 14.0])  # two tasks: start/stop pairs
    r = run_eval([_task(0), _task(1)], lambda t: Outcome("resolved"), CONFIG, now=NOW, clock=lambda: next(ticks))
    assert [t.latency_s for t in r.tasks] == [2.5, 4.0]


def test_empty_run_has_null_rates():
    r = run_eval([], lambda t: Outcome("resolved"), CONFIG, now=NOW)
    assert r.resolve_rate.model_dump() == {
        "successes": 0, "total": 0, "rate": None, "ci_low": None, "ci_high": None, "interval": "wilson95",
    }
    assert r.tokens.per_task is None and r.latency_s.p50 is None and r.tasks == []


def test_trajectory_metrics_come_from_the_rows_that_have_one():
    def agent(task: Task) -> Outcome:
        return Outcome("unresolved", trajectory=str(WORKED) if task.id == "t00" else None)

    r = run_eval([_task(0), _task(1)], agent, CONFIG, now=NOW)
    m = r.trajectory_metrics
    assert m is not None and m.trajectories == 1
    assert (m.tool_error_rate.num, m.tool_error_rate.den) == (2, 20)
    assert (m.redundant_call_rate.num, m.redundant_call_rate.den) == (7, 20)


def test_results_json_round_trips_and_keeps_the_dollar_field():
    r = run_eval([_task(0)], lambda t: Outcome("resolved", latency_s=1.0), CONFIG, now=NOW)
    data = json.loads(r.to_json())
    assert data["$_equivalent"] is None and "dollar_equivalent" not in data
    assert data["schema_version"] == 1
    assert Results.model_validate(data) == r


def test_schema_file_matches_the_models():
    assert json.loads(SCHEMA.read_text(encoding="utf-8")) == json.loads(schema_json())
    assert "$_equivalent" in json.loads(schema_json())["properties"]


def test_cli_run_with_the_stub_agent(tmp_path: Path, capsys):
    tasks = tmp_path / "tasks.json"
    tasks.write_text(json.dumps([_task(i).model_dump(mode="json") for i in range(4)]), encoding="utf-8")
    agent = tmp_path / "agent.json"
    agent.write_text(
        json.dumps({**CONFIG.model_dump(), "params": {"resolve": ["t00", "t01", "t02"], "latency_s": 2.0}}),
        encoding="utf-8",
    )
    out = tmp_path / "results.json"
    assert main(["run", "--tasks", str(tasks), "--agent", str(agent), "--out", str(out), "--run-id", "demo"]) == 0
    assert "demo: 3/4 resolved" in capsys.readouterr().out
    r = Results.model_validate_json(out.read_text(encoding="utf-8"))
    assert r.run_id == "demo" and r.agent.name == "stub"
    assert (r.resolve_rate.rate, r.latency_s.p50) == (0.75, 2.0)
    assert r.tokens.total.tokens_cached == 800


def test_committed_example_is_valid_results():
    example = SCHEMA.with_name("results.example.json")
    r = Results.model_validate_json(example.read_text(encoding="utf-8"))
    assert r.dollar_equivalent is None and r.counts.excluded == 1
