"""P6-T23 break it, local stand-in: a webhook for a new ticket is lost while the service is "asleep".

The real scenario needs a Render service (T12, T13, owner-only). Here the sleeping service is an
`Asleep` enqueuer that refuses every hand-over to the workflow engine, so the signed webhook reaches
the app, its background enqueue fails, and no workflow starts: the hint is lost. Then:

1. the poller (`Reconciler.poll_once`, reading recorded GitHub JSON) finds the new ticket and starts one workflow;
2. a late redelivery of the same webhook (same delivery id) changes nothing: still one workflow.

`scenario()` is shared by `test_render_sleep_break_it.py` (fake enqueuer, and the real DBOS workflow when
`ARGUS_FLOW_DATABASE_URL` is set). Run the story with the fake and print it:

    uv run --all-packages python packages/flow/tests/render_sleep_demo.py

No network, no model, no secret (the webhook secret below is a test value).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from typing import Callable

import httpx
from fastapi.testclient import TestClient

from flow.enqueue import Enqueuer, FakeEnqueuer
from flow.github_read import HttpGitHubReader
from flow.reconcile import PollConfig, PollResult, Reconciler, WorkflowLookup, WorkflowView
from flow.webhook import DELIVERY_HEADER, EVENT_HEADER, SECRET_ENV, SIGNATURE_HEADER, create_app
from reconcile_support import FIXTURE_TICKET, load, transport

SECRET = "test-secret-not-real"
DELIVERY = "render-sleep-delivery-1"


class Asleep:
    """An Enqueuer that refuses while `asleep`, like a service whose database or engine is not up."""

    def __init__(self, inner: Enqueuer) -> None:
        self.inner, self.asleep, self.refused = inner, True, 0

    def enqueue_reconcile(self, ticket_id: str) -> None:
        if self.asleep:
            self.refused += 1
            raise ConnectionError("service asleep")
        self.inner.enqueue_reconcile(ticket_id)


class FakeLookup:
    """A workflow exists once the fake enqueuer has been asked for it, like the DBOS id would."""

    def __init__(self, enq: FakeEnqueuer) -> None:
        self.enq = enq

    def get(self, ticket_id: str) -> WorkflowView | None:
        return WorkflowView("PENDING", None) if ticket_id in self.enq.workflows else None


@dataclass
class Story:
    lost_status: int  # the webhook's HTTP status while asleep
    refused: int  # hand-overs the sleeping enqueuer refused
    workflows_after_loss: int
    poll: PollResult
    workflows_after_poll: int
    redelivery_status: str  # the body's "status" for the late redelivery
    workflows_after_redelivery: int
    poll_again: PollResult
    workflows_at_end: int


def signed_post(client: TestClient, ticket: str, delivery_id: str) -> httpx.Response:
    repo, number = ticket.split("#")
    body = json.dumps({"action": "opened", "issue": {"number": int(number)}, "repository": {"full_name": repo}}).encode()
    sig = "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    return client.post("/webhook", content=body, headers={SIGNATURE_HEADER: sig, EVENT_HEADER: "issues", DELIVERY_HEADER: delivery_id})


def github_reader(ticket: str) -> HttpGitHubReader:
    """Recorded JSON for a brand-new ticket, plus the open-issue listing the poller starts from."""
    fx = load("new_ticket", ticket)
    repo, number = ticket.split("#")
    inner = transport(fx)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == f"/repos/{repo}/issues":
            return httpx.Response(200, json=[{"number": int(number), "title": fx["issue"]["title"]}])
        return inner.handle_request(request)

    return HttpGitHubReader("test-token", transport=httpx.MockTransport(handler))


def scenario(
    ticket: str,
    inner: Enqueuer,
    lookup: WorkflowLookup,
    count: Callable[[str], int],
) -> Story:
    """Lose the webhook, poll, redeliver. `count(ticket)` is the number of workflows with that id.
    The caller sets `GITHUB_WEBHOOK_SECRET` to `SECRET` first."""
    asleep = Asleep(inner)
    client = TestClient(create_app(asleep))
    lost = signed_post(client, ticket, DELIVERY)  # the background enqueue runs before post() returns
    refused, after_loss = asleep.refused, count(ticket)

    poller = Reconciler(github_reader(ticket), lookup, inner, PollConfig(repo=ticket.split("#")[0]))  # the awake side
    poll = poller.poll_once()
    after_poll = count(ticket)

    asleep.asleep = False  # the service is back; GitHub's redelivery of the same delivery id
    late = signed_post(client, ticket, DELIVERY)
    after_late = count(ticket)
    again = poller.poll_once()
    return Story(lost.status_code, refused, after_loss, poll, after_poll, late.json()["status"], after_late, again, count(ticket))


def main() -> None:
    os.environ[SECRET_ENV] = SECRET
    fake = FakeEnqueuer()
    s = scenario(FIXTURE_TICKET, fake, FakeLookup(fake), lambda t: int(t in fake.workflows))
    print(f"ticket {FIXTURE_TICKET} (recorded GitHub JSON: issue open, no run, no branch, no PR)")
    print(f"1. webhook while asleep: HTTP {s.lost_status}, enqueue refused {s.refused}x, workflows started: {s.workflows_after_loss}")
    r = s.poll.reconciled[0]
    print(f"2. poll_once: derived '{r.state.value}', action '{r.action}', errors {s.poll.errors}, workflows: {s.workflows_after_poll}")
    print(f"3. late redelivery of the same delivery id: status '{s.redelivery_status}', workflows: {s.workflows_after_redelivery}")
    print(f"4. poll_once again: action '{s.poll_again.reconciled[0].action}', workflows: {s.workflows_at_end}; enqueue calls on the engine: {fake.calls}")


if __name__ == "__main__":
    main()
