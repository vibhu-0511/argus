"""Launch DBOS and the real `Enqueuer` (P6-T03).

`DbosEnqueuer` is the implementation behind `flow.enqueue.Enqueuer`: the webhook (T06) and the
reconciliation poller (T07) both call `enqueue_reconcile(ticket_id)`, which starts the ticket
workflow on a database-backed queue under `SetWorkflowID(workflow_id(ticket_id))`.

Verified against dbos 3.4.0 (docs/notes/p6-t03.md): `SetWorkflowID` does apply to `Queue.enqueue`.
A second enqueue with the same id returns the first run's handle and starts nothing, also after
that run has finished (default reuse policy "return-existing"). So a ticket that reached `done`
is not run again by a later hint; a deliberate re-run needs a new attempt, which T02 reserves.

Neon (P6-T11): `launch` and `enqueue` first wake the database with `flow.db_wake.wait_for_database`
(bounded, logged without the URL). Everything after that, step results included, is DBOS's own
`db_retry`, which reconnects without a deadline.
"""

from __future__ import annotations

from dbos import DBOS, SetWorkflowID, WorkflowHandle

from flow.config import FlowSettings, dbos_config
from flow.db_wake import wait_for_database
from flow.states import workflow_id
from flow.workflow import Deps, set_deps, ticket_workflow

QUEUE_NAME = "argus-flow"


class DbosEnqueuer:
    def __init__(self, queue, database_url: str | None = None) -> None:
        self._queue = queue
        self._database_url = database_url  # set: probe (and wake) the database before each enqueue

    def enqueue(self, ticket_id: str) -> WorkflowHandle:
        if self._database_url:
            wait_for_database(self._database_url)  # raises DatabaseUnavailable instead of blocking in DBOS
        with SetWorkflowID(workflow_id(ticket_id)):
            return self._queue.enqueue(ticket_workflow, ticket_id)

    def enqueue_reconcile(self, ticket_id: str) -> None:
        self.enqueue(ticket_id)


def launch(settings: FlowSettings, deps: Deps) -> DbosEnqueuer:
    """Set the deps, start DBOS (which recovers this application version's pending workflows) and the queue."""
    if deps.qa_timeout_seconds is None:
        deps = deps._replace(qa_timeout_seconds=settings.qa_timeout_seconds)
    set_deps(deps)  # before launch: recovery can run workflows at once
    wait_for_database(settings.database_url)  # a suspended Neon compute wakes on this connection
    DBOS(config=dbos_config(settings))
    DBOS.launch()
    return DbosEnqueuer(DBOS.register_queue(QUEUE_NAME), settings.database_url)


def shutdown() -> None:
    DBOS.destroy()
