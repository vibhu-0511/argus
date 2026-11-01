"""The QA signal: one message to the ticket's workflow, deduplicated by its idempotency key (P6-T08).

Every QA path ends here: a GitHub review comment (T10), an MCP elicitation answer (T09), a test.
`send_qa_signal` puts a message on topic `QA_TOPIC` of the workflow whose id is the ticket id. The
workflow waits for it with `DBOS.recv` in `awaiting-qa` (`flow.workflow`).

The key is `flow.states.qa_signal_key(ticket, source, source_id)`. It is passed to `DBOS.send` as
`idempotency_key`; DBOS stores the message under that key and drops a second insert of the same key
(verified on dbos 3.4.0: one row in `dbos.notifications`). So a redelivered review comment or a
retried MRTR call changes nothing. A signal with a different key that arrives after the first has
been consumed is stored but never read: the workflow left `awaiting-qa`, so it is dropped.

ponytail: `send_qa_signal` cannot tell the caller "this was a duplicate"; DBOS does not report it.
Callers answer the same either way. Add a lookup in `dbos.notifications` only if a caller needs it.
"""

from __future__ import annotations

from typing import Any

from dbos import DBOS

from flow.states import qa_signal_key, workflow_id

QA_TOPIC = "qa"
DECISIONS = ("approve", "reject")


def qa_message(ticket_id: str, decision: str, source: str, source_id: str, by: str = "") -> dict[str, Any]:
    if decision not in DECISIONS:
        raise ValueError(f"decision must be one of {DECISIONS}, got {decision!r}")
    return {
        "decision": decision,
        "key": qa_signal_key(ticket_id, source, source_id),  # raises on an unknown source or empty id
        "source": source,
        "by": by,
    }


def send_qa_signal(ticket_id: str, decision: str, source: str, source_id: str, by: str = "") -> str:
    """Send the signal to the ticket's workflow and return its idempotency key.

    Raises ValueError for a bad decision, source or id, and DBOSNonExistentWorkflowError when the
    ticket has no workflow. Call it from outside a workflow (webhook handler, MCP tool).
    """
    msg = qa_message(ticket_id, decision, source, source_id, by)
    DBOS.send(workflow_id(ticket_id), msg, topic=QA_TOPIC, idempotency_key=msg["key"])
    return msg["key"]
