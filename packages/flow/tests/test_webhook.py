"""P6-T05: the webhook accepts a valid HMAC signature and rejects everything else."""
import hashlib
import hmac

import pytest
from fastapi.testclient import TestClient

from flow.webhook import SECRET_ENV, SIGNATURE_HEADER, create_app

SECRET = "test-secret-not-real"
BODY = b'{"action":"opened","issue":{"number":7}}'


def sign(body: bytes, secret: str = SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv(SECRET_ENV, SECRET)
    return TestClient(create_app())


def post(client, body=BODY, signature=None):
    headers = {} if signature is None else {SIGNATURE_HEADER: signature}
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
    assert post(TestClient(create_app()), signature=sign(BODY, "")).status_code == 401


def test_empty_secret_fails_closed(monkeypatch):
    monkeypatch.setenv(SECRET_ENV, "")
    assert post(TestClient(create_app()), signature=sign(BODY, "")).status_code == 401
