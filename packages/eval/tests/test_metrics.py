"""P5-T03: the metrics match docs/metrics.md, including its worked example on a stored trajectory."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from argus_core.types import StopReason, Trajectory, TrajectoryMeta, TrajectoryStep

from eval.__main__ import main
from eval.metrics import call_key, format_summary, load_dir, load_trajectory, run_metrics, summarize

ROOT = Path(__file__).resolve().parents[3]
WORKED = ROOT / "packages" / "fix-loop" / "runs" / "p4b-full-summary-h10" / "trajectory.jsonl"


def _call(index: int, tool: str, args: dict, *, error: str | None = None, stop: StopReason | None = None) -> TrajectoryStep:
    return TrajectoryStep(
        index=index,
        tool_name=tool,
        tool_error=error,
        stop_reason=stop,
        raw_response=json.dumps({"tool": tool, "arguments": args}),
    )


def _traj(steps: list[TrajectoryStep]) -> Trajectory:
    meta = TrajectoryMeta(run_id="r", task_id="t", model="m", host="h", prompt_hash="p", git_commit="g")
    return Trajectory(meta=meta, steps=steps)


def test_worked_example():
    m = run_metrics(load_trajectory(WORKED))
    assert m.steps == 20
    assert (m.tool_errors, m.tool_errors / m.steps) == (2, 0.10)
    assert (m.redundant, m.calls, m.redundant / m.calls) == (7, 20, 0.35)
    assert m.stuck is False
    assert (m.gate_failures, m.recovered) == (0, 0)
    summary = summarize([m])
    assert summary.tool_error_rate.value == 0.1
    assert summary.redundant_call_rate.value == 0.35
    assert summary.stuck_rate.value == 0.0
    assert summary.recover_after_gate_failure_rate.value is None


def test_edit_resets_redundancy_and_submit_is_not_counted():
    steps = [
        _call(0, "read_file", {"path": "a"}),
        _call(1, "edit", {"path": "a"}),
        _call(2, "read_file", {"path": "a"}),  # tree changed: not redundant
        _call(3, "read_file", {"path": "a"}),  # redundant
        _call(4, "submit", {}),
        _call(5, "submit", {}),
    ]
    m = run_metrics(_traj(steps))
    assert (m.calls, m.redundant) == (4, 1)


def test_stuck_needs_three_calls_in_a_row():
    same = [_call(i, "search", {"query": "x"}) for i in range(3)]
    assert run_metrics(_traj(same)).stuck is True
    broken = [same[0], same[1], TrajectoryStep(index=2, tool_error="failed", raw_response="oops"), same[2]]
    assert run_metrics(_traj(broken)).stuck is False
    assert run_metrics(_traj(same[:2])).stuck is False


def test_rejected_submit_recovers_when_a_later_submit_is_accepted():
    recovered = _traj([
        _call(0, "submit", {}),
        _call(1, "edit", {"path": "a"}),
        _call(2, "submit", {}, stop=StopReason.submit),
    ])
    m = run_metrics(recovered)
    assert (m.gate_failures, m.recovered) == (1, 1)
    never = _traj([
        _call(0, "submit", {}),
        _call(1, "search", {"query": "q"}, stop=StopReason.step_cap),
    ])
    assert (run_metrics(never).gate_failures, run_metrics(never).recovered) == (1, 0)
    s = summarize([run_metrics(recovered), run_metrics(never)])
    assert (s.recover_after_gate_failure_rate.num, s.recover_after_gate_failure_rate.den) == (1, 2)


def test_key_reads_bare_arguments_and_raw_text():
    bare = TrajectoryStep(index=0, tool_name="bash", raw_response='{"command": "ls"}')
    wrapped = _call(0, "bash", {"command": "ls"})
    assert call_key(bare) == call_key(wrapped)
    text = TrajectoryStep(index=0, tool_name="bash", raw_response="not json")
    assert call_key(text) != call_key(bare)


def test_rates_are_pooled_not_averaged():
    short = _traj([_call(0, "search", {"query": "a"}, error="not-found")])
    long = _traj([_call(i, "search", {"query": str(i)}) for i in range(9)])
    s = summarize([run_metrics(short), run_metrics(long)])
    assert (s.tool_error_rate.num, s.tool_error_rate.den) == (1, 10)
    assert (s.steps.total, s.steps.median) == (10, 5)


def test_empty_directory_has_null_rates(tmp_path: Path):
    s = summarize(load_dir(tmp_path))
    assert s.trajectories == 0 and s.tool_error_rate.value is None and s.steps.mean is None


def test_cli_prints_all_metrics(tmp_path: Path, capsys):
    run = tmp_path / "run-1"
    run.mkdir()
    (run / "trajectory.jsonl").write_text(load_trajectory(WORKED).to_jsonl(), encoding="utf-8")
    assert main(["metrics", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "trajectories: 1" in out
    assert "tool_error_rate: 0.1000 (2/20)" in out
    assert "redundant_call_rate: 0.3500 (7/20)" in out
    assert "stuck_rate: 0.0000 (0/1)" in out
    assert "recover_after_gate_failure_rate: n/a (0/0)" in out
    assert out.strip() == format_summary(summarize(load_dir(tmp_path))).strip()


def test_every_stored_trajectory_parses():
    runs = load_dir(ROOT / "packages" / "fix-loop" / "runs", "p[34]*/trajectory.jsonl")
    assert len(runs) > 100
    assert all(r.gate_failures == 0 for r in runs)
