"""The seam between the webhook and the durable workflow (P6-T06).

A webhook is only a hint that a ticket may have changed. The handler turns it
into `enqueue_reconcile(ticket_id)` and answers 202; it reads nothing from
GitHub. The reconciliation poller (P6-T07) makes the same call for the same
ticket, so the two paths meet on one workflow.

Contract for the real implementation (P6-T03, DBOS): start the reconcile
workflow under `SetWorkflowID(ticket_id)`. The ticket id is the ONLY workflow
key, so a hint from the webhook and one from the poller (or two webhooks for
one ticket) give one workflow, because DBOS does not start a second workflow
with an id it already has. The delivery id is never a workflow key: it only
feeds `HintDedup`, which drops a repeat of the same delivery early. Dropping
is an optimisation, not a safety property; the workflow id is what keeps the
run single.

Until DBOS lands, `FakeEnqueuer` stands in and models the same rule.
"""
import threading
import time
from collections import OrderedDict
from typing import Protocol


class Enqueuer(Protocol):
    def enqueue_reconcile(self, ticket_id: str) -> None:
        """Ask for a reconcile of `ticket_id`. Must be safe to call many times."""


class FakeEnqueuer:
    """In-memory stand-in: records every call, keeps one 'workflow' per ticket id."""

    def __init__(self, delay_s: float = 0.0) -> None:
        self.delay_s = delay_s
        self.calls: list[str] = []
        self.workflows: set[str] = set()

    def enqueue_reconcile(self, ticket_id: str) -> None:
        if self.delay_s:
            time.sleep(self.delay_s)
        self.calls.append(ticket_id)
        self.workflows.add(ticket_id)  # same workflow id -> no second workflow


class HintDedup:
    """Bounded record of delivery ids already seen. A hint-dedup record, nothing more.

    ponytail: in-memory and per process, so it is lost on restart and not shared
    between instances; a repeat after that is enqueued again and the workflow id
    absorbs it. Move to a Postgres table only if repeat hints become costly.
    """

    def __init__(self, max_size: int = 1024) -> None:
        self.max_size = max_size
        self._seen: OrderedDict[str, None] = OrderedDict()
        self._lock = threading.Lock()

    def first_time(self, delivery_id: str) -> bool:
        """Record the id; True if it was not there before."""
        with self._lock:
            if delivery_id in self._seen:
                return False
            self._seen[delivery_id] = None
            if len(self._seen) > self.max_size:
                self._seen.popitem(last=False)
            return True

    def forget(self, delivery_id: str) -> None:
        """Drop the id, so a redelivery after a failed enqueue is not discarded."""
        with self._lock:
            self._seen.pop(delivery_id, None)
