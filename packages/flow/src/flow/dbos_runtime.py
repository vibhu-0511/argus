"""Launch DBOS and the real `Enqueuer` (P6-T03).

`DbosEnqueuer` is the implementation behind `flow.enqueue.Enqueuer`: the webhook (T06) and the
reconciliation poller (T07) both call `enqueue_reconcile(ticket_id)`, which starts the ticket
workflow on a database-backed queue under `SetWorkflowID(workflow_id(ticket_id))`.

Verified against dbos 3.4.0 (docs/notes/p6-t03.md): `SetWorkflowID` does apply to `Queue.enqueue`.
A second enqueue with the same id returns the first run's handle and starts nothing, also after
that run has finished (default reuse policy "return-existing"). So a ticket that reached `done`
is not run again by a later hint; a deliberate re-run needs a new attempt, which T02 reserves.
"""

from __future__ import annotations

from dbos import DBOS, SetWorkflowID, WorkflowHandle

from flow.config import FlowSettings, dbos_config
from flow.states import workflow_id
from flow.workflow import Deps, set_deps, ticket_workflow

QUEUE_NAME = "argus-flow"


class DbosEnqueuer:
    def __init__(self, queue) -> None:
        self._queue = queue

    def enqueue(self, ticket_id: str) -> WorkflowHandle:
        with SetWorkflowID(workflow_id(ticket_id)):
            return self._queue.enqueue(ticket_workflow, ticket_id)

    def enqueue_reconcile(self, ticket_id: str) -> None:
        self.enqueue(ticket_id)


def launch(settings: FlowSettings, deps: Deps) -> DbosEnqueuer:
    """Set the deps, start DBOS (which recovers this application version's pending workflows) and the queue."""
    if deps.qa_timeout_seconds is None:
        deps = deps._replace(qa_timeout_seconds=settings.qa_timeout_seconds)
    set_deps(deps)  # before launch: recovery can run workflows at once
    DBOS(config=dbos_config(settings))
    DBOS.launch()
    return DbosEnqueuer(DBOS.register_queue(QUEUE_NAME))


def shutdown() -> None:
    DBOS.destroy()
