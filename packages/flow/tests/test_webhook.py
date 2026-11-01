"""P6-T05, P6-T06: HMAC check, then the event is a hint that is enqueued and answered with 202."""
import asyncio
import hashlib
import hmac
import json
import socket
import time

import pytest
from fastapi.testclient import TestClient

from flow.enqueue import FakeEnqueuer
from flow.webhook import DELIVERY_HEADER, EVENT_HEADER, SECRET_ENV, SIGNATURE_HEADER, create_app

SECRET = "test-secret-not-real"
BODY = b'{"action":"opened","issue":{"number":7},"repository":{"full_name":"acme/shop"}}'


def sign(body: bytes, secret: str = SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv(SECRET_ENV, SECRET)
    return TestClient(create_app(FakeEnqueuer()))


def post(client, body=BODY, signature=None, **headers):
    headers = {**headers, **({} if signature is None else {SIGNATURE_HEADER: signature})}
    return client.post("/webhook", content=body, headers=headers)


def test_valid_signature_is_accepted(client):
    assert post(client, signature=sign(BODY)).status_code == 202


def test_invalid_signature_is_401(client):
    assert post(client, signature=sign(BODY, "wrong-secret")).status_code == 401


def test_missing_header_is_401(client):
    assert post(client).status_code == 401


def test_tampered_body_is_401(client):
    assert post(client, body=BODY + b" ", signature=sign(BODY)).status_code == 401


def test_header_without_sha256_prefix_is_401(client):
    assert post(client, signature=sign(BODY).removeprefix("sha256=")).status_code == 401


def test_no_secret_configured_fails_closed(monkeypatch):
    monkeypatch.delenv(SECRET_ENV, raising=False)
    # the signature an empty secret would give must not get through
    assert post(TestClient(create_app(FakeEnqueuer())), signature=sign(BODY, "")).status_code == 401


def test_empty_secret_fails_closed(monkeypatch):
    monkeypatch.setenv(SECRET_ENV, "")
    assert post(TestClient(create_app(FakeEnqueuer())), signature=sign(BODY, "")).status_code == 401


def signed_post(client, body=BODY, **headers):
    return post(client, body, sign(body), **headers)


def test_event_and_delivery_give_ticket_and_one_enqueue(monkeypatch):
    monkeypatch.setenv(SECRET_ENV, SECRET)
    fake = FakeEnqueuer()
    client = TestClient(create_app(fake))
    r = signed_post(client, **{EVENT_HEADER: "issues", DELIVERY_HEADER: "d-1"})
    assert r.status_code == 202
    assert r.json() == {"status": "accepted", "event": "issues", "ticket": "acme/shop#7"}
    assert fake.calls == ["acme/shop#7"]


def test_pull_request_and_comment_events_name_a_ticket(monkeypatch):
    monkeypatch.setenv(SECRET_ENV, SECRET)
    fake = FakeEnqueuer()
    client = TestClient(create_app(fake))
    for payload in ({"pull_request": {"number": 9}}, {"issue": {"number": 3}}):
        body = json.dumps({**payload, "repository": {"full_name": "acme/shop"}}).encode()
        assert signed_post(client, body).status_code == 202
    assert fake.calls == ["acme/shop#9", "acme/shop#3"]


def test_event_without_a_ticket_is_acknowledged_not_enqueued(monkeypatch):
    monkeypatch.setenv(SECRET_ENV, SECRET)
    fake = FakeEnqueuer()
    body = b'{"zen":"ping"}'
    r = signed_post(TestClient(create_app(fake)), body, **{EVENT_HEADER: "ping"})
    assert (r.status_code, r.json()["status"]) == (202, "ignored")
    assert fake.calls == []


def test_signed_body_that_is_not_json_is_400(monkeypatch):
    monkeypatch.setenv(SECRET_ENV, SECRET)
    assert signed_post(TestClient(create_app(FakeEnqueuer())), b"not json").status_code == 400


def test_handler_reads_nothing_from_github(monkeypatch):
    monkeypatch.setenv(SECRET_ENV, SECRET)

    def no_network(*a, **k):
        raise AssertionError("handler tried to reach a host")

    # name lookup and outbound connects; the test client's own loopback socketpair is not affected
    monkeypatch.setattr(socket, "getaddrinfo", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    assert signed_post(TestClient(create_app(FakeEnqueuer()))).status_code == 202


def test_failed_enqueue_still_202_and_redelivery_is_not_dropped(monkeypatch):
    monkeypatch.setenv(SECRET_ENV, SECRET)

    class Broken:
        def enqueue_reconcile(self, ticket_id):
            raise RuntimeError("db down")

    client = TestClient(create_app(Broken()))
    assert signed_post(client, **{DELIVERY_HEADER: "d-1"}).status_code == 202
    assert signed_post(client, **{DELIVERY_HEADER: "d-1"}).json()["status"] == "accepted"


def drive_asgi(app, body: bytes, headers: dict[str, str]):
    """Call the app as an ASGI server would; return (seconds until the response was fully sent, seconds until the app returned)."""
    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "POST",
        "path": "/webhook", "raw_path": b"/webhook", "query_string": b"", "root_path": "", "scheme": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": ("127.0.0.1", 1), "server": ("testserver", 80),
    }
    marks: dict[str, float] = {}

    async def run():
        sent = False

        async def receive():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            await asyncio.sleep(3600)

        async def send(message):
            if message["type"] == "http.response.start":
                marks["status"] = message["status"]
            if message["type"] == "http.response.body" and not message.get("more_body"):
                marks["response_sent"] = time.perf_counter() - start

        start = time.perf_counter()
        await asyncio.wait_for(app(scope, receive, send), timeout=30)
        marks["app_done"] = time.perf_counter() - start

    asyncio.run(run())
    return marks


def test_handler_time_does_not_include_a_slow_enqueue(monkeypatch):
    monkeypatch.setenv(SECRET_ENV, SECRET)
    slow = 2.0
    fake = FakeEnqueuer(delay_s=slow)
    headers = {SIGNATURE_HEADER: sign(BODY), DELIVERY_HEADER: "d-slow", EVENT_HEADER: "issues"}
    marks = drive_asgi(create_app(fake), BODY, headers)
    print(f"handler time: response sent after {marks['response_sent'] * 1000:.1f} ms; "
          f"app (with background enqueue of {slow} s) returned after {marks['app_done']:.2f} s")
    assert marks["status"] == 202
    assert marks["response_sent"] < 1.0, "far under GitHub's 10 s timeout"
    assert marks["app_done"] >= slow  # the slow enqueue did run, after the response
    assert fake.calls == ["acme/shop#7"]
