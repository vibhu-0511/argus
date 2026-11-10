"""P10-T08: screen 4, the PR. Fixture run folders and the in-memory mock GitHub only. Any real HTTP fails the test; no model is called."""

import json
import socket
from pathlib import Path

import httpx
import pytest
from argus_core.types import Ticket
from flow.states import branch_name

from argus_workbench import decisions, fixtures, pull_request, store
from argus_workbench.mock_github import mock_for, preimages
from argus_workbench.routes import pr as pr_route
from argus_workbench.spec import load_spec

H = {"X-Workbench-Token": "test-token-not-secret"}
STATIC = Path(pr_route.__file__).parents[1] / "static"


@pytest.fixture(autouse=True)
def folders(runs_root):
    fixtures.write_all_fixtures(root=runs_root)


@pytest.fixture(autouse=True)
def only_the_pr_hook():
    decisions.ON_APPROVE.clear()  # test_review clears this list; start from the one hook this task registers
    pr_route.register()
    yield
    decisions.ON_APPROVE.clear()


@pytest.fixture(autouse=True)
def no_real_http(monkeypatch):
    """The only HTTP transports that reach a network. The test client and the mock are in memory and do not use them."""
    def boom(*args, **kwargs):
        pytest.fail("a real network call was attempted")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", boom)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", boom)
    monkeypatch.setattr(socket, "create_connection", boom)


def approve(client, run="fixture-normal", key="key-1", **body):
    return client.post(f"/api/runs/{run}/decision", json={"action": "approve", "idempotency_key": key, **body}, headers=H)


def pr_file(runs_root, run="fixture-normal"):
    return json.loads((runs_root / run / "pr.json").read_text("utf-8"))


# ---- on approve the PR is built through argus_app.pr and the mock ---------------------------------------------------


def test_approve_raises_one_draft_pr_with_everything_the_task_row_names(client, runs_root):
    out = approve(client).json()
    assert out["hook_errors"] == [] and out["decision"]["decision"] == "approve"
    pr = pr_file(runs_root)
    assert (pr["origin"], pr["transport"], pr["draft"], pr["action"]) == ("SIMULATED", "mock", True, "created")
    assert pr["title"] == "Argus fix for FIXTURE-1" and pr["branch"] == branch_name("FIXTURE-1")
    assert pr["url"].startswith("https://mock-github.invalid/") and pr["number"] == 1
    body = pr["body"]
    assert "| Verifier verdict | ok |" in body and "| Judge label (advisory) | pass |" in body
    assert "[trajectory](/api/runs/fixture-normal/trajectory.jsonl)" in body  # a relative link to a file this server serves
    assert "[report](/api/runs/fixture-normal/report)" in body
    assert "CI: not run." in body and pr["ci"]["state"] == "not run" and pr["ci"]["checks"] == load_spec()["sim"]["ci"]["checks"]
    b = load_spec()["sim"]["backport"]
    assert f"`{b['targetBranch']}`" in body and b["targetNote"] in body and b["conflictNote"] in body  # ILLUSTRATIVE branch, from the spec
    assert "Mock transport, no real PR" in body and "closes #" not in body.lower()
    assert "http://" not in body and "https://" not in body  # no URL in the body: nothing invented
    assert pr["mark_ready"]["enabled"] is False
    assert store.get_state("fixture-normal").state.value == "done"


def test_the_mock_saw_the_calls_and_a_json_title_and_body(client, runs_root):
    approve(client)
    mock = mock_for(runs_root)
    assert mock.count("GET", "/pulls") >= 1 and mock.count("POST", "/pulls") == 1 and mock.count("POST", "/git/refs") == 1
    assert mock.log.index("GET /repos/mock-owner/mock-repo/pulls") < mock.log.index("POST /repos/mock-owner/mock-repo/git/refs")  # find before push
    sent = json.loads(next(r for r in mock.requests if r.method == "POST" and r.url.path.endswith("/pulls")).content)
    assert sent["draft"] is True and sent["title"] == "Argus fix for FIXTURE-1" and sent["head"] == branch_name("FIXTURE-1")
    assert sent["body"] == pr_file(runs_root)["body"]
    branch_tree = mock.trees[mock.commits[mock.refs[branch_name("FIXTURE-1")]]["tree"]["sha"]]
    assert "min-width: 0;" in branch_tree["src/radar/header.css"]  # the patch was applied on the mock branch


def test_a_title_and_text_with_shell_syntax_are_stored_and_shown_as_text(client, runs_root, tmp_path, monkeypatch):
    work = tmp_path / "cwd"
    work.mkdir()
    monkeypatch.chdir(work)
    ticket = Ticket(id="FIX-$(touch pwned)", text="Header cut off $(touch pwned) `touch pwned2` <script>alert(1)</script>\nsecond line")
    store.write_file("fixture-normal", "ticket.json", ticket)
    approve(client)
    pr = client.get("/api/runs/fixture-normal/pr").json()["pr"]
    assert pr["title"] == "Argus fix for FIX-$(touch pwned)"
    assert "$(touch pwned)" in pr["body"] and "<script>alert(1)</script>" in pr["body"]
    assert "`touch pwned2`" not in pr["body"]  # argus_app.pr's own rule: no backticks inside its code span
    assert list(work.iterdir()) == [] and not Path("pwned").exists()  # nothing was executed
    mock = mock_for(runs_root)
    assert mock.pulls[0]["title"] == "Argus fix for FIX-$(touch pwned)"


def test_an_empty_patch_gives_no_pr_a_typed_message_and_no_call(client, runs_root):
    store.write_file("fixture-normal", "patch.diff", "")
    out = approve(client).json()
    assert [e["code"] for e in out["hook_errors"]] == ["no_patch"] and "patch is empty" in out["hook_errors"][0]["message"]
    assert not (runs_root / "fixture-normal" / "pr.json").exists()
    assert mock_for(runs_root).requests == []  # not even a lookup
    view = client.get("/api/runs/fixture-normal/pr").json()
    assert view["state"] == "no-pr" and "patch is empty" in view["reason"] and view["pr"] is None and view["can_raise"] is False
    r = client.post("/api/runs/fixture-normal/pr", headers=H)
    assert r.status_code == 409 and r.json()["error"]["code"] == "no_patch"
    assert mock_for(runs_root).requests == []


def test_a_patch_the_mock_cannot_apply_is_a_typed_error_and_leaves_no_pr_file(client, runs_root):
    store.write_file("fixture-normal", "patch.diff", "--- old.txt\n+++ new.txt\n@@ -1 +1 @@\n-a\n+b\n")
    out = approve(client).json()
    assert out["hook_errors"][0]["code"] == "pr_failed" and "mock GitHub refused" in out["hook_errors"][0]["message"]
    assert not (runs_root / "fixture-normal" / "pr.json").exists()
    assert mock_for(runs_root).pulls == []


def test_a_machine_that_cannot_load_the_pr_code_still_decides_and_says_so(client, runs_root, monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "argus_app.pr", None)  # an import of it now raises ImportError
    out = approve(client).json()
    assert out["decision"]["decision"] == "approve" and [e["code"] for e in out["hook_errors"]] == ["pr_unavailable"]
    assert not (runs_root / "fixture-normal" / "pr.json").exists() and mock_for(runs_root).requests == []


# ---- approving again updates the same PR ----------------------------------------------------------------------------


def test_same_key_again_returns_the_stored_decision_and_makes_no_second_pr(client, runs_root):
    approve(client)
    again = approve(client).json()
    assert again["replayed"] is True and again["hook_errors"] == []
    assert mock_for(runs_root).count("POST", "/pulls") == 1 and len(mock_for(runs_root).pulls) == 1


def test_a_new_key_is_a_conflict_and_touches_no_pr(client, runs_root):
    approve(client)
    seen = len(mock_for(runs_root).requests)
    r = approve(client, key="key-2")
    assert r.status_code == 409 and r.json()["error"]["code"] == "already_decided"
    assert len(mock_for(runs_root).requests) == seen


def test_approving_again_finds_the_pr_and_updates_it(client, runs_root):
    approve(client)
    first = pr_file(runs_root)
    ticket = store.read_file("fixture-normal", "ticket.json")
    store.write_file("fixture-normal", "ticket.json", ticket.model_copy(update={"text": "The Radar header is cut off. New wording."}))
    r = client.post("/api/runs/fixture-normal/pr", headers=H)
    assert r.status_code == 200 and r.json()["state"] == "draft"
    second = pr_file(runs_root)
    assert (second["number"], second["branch"], second["action"], second["updates"]) == (first["number"], first["branch"], "updated", 1)
    mock = mock_for(runs_root)
    assert len(mock.pulls) == 1 and mock.count("POST", "/pulls") == 1 and mock.count("PATCH", "/pulls/1") == 1  # edited, not created
    assert "New wording." in mock.pulls[0]["body"] and mock.pulls[0]["draft"] is True


def test_a_second_run_of_the_same_ticket_updates_the_same_pr(client, runs_root):
    approve(client)
    approve(client, run="fixture-judge", key="key-j", reason="Reviewed by hand, the judge is advisory.")
    first, second = pr_file(runs_root), pr_file(runs_root, "fixture-judge")
    assert second["number"] == first["number"] == 1 and second["branch"] == first["branch"] and second["action"] == "updated"
    mock = mock_for(runs_root)
    assert len(mock.pulls) == 1 and mock.count("POST", "/pulls") == 1
    assert "| Judge label (advisory) | fail |" in mock.pulls[0]["body"]  # the latest run's evidence is on the PR


def test_an_unchanged_repeat_edits_nothing(client, runs_root):
    approve(client)
    client.post("/api/runs/fixture-normal/pr", headers=H)
    assert mock_for(runs_root).count("PATCH", "/pulls/1") == 0  # argus_app.pr / flow skip an edit that changes nothing
    assert mock_for(runs_root).count("POST", "/pulls") == 1


# ---- no PR without an approval, and the server says why --------------------------------------------------------------


def test_verifier_failed_has_no_pr_and_no_call(client, runs_root):
    r = approve(client, run="fixture-verifier")
    assert r.status_code == 409 and r.json()["error"]["code"] == "verifier_failed"
    assert mock_for(runs_root).requests == []
    r = client.post("/api/runs/fixture-verifier/pr", headers=H)
    assert r.status_code == 409 and r.json()["error"]["code"] == "not_approved"


def test_reject_and_undecided_runs_show_no_pr_with_a_reason(client, runs_root):
    view = client.get("/api/runs/fixture-normal/pr").json()
    assert view["state"] == "no-pr" and "not been approved" in view["reason"]
    client.post("/api/runs/fixture-normal/decision", json={"action": "reject", "reason": "Not a bug", "idempotency_key": "k"}, headers=H)
    view = client.get("/api/runs/fixture-normal/pr").json()
    assert view["state"] == "no-pr" and "rejected" in view["reason"] and view["can_raise"] is False
    assert mock_for(runs_root).requests == []


def test_view_has_the_states_of_the_spec_and_a_disabled_mark_ready(client):
    view = client.get("/api/runs/fixture-normal/pr").json()
    spec_states = load_spec()["screens"][3]["states"]
    assert [s["id"] for s in view["states"]] == [s["id"] for s in spec_states] == ["no-pr", "draft", "ready", "merged", "conflict"]
    assert {s["id"]: s["reachable"] for s in view["states"]} == {"no-pr": True, "draft": True, "ready": False, "merged": False, "conflict": False}
    assert view["mark_ready"]["enabled"] is False and "real QA signal" in view["mark_ready"]["reason"]
    assert "Mock transport, no real PR" in view["mock_note"]


def test_unknown_and_bad_run_ids_are_typed_errors(client):
    assert client.get("/api/runs/nope/pr").json()["error"]["code"] == "unknown_run"
    assert client.get("/api/runs/BAD_ID/pr").json()["error"]["code"] == "bad_run_id"
    assert client.post("/api/runs/nope/pr", headers=H).json()["error"]["code"] == "unknown_run"


def test_post_pr_needs_the_token(client):
    r = client.post("/api/runs/fixture-normal/pr")
    assert r.status_code == 403 and r.json()["error"]["code"] == "token_required"


# ---- the trajectory link target and the hook ------------------------------------------------------------------------


def test_trajectory_file_is_served_as_text(client):
    r = client.get("/api/runs/fixture-normal/trajectory.jsonl")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/plain") and r.headers["x-content-type-options"] == "nosniff"
    lines = r.text.splitlines()
    assert json.loads(lines[0]) and len(lines) > 2
    assert client.get("/api/runs/nope/trajectory.jsonl").json()["error"]["code"] == "unknown_run"


def test_register_is_idempotent():
    pr_route.register()
    pr_route.register()
    assert decisions.ON_APPROVE.count(pull_request.on_approve) == 1


def test_preimages_rebuild_the_old_side_of_a_patch():
    patch = "--- a/x.txt\n+++ b/x.txt\n@@ -3,2 +3,2 @@\n keep\n-old\n+new\n--- /dev/null\n+++ b/y.txt\n@@ -0,0 +1 @@\n+hi\n"
    assert preimages(patch) == {"x.txt": "(not shown by the patch)\n(not shown by the patch)\nkeep\nold\n"}


def test_the_page_is_the_pr_screen_and_says_the_two_plain_things():
    js = (STATIC / "screens" / "pr.js").read_text("utf-8")
    assert "not built yet" not in js and "mock_note" in js and "mark_ready" in js and "disabled = true" in js
    assert "textContent" in (STATIC / "dom.js").read_text("utf-8") and (STATIC / "screens" / "pr.css").is_file()
