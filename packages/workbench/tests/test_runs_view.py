"""P10-T06: GET /api/runs/{id}, the data behind the live-run screen.

Scenarios are played through the real RunManager (and the real ScriptedRunner) with a zero-millisecond tick, then the
endpoint is polled. One test holds a run between steps to see the view change while it plays. No model, no sleeping.
"""

import queue
import re
import threading
import time
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from argus_workbench import fixtures, store
from argus_workbench.manager import RunManager
from argus_workbench.runner import ScriptedRunner
from argus_workbench.server import create_app

TOKEN = "test-token-not-secret"
H = {"X-Workbench-Token": TOKEN}
TICKET = {"id": "T-1", "text": "SIMULATED test ticket: the header is cut off at 375 px."}
STAGES = ["reproduce", "locate", "fix", "verify"]


@pytest.fixture(autouse=True)
def no_ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("ARGUS_WORKBENCH_LEDGER", str(tmp_path / "no-such-ledger.json"))


def build(clock=None, tick_ms=0):
    mgr = RunManager(tick_ms=tick_ms, **({"clock": clock} if clock else {}))
    app = create_app(token=TOKEN)
    app.state.run_manager = mgr
    return mgr, TestClient(app, base_url="http://127.0.0.1")


@pytest.fixture
def env():
    return build()


def play(env, scenario, run_id=None):
    mgr, api = env
    run_id = run_id or f"run-{scenario}"
    store.create_run(TICKET, scenario=scenario, origin="SIMULATED", run_id=run_id)
    assert api.post(f"/api/runs/{run_id}/start", headers=H).status_code == 200
    mgr.wait(run_id)
    return api.get(f"/api/runs/{run_id}").json()


def statuses(view):
    return {s["id"]: s["status"] for s in view["stages"]}


def test_normal_run(env):
    view = play(env, "normal")
    assert (view["run"]["state"], view["run"]["display_state"], view["run"]["stop_reason"]) == ("awaiting-qa", "awaiting-qa", "submit")
    assert [s["id"] for s in view["stages"]] == STAGES and [s["label"] for s in view["stages"]] == ["Reproduce", "Locate", "Fix", "Verify"]
    assert set(statuses(view).values()) == {"done"}
    assert len(view["steps"]) == 12 and [s["index"] for s in view["steps"]] == list(range(12))
    assert view["steps"][0] == {
        "index": 0, "stage": "reproduce", "tool": "navigate", "text": "open the page named in the ticket at 375 px",
        "tokens_in": 1180, "tokens_out": 40, "tokens_cached": 0, "stop_reason": None, "tool_error": None, "repeat": False,
    }
    assert view["totals"] == {k: sum(s[k] for s in view["steps"]) for k in ("tokens_in", "tokens_out", "tokens_cached")}
    assert view["reason"] is None and not any(s["repeat"] for s in view["steps"])
    assert view["poll"]["again"] is False
    assert view["actions"]["stop"]["enabled"] is False
    assert view["actions"]["retry"]["enabled"] is False  # a run that passed is not retried


def test_every_run_carries_its_origin_tag(env):
    view = play(env, "normal")
    assert view["origin"]["tag"] == "SIMULATED"
    assert "illustrative" in view["origin"]["note"] and "no model was called" in view["origin"]["note"]


def test_quota_run(env):
    view = play(env, "quota")
    run = view["run"]
    assert (run["state"], run["display_state"], run["stop_reason"]) == ("failed", "quota-wait", "QuotaExceeded")
    assert statuses(view) == {"reproduce": "done", "locate": "done", "fix": "failed", "verify": "pending"}
    reason = view["reason"]
    assert reason["kind"] == "quota" and reason["label"] == "Quota used up"
    assert re.fullmatch(r"scripted-sim would exceed tokens_per_day: \d+ of \d+", reason["text"])  # the ledger's own message
    assert view["steps"][-1]["tool_error"] == reason["text"] and view["steps"][-1]["stop_reason"] == "QuotaExceeded"
    (row,) = view["meter"]["rows"]
    assert row["model"] == "scripted-sim" and row["limit"] == "tokens_per_day" and row["over"] is True and row["percent"] == 100
    assert row["illustrative"] is True and "ILLUSTRATIVE" in view["meter"]["note"]
    used, cap = map(int, re.findall(r"(\d+) of (\d+)", reason["text"])[0])
    assert (row["used"], row["cap"]) == (used, cap)
    retry = view["actions"]["retry"]
    assert retry["enabled"] is False and "quota" in retry["why"]
    reset = datetime.fromisoformat(retry["reset_utc"])
    assert reset.utcoffset() == timedelta(0) and (reset.hour, reset.minute, reset.second) == (0, 0, 0)
    assert reset.date() == datetime.fromisoformat(run["updated_at"]).astimezone(UTC).date() + timedelta(days=1)
    assert retry["reset_text"] == f"resets 00:00 UTC on {reset.date().isoformat()}"
    assert view["actions"]["stop"]["enabled"] is False and view["poll"]["again"] is False


def test_stuck_run(env):
    view = play(env, "stuck")
    assert (view["run"]["state"], view["run"]["display_state"], view["run"]["stop_reason"]) == ("failed", "stuck", "stuck")
    assert statuses(view) == {"reproduce": "done", "locate": "failed", "fix": "pending", "verify": "pending"}
    reason = view["reason"]
    assert reason["kind"] == "stuck" and "stop_reason=stuck after the same tool call three times" in reason["text"]
    assert "locate" in reason["text"]
    repeats = [s for s in view["steps"] if s["repeat"]]
    assert len(repeats) == 3 and {s["tool"] for s in repeats} == {"locate"} and view["steps"][-1]["stop_reason"] == "stuck"
    assert view["meter"]["rows"] == []  # nothing in the ledger: a dash on the page, not a number
    assert view["actions"]["retry"]["enabled"] is True and "reset_utc" not in view["actions"]["retry"]
    assert view["actions"]["stop"]["enabled"] is False


def test_quota_and_stuck_look_different(env):
    quota, stuck = play(env, "quota"), play(env, "stuck")
    assert quota["reason"]["kind"] != stuck["reason"]["kind"] and quota["reason"]["label"] != stuck["reason"]["label"]
    assert quota["run"]["display_state"] != stuck["run"]["display_state"] and quota["reason"]["text"] != stuck["reason"]["text"]


def test_verifier_and_judge_runs(env):
    verifier = play(env, "verifier")
    assert statuses(verifier) == {"reproduce": "done", "locate": "done", "fix": "done", "verify": "failed"}
    assert verifier["reason"]["kind"] == "verifier" and verifier["reason"]["text"] == "overflow on /ops/horizon"
    judge = play(env, "judge")
    assert set(statuses(judge).values()) == {"done"} and judge["reason"] is None


def test_retry_button_matches_what_the_server_does_in_every_scenario(env):
    mgr, api = env
    for scenario in ("normal", "quota", "stuck", "verifier", "judge"):
        view = play(env, scenario)
        res = api.post(f"/api/runs/run-{scenario}/retry", headers=H)
        assert (res.status_code == 200) == view["actions"]["retry"]["enabled"], scenario
        if res.status_code != 200:
            assert res.json()["error"]["code"] in ("quota_wait", "not_retryable")


def test_retry_opens_after_the_reset():
    day = [datetime(2026, 5, 4, 15, 0, tzinfo=UTC)]
    env = build(clock=lambda: day[0])
    mgr, api = env
    assert play(env, "quota")["actions"]["retry"]["enabled"] is False
    day[0] = datetime(2026, 5, 4, 23, 59, tzinfo=UTC)
    assert api.get("/api/runs/run-quota").json()["actions"]["retry"]["enabled"] is False
    day[0] = datetime(2026, 5, 5, 0, 0, tzinfo=UTC)  # the reset the view announced
    view = api.get("/api/runs/run-quota").json()
    assert view["actions"]["retry"]["enabled"] is True
    assert api.post("/api/runs/run-quota/retry", headers=H).status_code == 200


def test_the_view_changes_while_a_scripted_run_plays():
    """Hold the real ScriptedRunner after every step and poll in between: stage bar and timeline grow one step at a time."""
    _, api = build()
    store.create_run(TICKET, scenario="normal", origin="SIMULATED", run_id="run-live")
    at, go = queue.Queue(), queue.Queue()

    def tick():
        at.put(1)
        go.get(timeout=10)

    thread = threading.Thread(target=lambda: ScriptedRunner("normal").play(store.run_dir("run-live"), tick=tick), daemon=True)
    thread.start()
    seen = []
    for n in range(1, 13):
        at.get(timeout=10)
        view = api.get("/api/runs/run-live").json()
        seen.append((n, statuses(view), view["run"]["state"], view["poll"]["again"], view["actions"]["stop"]["enabled"]))
        assert len(view["steps"]) == n and view["totals"]["tokens_in"] == sum(s["tokens_in"] for s in view["steps"])
        go.put(1)
    thread.join(10)
    assert seen[0][1] == {"reproduce": "running", "locate": "pending", "fix": "pending", "verify": "pending"}
    assert seen[4][1] == {"reproduce": "done", "locate": "running", "fix": "pending", "verify": "pending"}  # step 5 is the first locate
    assert seen[7][1] == {"reproduce": "done", "locate": "done", "fix": "running", "verify": "pending"}
    assert seen[11][1]["verify"] == "running" and seen[11][2] == "verifying"
    assert all(again and stop for _, _, _, again, stop in seen)  # polling and Stop stay on while it plays
    final = api.get("/api/runs/run-live").json()
    assert final["run"]["state"] == "awaiting-qa" and final["poll"]["again"] is False and set(statuses(final).values()) == {"done"}


def test_stop_works_on_a_running_run_and_not_on_a_finished_one():
    mgr, api = build(tick_ms=60_000)  # a slow tick; Stop wakes it at once
    store.create_run(TICKET, scenario="normal", origin="SIMULATED", run_id="run-slow")
    api.post("/api/runs/run-slow/start", headers=H)
    for _ in range(500):  # wait for the first step to be written
        view = api.get("/api/runs/run-slow").json()
        if view["steps"]:
            break
        time.sleep(0.01)
    assert view["poll"]["again"] is True and view["actions"]["stop"]["enabled"] is True
    assert view["actions"]["retry"]["enabled"] is False  # still running
    stopped = api.post("/api/runs/run-slow/stop", headers=H)
    assert stopped.status_code == 200
    view = api.get("/api/runs/run-slow").json()
    assert view["run"]["state"] == "failed" and view["run"]["stop_reason"] is None
    assert view["reason"] == {"kind": "stopped", "label": "Stopped by owner", "text": "stopped by owner"}
    assert statuses(view)["reproduce"] == "stopped" and view["steps"][-1]["tool"] == "owner-stop"
    assert view["actions"]["stop"]["enabled"] is False and view["poll"]["again"] is False and view["actions"]["retry"]["enabled"] is True
    again = api.post("/api/runs/run-slow/stop", headers=H)
    assert again.status_code == 409 and again.json()["error"]["code"] == "not_running"


def test_a_received_run_has_a_start_action_and_no_steps(env):
    _, api = env
    store.create_run(TICKET, scenario="stuck", origin="SIMULATED", run_id="run-new")
    view = api.get("/api/runs/run-new").json()
    assert view["steps"] == [] and set(statuses(view).values()) == {"pending"} and view["reason"] is None
    assert view["actions"]["start"]["enabled"] is True and view["actions"]["stop"]["enabled"] is False
    assert view["poll"]["again"] is False and view["totals"] == {"tokens_in": 0, "tokens_out": 0, "tokens_cached": 0}


def test_a_replay_run_says_its_token_counts_are_not_real(env):
    mgr, api = env
    fixtures.write_fixture_run("normal", run_id="source-run", origin="REPLAY")
    store.create_run(TICKET, scenario=None, origin="REPLAY", run_id="run-replay")
    assert api.post("/api/runs/run-replay/start", headers=H, json={"replay_from": "source-run"}).status_code == 200
    mgr.wait("run-replay")
    view = api.get("/api/runs/run-replay").json()
    assert view["origin"]["tag"] == "REPLAY" and "not real" in view["origin"]["note"]
    assert len(view["steps"]) == 12 and view["run"]["state"] == "failed" and view["reason"]["kind"] == "failed"


def test_typed_errors(env):
    _, api = env
    missing = api.get("/api/runs/run-nope")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "unknown_run"
    bad = api.get("/api/runs/Run_Bad")
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "bad_run_id"


def test_the_endpoint_is_read_only(env):
    play(env, "stuck")
    _, api = env
    before = {p.name: p.read_bytes() for p in store.run_dir("run-stuck").iterdir()}
    for _ in range(3):
        api.get("/api/runs/run-stuck")
    assert {p.name: p.read_bytes() for p in store.run_dir("run-stuck").iterdir()} == before
    assert api.post("/api/runs/run-stuck", headers=H).status_code == 405


def test_hostile_text_is_data_in_the_json(env):
    mgr, api = env
    store.create_run({"id": "T-2", "text": "<script>alert(1)</script>"}, scenario="normal", origin="SIMULATED", run_id="run-x")
    api.post("/api/runs/run-x/start", headers=H)
    mgr.wait("run-x")
    res = api.get("/api/runs/run-x")
    assert res.headers["content-type"].startswith("application/json") and "script-src 'self'" in res.headers["content-security-policy"]
