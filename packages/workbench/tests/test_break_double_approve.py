"""P10-T13 break it: double approve. The real routes through the real app, run in a thread pool; no model, no network.

Cases: two approves with one idempotency key give one decision and one PR; two approves with different keys at the same
moment give exactly one PR and the loser gets the typed conflict `already_decided`; an approve after a failed verifier
is refused by the SERVER (the API is called directly, the page and its disabled button are not involved).
The concurrent cases repeat ROUNDS times (a race shows up now and then, not every time), each round on its own run with
its own ticket, so "one PR" is counted per round. A second variant widens the race window on purpose (the decision read
sleeps) so a missing lock is seen every time, not by luck.

Mutation proof: docs/notes/p10-break-it-t13.md (lock removed, lock and atomic create removed, server verdict check removed).
"""

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from argus_core.types import Ticket
from fastapi.testclient import TestClient
from flow.states import branch_name

from argus_workbench import decisions, fixtures, store
from argus_workbench.mock_github import mock_for
from argus_workbench.routes import pr as pr_route

TOKEN = "test-token-not-secret"
H = {"X-Workbench-Token": TOKEN}
ROUNDS = 30


@pytest.fixture(autouse=True)
def only_the_pr_hook():
    decisions.ON_APPROVE.clear()  # other test files clear this list; start from the one hook the PR screen registers
    pr_route.register()
    yield
    decisions.ON_APPROVE.clear()


def new_run(root, i: int, scenario: str = "normal") -> tuple[str, str]:
    """A fixture run with its own ticket id, so each round has its own branch and its own PR count."""
    run, ticket_id = f"dbl-{scenario}-{i}", f"DBL-{i}"
    fixtures.write_fixture_run(scenario, run_id=run, root=root)
    store.write_file(run, "ticket.json", Ticket(id=ticket_id, text=f"SIMULATED ticket {i}: the Radar header is cut off."), root=root)
    return run, ticket_id


def post_decision(app, run: str, body: dict):
    return TestClient(app, base_url="http://127.0.0.1").post(f"/api/runs/{run}/decision", json=body, headers=H)


def race(app, run: str, bodies: list[dict]) -> list:
    """Send all bodies at the same moment from a thread pool. Returns the responses in the order of `bodies`."""
    gate = threading.Barrier(len(bodies))

    def go(body):
        gate.wait(timeout=30)
        return post_decision(app, run, body)

    with ThreadPoolExecutor(max_workers=len(bodies)) as pool:
        return [f.result(timeout=60) for f in [pool.submit(go, b) for b in bodies]]


def approve(key: str, **extra) -> dict:
    return {"action": "approve", "idempotency_key": key, **extra}


def prs_of(root, ticket_id: str) -> list[dict]:
    return [p for p in mock_for(root).pulls if p["head"]["ref"] == branch_name(ticket_id)]


def assert_one_decision_one_pr(root, run: str, ticket_id: str, key: str) -> None:
    saved = json.loads((root / run / "decision.json").read_text("utf-8"))
    assert saved["decision"] == "approve" and saved["idempotency_key"] == key
    assert len(prs_of(root, ticket_id)) == 1  # one PR for the ticket's branch, not two
    pr = json.loads((root / run / "pr.json").read_text("utf-8"))
    assert pr["action"] == "created" and pr["updates"] == 0 and pr["draft"] is True  # written once, by the winner only
    assert store.get_state(run, root=root).state.value == "done"
    assert sorted(p.name for p in (root / run).glob(".*.tmp")) == []  # no half-written temp file left behind


def assert_requests_once_per_branch(root, rounds_done: int) -> None:
    mock = mock_for(root)
    assert mock.count("POST", "/pulls") == rounds_done and mock.count("POST", "/git/refs") == rounds_done
    assert len(mock.pulls) == rounds_done


# ---- same key twice -----------------------------------------------------------------------------------------------


def test_two_approves_with_one_key_at_once_give_one_decision_and_one_pr_30_times(app, runs_root):
    for i in range(ROUNDS):
        run, ticket = new_run(runs_root, i)
        a, b = race(app, run, [approve("same-key"), approve("same-key")])
        assert (a.status_code, b.status_code) == (200, 200), (i, a.text, b.text)
        assert sorted([a.json()["replayed"], b.json()["replayed"]]) == [False, True], i  # one decided, one got the stored decision back
        assert a.json()["decision"] == b.json()["decision"] and a.json()["hook_errors"] == b.json()["hook_errors"] == []
        assert_one_decision_one_pr(runs_root, run, ticket, "same-key")
        assert_requests_once_per_branch(runs_root, i + 1)


def test_the_same_key_sequentially_replays_and_makes_no_second_pr(app, runs_root):
    run, ticket = new_run(runs_root, 0)
    first, second = post_decision(app, run, approve("k")), post_decision(app, run, approve("k"))
    assert (first.json()["replayed"], second.json()["replayed"]) == (False, True) and first.json()["decision"] == second.json()["decision"]
    assert_one_decision_one_pr(runs_root, run, ticket, "k")
    assert_requests_once_per_branch(runs_root, 1)


# ---- different keys at once ---------------------------------------------------------------------------------------


def test_two_approves_with_different_keys_at_once_give_one_pr_and_a_typed_conflict_30_times(app, runs_root):
    wins = {"key-a": 0, "key-b": 0}
    for i in range(ROUNDS):
        run, ticket = new_run(runs_root, i)
        responses = race(app, run, [approve("key-a"), approve("key-b")])
        ok = [(k, r) for k, r in zip(["key-a", "key-b"], responses, strict=True) if r.status_code == 200]
        lost = [r for r in responses if r.status_code != 200]
        assert len(ok) == 1 and len(lost) == 1, (i, [r.status_code for r in responses])
        assert lost[0].status_code == 409
        assert lost[0].json() == {"error": {"code": "already_decided", "field": "idempotency_key", "message": lost[0].json()["error"]["message"]}}
        assert ok[0][1].json()["replayed"] is False
        assert_one_decision_one_pr(runs_root, run, ticket, ok[0][0])  # the stored key is the winner's
        assert_requests_once_per_branch(runs_root, i + 1)
        wins[ok[0][0]] += 1
    assert sum(wins.values()) == ROUNDS


def test_four_approves_with_four_keys_at_once_give_exactly_one_pr(app, runs_root):
    for i in range(10):
        run, ticket = new_run(runs_root, i)
        responses = race(app, run, [approve(f"k{n}") for n in range(4)])
        assert sorted(r.status_code for r in responses) == [200, 409, 409, 409], i
        assert {r.json()["error"]["code"] for r in responses if r.status_code == 409} == {"already_decided"}
        winner = next(f"k{n}" for n, r in enumerate(responses) if r.status_code == 200)
        assert_one_decision_one_pr(runs_root, run, ticket, winner)
        assert_requests_once_per_branch(runs_root, i + 1)


def test_the_race_window_widened_on_purpose_still_gives_one_decision_and_one_pr(app, runs_root, monkeypatch):
    """The read of decision.json sleeps after it read, so two requests both see "no decision yet" unless something serialises them."""
    real = decisions.stored_decision

    def slow(run_id, *, root=None):
        seen = real(run_id, root=root)
        time.sleep(0.05)
        return seen

    monkeypatch.setattr(decisions, "stored_decision", slow)
    for i in range(5):
        run, ticket = new_run(runs_root, i)
        responses = race(app, run, [approve("key-a"), approve("key-b")])
        assert sorted(r.status_code for r in responses) == [200, 409], (i, [r.text for r in responses])
        assert [r.json()["error"]["code"] for r in responses if r.status_code == 409] == ["already_decided"]
        winner = "key-a" if responses[0].status_code == 200 else "key-b"
        assert_one_decision_one_pr(runs_root, run, ticket, winner)
        assert_requests_once_per_branch(runs_root, i + 1)
    for i in range(5, 8):  # and the same key, widened: the second request is a replay, not a second decision
        run, ticket = new_run(runs_root, i)
        a, b = race(app, run, [approve("same"), approve("same")])
        assert sorted([a.json()["replayed"], b.json()["replayed"]]) == [False, True], i
        assert_one_decision_one_pr(runs_root, run, ticket, "same")
        assert_requests_once_per_branch(runs_root, i + 1)


def test_approve_racing_with_the_raise_pr_route_still_gives_one_pr(app, runs_root):
    for i in range(10):
        run, ticket = new_run(runs_root, i)
        gate = threading.Barrier(4)

        def go(kind):
            gate.wait(timeout=30)
            c = TestClient(app, base_url="http://127.0.0.1")
            return c.post(f"/api/runs/{run}/decision", json=approve("k"), headers=H) if kind == "approve" else c.post(f"/api/runs/{run}/pr", headers=H)

        with ThreadPoolExecutor(max_workers=4) as pool:
            out = [f.result(timeout=60) for f in [pool.submit(go, k) for k in ("approve", "pr", "pr", "pr")]]
        assert out[0].status_code == 200
        assert {r.status_code for r in out[1:]} <= {200, 409}  # 409 not_approved when it got in before the approval
        assert len(prs_of(runs_root, ticket)) == 1 and len(mock_for(runs_root).pulls) == i + 1
        assert mock_for(runs_root).count("POST", "/pulls") == i + 1


# ---- approve after a failed verifier: the server says no --------------------------------------------------------------


def untouched(root, run: str) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted((root / run).iterdir()) if p.is_file()}


@pytest.mark.parametrize("extra", [{}, {"reason": "I looked at it by hand and it is fine."}, {"note": "approve anyway"}])
def test_approve_after_a_failed_verifier_is_refused_by_the_server(app, runs_root, extra):
    fixtures.write_all_fixtures(root=runs_root)
    before = untouched(runs_root, "fixture-verifier")
    r = post_decision(app, "fixture-verifier", approve("any-key", **extra))
    assert r.status_code == 409 and r.json()["error"]["code"] == "verifier_failed" and r.json()["error"]["field"] == "action"
    assert untouched(runs_root, "fixture-verifier") == before  # no decision.json, state.json as it was
    assert mock_for(runs_root).requests == []  # no GitHub call, not even a lookup
    assert not (runs_root / "fixture-verifier" / "pr.json").exists()


def test_a_run_that_looks_reviewable_but_has_a_failing_verdict_on_disk_is_refused_too(app, runs_root):
    """State awaiting-qa (the page would show Approve) but verdict.json says fail: only the server-side verdict check stands in the way."""
    run, ticket = new_run(runs_root, 0)
    store.write_file(run, "verdict.json", fixtures._verdict("verifier", "SIMULATED"), root=runs_root)
    assert store.get_state(run, root=runs_root).state.value == "awaiting-qa" and not store.read_file(run, "verdict.json", root=runs_root).ok
    before = untouched(runs_root, run)
    r = post_decision(app, run, approve("any-key", reason="the checks are wrong, ship it"))
    assert r.status_code == 409 and r.json()["error"]["code"] == "verifier_failed"
    assert untouched(runs_root, run) == before and mock_for(runs_root).requests == []
    assert store.get_state(run, root=runs_root).state.value == "awaiting-qa"  # still waiting, nothing moved


def test_many_approves_at_once_after_a_failed_verifier_are_all_refused(app, runs_root):
    fixtures.write_all_fixtures(root=runs_root)
    before = untouched(runs_root, "fixture-verifier")
    responses = race(app, "fixture-verifier", [approve(f"k{n}") for n in range(8)])
    assert {(r.status_code, r.json()["error"]["code"]) for r in responses} == {(409, "verifier_failed")}
    assert untouched(runs_root, "fixture-verifier") == before and mock_for(runs_root).requests == []


def test_the_request_cannot_claim_the_verifier_passed(app, runs_root):
    fixtures.write_all_fixtures(root=runs_root)
    for field in ("verdict_ok", "verifier_passed", "force"):
        r = post_decision(app, "fixture-verifier", {**approve("k"), field: True})
        assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_request"
    assert not (runs_root / "fixture-verifier" / "decision.json").exists() and mock_for(runs_root).requests == []


def test_the_pr_route_also_refuses_when_the_verdict_turned_bad_after_the_approval(app, runs_root):
    """Second layer: raise_pr checks the verdict itself, so a later POST /pr cannot publish a run whose verdict is now a fail."""
    run, ticket = new_run(runs_root, 0)
    assert post_decision(app, run, approve("k")).status_code == 200
    seen = len(mock_for(runs_root).requests)
    pr_before = (runs_root / run / "pr.json").read_bytes()
    store.write_file(run, "verdict.json", fixtures._verdict("verifier", "SIMULATED"), root=runs_root)
    r = TestClient(app, base_url="http://127.0.0.1").post(f"/api/runs/{run}/pr", headers=H)
    assert r.status_code == 409 and r.json()["error"]["code"] == "verifier_failed"
    assert len(mock_for(runs_root).requests) == seen and (runs_root / run / "pr.json").read_bytes() == pr_before


def test_a_genuine_approve_of_a_passing_run_still_works(app, runs_root):
    """Control: the refusals above are about the failed verifier, not about approve being broken."""
    run, ticket = new_run(runs_root, 0)
    r = post_decision(app, run, approve("k"))
    assert r.status_code == 200 and r.json()["hook_errors"] == []
    assert_one_decision_one_pr(runs_root, run, ticket, "k")
