"""P8-T08: a labelled issue starts exactly one workflow; a label from a user without write access is ignored and logged.

GitHub is a `httpx.MockTransport` that answers the collaborator-permission call; no network, no model. The real App
and a real label event were not used (docs/notes/p8-t08.md).
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging

import httpx
import pytest
from fastapi.testclient import TestClient
from guard.auditlog import AuditLog, verify

from flow.enqueue import FakeEnqueuer
from flow.installations import RepoNotInstalled
from flow.intake import Intake
from flow.webhook import DELIVERY_HEADER, EVENT_HEADER, SECRET_ENV, SIGNATURE_HEADER, create_app

SECRET = "test-secret-not-real"
FAKE_TOKEN = "fake-installation-token-not-real"
ROLES = {"maya": "write", "boss": "admin", "lead": "maintain", "triager": "triage", "reader": "read", "stranger": None}


class FakeGitHub:
    """`GET /repos/{repo}/collaborators/{login}/permission` as the docs describe it: 404 for a non-collaborator."""

    def __init__(self, status: int | None = None) -> None:
        self.status, self.calls = status, []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append((request.method, request.url.path, request.headers.get("authorization")))
        login = request.url.path.split("/")[-2]
        if self.status:
            return httpx.Response(self.status, json={"message": "boom"})
        role = ROLES.get(login)
        if role is None:
            return httpx.Response(404, json={"message": "Not Found"})
        legacy = {"admin": "admin", "maintain": "write", "write": "write", "triage": "read", "read": "read"}[role]
        return httpx.Response(200, json={"permission": legacy, "role_name": role, "user": {"login": login}})


def event(label: str = "argus", actor: str = "maya", number: int = 7, action: str = "labeled") -> dict:
    return {
        "action": action,
        "label": {"name": label},
        "sender": {"login": actor},
        "issue": {"number": number, "state": "open", "title": "Button is cut off"},
        "repository": {"full_name": "acme/shop"},
    }


class Rig:
    def __init__(self, monkeypatch, github: FakeGitHub | None = None, audit=None, token_for=None) -> None:
        monkeypatch.setenv(SECRET_ENV, SECRET)
        self.github = github or FakeGitHub()
        self.enqueuer = FakeEnqueuer()
        self.intake = Intake(
            self.enqueuer, token_for or (lambda repo: FAKE_TOKEN), label="argus", audit=audit, transport=httpx.MockTransport(self.github)
        )
        self.app = create_app(self.enqueuer, on_intake=self.intake.handle)
        self.client = TestClient(self.app)

    def post(self, payload: dict, delivery: str | None = "d-1", event_name: str = "issues") -> httpx.Response:
        body = json.dumps(payload).encode()
        headers = {EVENT_HEADER: event_name, SIGNATURE_HEADER: "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()}
        if delivery:
            headers[DELIVERY_HEADER] = delivery
        return self.client.post("/webhook", content=body, headers=headers)


@pytest.fixture
def rig(monkeypatch):
    return Rig(monkeypatch)


def test_the_label_from_a_user_with_write_access_starts_one_workflow(rig):
    r = rig.post(event())
    assert r.status_code == 202 and r.json()["status"] == "intake"
    assert rig.enqueuer.workflows == {"acme/shop#7"}
    assert rig.github.calls == [("GET", "/repos/acme/shop/collaborators/maya/permission", f"Bearer {FAKE_TOKEN}")]


@pytest.mark.parametrize("actor", ["maya", "boss", "lead"])
def test_write_maintain_and_admin_may_start(monkeypatch, actor):
    rig = Rig(monkeypatch)
    rig.post(event(actor=actor))
    assert rig.enqueuer.workflows == {"acme/shop#7"}


def test_the_same_delivery_twice_is_one_workflow_and_one_permission_check(rig):
    assert rig.post(event(), delivery="d-1").status_code == 202
    assert rig.post(event(), delivery="d-1").status_code == 202  # GitHub's redelivery
    assert rig.enqueuer.workflows == {"acme/shop#7"} and rig.enqueuer.calls == ["acme/shop#7"]
    assert len(rig.github.calls) == 1


def test_the_label_added_again_is_still_one_workflow(rig):
    """Removed and added again, or added by a second person: new delivery ids, the same ticket id."""
    rig.post(event(), delivery="d-1")
    rig.post(event(), delivery="d-2")
    rig.post(event(actor="boss"), delivery="d-3")
    assert rig.enqueuer.workflows == {"acme/shop#7"}  # one workflow id, however often it is asked for


def test_two_issues_are_two_workflows(rig):
    rig.post(event(number=7), delivery="d-1")
    rig.post(event(number=8), delivery="d-2")
    assert rig.enqueuer.workflows == {"acme/shop#7", "acme/shop#8"}


@pytest.mark.parametrize("actor", ["triager", "reader", "stranger"])
def test_a_label_from_a_user_without_write_access_is_ignored_and_logged(monkeypatch, caplog, tmp_path, actor):
    audit = AuditLog(tmp_path / "audit.jsonl")
    rig = Rig(monkeypatch, audit=audit.append)
    with caplog.at_level(logging.INFO, logger="flow.intake"):
        r = rig.post(event(actor=actor))
    assert r.status_code == 202
    assert rig.enqueuer.workflows == set() and rig.enqueuer.calls == []  # nothing was started
    line = next(rec.getMessage() for rec in caplog.records if rec.getMessage().startswith("intake_ignored"))
    record = json.loads(line.removeprefix("intake_ignored "))
    assert record["actor"] == actor and record["ticket"] == "acme/shop#7" and record["label"] == "argus"
    assert "write" in record["reason"] or "access" in record["reason"]
    logged = [json.loads(x) for x in (tmp_path / "audit.jsonl").read_text().splitlines()]  # the guard audit log has it too
    assert [(x["kind"], x["payload"]) for x in logged] == [("intake_ignored", record)]
    assert verify(tmp_path / "audit.jsonl").bad_line is None


def test_a_failed_permission_check_refuses(monkeypatch, caplog):
    rig = Rig(monkeypatch, github=FakeGitHub(status=500))
    with caplog.at_level(logging.INFO, logger="flow.intake"):
        assert rig.post(event()).status_code == 202
    assert rig.enqueuer.calls == []
    assert any("intake_ignored" in r.getMessage() and "permission check failed" in r.getMessage() for r in caplog.records)
    rig.github.status = None  # GitHub is back and the delivery is sent again by hand: it is not swallowed as a repeat
    rig.post(event())
    assert rig.enqueuer.workflows == {"acme/shop#7"}


def test_a_repo_without_the_app_is_refused_before_any_http_call(monkeypatch, caplog):
    def not_installed(repo: str) -> str:
        raise RepoNotInstalled(repo)

    rig = Rig(monkeypatch, token_for=not_installed)
    with caplog.at_level(logging.INFO, logger="flow.intake"):
        rig.post(event())
    assert rig.github.calls == [] and rig.enqueuer.calls == []
    assert any("intake_ignored" in r.getMessage() and "RepoNotInstalled" in r.getMessage() for r in caplog.records)


def test_other_labels_and_other_actions_start_nothing(rig):
    assert rig.post(event(label="bug"), delivery="d-1").status_code == 202
    assert rig.post(event(action="opened"), delivery="d-2").json()["status"] == "ignored"
    assert rig.post(event(action="unlabeled"), delivery="d-3").json()["status"] == "ignored"
    assert rig.enqueuer.calls == [] and rig.github.calls == []  # not even a permission call for another label


def test_a_pull_request_is_not_an_issue(rig):
    payload = event()
    payload["issue"]["pull_request"] = {"url": "x"}
    rig.post(payload)
    assert rig.enqueuer.calls == [] and rig.github.calls == []


def test_the_label_name_ignores_case(rig):
    rig.post(event(label="Argus"))
    assert rig.enqueuer.workflows == {"acme/shop#7"}


def test_a_bad_signature_still_gets_401_and_starts_nothing(rig):
    r = rig.client.post("/webhook", content=json.dumps(event()).encode(), headers={EVENT_HEADER: "issues", SIGNATURE_HEADER: "sha256=00"})
    assert r.status_code == 401 and rig.enqueuer.calls == [] and rig.github.calls == []


def test_without_intake_an_issue_event_is_a_plain_hint(monkeypatch):
    monkeypatch.setenv(SECRET_ENV, SECRET)
    fake = FakeEnqueuer()
    body = json.dumps(event(action="opened")).encode()
    sig = "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    r = TestClient(create_app(fake)).post("/webhook", content=body, headers={EVENT_HEADER: "issues", SIGNATURE_HEADER: sig})
    assert r.json()["status"] == "accepted" and fake.calls == ["acme/shop#7"]  # the P6 behaviour is unchanged


def test_the_answer_is_sent_before_the_permission_call(monkeypatch):
    """ADR-021: the webhook answers first and the GitHub call happens after."""
    order: list[str] = []

    def token_for(repo: str) -> str:
        order.append("github")
        return FAKE_TOKEN

    rig = Rig(monkeypatch, token_for=token_for)
    body = json.dumps(event()).encode()
    headers = {EVENT_HEADER: "issues", SIGNATURE_HEADER: "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()}
    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "POST", "scheme": "http", "path": "/webhook",
        "raw_path": b"/webhook", "query_string": b"", "server": ("test", 80), "client": ("test", 1),
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
    }

    async def drive() -> None:
        sent_body = False

        async def receive():
            nonlocal sent_body
            if sent_body:
                await asyncio.sleep(3600)
            sent_body = True
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message):
            if message["type"] == "http.response.start":
                order.append(f"response {message['status']}")

        await rig.app(scope, receive, send)

    asyncio.run(drive())
    assert order == ["response 202", "github"]
    assert rig.enqueuer.workflows == {"acme/shop#7"}


def test_no_token_in_the_log(monkeypatch, caplog):
    rig = Rig(monkeypatch)
    with caplog.at_level(logging.DEBUG, logger="flow.intake"):
        rig.post(event(actor="stranger"))
        rig.post(event(), delivery="d-2")
    assert FAKE_TOKEN not in caplog.text
