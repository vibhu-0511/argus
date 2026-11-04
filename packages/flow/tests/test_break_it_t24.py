"""P8-T24 break it: the intake label added by a user without write access.

Everything goes through the real T08 code: a signed webhook delivery, `flow.webhook.create_app`, `flow.intake.Intake`,
the guard audit log. GitHub is a mock transport (no network, no model). The write-up is docs/notes/p8-break-it-t24.md.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging

import httpx
import pytest
from fastapi.testclient import TestClient
from guard.auditlog import AuditLog, verify

from flow.enqueue import FakeEnqueuer
from flow.intake import Intake
from flow.webhook import DELIVERY_HEADER, EVENT_HEADER, SECRET_ENV, SIGNATURE_HEADER, create_app

SECRET = "test-secret-not-real"
FAKE_TOKEN = "fake-installation-token-not-real"
ROLES = {"maya": "write", "mallory": "read", "triager": "triage", "stranger": None}


def github(request: httpx.Request) -> httpx.Response:
    """Only `maya` may write. Every request is kept in `github.calls` so a test can see which user was asked about."""
    github.calls.append((request.method, request.url.path))
    parts = request.url.path.split("/")
    role = ROLES.get(parts[-2]) if len(parts) > 2 and parts[-1] == "permission" else None
    if role is None:
        return httpx.Response(404, json={"message": "Not Found"})
    return httpx.Response(200, json={"permission": "write" if role == "write" else "read", "role_name": role})


github.calls = []


class Rig:
    def __init__(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setenv(SECRET_ENV, SECRET)
        github.calls = []
        self.audit_path = tmp_path / "audit.jsonl"
        self.enqueuer = FakeEnqueuer()
        intake = Intake(self.enqueuer, lambda repo: FAKE_TOKEN, label="argus", audit=AuditLog(self.audit_path).append, transport=httpx.MockTransport(github))
        self.client = TestClient(create_app(self.enqueuer, on_intake=intake.handle))
        self.n = 0

    def label(self, payload: dict) -> httpx.Response:
        self.n += 1
        body = json.dumps(payload).encode()
        headers = {EVENT_HEADER: "issues", DELIVERY_HEADER: f"d-{self.n}", SIGNATURE_HEADER: "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()}
        return self.client.post("/webhook", content=body, headers=headers)

    def audit(self) -> list[dict]:
        return [json.loads(x) for x in self.audit_path.read_text().splitlines()] if self.audit_path.exists() else []


def labeled(actor: str = "mallory", number: int = 7, **changes) -> dict:
    payload = {
        "action": "labeled",
        "label": {"name": "argus"},
        "sender": {"login": actor},
        "issue": {"number": number, "state": "open", "title": "Button is cut off"},
        "repository": {"full_name": "acme/shop"},
    }
    payload.update(changes)
    return payload


def ignores(caplog) -> list[dict]:
    return [json.loads(r.getMessage().removeprefix("intake_ignored ")) for r in caplog.records if r.getMessage().startswith("intake_ignored")]


@pytest.fixture
def rig(monkeypatch, tmp_path):
    return Rig(monkeypatch, tmp_path)


def test_a_read_only_user_adds_the_label_nothing_starts_and_the_ignore_is_logged(rig, caplog):
    with caplog.at_level(logging.INFO, logger="flow.intake"):
        assert rig.label(labeled("mallory")).status_code == 202  # the webhook still answers: GitHub must not retry
    assert rig.enqueuer.workflows == set() and rig.enqueuer.calls == []
    assert ignores(caplog) == [{"ticket": "acme/shop#7", "actor": "mallory", "label": "argus", "reason": "actor has read access, write is needed"}]
    assert [(x["kind"], x["payload"]["actor"]) for x in rig.audit()] == [("intake_ignored", "mallory")]  # the tamper-evident log has it too
    assert verify(rig.audit_path).bad_line is None
    assert github.calls == [("GET", "/repos/acme/shop/collaborators/mallory/permission")]  # a read, asked once
    assert FAKE_TOKEN not in caplog.text and FAKE_TOKEN not in rig.audit_path.read_text()


def test_the_ignore_does_not_block_a_real_start_and_every_ignore_is_logged(rig, caplog):
    with caplog.at_level(logging.INFO, logger="flow.intake"):
        for actor in ("mallory", "triager", "stranger", "mallory"):  # the same person twice is two log lines, not one
            rig.label(labeled(actor))
        assert rig.enqueuer.workflows == set()
        rig.label(labeled("maya"))  # a maintainer then adds it: this one starts, the earlier ignores did not poison the ticket
    assert rig.enqueuer.workflows == {"acme/shop#7"}
    assert [x["actor"] for x in ignores(caplog)] == ["mallory", "triager", "stranger", "mallory"]
    assert len(rig.audit()) == 4 and verify(rig.audit_path).bad_line is None


@pytest.mark.parametrize(
    "actor",
    ["mallory/../maya", "mallory/../../maya", "maya?x=1", "maya#x", "maya%2F..%2Fx", "maya/", "ma ya", "x" * 60, ""],
)
def test_a_login_that_rewrites_the_url_path_is_ignored_and_never_reaches_github(rig, caplog, actor):
    """Found by this break-it: `mallory/../maya` was normalised by the HTTP client to maya's page, so it started a workflow."""
    with caplog.at_level(logging.INFO, logger="flow.intake"):
        assert rig.label(labeled(actor)).status_code == 202
    assert rig.enqueuer.calls == [] and github.calls == []
    assert len(ignores(caplog)) == 1 and len(rig.audit()) == 1


@pytest.mark.parametrize("repo", ["../..", "acme/..", "acme/shop/../x", "acme/shop?x", "acme", "", "acme/ shop"])
def test_a_repo_name_that_rewrites_the_url_path_is_ignored(rig, caplog, repo):
    with caplog.at_level(logging.INFO, logger="flow.intake"):
        rig.label(labeled("maya", repository={"full_name": repo}))
    assert rig.enqueuer.calls == [] and github.calls == [] and len(ignores(caplog)) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"sender": None},
        {"sender": "maya"},
        {"issue": None},
        {"issue": {"number": "7"}},
        {"issue": {"number": True}},
        {"repository": []},
    ],
    ids=["no-sender", "sender-is-a-string", "no-issue", "number-is-a-string", "number-is-a-bool", "repository-is-a-list"],
)
def test_the_intake_label_on_a_broken_event_is_ignored_and_logged_and_never_raises(rig, caplog, changes):
    with caplog.at_level(logging.INFO, logger="flow.intake"):
        assert rig.label(labeled("maya", **changes)).status_code == 202
    assert rig.enqueuer.calls == [] and github.calls == []
    assert len(ignores(caplog)) == 1 and verify(rig.audit_path).bad_line is None


def test_the_label_on_a_pull_request_is_ignored_and_logged(rig, caplog):
    payload = labeled("maya")
    payload["issue"]["pull_request"] = {"url": "https://api.github.com/x"}
    with caplog.at_level(logging.INFO, logger="flow.intake"):
        rig.label(payload)
    assert rig.enqueuer.calls == [] and github.calls == []
    assert ignores(caplog)[0]["reason"] == "the label is on a pull request, not an issue"


def test_a_forged_delivery_without_the_signature_is_rejected_before_intake(rig, caplog):
    """The sender of an unsigned body is not believed: 401, no permission call, nothing logged as an intake ignore."""
    body = json.dumps(labeled("maya")).encode()
    with caplog.at_level(logging.INFO, logger="flow.intake"):
        r = rig.client.post("/webhook", content=body, headers={EVENT_HEADER: "issues", SIGNATURE_HEADER: "sha256=" + "0" * 64})
    assert r.status_code == 401 and rig.enqueuer.calls == [] and github.calls == [] and ignores(caplog) == []


def test_the_log_line_of_a_hostile_login_stays_one_json_line(rig, caplog):
    with caplog.at_level(logging.INFO, logger="flow.intake"):
        rig.label(labeled("evil\nintake_started {}\r\n" + "x" * 500))
    assert len(ignores(caplog)) == 1
    message = caplog.records[-1].getMessage()
    assert "\n" not in message and len(message) < 400  # json escapes the newline, and the login is cut at 100 characters
