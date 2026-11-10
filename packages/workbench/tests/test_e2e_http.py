"""P10-T14, HTTP level: the walk the browser run does (issue, run, review, PR, history), through the real app with a
TestClient, the real RunManager and the real ScriptedRunner at a 0 ms tick. Every run is SIMULATED. No model, no
network (the PR goes to the in-memory mock). This is the evidence that exists without a browser."""

import json
import time

import pytest
from fastapi.testclient import TestClient

from argus_workbench import decisions
from argus_workbench.manager import RunManager
from argus_workbench.routes import pr as pr_route
from argus_workbench.server import create_app

TOKEN = "test-token-not-secret"
H = {"X-Workbench-Token": TOKEN}
FIELDS = {"text": "SIMULATED: the radar card text is 10 px at 375 px.", "repo": "dcortex", "route": "/ops/radar", "ack_public_or_synthetic": "true"}


@pytest.fixture
def c(tmp_path, monkeypatch):
    monkeypatch.setenv("ARGUS_WORKBENCH_LEDGER", str(tmp_path / "no-ledger.json"))
    monkeypatch.setenv("ARGUS_WORKBENCH_RESULTS", "")  # no result files: every metric is a dash
    decisions.ON_APPROVE.clear()  # another test file clears this list
    pr_route.register()
    app = create_app(token=TOKEN)
    app.state.run_manager = RunManager(tick_ms=0)
    yield TestClient(app, base_url="http://127.0.0.1")
    decisions.ON_APPROVE.clear()


def issue(c, scenario):
    """Screen 1: the form posts multipart, then the page calls start."""
    parts = [(k, (None, v)) for k, v in {**FIELDS, "scenario": scenario}.items()]
    r = c.post("/api/issues", files=parts, headers=H)
    assert r.status_code == 201, r.text
    run_id = r.json()["run_id"]
    assert r.json()["state"]["state"] == "received" and r.json()["state"]["origin"] == "SIMULATED"
    assert c.post(f"/api/runs/{run_id}/start", headers=H).json()["state"]["state"] == "reproducing"
    return run_id


def watch(c, run_id):
    """Screen 2: poll the view the way the page does, until the run stops playing."""
    for _ in range(500):
        view = c.get(f"/api/runs/{run_id}").json()
        if not view["poll"]["again"]:
            return view
        time.sleep(0.01)
    pytest.fail("the run never stopped playing")


def test_the_normal_walk_issue_run_review_pr_history(c):
    run = issue(c, "normal")
    view = watch(c, run)
    assert view["run"]["display_state"] == "awaiting-qa" and view["run"]["origin"] == "SIMULATED"
    assert [s["status"] for s in view["stages"]] == ["done"] * 4 and view["reason"] is None

    review = c.get(f"/api/runs/{run}/review").json()  # screen 3
    assert [x["status"] for x in review["checks"]] == ["pass"] * 4 and review["judge"]["label"] == "pass"
    assert review["approve"]["enabled"] and review["report_url"]
    assert "sandbox" in c.get(review["report_url"]).headers["content-security-policy"]
    out = c.post(f"/api/runs/{run}/decision", json={"action": "approve", "idempotency_key": "e2e-1"}, headers=H).json()
    assert out["decision"]["decision"] == "approve" and out["hook_errors"] == []

    pr = c.get(f"/api/runs/{run}/pr").json()  # screen 4
    assert pr["state"] == "draft" and pr["pr"]["draft"] is True and pr["pr"]["origin"] == "SIMULATED"
    assert pr["pr"]["transport"] == "mock" and ".invalid" in pr["pr"]["url"]
    assert pr["mark_ready"]["enabled"] is False
    assert c.get(f"/api/runs/{run}/trajectory.jsonl").status_code == 200

    hist = c.get("/api/history").json()  # screen 5
    row = next(r for r in hist["runs"] if r["run_id"] == run)
    assert (row["state"], row["decision"], row["pr"], row["origin"]) == ("done", "approve", True, "SIMULATED")
    metrics = c.get("/api/history/metrics").json()
    assert hist["count"] == 1 and metrics["excluded"]["SIMULATED"] == 1  # listed, in no number


def test_quota_view(c):
    view = watch(c, issue(c, "quota"))
    assert (view["run"]["state"], view["run"]["stop_reason"], view["run"]["display_state"]) == ("failed", "QuotaExceeded", "quota-wait")
    assert view["reason"]["kind"] == "quota"
    assert view["actions"]["retry"]["enabled"] is False  # disabled until the UTC day changes
    assert c.get(f"/api/runs/{view['run']['run_id']}/review").status_code == 404  # no verdict, typed


def test_stuck_view(c):
    view = watch(c, issue(c, "stuck"))
    assert (view["run"]["state"], view["run"]["stop_reason"], view["run"]["display_state"]) == ("failed", "stuck", "stuck")
    assert view["actions"]["retry"]["enabled"] is True
    assert view["reason"]["kind"] == "stuck" and sum(1 for s in view["steps"] if s["repeat"]) >= 3


def test_verifier_failed_view_and_the_server_refuses_approve(c):
    run = issue(c, "verifier")
    view = watch(c, run)
    assert (view["run"]["state"], view["run"]["display_state"]) == ("failed", "failed")
    review = c.get(f"/api/runs/{run}/review").json()
    assert review["verdict_ok"] is False and review["approve"]["enabled"] is False
    assert review["failed_check"] == "overflow" and review["judge"]["label"] == "not run"
    assert "not run" in [x["status"] for x in review["checks"]]
    r = c.post(f"/api/runs/{run}/decision", json={"action": "approve", "idempotency_key": "e2e-v"}, headers=H)
    assert r.status_code == 409 and r.json()["error"]["code"] == "verifier_failed"
    assert c.get(f"/api/runs/{run}/pr").json()["state"] == "no-pr"


def test_judge_disagrees_view_needs_a_reason_then_approves(c):
    run = issue(c, "judge")
    assert watch(c, run)["run"]["display_state"] == "awaiting-qa"
    review = c.get(f"/api/runs/{run}/review").json()
    assert review["judge"]["label"] == "fail" and review["judge"]["advisory"] is True
    assert review["approve"] == {"enabled": True, "needs_reason": True, "disabled_reason": None}
    r = c.post(f"/api/runs/{run}/decision", json={"action": "approve", "idempotency_key": "e2e-j"}, headers=H)
    assert r.status_code == 400 and r.json()["error"]["code"] == "reason_required"
    ok = c.post(f"/api/runs/{run}/decision", json={"action": "approve", "reason": "Judge is advisory; I checked the text.", "idempotency_key": "e2e-j2"}, headers=H)
    assert ok.status_code == 200 and c.get(f"/api/runs/{run}/pr").json()["state"] == "draft"


def test_all_five_scenarios_end_up_in_history_with_the_simulated_badge(c):
    runs = {s: issue(c, s) for s in ("normal", "quota", "stuck", "verifier", "judge")}
    for run in runs.values():
        watch(c, run)
    rows = c.get("/api/history").json()["runs"]
    assert {r["run_id"] for r in rows} == set(runs.values()) and {r["origin"] for r in rows} == {"SIMULATED"}
    assert json.dumps(c.get("/api/history/metrics").json())  # readable, and nothing here is a model result
