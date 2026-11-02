"""P5-T14 Claude-session driver: policies, stage and tier on a pending turn, wrong-kind replies, and folding finished runs
into a results file. Hand-built run folders, no platform checkout, no Docker, no model. Needs the fix-loop and repro-agent
dependencies: `uv run --package repro-agent pytest packages/eval/tests/test_t14_turn.py`."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp", reason="run with: uv run --package repro-agent pytest packages/eval/tests/test_t14_turn.py")
for src in ("eval", "fix-loop", "repro-agent", "bench"):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / src / "src"))

from argus_core.ledger import Ledger
from argus_core.prices import dollar_equivalent
from argus_core.router import load_policy
from argus_core.types import Check, CheckType, Task, TaskMeta, Ticket, Trajectory, TrajectoryMeta, TrajectoryStep

from eval import t14_turn
from eval.runner import AgentConfig

SONNET, HAIKU = "claude-sonnet-5-5", "claude-haiku-5-5"


def test_policies_route_by_variant_and_share_the_strong_tier():
    a, b = (load_policy(t14_turn.VARIANTS[v][1]) for v in "AB")
    assert {a.tiers["strong"].primary.model, b.tiers["strong"].primary.model} == {SONNET}
    assert set(a.stages.values()) == {"strong"}
    assert b.stages == {"repro": "cheap", "localize": "cheap", "fix": "strong"} and b.tiers["cheap"].primary.model == HAIKU
    assert set(t14_turn.WORKER_MODEL) == {SONNET, HAIKU} == set(t14_turn.BUDGET)


def _router(variant: str, answers: list[dict]) -> t14_turn._StageRouter:
    policy = load_policy(t14_turn.VARIANTS[variant][1])
    return t14_turn._StageRouter(policy, Ledger(Path("unused.json"), t14_turn.BUDGET), {t14_turn.HOST: t14_turn._Replay(answers)})


def test_a_pending_turn_names_its_stage_tier_and_model(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for variant, stage, tier, model in [("B", "repro", "cheap", HAIKU), ("B", "fix", "strong", SONNET), ("A", "repro", "strong", SONNET)]:
        with pytest.raises(t14_turn.NeedTurn) as need:
            _router(variant, []).complete(stage, [{"role": "user", "content": "x"}])
        assert (need.value.stage, need.value.tier, need.value.model) == (stage, tier, model)


def test_a_stored_answer_is_served_once_and_a_policy_change_is_caught(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    given = [{"stage": "repro", "tier": "cheap", "model": HAIKU, "reply": "await expect(a).toBeVisible();"}]
    router = _router("B", given)
    messages = [{"role": "user", "content": "x" * 400}]
    routed = router.complete("repro", messages)
    assert routed.completion.content == given[0]["reply"] and (routed.tier, routed.model) == ("cheap", HAIKU)
    assert routed.completion.usage.tokens_in == len(json.dumps(messages)) // 4  # chars/4 estimate, as in fix_loop.turn
    with pytest.raises(RuntimeError, match="policy now routes"):
        _router("A", given).complete("repro", [{"role": "user", "content": "x"}])


def test_wrong_kind_of_reply_is_rejected_by_stage():
    call = json.dumps({"tool": "submit", "arguments": {}})
    assert t14_turn._wrong_kind("fix", call) is None
    assert t14_turn._wrong_kind("fix", "just text") and t14_turn._wrong_kind("fix", "")
    assert t14_turn._wrong_kind("repro", "```js\nawait expect(a).toBeVisible();\n```") is None
    assert t14_turn._wrong_kind("repro", call) and t14_turn._wrong_kind("repro", "  ")


def _task(i: int) -> Task:
    return Task(
        id=f"seed-t{i}", ticket=Ticket(id=f"seed-t{i}", text="x"), bug_patch="b", golden_patch="g",
        checks=[Check(type=CheckType.pixel_diff)], meta=TaskMeta(source="seeded", archetype="a", tier="easy"),
    )


def _traj(path: Path, rows: list[tuple[str, str, int, int]]) -> None:
    steps = [TrajectoryStep(index=i, tokens_in=a, tokens_out=b, tier=tier, host="claude-session", model=model) for i, (tier, model, a, b) in enumerate(rows)]
    meta = TrajectoryMeta(run_id="r", task_id="t", model=SONNET, host="claude-session", prompt_hash="p", git_commit="c")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(Trajectory(meta=meta, steps=steps).to_jsonl(), encoding="utf-8")


def test_finished_runs_fold_into_a_results_file_split_by_tier(tmp_path: Path, monkeypatch):
    base = tmp_path / "B"
    done = base / "seed-t0"
    _traj(done / "repro" / "trajectory.jsonl", [("cheap", HAIKU, 300, 40)])
    _traj(done / "fix" / "trajectory.jsonl", [("strong", SONNET, 800, 20), ("strong", SONNET, 900, 10)])
    (done / "verdict.json").write_text(json.dumps({"verdict": "resolved", "stop_reason": "submit", "wall_s": 61.5}), encoding="utf-8")
    monkeypatch.setattr(t14_turn, "RUNS", tmp_path)
    tasks = tmp_path / "tasks.json"
    tasks.write_text(json.dumps([_task(i).model_dump(mode="json") for i in range(2)]), encoding="utf-8")
    out = tmp_path / "res.json"
    assert t14_turn.results("B", tasks, out, []) == 0
    res = json.loads(out.read_text(encoding="utf-8"))
    rows = {r["task_id"]: r for r in res["tasks"]}
    assert rows["seed-t0"]["verdict"] == "resolved" and rows["seed-t0"]["tokens"]["tokens_in"] == 2000
    assert rows["seed-t1"]["verdict"] == "error" and "did not finish" in rows["seed-t1"]["reason"]  # a task with no run is an error row, not a gap
    assert res["agent"]["params"]["claude_session"] is True and res["agent"]["params"]["worker_models"] == {"cheap": "haiku", "strong": "sonnet"}
    # priced model by model: haiku tokens at the haiku rate, sonnet tokens at the sonnet rate
    want = dollar_equivalent(HAIKU, 300, 40) + dollar_equivalent(SONNET, 1700, 30)
    assert res["$_equivalent"] == pytest.approx(want, abs=1e-6)
    assert rows["seed-t0"]["latency_s"] == 61.5  # the run's own wall clock, not the replay's


def test_replay_agent_reads_only_what_the_run_wrote(tmp_path: Path):
    agent = t14_turn.replay(AgentConfig(name="n", model=SONNET, factory="eval.t14_turn:replay", params={"out_dir": str(tmp_path)}))
    assert agent(_task(9)).verdict == "error"


def test_replay_fix_only_leaves_the_repro_stage_out_of_the_totals(tmp_path: Path):
    done = tmp_path / "seed-t0"
    _traj(done / "repro" / "trajectory.jsonl", [("strong", SONNET, 300, 40)])
    _traj(done / "fix" / "trajectory.jsonl", [("strong", SONNET, 800, 20)])
    (done / "verdict.json").write_text(json.dumps({"verdict": "resolved", "stop_reason": "submit", "wall_s": 1.0}), encoding="utf-8")

    def tokens(**params) -> tuple[int, int]:
        config = AgentConfig(name="n", model=SONNET, factory="eval.t14_turn:replay", params={"out_dir": str(tmp_path), **params})
        out = t14_turn.replay(config)(_task(0))
        return out.tokens_in, out.tokens_out

    assert tokens() == (1100, 60) and tokens(fix_only=True) == (800, 20)


def test_the_table_labels_a_claude_session_run_and_leaves_the_quota_cell_a_dash(tmp_path: Path, monkeypatch):
    from eval.ablation import DASH, table

    test_finished_runs_fold_into_a_results_file_split_by_tier(tmp_path, monkeypatch)
    text = table(tmp_path / "res.json", tmp_path / "res.json")
    assert "Claude-session tiers" in text and "chars/4 estimates" in text
    assert f"| {DASH} | " in text and f"{DASH} (stage" not in text  # quota share is a dash; the trajectories matched


def _git(repo: Path, *args: str) -> None:
    import subprocess

    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-C", str(repo), *args], check=True, capture_output=True)


def test_variant_t_starts_a_mutated_task_fix_stage_only(tmp_path: Path, monkeypatch, capsys):
    """P5.5-T04: a train mutant is found under tasks/mutated, runs under runs/p55-t04/<id>, and the first model turn is a fix turn."""
    repo = tmp_path / "platform"
    repo.mkdir()
    (repo / "a.css").write_text(".x {\n  font-size: 13px;\n}\n", encoding="utf-8", newline="\n")
    _git(repo, "init", "-q")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "init")
    mutated = tmp_path / "mutated" / "mut-9999"
    mutated.mkdir(parents=True)
    (mutated / "ticket.json").write_text(json.dumps({"id": "mut-9999", "text": "font-size on .x changed from 13px."}), encoding="utf-8")
    (mutated / "checks.json").write_text("[]", encoding="utf-8")
    (mutated / "bug.patch").write_bytes(b"--- a/a.css\n+++ b/a.css\n@@ -1,3 +1,3 @@\n .x {\n-  font-size: 13px;\n+  font-size: 99px;\n }\n")
    monkeypatch.setenv("ARGUS_PLATFORM_REPO", str(repo))
    monkeypatch.setattr(t14_turn, "MUTATED", tmp_path / "mutated")
    monkeypatch.setattr(t14_turn, "SEEDED", tmp_path / "seeded")
    monkeypatch.setattr(t14_turn, "TRAIN_RUNS", tmp_path / "p55-t04")
    monkeypatch.setattr(t14_turn, "_head", lambda: "stub")

    with pytest.raises(SystemExit, match="not found"):  # A and B still look only in seeded
        t14_turn.start("A", "mut-9999")
    assert t14_turn.start("T", "mut-9999") == 0
    assert "next: stage=fix tier=strong worker_model=sonnet" in capsys.readouterr().out  # no repro stage was asked for
    out = tmp_path / "p55-t04" / "mut-9999"
    assert json.loads((out / "task.json").read_text(encoding="utf-8"))["task"] == str(mutated)
    assert not (out / "repro").exists()
    # a stub reply moves the run on; the patch was applied to the tree
    assert t14_turn.answer("T-mut-9999", json.dumps({"tool": "read_file", "arguments": {"path": "a.css"}})) == 0
    assert "recorded 1 answers; next: stage=fix" in capsys.readouterr().out
    assert "99px" in (Path(json.loads((out / "task.json").read_text(encoding="utf-8"))["tree"]) / "a.css").read_text(encoding="utf-8")
    assert t14_turn._run_dir("T-mut-9999") == out


def test_variant_s_runs_a_seeded_task_fix_stage_only_with_the_skill_catalog(tmp_path: Path, monkeypatch, capsys):
    """P5.5-T08: variant S is variant A's task and policy with the repro stage off and the reviewed skills on."""
    repo = tmp_path / "platform"
    repo.mkdir()
    (repo / "a.css").write_text(".x {\n  font-size: 13px;\n}\n", encoding="utf-8", newline="\n")
    _git(repo, "init", "-q")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "init")
    seeded = tmp_path / "seeded" / "seed-x01"
    seeded.mkdir(parents=True)
    (seeded / "ticket.json").write_text(json.dumps({"id": "seed-x01", "text": "font-size on .x changed from 13px."}), encoding="utf-8")
    (seeded / "checks.json").write_text("[]", encoding="utf-8")
    (seeded / "bug.patch").write_bytes(b"--- a/a.css\n+++ b/a.css\n@@ -1,3 +1,3 @@\n .x {\n-  font-size: 13px;\n+  font-size: 99px;\n }\n")
    monkeypatch.setenv("ARGUS_PLATFORM_REPO", str(repo))
    monkeypatch.setattr(t14_turn, "SEEDED", tmp_path / "seeded")
    monkeypatch.setattr(t14_turn, "SKILL_RUNS", tmp_path / "p55-t08")
    monkeypatch.setattr(t14_turn, "_head", lambda: "stub")

    assert t14_turn.start("S", "seed-x01") == 0
    assert "next: stage=fix tier=strong worker_model=sonnet" in capsys.readouterr().out
    out = tmp_path / "p55-t08" / "seed-x01"
    assert t14_turn._run_dir("S-seed-x01") == out and not (out / "repro").exists()
    assert t14_turn.SKILLS.is_dir() and sorted(p.name for p in t14_turn.SKILLS.iterdir()) and "load_skill" in _shown(out, capsys)
    assert "Repro: not-run" in _shown(out, capsys)  # the same fix prompt variant A had when its repro stage found nothing


def _shown(out: Path, capsys) -> str:
    t14_turn._replay(out)
    return capsys.readouterr().out
