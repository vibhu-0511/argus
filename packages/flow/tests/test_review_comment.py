"""P6-T10: the review-comment QA path. Fixture payloads, no Postgres, no MCP, no network."""

import hashlib
import hmac
import json
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from flow.enqueue import FakeEnqueuer
from flow.qa import qa_message
from flow.review_comment import REVIEWERS_ENV, parse_decision, parse_review_event, reviewers_from_env
from flow.states import branch_name, qa_signal_key
from flow.webhook import EVENT_HEADER, SECRET_ENV, SIGNATURE_HEADER, create_app

TICKET = "acme/shop#7"
REVIEWERS = frozenset({"alice"})


def pr(ticket: str = TICKET, **over) -> dict:
    return {"number": 12, "title": f"Argus fix for {ticket}", "head": {"ref": branch_name(ticket)}, **over}


def review(body: str, login: str = "Alice", action: str = "submitted", rid: int = 9001, **over) -> dict:
    """A `pull_request_review` payload, trimmed to the fields GitHub sends that we read."""
    return {
        "action": action,
        "review": {"id": rid, "body": body, "state": "commented", "user": {"login": login}},
        "pull_request": pr(**over),
        "repository": {"full_name": "acme/shop"},
    }


def inline(body: str, login: str = "alice", action: str = "created", cid: int = 5005) -> dict:
    """A `pull_request_review_comment` payload."""
    return {
        "action": action,
        "comment": {"id": cid, "body": body, "user": {"login": login}},
        "pull_request": pr(),
        "repository": {"full_name": "acme/shop"},
    }


def parse(event: str, payload: dict):
    return parse_review_event(event, payload, REVIEWERS)


def test_approve_keyword_in_a_review_gives_an_approve_signal():
    sig = parse("pull_request_review", review("Looks good.\n/argus approve\n"))
    assert (sig.ticket_id, sig.decision, sig.source_id, sig.by) == (TICKET, "approve", "review-9001", "alice")


def test_reject_keyword_in_an_inline_comment_gives_a_reject_signal():
    sig = parse("pull_request_review_comment", inline("/argus reject this breaks the cart"))
    assert (sig.ticket_id, sig.decision, sig.source_id) == (TICKET, "reject", "comment-5005")


def test_keyword_is_case_insensitive_and_needs_its_own_line_start():
    assert parse_decision("  /ARGUS   Approve  ") == "approve"
    assert parse_decision("I would /argus approve this") is None
    assert parse_decision("> /argus approve\nquoted, not said") is None
    assert parse_decision("/argusapprove") is None and parse_decision("/argus approved") is None
    assert parse_decision(None) is None and parse_decision("") is None


def test_both_keywords_are_ambiguous_and_count_as_neither():
    assert parse_decision("/argus approve\n/argus reject") is None
    assert parse_decision("/argus approve\n/argus approve") == "approve"


@pytest.mark.parametrize("login", ["mallory", "", "ALICE-bot"])
def test_a_commenter_who_is_not_allowed_is_ignored(login):
    assert parse("pull_request_review", review("/argus approve", login=login)) is None


def test_nobody_is_allowed_when_the_reviewer_list_is_unset(monkeypatch):
    monkeypatch.delenv(REVIEWERS_ENV, raising=False)
    assert reviewers_from_env() == frozenset()
    assert parse_review_event("pull_request_review", review("/argus approve")) is None
    monkeypatch.setenv(REVIEWERS_ENV, " Alice, bob ,,")
    assert reviewers_from_env() == {"alice", "bob"}
    assert parse_review_event("pull_request_review", review("/argus approve")).by == "alice"


def test_edits_and_deletes_do_not_signal():
    assert parse("pull_request_review", review("/argus approve", action="edited")) is None
    assert parse("pull_request_review_comment", inline("/argus approve", action="deleted")) is None


def test_other_events_and_malformed_payloads_do_not_signal():
    assert parse("issue_comment", review("/argus approve")) is None
    assert parse("pull_request_review", []) is None
    assert parse("pull_request_review", {"action": "submitted"}) is None
    assert parse("pull_request_review", review("/argus approve") | {"review": {"id": 1}}) is None


def test_a_pr_that_is_not_an_argus_pr_is_ignored():
    assert parse("pull_request_review", review("/argus approve", title="Fix the cart")) is None
    # right title, wrong branch: the ticket id in a title is not trusted on its own
    assert parse("pull_request_review", review("/argus approve", head={"ref": "someone/else"})) is None
    assert parse("pull_request_review", review("/argus approve", title="Argus fix for ")) is None


def test_the_signal_key_is_the_same_for_a_redelivery_and_differs_per_comment():
    a = parse("pull_request_review", review("/argus approve"))
    again = parse("pull_request_review", review("/argus approve"))
    other = parse("pull_request_review", review("/argus approve", rid=9002))

    def key(s):
        return qa_message(s.ticket_id, s.decision, "review-comment", s.source_id)["key"]

    assert key(a) == key(again) == qa_signal_key(TICKET, "review-comment", "review-9001")
    assert key(other) != key(a)


def test_the_review_path_needs_no_mcp():
    code = "import sys, flow.webhook, flow.review_comment; sys.exit('mcp' in sys.modules)"
    assert subprocess.run([sys.executable, "-I", "-c", code]).returncode == 0


# --- through the webhook ----------------------------------------------------------------------

SECRET = "test-secret-not-real"


def post(client: TestClient, event: str, payload: dict):
    body = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    return client.post("/webhook", content=body, headers={SIGNATURE_HEADER: sig, EVENT_HEADER: event})


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv(SECRET_ENV, SECRET)
    monkeypatch.setenv(REVIEWERS_ENV, "alice")
    enq, sent = FakeEnqueuer(), []
    return TestClient(create_app(enq, qa_send=sent.append)), enq, sent


def test_webhook_sends_the_qa_signal_and_enqueues_nothing(app):
    client, enq, sent = app
    r = post(client, "pull_request_review", review("/argus approve"))
    assert r.status_code == 202 and r.json()["status"] == "qa-signal" and r.json()["decision"] == "approve"
    assert [(s.ticket_id, s.decision) for s in sent] == [(TICKET, "approve")]
    assert enq.calls == []  # the PR number is not a ticket id; nothing to reconcile


def test_the_same_delivery_twice_sends_the_same_signal_twice_and_the_key_makes_it_one(app):
    client, _, sent = app
    for _ in range(2):
        assert post(client, "pull_request_review", review("/argus reject")).status_code == 202
    assert len(sent) == 2 and sent[0] == sent[1]  # same ticket, decision and source id -> same key downstream


def test_a_review_without_the_keyword_is_just_a_hint_as_before(app):
    client, enq, sent = app
    r = post(client, "pull_request_review", review("nice work"))
    assert r.status_code == 202 and r.json()["status"] == "accepted"
    assert sent == [] and enq.calls == ["acme/shop#12"]


def test_a_commenter_who_is_not_allowed_sends_nothing(app):
    client, _, sent = app
    post(client, "pull_request_review", review("/argus approve", login="mallory"))
    assert sent == []


def test_a_failing_send_is_logged_and_the_response_is_still_202(monkeypatch):
    monkeypatch.setenv(SECRET_ENV, SECRET)
    monkeypatch.setenv(REVIEWERS_ENV, "alice")

    def boom(signal):
        raise RuntimeError("no workflow")

    client = TestClient(create_app(FakeEnqueuer(), qa_send=boom))
    assert post(client, "pull_request_review", review("/argus approve")).status_code == 202


def test_an_unsigned_review_comment_is_401_and_sends_nothing(app):
    client, _, sent = app
    body = json.dumps(review("/argus approve")).encode()
    r = client.post("/webhook", content=body, headers={EVENT_HEADER: "pull_request_review"})
    assert r.status_code == 401 and sent == []


def test_without_qa_send_the_webhook_behaves_as_in_t06(monkeypatch):
    monkeypatch.setenv(SECRET_ENV, SECRET)
    monkeypatch.setenv(REVIEWERS_ENV, "alice")
    enq = FakeEnqueuer()
    r = post(TestClient(create_app(enq)), "pull_request_review", review("/argus approve"))
    assert r.json()["status"] == "accepted" and enq.calls == ["acme/shop#12"]
