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

from argus_core.ledger import load_quotas
from argus_core.prices import dollar_equivalent
from argus_core.types import Check, CheckType, Task, TaskMeta, Ticket, Trajectory

from eval.__main__ import main
from eval.ablation import QUOTAS, Measured, quota_share, table, tier_usage
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
