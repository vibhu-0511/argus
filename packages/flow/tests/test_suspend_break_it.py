"""P6-T24 break it: the database suspends while a workflow is running.

The workflow runs against a local Postgres with fake runners and a fake GitHub; the "suspend" is
`suspend_support` (all sessions ended, or the container stopped and started). The fakes count every
call, so "no duplicated side effect" is an assertion on those counts, not a claim. Write-up:
docs/notes/p6-t24-break-it.md; it also says what a local stand-in cannot show about Neon.
Needs `ARGUS_FLOW_DATABASE_URL`; the stop/start tests also need `ARGUS_FLOW_TEST_CONTAINER`.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid

import pytest
from dbos import DBOS
from fastapi.testclient import TestClient

from flow import db_wake
from flow.config import DATABASE_URL_ENV, FlowSettings
from flow.dbos_runtime import launch, shutdown
from flow.fakes import FakeRunner
from flow.qa import send_qa_signal
from flow.states import branch_name
from flow.webhook import DELIVERY_HEADER, EVENT_HEADER, SECRET_ENV, SIGNATURE_HEADER, create_app
from flow.workflow import Deps, Outcome, set_deps
from suspend_support import World, container, dbos_log_messages, needs_container, terminate_connections

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(not os.environ.get(DATABASE_URL_ENV), reason=f"{DATABASE_URL_ENV} is not set; needs a real Postgres"),
]

STEP_NAMES = ["repro_step", "fix_step", "verify_step", "open_pr_step", "finish_step"]


class SuspendingRunner(FakeRunner):
    """Does its work, then the database goes away before DBOS can store the step's result."""

    def __init__(self, outcome: Outcome, suspend) -> None:
        super().__init__(outcome)
        self.suspend, self.suspended = suspend, 0

    def run(self, ticket_id: str, run_key: str, upstream: str) -> Outcome:
        outcome = super().run(ticket_id, run_key, upstream)  # the side effect is made
        if not self.suspended:
            self.suspended += 1
            self.suspend()
        return outcome


@pytest.fixture(scope="module")
def enqueuer():
    enq = launch(FlowSettings.from_env(), Deps(None, None, None, None))
    yield enq
    shutdown()


@pytest.fixture
def ticket():
    return f"acme/{uuid.uuid4().hex[:8]}#24"


def assert_finished_once(world: World, ticket: str, out: dict) -> None:
    assert out["state"] == "done" and out["trail"][-2:] == ["awaiting-qa", "done"]
    world.assert_each_effect_happened_once(ticket)
    assert [s["function_name"] for s in DBOS.list_workflow_steps(ticket) if s["function_name"] in STEP_NAMES] == STEP_NAMES
    assert len(DBOS.list_workflows(workflow_ids=[ticket])) == 1


def test_every_session_killed_during_a_step_the_workflow_still_finishes_once(enqueuer, ticket):
    url = os.environ[DATABASE_URL_ENV]
    killed: list[int] = []
    world = World(fix=SuspendingRunner(Outcome(True, "the patch"), lambda: killed.append(terminate_connections(url))))
    set_deps(world.deps)
    handle = enqueuer.enqueue(ticket)
    send_qa_signal(ticket, "approve", "review-comment", "1")
    out = handle.get_result()
    print(f"\nkilled {killed} sessions during fix_step; run finished: {out['state']}")
    assert killed and killed[0] >= 1
    assert_finished_once(world, ticket, out)


@needs_container
def test_server_stopped_during_a_step_the_workflow_waits_reconnects_and_finishes_once(enqueuer, ticket):
    server = container()

    def suspend() -> None:
        server.stop()
        world.restart = server.start_later(3)

    world = World(fix=SuspendingRunner(Outcome(True, "the patch"), suspend))
    set_deps(world.deps)
    try:
        started = time.monotonic()
        with dbos_log_messages() as log:
            handle = enqueuer.enqueue(ticket)
            send_qa_signal(ticket, "approve", "review-comment", "1")
            out = handle.get_result()
        took = time.monotonic() - started
    finally:
        server.start()  # a no-op when it is already running
    retries = [m for m in log if "Database connection failed" in m and "Retrying" in m]
    print(f"\nserver down for about {server.down_seconds:.0f} s inside fix_step; DBOS logged {len(retries)} retry warnings; run took {took:.1f} s")
    assert retries, "DBOS never noticed the outage; the test did not suspend anything"
    assert os.environ[DATABASE_URL_ENV].split(":")[2].split("@")[0] not in " ".join(log)  # the password
    assert_finished_once(world, ticket, out)


@needs_container
def test_a_webhook_during_the_outage_is_lost_then_its_redelivery_runs_the_ticket(enqueuer, ticket, monkeypatch):
    """The hint arrives while the database is down: enqueue gives up (bounded), the delivery id is forgotten,
    GitHub's redelivery of the same id is accepted and starts the workflow once."""
    secret, delivery = "test-secret-not-real", "delivery-24"
    monkeypatch.setenv(SECRET_ENV, secret)
    monkeypatch.setattr(db_wake, "ATTEMPTS", 2)
    repo, number = ticket.split("#")
    body = json.dumps({"action": "opened", "issue": {"number": int(number)}, "repository": {"full_name": repo}}).encode()
    headers = {
        SIGNATURE_HEADER: "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest(),
        EVENT_HEADER: "issues",
        DELIVERY_HEADER: delivery,
    }
    world = World()
    set_deps(world.deps)
    client, server = TestClient(create_app(enqueuer)), container()
    server.stop()
    try:
        first = client.post("/webhook", content=body, headers=headers)  # returns after its background enqueue gave up
    finally:
        server.start()
    assert first.status_code == 202 and first.json()["status"] == "accepted"
    monkeypatch.setattr(db_wake, "ATTEMPTS", 6)  # the normal bound again, the server needs a moment after `docker start`
    assert world.repro.calls == [] and world.github.prs == {}  # nothing ran
    again = client.post("/webhook", content=body, headers=headers)  # the redelivery, same delivery id
    assert again.json()["status"] == "accepted"  # the id was forgotten when the enqueue failed, so not "duplicate"
    send_qa_signal(ticket, "approve", "review-comment", "1")
    out = DBOS.retrieve_workflow(ticket).get_result()
    assert_finished_once(world, ticket, out)
    assert world.github.prs[branch_name(ticket)].draft is False
