"""P10-T01: the example run folders validate and end where the spec says. All SIMULATED; no model is called."""

import json

import pytest
from argus_core.types import StopReason
from flow.states import State

from argus_workbench import fixtures, store
from argus_workbench.spec import scenario_ids

ENDS = {  # scenario -> (state, stop reason, display state, verdict ok, judge label)
    "normal": (State.AWAITING_QA, StopReason.submit, "awaiting-qa", True, "pass"),
    "quota": (State.FAILED, StopReason.quota_exceeded, "quota-wait", None, None),
    "stuck": (State.FAILED, StopReason.stuck, "stuck", None, None),
    "verifier": (State.FAILED, StopReason.submit, "failed", False, "not run"),
    "judge": (State.AWAITING_QA, StopReason.submit, "awaiting-qa", True, "fail"),
}


def test_every_scenario_has_a_fixture_expectation():
    assert set(ENDS) == set(scenario_ids())


@pytest.mark.parametrize("scenario", scenario_ids())
def test_fixture_folder_ends_where_the_spec_says(tmp_path, scenario):
    fixtures.write_fixture_run(scenario, root=tmp_path)
    rid = f"fixture-{scenario}"
    state = store.get_state(rid, root=tmp_path)
    want_state, want_stop, want_display, want_ok, want_judge = ENDS[scenario]
    assert (state.state, state.stop_reason, state.display_state) == (want_state, want_stop, want_display)
    assert state.origin == "SIMULATED" and state.scenario == scenario
    traj = store.read_file(rid, "trajectory.jsonl", root=tmp_path)
    assert traj.steps and traj.steps[-1].stop_reason == want_stop
    assert all(s.message["origin"] == "SIMULATED" for s in traj.steps)
    assert [s.index for s in traj.steps] == list(range(len(traj.steps)))
    assert all(s.tokens_in >= 0 and s.tokens_cached >= 0 for s in traj.steps)
    if want_ok is None:
        assert not store.has_file(rid, "verdict.json", root=tmp_path)
        assert not store.has_file(rid, "patch.diff", root=tmp_path)
    else:
        v = store.read_file(rid, "verdict.json", root=tmp_path)
        assert v.ok is want_ok and v.judge_label == want_judge and v.origin == "SIMULATED" and v.judge_advisory
        assert store.read_file(rid, "patch.diff", root=tmp_path).strip()
        assert "SIMULATED" in store.read_file(rid, "report.html", root=tmp_path)


def test_verifier_fixture_fails_overflow_on_another_route(tmp_path):
    fixtures.write_fixture_run("verifier", root=tmp_path)
    v = store.read_file("fixture-verifier", "verdict.json", root=tmp_path)
    assert [c.name for c in v.checks] == ["pixel", "overflow"]  # short-circuited: axe and console never ran
    assert v.failed_check == "overflow" and v.checks[1].route == "/ops/horizon" and v.first_failure == "overflow on /ops/horizon"


def test_stuck_repeats_one_call_and_quota_names_the_ledger_message(tmp_path):
    fixtures.write_all_fixtures(root=tmp_path)
    stuck = store.read_file("fixture-stuck", "trajectory.jsonl", root=tmp_path)
    assert [s.tool_name for s in stuck.steps[-3:]] == ["locate"] * 3
    quota = store.read_file("fixture-quota", "trajectory.jsonl", root=tmp_path)
    assert quota.steps[-1].stop_reason == StopReason.quota_exceeded and "would exceed" in quota.steps[-1].tool_error


def test_write_all_and_replay_variant(tmp_path):
    states = fixtures.write_all_fixtures(root=tmp_path)
    assert set(states) == set(scenario_ids())
    replay = fixtures.write_all_fixtures(root=tmp_path, origin="REPLAY")
    assert all(s.origin == "REPLAY" and s.scenario is None for s in replay.values())
    assert len(store.list_runs(root=tmp_path)) == 10
    assert {json.loads(p.read_text("utf-8"))["origin"] for p in tmp_path.glob("*/verdict.json")} == {"SIMULATED", "REPLAY"}


def test_fixture_with_unknown_scenario_is_refused(tmp_path):
    with pytest.raises(ValueError):
        fixtures.write_fixture_run("bogus", root=tmp_path)
