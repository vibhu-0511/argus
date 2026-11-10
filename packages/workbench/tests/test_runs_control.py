"""P10-T04: start, stop and retry over HTTP and through the manager. A zero-millisecond tick: no test sleeps."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from flow.states import Event

from argus_workbench import fixtures, store
from argus_workbench.manager import RunManager
from argus_workbench.server import create_app

TOKEN = "test-token-not-secret"
H = {"X-Workbench-Token": TOKEN}
TICKET = {"id": "T-1", "text": "SIMULATED test ticket: the header is cut off at 375 px."}


@pytest.fixture
def mgr():
    return RunManager(tick_ms=0)


@pytest.fixture
def api(mgr):
    app = create_app(token=TOKEN)
    app.state.run_manager = mgr
    return TestClient(app, base_url="http://127.0.0.1")


def new(run_id="run-a", scenario="normal", origin="SIMULATED"):
    return store.create_run(TICKET, scenario=scenario, origin=origin, run_id=run_id)


def folder_bytes(run_id):
    return {p.name: p.read_bytes() for p in store.run_dir(run_id).iterdir()}


def test_start_plays_a_normal_run_to_awaiting_qa(api, mgr):
    new()
    res = api.post("/api/runs/run-a/start", headers=H)
    assert res.status_code == 200 and res.json()["state"]["state"] == "reproducing"
    mgr.wait("run-a")
    state = store.get_state("run-a")
    assert (state.state.value, state.stop_reason.value, state.origin) == ("awaiting-qa", "submit", "SIMULATED")


def test_start_needs_the_token(api):
    new()
    assert api.post("/api/runs/run-a/start").status_code == 403
    assert api.post("/api/runs/run-a/stop").status_code == 403
    assert api.post("/api/runs/run-a/retry").status_code == 403
    assert store.get_state("run-a").state.value == "received"


def test_start_twice_and_start_after_the_end_are_refused(api, mgr):
    new()
    api.post("/api/runs/run-a/start", headers=H)
    again = api.post("/api/runs/run-a/start", headers=H)
    mgr.wait()
    assert again.status_code == 409 and again.json()["error"]["code"] == "not_startable"
    assert api.post("/api/runs/run-a/start", headers=H).status_code == 409


def test_start_errors_are_typed(api):
    assert api.post("/api/runs/run-none/start", headers=H).json()["error"]["code"] == "unknown_run"
    assert api.post("/api/runs/BAD ID/start", headers=H).json()["error"]["code"] == "bad_run_id"
    store.create_run(TICKET, run_id="run-b")  # no scenario
    res = api.post("/api/runs/run-b/start", headers=H)
    assert res.status_code == 400 and res.json()["error"] == {"code": "scenario_required", "field": "scenario", "message": res.json()["error"]["message"]}
    assert api.post("/api/runs/run-b/start", headers=H, json={"scenario": "nope"}).json()["error"]["code"] == "unknown_scenario"
    assert api.post("/api/runs/run-b/start", headers=H, json={"extra": 1}).status_code == 422
    assert store.get_state("run-b").state.value == "received"  # none of the refusals moved it


def test_start_can_pick_the_scenario_for_a_run_made_without_one(api, mgr):
    store.create_run(TICKET, run_id="run-b")
    api.post("/api/runs/run-b/start", headers=H, json={"scenario": "stuck"})
    mgr.wait()
    state = store.get_state("run-b")
    assert (state.scenario, state.display_state) == ("stuck", "stuck")


def test_a_replay_run_needs_a_stored_source(api, mgr):
    store.create_run(TICKET, run_id="run-r", origin="REPLAY")
    assert api.post("/api/runs/run-r/start", headers=H).json()["error"]["code"] == "replay_source_required"
    assert api.post("/api/runs/run-r/start", headers=H, json={"replay_from": "run-r"}).json()["error"]["code"] == "bad_replay_source"
    assert api.post("/api/runs/run-r/start", headers=H, json={"replay_from": "../x"}).json()["error"]["code"] == "bad_run_id"
    fixtures.write_fixture_run("stuck", root=store.store_root())
    assert api.post("/api/runs/run-r/start", headers=H, json={"replay_from": "fixture-stuck"}).status_code == 200
    mgr.wait()
    state = store.get_state("run-r")
    assert (state.origin, state.display_state) == ("REPLAY", "stuck")
    new("run-s")  # a SIMULATED run cannot be given a replay source
    assert api.post("/api/runs/run-s/start", headers=H, json={"replay_from": "fixture-stuck"}).json()["error"]["code"] == "bad_replay_source"


def test_a_crash_in_the_runner_never_leaves_a_running_state(api, mgr, monkeypatch):
    new()
    monkeypatch.setattr("argus_workbench.runner.fixtures._steps", lambda scenario: 1 / 0)
    api.post("/api/runs/run-a/start", headers=H)
    mgr.wait()
    assert store.get_state("run-a").state.value == "failed"


# ---- stop -----------------------------------------------------------------------------------------------------


def test_stop_ends_a_slow_run_at_once():
    slow = RunManager(tick_ms=60_000)  # one tick would take a minute; stop must wake it
    app = create_app(token=TOKEN)
    app.state.run_manager = slow
    api = TestClient(app, base_url="http://127.0.0.1")
    new()
    api.post("/api/runs/run-a/start", headers=H)
    res = api.post("/api/runs/run-a/stop", headers=H)
    assert res.status_code == 200 and res.json()["state"]["state"] == "failed"
    last = store.read_file("run-a", "trajectory.jsonl").steps[-1]
    assert last.tool_error == "stopped by owner" and store.get_state("run-a").stop_reason is None


def test_stop_refuses_a_run_that_is_not_running(api, mgr):
    new()
    res = api.post("/api/runs/run-a/stop", headers=H)
    assert res.status_code == 409 and res.json()["error"]["code"] == "not_running"
    api.post("/api/runs/run-a/start", headers=H)
    mgr.wait()
    assert api.post("/api/runs/run-a/stop", headers=H).json()["error"]["code"] == "not_running"  # awaiting-qa
    assert store.get_state("run-a").state.value == "awaiting-qa"


def test_stop_ends_an_orphan_with_no_thread(api):
    new()
    store.advance("run-a", Event.START)  # running, but nobody plays it
    assert api.post("/api/runs/run-a/stop", headers=H).json()["state"]["state"] == "failed"


# ---- retry ----------------------------------------------------------------------------------------------------


def finish(api, mgr, run_id, scenario):
    new(run_id, scenario)
    api.post(f"/api/runs/{run_id}/start", headers=H)
    mgr.wait()


def test_retry_makes_a_new_run_and_never_touches_the_old_one(api, mgr):
    finish(api, mgr, "run-stuck", "stuck")
    store.write_file("run-stuck", "intake.json", {"repo": "dcortex", "route": "/ops/radar", "ack_public_or_synthetic": True})
    before = folder_bytes("run-stuck")
    res = api.post("/api/runs/run-stuck/retry", headers=H)
    assert res.status_code == 200
    new_state = res.json()["state"]
    assert new_state["run_id"] != "run-stuck" and new_state["state"] == "received"
    assert new_state["created_by_retry_of"] == "run-stuck" and new_state["scenario"] == "stuck" and new_state["origin"] == "SIMULATED"
    assert folder_bytes("run-stuck") == before  # byte for byte
    assert store.read_file(new_state["run_id"], "ticket.json") == store.read_file("run-stuck", "ticket.json")
    assert store.read_file(new_state["run_id"], "intake.json").repo == "dcortex"
    assert sorted(p.name for p in store.run_dir(new_state["run_id"]).iterdir()) == ["intake.json", "state.json", "ticket.json"]


def test_retry_with_another_scenario_then_start_reaches_awaiting_qa(api, mgr):
    finish(api, mgr, "run-stuck", "stuck")
    new_id = api.post("/api/runs/run-stuck/retry", headers=H, json={"scenario": "normal"}).json()["state"]["run_id"]
    api.post(f"/api/runs/{new_id}/start", headers=H)
    mgr.wait()
    assert store.get_state(new_id).display_state == "awaiting-qa" and store.get_state("run-stuck").display_state == "stuck"


def test_retry_of_a_run_that_is_not_finished_or_not_failed_is_refused(api, mgr):
    new("run-a")
    assert api.post("/api/runs/run-a/retry", headers=H).json()["error"]["code"] == "not_retryable"  # received
    finish(api, mgr, "run-n", "normal")
    assert api.post("/api/runs/run-n/retry", headers=H).json()["error"]["code"] == "not_retryable"  # awaiting-qa
    assert api.post("/api/runs/run-zzz/retry", headers=H).json()["error"]["code"] == "unknown_run"
    assert api.post("/api/runs/run-a/retry", headers=H, json={"scenario": "nope"}).status_code in (400, 409)
    assert len(store.list_runs()) == 2  # nothing was created by a refusal


def test_retry_in_quota_wait_is_refused_until_the_utc_day_changes():
    now = [datetime(2030, 1, 1, 23, 59, tzinfo=UTC)]
    mgr = RunManager(tick_ms=0, clock=lambda: now[0])
    app = create_app(token=TOKEN)
    app.state.run_manager = mgr
    api = TestClient(app, base_url="http://127.0.0.1")
    finish(api, mgr, "run-q", "quota")
    assert store.get_state("run-q").display_state == "quota-wait"
    before = folder_bytes("run-q")
    refused = api.post("/api/runs/run-q/retry", headers=H)
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "quota_wait" and "00:00 UTC" in refused.json()["error"]["message"]
    assert len(store.list_runs()) == 1
    now[0] += timedelta(minutes=2)  # 00:01 UTC the next day
    assert api.post("/api/runs/run-q/retry", headers=H).status_code == 200
    assert folder_bytes("run-q") == before


def test_retry_of_a_replay_run_stays_a_replay_run(api, mgr):
    fixtures.write_fixture_run("normal", root=store.store_root())
    store.create_run(TICKET, run_id="run-r", origin="REPLAY")
    api.post("/api/runs/run-r/start", headers=H, json={"replay_from": "fixture-normal"})
    mgr.wait()
    again = api.post("/api/runs/run-r/retry", headers=H).json()["state"]
    assert again["origin"] == "REPLAY" and again["scenario"] is None
    assert api.post("/api/runs/run-r/retry", headers=H, json={"scenario": "normal"}).json()["error"]["code"] == "unknown_scenario"
