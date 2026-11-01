"""P6-T03 and P6-T08: the DBOS ticket workflow and its QA signal wait against a real local Postgres,
with fake runners and GitHub.

Needs `ARGUS_FLOW_DATABASE_URL` (see docs/notes/p6-t03.md); skipped with a reason when it is unset.
No LLM, no network. Each test uses its own ticket id, so runs do not see each other in the
shared system database.
"""

from __future__ import annotations

import os
import time
import uuid

import psycopg
import pytest
from dbos import DBOS

from flow.config import DATABASE_URL_ENV, FlowSettings
from flow.dbos_runtime import QUEUE_NAME, DbosEnqueuer, launch, shutdown
from flow.fakes import FakeGitHub, FakeRunner
from flow.qa import QA_TOPIC, send_qa_signal
from flow.states import TRANSITIONS, branch_name, effect_key, qa_signal_key
from flow.workflow import Deps, Outcome, PullRequest, fix_step, set_deps

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(not os.environ.get(DATABASE_URL_ENV), reason=f"{DATABASE_URL_ENV} is not set; needs a real Postgres"),
]

STEP_NAMES = ["repro_step", "fix_step", "verify_step", "open_pr_step", "finish_step"]


class World:
    """One test's fakes, wired in as the workflow's deps."""

    def __init__(self) -> None:
        self.repro, self.fix, self.verify = FakeRunner(Outcome(True, "repro.sh")), FakeRunner(Outcome(True, "the patch")), FakeRunner()
        self.github = FakeGitHub()
        self.deps = Deps(self.repro, self.fix, self.verify, self.github, qa_timeout_seconds=60.0)


@pytest.fixture(scope="module")
def enqueuer():
    enq = launch(FlowSettings.from_env(), Deps(None, None, None, None))
    yield enq
    shutdown()


@pytest.fixture
def world(enqueuer):
    w = World()
    set_deps(w.deps)
    return w


@pytest.fixture
def ticket():
    return f"acme/{uuid.uuid4().hex[:8]}#7"


def run(enqueuer: DbosEnqueuer, ticket: str, decision: str = "approve") -> dict:
    """Start the workflow, send the QA signal at once (it waits in the mailbox), return the result."""
    handle = enqueuer.enqueue(ticket)
    send_qa_signal(ticket, decision, "review-comment", "1", by="reviewer")
    return handle.get_result()


def wait_until(predicate, seconds: float = 30.0) -> None:
    deadline = time.monotonic() + seconds
    while not predicate():
        assert time.monotonic() < deadline, "timed out waiting for the workflow"
        time.sleep(0.2)


def mailbox_rows(ticket: str) -> int:
    with psycopg.connect(os.environ[DATABASE_URL_ENV]) as conn:
        return conn.execute("select count(*) from dbos.notifications where destination_uuid = %s", (ticket,)).fetchone()[0]


def stored_steps(ticket: str) -> list[dict]:
    return [s for s in DBOS.list_workflow_steps(ticket) if s["function_name"] in STEP_NAMES]


def assert_legal_path(trail: list[str]) -> None:
    legal = {(frm.value, to.value) for frm, _, to, _ in TRANSITIONS}
    for a, b in zip(trail, trail[1:]):
        assert (a, b) in legal, f"{a} -> {b} is not a transition in states.TRANSITIONS"


def test_full_run_on_a_fixture_ticket_reaches_done(enqueuer, world, ticket):
    out = run(enqueuer, ticket)
    assert out["state"] == "done"
    assert out["trail"] == ["received", "reproducing", "fixing", "verifying", "opening-pr", "awaiting-qa", "done"]
    assert_legal_path(out["trail"])
    # each dispatch step got its own idempotency key, and each effect happened once
    assert world.repro.calls == [effect_key(ticket, "dispatch-repro")]
    assert world.fix.calls == [effect_key(ticket, "dispatch-fix")]
    assert world.verify.calls == [effect_key(ticket, "dispatch-verify")]
    branch = branch_name(ticket)
    assert world.github.branches[branch] == {effect_key(ticket, "push-branch")}
    assert list(world.github.prs) == [branch]  # one PR; created as a draft (checked below), ready after approval
    assert set(world.github.comments) == {effect_key(ticket, "comment-awaiting-qa"), effect_key(ticket, "comment-done")}
    assert world.github.labels[ticket] == "done"
    assert not world.github.prs[branch].draft and world.github.calls.count("ready_pr") == 1  # ready only after approval
    title, body = world.github.bodies[branch]
    assert "closes" not in (title + body).lower()


def test_each_steps_result_is_stored(enqueuer, world, ticket):
    run(enqueuer, ticket)
    steps = stored_steps(ticket)
    assert [s["function_name"] for s in steps] == STEP_NAMES
    by_name = {s["function_name"]: s["output"] for s in steps}
    assert by_name["repro_step"] == {"ok": True, "output": "repro.sh"}
    assert by_name["fix_step"] == {"ok": True, "output": "the patch"}
    assert by_name["verify_step"] == {"ok": True, "output": "ok"}
    assert by_name["open_pr_step"]["ok"] and by_name["open_pr_step"]["draft"] is True
    assert by_name["finish_step"] == {"ok": True, "output": "done"}
    status = DBOS.retrieve_workflow(ticket).get_status()
    assert status.status == "SUCCESS" and status.output["state"] == "done"


def test_starting_the_workflow_twice_repeats_no_side_effect(enqueuer, world, ticket):
    first = enqueuer.enqueue(ticket)
    second = enqueuer.enqueue(ticket)  # webhook and poller meeting on one ticket
    send_qa_signal(ticket, "approve", "review-comment", "1")
    assert first.get_workflow_id() == second.get_workflow_id() == ticket
    assert first.get_result() == second.get_result()
    enqueuer.enqueue_reconcile(ticket)  # a late hint, after the run finished
    assert len(DBOS.list_workflows(workflow_ids=[ticket])) == 1
    assert len(world.repro.calls) == len(world.fix.calls) == len(world.verify.calls) == 1
    assert world.github.calls.count("create_draft_pr") == 1 and len(world.github.prs) == 1
    assert len(world.github.comments) == 2


def test_rerunning_a_step_finds_its_effect(enqueuer, world, ticket):
    run(enqueuer, ticket)
    open_pr = next(s for s in stored_steps(ticket) if s["function_name"] == "open_pr_step")
    # a fork re-runs open_pr_step and finish_step, as a crash after the PR but before the result would
    fork = DBOS.fork_workflow(ticket, open_pr["function_id"])
    DBOS.send(fork.get_workflow_id(), {"decision": "approve", "key": "k", "source": "review-comment", "by": ""}, QA_TOPIC)
    forked = fork.get_result()
    assert forked["state"] == "done"
    assert len(world.repro.calls) == len(world.fix.calls) == len(world.verify.calls) == 1  # earlier results reused
    assert world.github.calls.count("find_pr") == 2 and world.github.calls.count("create_draft_pr") == 1
    assert len(world.github.prs) == 1 and len(world.github.comments) == 2
    assert len(world.github.branches[branch_name(ticket)]) == 1
    # and a step called twice outside any workflow: it runs twice, the effect happens once
    fix_step(ticket, "repro.sh")
    fix_step(ticket, "repro.sh")
    assert len(world.fix.calls) == 3 and len(world.fix.runs) == 1


def test_a_failed_step_ends_in_failed_and_opens_no_pr(enqueuer, world, ticket):
    world.fix.outcome = Outcome(False, "budget exhausted")
    out = run(enqueuer, ticket)
    assert out["state"] == "failed" and out["trail"] == ["received", "reproducing", "fixing", "failed"]
    assert_legal_path(out["trail"])
    assert "budget exhausted" in out["reason"]
    assert world.verify.calls == [] and world.github.prs == {} and world.github.branches == {}
    assert world.github.labels[ticket] == "failed"
    assert set(world.github.comments) == {effect_key(ticket, "comment-failed")}


def test_existing_pr_is_reused_not_recreated(enqueuer, world, ticket):
    existing = world.github.prs[branch_name(ticket)] = PullRequest(41, "https://example.test/pr/41", True)
    out = run(enqueuer, ticket)
    assert out["state"] == "done"
    assert world.github.prs[branch_name(ticket)].number == existing.number == 41  # same PR, made ready by approval
    assert "create_draft_pr" not in world.github.calls


def test_a_lookup_error_leaves_the_existing_pr_untouched(enqueuer, world, ticket):
    existing = world.github.prs[branch_name(ticket)] = PullRequest(41, "https://example.test/pr/41", True)
    world.github.lookup_error = ConnectionError("github 502")
    out = run(enqueuer, ticket)
    # the step retried its three attempts, never created a PR, and the ticket ends in failed
    assert world.github.calls.count("find_pr") == 3 and "create_draft_pr" not in world.github.calls
    assert world.github.prs == {branch_name(ticket): existing}
    assert out["state"] == "failed" and out["trail"][-2:] == ["opening-pr", "failed"]
    assert world.github.labels[ticket] == "failed"


def test_the_queue_is_database_backed(enqueuer, ticket, world):
    assert DBOS.retrieve_queue(QUEUE_NAME) is not None
    run(enqueuer, ticket)
    assert DBOS.retrieve_workflow(ticket).get_status().queue_name == QUEUE_NAME


# --- P6-T08: the QA signal wait ---------------------------------------------------------------


def test_the_workflow_pauses_in_awaiting_qa_until_a_signal_arrives(enqueuer, world, ticket):
    handle = enqueuer.enqueue(ticket)
    wait_until(lambda: world.github.labels.get(ticket) == "awaiting-qa")
    time.sleep(2.5)  # past two polls of the mailbox: still waiting, nothing decided
    assert handle.get_status().status == "PENDING"
    assert world.github.prs[branch_name(ticket)].draft and "ready_pr" not in world.github.calls
    assert effect_key(ticket, "comment-done") not in world.github.comments
    send_qa_signal(ticket, "approve", "mrtr", "req-1", by="alice")
    out = handle.get_result()
    assert out["state"] == "done" and out["reason"] == "approve via mrtr by alice"
    assert out["trail"][-2:] == ["awaiting-qa", "done"]
    assert not world.github.prs[branch_name(ticket)].draft and world.github.labels[ticket] == "done"


def test_a_reject_signal_ends_in_rejected_and_closes_the_pr(enqueuer, world, ticket):
    out = run(enqueuer, ticket, "reject")
    assert out["state"] == "rejected" and out["trail"][-2:] == ["awaiting-qa", "rejected"]
    assert_legal_path(out["trail"])
    branch = branch_name(ticket)
    assert world.github.closed == {branch} and world.github.prs[branch].draft  # closed, never made ready
    assert "ready_pr" not in world.github.calls
    assert world.github.labels[ticket] == "rejected"
    assert effect_key(ticket, "comment-rejected") in world.github.comments


def test_no_signal_times_out_into_timed_out_and_leaves_the_pr_open_and_draft(enqueuer, world, ticket):
    world.deps = world.deps._replace(qa_timeout_seconds=1.0)
    set_deps(world.deps)
    out = enqueuer.enqueue(ticket).get_result()
    assert out["state"] == "timed-out" and out["trail"][-2:] == ["awaiting-qa", "timed-out"]
    assert_legal_path(out["trail"])
    assert "no QA signal within 1 s" in out["reason"]
    branch = branch_name(ticket)
    assert world.github.prs[branch].draft and not world.github.closed
    assert "ready_pr" not in world.github.calls and "close_pr" not in world.github.calls
    assert world.github.labels[ticket] == "timed-out"
    assert effect_key(ticket, "comment-timed-out") in world.github.comments


def test_a_duplicate_signal_changes_nothing(enqueuer, world, ticket):
    handle = enqueuer.enqueue(ticket)
    keys = {send_qa_signal(ticket, "approve", "review-comment", "c-17") for _ in range(3)}  # redelivered thrice
    assert keys == {qa_signal_key(ticket, "review-comment", "c-17")}
    out = handle.get_result()
    send_qa_signal(ticket, "approve", "review-comment", "c-17")  # and once more after the end
    assert out["state"] == "done" and mailbox_rows(ticket) == 1
    assert world.github.calls.count("ready_pr") == 1 and len(world.github.comments) == 2


def test_a_different_signal_after_the_first_is_dropped(enqueuer, world, ticket):
    out = run(enqueuer, ticket, "approve")
    send_qa_signal(ticket, "reject", "review-comment", "2", by="bob")  # different key, workflow already done
    assert DBOS.retrieve_workflow(ticket).get_status().output["state"] == out["state"] == "done"
    assert world.github.closed == set() and not world.github.prs[branch_name(ticket)].draft
    assert world.github.labels[ticket] == "done"


def test_a_bad_signal_is_refused_before_it_is_sent(enqueuer, world, ticket):
    enqueuer.enqueue(ticket)
    for args in (("maybe", "review-comment", "1"), ("approve", "email", "1"), ("approve", "mrtr", "")):
        with pytest.raises(ValueError):
            send_qa_signal(ticket, *args)
    assert mailbox_rows(ticket) == 0
    send_qa_signal(ticket, "approve", "mrtr", "1")  # let the workflow end
    wait_until(lambda: world.github.labels.get(ticket) == "done")


# --- P6-T10: the same signal from a GitHub review comment, through the webhook -----------------


def test_a_review_comment_resumes_the_waiting_workflow_without_mcp(enqueuer, world, ticket, monkeypatch):
    import hashlib
    import hmac
    import json

    from fastapi.testclient import TestClient

    from flow.review_comment import REVIEWERS_ENV, send_review_signal
    from flow.webhook import EVENT_HEADER, SECRET_ENV, SIGNATURE_HEADER, create_app

    monkeypatch.setenv(SECRET_ENV, "test-secret-not-real")
    monkeypatch.setenv(REVIEWERS_ENV, "alice")
    client = TestClient(create_app(enqueuer, qa_send=send_review_signal))
    handle = enqueuer.enqueue(ticket)
    wait_until(lambda: world.github.labels.get(ticket) == "awaiting-qa")
    payload = {
        "action": "submitted",
        "review": {"id": 77, "body": "ship it\n/argus approve", "user": {"login": "Alice"}},
        "pull_request": {"number": 3, "title": f"Argus fix for {ticket}", "head": {"ref": branch_name(ticket)}},
        "repository": {"full_name": "acme/x"},
    }
    body = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(b"test-secret-not-real", body, hashlib.sha256).hexdigest()
    for _ in range(2):  # GitHub delivers it twice
        r = client.post("/webhook", content=body, headers={SIGNATURE_HEADER: sig, EVENT_HEADER: "pull_request_review"})
        assert r.json()["status"] == "qa-signal"
    out = handle.get_result()
    assert out["state"] == "done" and out["reason"] == "approve via review-comment by alice"
    assert mailbox_rows(ticket) == 1 and not world.github.prs[branch_name(ticket)].draft
    key = qa_signal_key(ticket, "review-comment", "review-77")
    with psycopg.connect(os.environ[DATABASE_URL_ENV]) as conn:
        row = conn.execute("select message_uuid from dbos.notifications where destination_uuid = %s", (ticket,)).fetchone()
    assert row[0] == f"{key}::{ticket}"
