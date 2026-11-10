"""P10-T07: the review view, the inert report, and the decision rules. Fixture run folders only; no model is called."""

import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from argus_core.types import Screenshot
from flow.states import Event

from argus_workbench import decisions, fixtures, store
from argus_workbench.errors import WorkbenchError
from argus_workbench.routes import review as review_route
from argus_workbench.spec import load_spec

H = {"X-Workbench-Token": "test-token-not-secret"}
STATIC = Path(review_route.__file__).parents[1] / "static"


@pytest.fixture(autouse=True)
def folders(runs_root):
    fixtures.write_all_fixtures(root=runs_root)


@pytest.fixture(autouse=True)
def no_leftover_hooks():
    decisions.ON_APPROVE.clear()
    yield
    decisions.ON_APPROVE.clear()


def post(client, run, **body):
    body.setdefault("idempotency_key", "key-1")
    return client.post(f"/api/runs/{run}/decision", json=body, headers=H)


def state_bytes(runs_root, run):
    return (runs_root / run / "state.json").read_bytes()


# ---- the review view -------------------------------------------------------------------------------------------


def test_normal_review_lists_four_checks_in_order_with_an_advisory_judge(client):
    r = client.get("/api/runs/fixture-normal/review")
    assert r.status_code == 200
    d = r.json()
    assert [c["name"] for c in d["checks"]] == ["pixel", "overflow", "axe", "console"]
    assert {c["status"] for c in d["checks"]} == {"pass"}
    assert d["verdict_ok"] and d["first_failure"] is None and d["short_circuit_note"] is None
    assert d["judge"]["label"] == "pass" and d["judge"]["advisory"] is True
    assert d["judge"]["alpha"] == "—"  # a dash, not a number: there is no calibration run
    card = load_spec()["sim"]["judgeCard"]
    assert (d["judge"]["family"], d["judge"]["model"]) == (card["family"], card["model"])  # the spec text, nothing else
    assert d["origin"] == "SIMULATED" and d["decision"] is None
    assert d["approve"] == {"enabled": True, "needs_reason": False, "disabled_reason": None}
    assert d["patch"]["files"] == ["src/radar/header.css"] and d["patch"]["added"] == 1 and d["patch"]["removed"] == 1
    assert d["report_url"] == "/api/runs/fixture-normal/report"
    assert d["reject_reasons"] == load_spec()["targets"]["reasons"]["reject"]


def test_verifier_failed_names_the_first_failure_and_the_checks_that_did_not_run(client):
    d = client.get("/api/runs/fixture-verifier/review").json()
    assert [(c["name"], c["status"]) for c in d["checks"]] == [("pixel", "pass"), ("overflow", "fail"), ("axe", "not run"), ("console", "not run")]
    assert d["first_failure"] == "overflow on /ops/horizon" and d["failed_check"] == "overflow"
    assert "axe, console" in d["short_circuit_note"] and "first hard failure" in d["short_circuit_note"]
    assert d["judge"]["label"] == "not run"
    assert d["approve"]["enabled"] is False and "verifier failed" in d["approve"]["disabled_reason"]


def test_judge_disagrees_keeps_the_verdict_and_asks_for_a_reason(client):
    d = client.get("/api/runs/fixture-judge/review").json()
    assert d["verdict_ok"] is True and {c["status"] for c in d["checks"]} == {"pass"}
    assert d["judge"]["label"] == "fail" and d["judge"]["advisory"] is True
    assert d["approve"] == {"enabled": True, "needs_reason": True, "disabled_reason": None}


@pytest.mark.parametrize("run", ["fixture-quota", "fixture-stuck"])
def test_run_without_verdict_has_nothing_to_review(client, run):
    r = client.get(f"/api/runs/{run}/review")
    assert r.status_code == 404 and r.json()["error"]["code"] == "no_verdict"


def test_unknown_and_bad_run_ids_are_typed_errors(client):
    assert client.get("/api/runs/nope/review").json()["error"]["code"] == "unknown_run"
    r = client.get("/api/runs/BAD_ID/review")
    assert r.status_code == 400 and r.json()["error"]["code"] == "bad_run_id"


# ---- the report is inert -----------------------------------------------------------------------------------------


def test_report_response_is_sandboxed_by_its_own_csp(client):
    r = client.get("/api/runs/fixture-normal/report")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    assert r.headers["content-security-policy"] == "sandbox; default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert "SIMULATED before/after report" in r.text


def test_report_with_script_is_served_with_the_inert_csp_unchanged(client, runs_root):
    (runs_root / "fixture-normal" / "report.html").write_text("<script>alert(1)</script><img src=https://evil.example/x>", encoding="utf-8")
    r = client.get("/api/runs/fixture-normal/report")
    assert "<script>" in r.text  # served as is; the CSP is what makes it inert
    csp = r.headers["content-security-policy"]
    assert csp.startswith("sandbox;") and "script-src" not in csp and "allow-" not in csp and "default-src 'none'" in csp


def test_report_missing_is_a_typed_404(client, runs_root):
    (runs_root / "fixture-normal" / "report.html").unlink()
    assert client.get("/api/runs/fixture-normal/report").json()["error"]["code"] == "missing_file"
    assert client.get("/api/runs/fixture-normal/review").json()["report_url"] is None


def test_the_page_shows_the_report_only_in_a_sandbox_frame_without_allow_tokens():
    js = (STATIC / "screens" / "review.js").read_text("utf-8")
    assert js.count("el('iframe'") == 1 and "sandbox: ''" in js
    assert "allow-scripts" not in js and "allow-same-origin" not in js
    assert "srcdoc" not in js and "innerHTML" not in js


# ---- approve -----------------------------------------------------------------------------------------------------


def test_approve_is_stored_once_and_the_same_key_returns_it_unchanged(client, runs_root):
    first = post(client, "fixture-normal", action="approve", reason="looks right", idempotency_key="k1")
    assert first.status_code == 200
    stored = first.json()["decision"]
    assert stored["decision"] == "approve" and stored["reason"] == "looks right" and first.json()["replayed"] is False
    again = post(client, "fixture-normal", action="approve", reason="a different text", idempotency_key="k1")
    assert again.status_code == 200 and again.json()["replayed"] is True and again.json()["decision"] == stored
    assert store.get_state("fixture-normal").state.value == "done"
    assert client.get("/api/runs/fixture-normal/review").json()["decision"] == stored


def test_a_different_key_after_a_decision_is_a_typed_conflict_and_changes_nothing(client, runs_root):
    post(client, "fixture-normal", action="approve", idempotency_key="k1")
    before = (runs_root / "fixture-normal" / "decision.json").read_bytes()
    r = post(client, "fixture-normal", action="reject", reason="Not a bug", idempotency_key="k2")
    assert r.status_code == 409 and r.json()["error"] == {
        "code": "already_decided", "field": "idempotency_key", "message": "this run was already decided: approve",
    }
    assert (runs_root / "fixture-normal" / "decision.json").read_bytes() == before


def test_approve_is_refused_by_the_server_when_the_verifier_failed(client, runs_root):
    before = state_bytes(runs_root, "fixture-verifier")
    r = post(client, "fixture-verifier", action="approve", reason="please", note="please")
    assert r.status_code == 409 and r.json()["error"]["code"] == "verifier_failed"
    assert not (runs_root / "fixture-verifier" / "decision.json").exists()
    assert state_bytes(runs_root, "fixture-verifier") == before


def test_approve_needs_a_written_reason_when_the_judge_disagrees(client, runs_root):
    for empty in (None, "", "   \n"):
        r = post(client, "fixture-judge", action="approve", reason=empty)
        assert r.status_code == 400 and r.json()["error"]["code"] == "reason_required" and r.json()["error"]["field"] == "reason"
    assert not (runs_root / "fixture-judge" / "decision.json").exists()
    ok = post(client, "fixture-judge", action="approve", reason="judge text is about an unrelated route")
    assert ok.status_code == 200 and ok.json()["decision"]["reason"] == "judge text is about an unrelated route"


def test_run_without_a_verdict_cannot_be_decided(client):
    r = post(client, "fixture-quota", action="reject", reason="Not a bug")
    assert r.status_code == 409 and r.json()["error"]["code"] == "no_verdict"


def test_approve_hooks_run_once_after_the_decision_and_not_on_a_replay(client):
    seen = []
    decisions.ON_APPROVE.append(lambda run_id, d: seen.append((run_id, d.decision, d.idempotency_key, store.get_state(run_id).state.value)))
    post(client, "fixture-normal", action="approve", idempotency_key="k1")
    post(client, "fixture-normal", action="approve", idempotency_key="k1")
    assert seen == [("fixture-normal", "approve", "k1", "done")]


def test_a_hook_error_is_reported_and_the_decision_stays_stored(client):
    def failing(run_id, decision):
        raise WorkbenchError("pr_failed", "the mock transport refused", field=None)

    decisions.ON_APPROVE.append(failing)
    r = post(client, "fixture-normal", action="approve")
    assert r.status_code == 200 and r.json()["hook_errors"] == [{"code": "pr_failed", "field": None, "message": "the mock transport refused"}]
    assert client.get("/api/runs/fixture-normal/review").json()["decision"]["decision"] == "approve"


def test_hooks_do_not_run_for_reject_or_request_changes(client):
    seen = []
    decisions.ON_APPROVE.append(lambda run_id, d: seen.append(run_id))
    post(client, "fixture-normal", action="reject", reason="Not a bug")
    post(client, "fixture-judge", action="request-changes", note="check the other routes too")
    assert seen == []


def test_parallel_decisions_with_different_keys_store_exactly_one(client, runs_root):
    barrier = threading.Barrier(4)

    def go(i):
        barrier.wait()
        return post(client, "fixture-normal", action="approve", idempotency_key=f"k{i}").status_code

    with ThreadPoolExecutor(4) as pool:
        codes = sorted(pool.map(go, range(4)))
    assert codes == [200, 409, 409, 409]


# ---- request changes -----------------------------------------------------------------------------------------------


def test_request_changes_needs_a_note(client, runs_root):
    for body in ({"note": ""}, {"note": "  "}, {}):
        r = post(client, "fixture-judge", action="request-changes", **body)
        assert r.status_code == 400 and r.json()["error"]["code"] == "note_required"
    assert [s.run_id for s in store.list_runs()].count("fixture-judge") == 1 and len(store.list_runs()) == 5


def test_request_changes_creates_a_new_received_run_with_the_note_and_leaves_the_old_run_alone(client, runs_root):
    old_files = {p.name: p.read_bytes() for p in (runs_root / "fixture-judge").iterdir()}
    r = post(client, "fixture-judge", action="request-changes", reason="Collateral change on another route", note="Also fix /ops/horizon")
    assert r.status_code == 200
    new_id = r.json()["new_run_id"]
    assert new_id and new_id != "fixture-judge"
    new_state = store.get_state(new_id)
    assert new_state.state.value == "received" and new_state.created_by_retry_of == "fixture-judge"
    assert (new_state.origin, new_state.scenario) == ("SIMULATED", "judge")
    intake = store.read_file(new_id, "intake.json")
    assert intake.model_dump()["reviewer_note"] == "Also fix /ops/horizon" and intake.repo == "dcortex"
    assert intake.model_dump()["change_reason"] == "Collateral change on another route"
    assert store.read_file(new_id, "ticket.json") == store.read_file("fixture-judge", "ticket.json")
    assert not store.has_file(new_id, "trajectory.jsonl")  # created, not started
    new_files = {p.name: p.read_bytes() for p in (runs_root / "fixture-judge").iterdir()}
    assert {k: v for k, v in new_files.items() if k != "decision.json"} == old_files  # the old run is read only
    assert store.read_file("fixture-judge", "decision.json").decision == "request-changes"
    view = client.get("/api/runs/fixture-judge/review").json()
    assert view["follow_up_run_id"] == new_id
    replay = post(client, "fixture-judge", action="request-changes", note="other text")
    assert replay.json()["replayed"] is True and replay.json()["new_run_id"] == new_id
    assert len(store.list_runs()) == 6  # no second run


def test_request_changes_on_a_failed_verifier_run_is_allowed(client):
    r = post(client, "fixture-verifier", action="request-changes", note="keep /ops/horizon untouched")
    assert r.status_code == 200 and store.get_state(r.json()["new_run_id"]).state.value == "received"
    assert store.get_state("fixture-verifier").state.value == "failed"


def test_request_changes_rejects_an_unlisted_reason_and_copies_the_screenshot(client, runs_root):
    assert post(client, "fixture-judge", action="request-changes", reason="because", note="x").json()["error"]["code"] == "unknown_reason"
    folder = runs_root / "fixture-judge"
    (folder / "shot.png").write_bytes(b"\x89PNG fake")
    ticket = store.read_file("fixture-judge", "ticket.json").model_copy(update={"screenshot": Screenshot(media_type="image/png", path="shot.png")})
    store.write_file("fixture-judge", "ticket.json", ticket)
    new_id = post(client, "fixture-judge", action="request-changes", note="x").json()["new_run_id"]
    assert (runs_root / new_id / "shot.png").read_bytes() == b"\x89PNG fake"
    assert store.read_file(new_id, "ticket.json").screenshot.path == "shot.png"


# ---- reject --------------------------------------------------------------------------------------------------------


def test_reject_takes_only_a_listed_reason(client, runs_root):
    assert post(client, "fixture-normal", action="reject").json()["error"]["code"] == "reason_required"
    bad = post(client, "fixture-normal", action="reject", reason="I just do not like it")
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "unknown_reason" and bad.json()["error"]["field"] == "reason"
    assert not (runs_root / "fixture-normal" / "decision.json").exists()
    ok = post(client, "fixture-normal", action="reject", reason="Patch looks unsafe")
    assert ok.status_code == 200 and ok.json()["decision"]["reason"] == "Patch looks unsafe"
    assert store.get_state("fixture-normal").state.value == "rejected"


def test_reject_other_needs_text_and_every_listed_reason_works(client):
    assert post(client, "fixture-normal", action="reject", reason="Other (say what)", note=" ").json()["error"]["code"] == "note_required"
    ok = post(client, "fixture-normal", action="reject", reason="Other (say what)", note="the ticket is a duplicate in another tracker")
    assert ok.json()["decision"]["reason"] == "Other: the ticket is a duplicate in another tracker"


def test_reject_on_a_failed_verifier_run_stores_the_decision_and_keeps_the_state(client):
    assert post(client, "fixture-verifier", action="reject", reason="Not a bug").status_code == 200
    assert store.get_state("fixture-verifier").state.value == "failed"


# ---- request shape ---------------------------------------------------------------------------------------------------


def test_unknown_action_missing_key_and_missing_token_are_typed_refusals(client):
    assert post(client, "fixture-normal", action="merge").json()["error"]["code"] == "invalid_action"
    r = client.post("/api/runs/fixture-normal/decision", json={"action": "approve"}, headers=H)
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_request" and r.json()["error"]["field"] == "idempotency_key"
    r = client.post("/api/runs/fixture-normal/decision", json={"action": "approve", "idempotency_key": "x" * 129}, headers=H)
    assert r.status_code == 422
    r = client.post("/api/runs/fixture-normal/decision", json={"action": "approve", "idempotency_key": "k"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "token_required"
    assert not (Path(store.run_dir("fixture-normal")) / "decision.json").exists()


def test_a_run_that_is_already_done_is_not_reviewable(client):
    store.advance("fixture-normal", Event.QA_APPROVED)  # now done, no decision file
    r = post(client, "fixture-normal", action="approve")
    assert r.status_code == 409 and r.json()["error"]["code"] == "not_reviewable"
