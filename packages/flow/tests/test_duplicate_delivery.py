"""P6-T22 break it: the same webhook delivered twice. No network, no model."""
import hashlib
import hmac

import pytest
from fastapi.testclient import TestClient

from flow.enqueue import FakeEnqueuer, HintDedup
from flow.webhook import DELIVERY_HEADER, EVENT_HEADER, SECRET_ENV, SIGNATURE_HEADER, create_app

SECRET = "test-secret-not-real"
BODY = b'{"action":"opened","issue":{"number":7},"repository":{"full_name":"acme/shop"}}'
TICKET = "acme/shop#7"


def deliver(client, delivery_id: str, body: bytes = BODY):
    sig = "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    return client.post(
        "/webhook", content=body,
        headers={SIGNATURE_HEADER: sig, EVENT_HEADER: "issues", DELIVERY_HEADER: delivery_id},
    )


@pytest.fixture(autouse=True)
def secret(monkeypatch):
    monkeypatch.setenv(SECRET_ENV, SECRET)


def test_second_delivery_with_same_id_is_a_noop():
    fake = FakeEnqueuer()
    client = TestClient(create_app(fake))
    first, second = deliver(client, "d-1"), deliver(client, "d-1")
    assert (first.status_code, first.json()["status"]) == (202, "accepted")
    assert (second.status_code, second.json()["status"]) == (202, "duplicate")
    assert fake.calls == [TICKET]  # enqueue called once
    assert fake.workflows == {TICKET}


def test_new_delivery_id_for_same_ticket_still_means_one_workflow():
    """Another event for the ticket is a real new hint: enqueued, but it lands on the same workflow id."""
    fake = FakeEnqueuer()
    client = TestClient(create_app(fake))
    deliver(client, "d-1")
    deliver(client, "d-2")
    assert fake.calls == [TICKET, TICKET]
    assert fake.workflows == {TICKET}


def test_dedup_is_only_a_hint_record_workflow_id_still_keeps_one_workflow():
    """With the dedup record switched off (size 0) or lost on restart, the repeat is enqueued again, yet one workflow exists."""
    fake = FakeEnqueuer()
    off = TestClient(create_app(fake, HintDedup(max_size=0)))
    deliver(off, "d-1")
    deliver(off, "d-1")
    restarted = TestClient(create_app(fake))  # fresh process, empty record
    deliver(restarted, "d-1")
    assert fake.calls == [TICKET] * 3
    assert fake.workflows == {TICKET}


def test_record_is_bounded_oldest_ids_are_evicted():
    fake = FakeEnqueuer()
    client = TestClient(create_app(fake, HintDedup(max_size=2)))
    for delivery_id in ("d-1", "d-2", "d-3"):
        deliver(client, delivery_id)
    assert deliver(client, "d-3").json()["status"] == "duplicate"  # still remembered
    assert deliver(client, "d-1").json()["status"] == "accepted"  # evicted, enqueued again
    assert fake.workflows == {TICKET}


def test_duplicate_of_a_bad_signature_is_never_recorded():
    fake = FakeEnqueuer()
    client = TestClient(create_app(fake))
    bad = client.post("/webhook", content=BODY, headers={SIGNATURE_HEADER: "sha256=00", DELIVERY_HEADER: "d-1"})
    assert bad.status_code == 401
    assert deliver(client, "d-1").json()["status"] == "accepted"  # the forged one did not use up the id
