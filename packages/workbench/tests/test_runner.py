"""P10-T04: the runners play a run folder, one step at a time, with no model and no sleeping.

Every test points the store at tmp_path (conftest) and passes a tick that does nothing.
"""

import json
import threading
from datetime import UTC, datetime, timedelta

import pytest
from argus_core import ledger as ledger_module
from argus_core.types import StopReason, Trajectory
from flow.states import TRANSITIONS, Event, State

from argus_workbench import fixtures, store
from argus_workbench.errors import WorkbenchError
from argus_workbench.runner import ReplayRunner, ScriptedRunner, owner_stop

TICKET = {"id": "T-1", "text": "SIMULATED test ticket: the header is cut off at 375 px."}
ENDS = {  # scenario -> (state, stop reason, display state), the table in docs/architecture/p10.md
    "normal": (State.AWAITING_QA, StopReason.submit, "awaiting-qa"),
    "quota": (State.FAILED, StopReason.quota_exceeded, "quota-wait"),
    "stuck": (State.FAILED, StopReason.stuck, "stuck"),
    "verifier": (State.FAILED, StopReason.submit, "failed"),
    "judge": (State.AWAITING_QA, StopReason.submit, "awaiting-qa"),
}
LEGAL = {(a, b) for a, _, b, _ in TRANSITIONS}


def make(run_id="run-a", scenario="normal", origin="SIMULATED", clock=None):
    store.create_run(TICKET, scenario=scenario if origin == "SIMULATED" else None, origin=origin, run_id=run_id,
                     clock=clock or fixtures.fixed_clock())
    return store.run_dir(run_id)


def play(scenario, run_id=None, **kw):
    run_dir = make(run_id or f"run-{scenario}", scenario)
    return run_dir, ScriptedRunner(scenario).play(run_dir, clock=fixtures.fixed_clock(), **kw)


@pytest.fixture
def visited(monkeypatch):
    """Every state a run is moved into, in order, recorded around the real store.advance."""
    seen = []
    real = store.advance

    def spy(run_id, event, **kw):
        before = store.get_state(run_id).state
        after = real(run_id, event, **kw)
        seen.append((before, after.state))
        return after

    monkeypatch.setattr(store, "advance", spy)
    return seen


@pytest.mark.parametrize("scenario", ENDS)
def test_each_scenario_ends_in_the_state_and_stop_reason_the_table_names(scenario, visited):
    run_dir, end = play(scenario)
    state, reason, display = ENDS[scenario]
    assert (end.state, end.stop_reason, end.display_state, end.origin) == (state, reason, display, "SIMULATED")
    assert store.get_state(run_dir.name) == end
    assert all(step in LEGAL for step in visited), visited  # only flow.states transitions


def test_a_normal_run_walks_the_whole_path(visited):
    play("normal")
    assert [after for _, after in visited] == [State.REPRODUCING, State.FIXING, State.VERIFYING, State.OPENING_PR, State.AWAITING_QA]


@pytest.mark.parametrize("scenario", ENDS)
def test_trajectory_validates_with_tokens_on_every_step(scenario):
    run_dir, _ = play(scenario)
    raw = (run_dir / "trajectory.jsonl").read_text("utf-8")
    trajectory = Trajectory.from_jsonl(raw)  # the argus-core schema
    assert [s.index for s in trajectory.steps] == list(range(len(trajectory.steps)))
    for line in raw.splitlines()[1:]:
        row = json.loads(line)
        assert {"tokens_in", "tokens_out", "tokens_cached"} <= row.keys()
        assert row["message"]["origin"] == "SIMULATED" and row["message"]["stage"] in ("reproduce", "locate", "fix", "verify")
    assert trajectory.steps[-1].stop_reason is not None or scenario == "verifier"
    assert sum(s.tokens_in for s in trajectory.steps) > 0


def test_steps_are_written_one_at_a_time():
    sizes = []
    run_dir = make()
    ScriptedRunner("normal").play(run_dir, clock=fixtures.fixed_clock(), tick=lambda: sizes.append(len(store.read_file("run-a", "trajectory.jsonl").steps)))
    assert sizes == list(range(1, len(sizes) + 1)) and len(sizes) > 5


def test_the_quota_scenario_is_stopped_by_the_real_ledger(monkeypatch):
    raised = []
    real_call = ledger_module.Ledger.call

    def call(self, model, send, **kw):
        try:
            return real_call(self, model, send, **kw)
        except ledger_module.QuotaExceeded as exc:
            raised.append(exc)
            raise

    monkeypatch.setattr(ledger_module.Ledger, "call", call)
    run_dir, end = play("quota")
    assert len(raised) == 1 and raised[0].limit == "tokens_per_day"
    last = store.read_file(run_dir.name, "trajectory.jsonl").steps[-1]
    assert last.stop_reason is StopReason.quota_exceeded and last.tool_error == str(raised[0])
    assert last.message["text"] == str(raised[0]) and "would exceed tokens_per_day" in last.tool_error
    assert end.display_state == "quota-wait" and not (run_dir / "verdict.json").exists()


def test_the_other_scenarios_never_hit_the_quota(monkeypatch):
    for scenario in ("normal", "stuck", "verifier", "judge"):
        play(scenario)  # a QuotaExceeded here would have been raised out of play()


def test_stuck_repeats_one_tool_call_three_times():
    run_dir, _ = play("stuck")
    steps = store.read_file(run_dir.name, "trajectory.jsonl").steps
    assert [s.tool_name for s in steps[-3:]] == ["locate"] * 3 and steps[-1].stop_reason is StopReason.stuck


def test_files_by_scenario():
    got = {}
    for scenario in ENDS:
        run_dir, _ = play(scenario)
        got[scenario] = sorted(p.name for p in run_dir.iterdir())
    full = ["patch.diff", "report.html", "state.json", "ticket.json", "trajectory.jsonl", "verdict.json"]
    assert got["normal"] == got["judge"] == got["verifier"] == full
    assert got["quota"] == got["stuck"] == ["state.json", "ticket.json", "trajectory.jsonl"]
    assert store.read_file("run-verifier", "verdict.json").ok is False
    assert store.read_file("run-judge", "verdict.json").judge_label == "fail"
    assert store.read_file("run-normal", "verdict.json").judge_label == "pass"


def test_every_file_carries_the_simulated_tag():
    run_dir, end = play("normal")
    assert end.origin == "SIMULATED"
    assert store.read_file("run-normal", "verdict.json").origin == "SIMULATED"
    assert "SIMULATED" in store.read_file("run-normal", "report.html") and "SIMULATED" in store.read_file("run-normal", "patch.diff")
    assert all(s.message["origin"] == "SIMULATED" for s in store.read_file("run-normal", "trajectory.jsonl").steps)
    assert not list(run_dir.glob(".*.tmp"))  # no temp file left by the atomic writes


def test_a_runner_for_one_origin_refuses_a_run_of_the_other():
    run_dir = make("run-r", origin="REPLAY")
    with pytest.raises(WorkbenchError) as err:
        ScriptedRunner("normal").play(run_dir)
    assert err.value.code == "bad_origin" and store.get_state("run-r").state is State.RECEIVED


def test_unknown_scenario():
    with pytest.raises(WorkbenchError) as err:
        ScriptedRunner("nope")
    assert err.value.code == "unknown_scenario"


# ---- stop -----------------------------------------------------------------------------------------------------


def test_stop_ends_a_running_run_in_failed_with_the_owner_step():
    stop, count = threading.Event(), []

    def tick():
        count.append(1)
        if len(count) == 3:
            stop.set()

    run_dir = make()
    end = ScriptedRunner("normal").play(run_dir, clock=fixtures.fixed_clock(), tick=tick, stop=stop)
    assert (end.state, end.stop_reason, end.display_state) == (State.FAILED, None, "failed")
    steps = store.read_file("run-a", "trajectory.jsonl").steps
    assert len(steps) == 4 and steps[2].tool_name != "owner-stop"  # 3 played steps, then the stop step
    assert steps[-1].tool_name == "owner-stop" and steps[-1].tool_error == "stopped by owner"
    assert steps[-1].message["origin"] == "SIMULATED" and not (run_dir / "verdict.json").exists()


@pytest.mark.parametrize("stop_at", [1, 6, 11])
def test_stop_in_each_stage_uses_a_legal_failure_event(stop_at, visited):
    stop, count = threading.Event(), []
    run_dir = make()
    ScriptedRunner("normal").play(run_dir, clock=fixtures.fixed_clock(), stop=stop,
                                  tick=lambda: (count.append(1), stop.set() if len(count) == stop_at else None))
    assert store.get_state("run-a").state is State.FAILED and all(step in LEGAL for step in visited)


def test_owner_stop_works_with_no_player_and_refuses_a_run_that_is_not_running():
    run_dir = make()
    with pytest.raises(WorkbenchError) as err:
        owner_stop("run-a", clock=fixtures.fixed_clock(), root=run_dir.parent)
    assert err.value.code == "not_running"  # received: nothing to stop
    store.advance("run-a", Event.START)
    end = owner_stop("run-a", clock=fixtures.fixed_clock(), root=run_dir.parent)  # reproducing, no trajectory file yet
    assert end.state is State.FAILED and end.stop_reason is None
    with pytest.raises(WorkbenchError):
        owner_stop("run-a", clock=fixtures.fixed_clock(), root=run_dir.parent)


# ---- replay ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("scenario", ["normal", "quota", "stuck", "verifier"])
def test_replay_copies_the_recorded_steps_tagged_replay(scenario):
    source = fixtures.write_fixture_run(scenario, root=store.store_root())
    src_dir = store.run_dir(source.run_id)
    play_dir = make("run-replay", origin="REPLAY")
    end = ReplayRunner(src_dir).play(play_dir, clock=fixtures.fixed_clock())
    recorded = store.read_file(source.run_id, "trajectory.jsonl")
    replayed = store.read_file("run-replay", "trajectory.jsonl")
    assert [(s.tokens_in, s.tokens_out, s.tokens_cached, s.tool_name, s.stop_reason) for s in replayed.steps] == \
           [(s.tokens_in, s.tokens_out, s.tokens_cached, s.tool_name, s.stop_reason) for s in recorded.steps]
    assert all(s.message["origin"] == "REPLAY" for s in replayed.steps)
    assert replayed.meta.run_id == "run-replay" and replayed.meta.host == "replay"
    assert (end.state, end.origin, end.stop_reason) == (State.FAILED, "REPLAY", recorded.steps[-1].stop_reason)
    assert sorted(p.name for p in play_dir.iterdir()) == ["state.json", "ticket.json", "trajectory.jsonl"]  # no patch, no verdict
    assert store.get_state(source.run_id) == source  # the source folder is not touched


def test_replay_of_a_quota_run_shows_quota_wait():
    source = fixtures.write_fixture_run("quota", root=store.store_root())
    end = ReplayRunner(store.run_dir(source.run_id)).play(make("run-replay", origin="REPLAY"), clock=fixtures.fixed_clock())
    assert end.display_state == "quota-wait"


def test_replay_validates_before_writing_anything():
    bad = store.store_root() / "not-a-run"
    bad.mkdir(parents=True)
    play_dir = make("run-replay", origin="REPLAY")
    for text, code in [("", "invalid_trajectory"), ('{"kind": "meta"}\n', "invalid_trajectory"), ("not json\n", "invalid_trajectory")]:
        (bad / "trajectory.jsonl").write_text(text, encoding="utf-8")
        with pytest.raises(WorkbenchError) as err:
            ReplayRunner(bad).play(play_dir)
        assert err.value.code == code
    (bad / "trajectory.jsonl").unlink()
    with pytest.raises(WorkbenchError) as err:
        ReplayRunner(bad).play(play_dir)
    assert err.value.code == "missing_file"
    assert store.get_state("run-replay").state is State.RECEIVED and not (play_dir / "trajectory.jsonl").exists()


def test_a_step_with_an_unknown_field_is_refused_by_the_schema():
    source = fixtures.write_fixture_run("normal", root=store.store_root())
    path = store.run_dir(source.run_id) / "trajectory.jsonl"
    lines = path.read_text("utf-8").splitlines()
    row = json.loads(lines[1])
    row["origin"] = "SIMULATED"  # an extra top-level field: the schema forbids it, which is why the tag sits in `message`
    path.write_text("\n".join([lines[0], json.dumps(row), *lines[2:]]) + "\n", encoding="utf-8")
    with pytest.raises(WorkbenchError):
        ReplayRunner(path.parent).load()


def test_the_clock_is_injected():
    start = datetime(2030, 5, 1, tzinfo=UTC)
    calls = iter(range(10**6))
    run_dir = make(clock=lambda: start)
    end = ScriptedRunner("normal").play(run_dir, clock=lambda: start + timedelta(seconds=next(calls)))
    assert end.updated_at > start and end.created_at == start
