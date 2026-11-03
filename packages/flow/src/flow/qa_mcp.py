"""QA approval as an MCP tool that asks the reviewer through MRTR elicitation (P6-T09).

Spec 2026-07-28 (docs/notes/p6-t01-dbos-mrtr.md): a `tools/call` that needs an answer returns
`resultType: "input_required"` with `inputRequests`; the client asks its user and retries the same
call with `inputResponses` (and the echoed `requestState`). This module is the server half for one
tool, `qa_decision(ticket_id)`:

1. round one: the tool has no answer, so the SDK returns `input_required` with one elicitation
   asking approve or reject (plus an optional comment);
2. round two: the retry carries the answer, the tool sends the QA signal (`flow.qa.send_qa_signal`,
   source `mrtr`) and returns. The waiting workflow resumes from the same `DBOS.recv` the review
   comment path (T10) uses.

The wire work is the `mcp` 2.3.0 SDK's, not ours: the `Resolve(...)` / `Elicit` resolver in
`mcp.server.mcpserver.resolve` builds the `InputRequiredResult`, and `RequestStateBoundary` seals
the `requestState` (AES-GCM, 10 min, bound to the request). Found in practice (docs/notes/p6-t09.md):
that holds for a client at 2026-07-28; the SDK answers a client at an older version with a
standalone `elicitation/create` request inside the call instead.

The MRTR answer is not durable by itself and `requestState` is not a decision record. What makes it
once is the signal key: `qa_signal_key(ticket, "mrtr", <JSON-RPC request id>)`. A second
answer under another request id is a different key; the workflow has left `awaiting-qa` by then
and drops it (flow.states EFFECTS `record-qa-signal`).

ponytail: the tool asks first and only then finds out whether the ticket has a workflow; an unknown
ticket costs the reviewer one wasted answer. Look the workflow up before asking if that shows up.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Annotated, Any, Literal

import anyio.to_thread
from dbos._error import DBOSNonExistentWorkflowError
from mcp.server.elicitation import AcceptedElicitation, ElicitationResult
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.mcpserver.resolve import Elicit, Resolve
from pydantic import BaseModel, Field

from flow.qa import send_qa_signal

log = logging.getLogger("flow.qa_mcp")

SERVER_NAME = "argus-flow-qa"
TOOL_NAME = "qa_decision"


class QaDecision(BaseModel):
    decision: Literal["approve", "reject"] = Field(description="approve marks the PR ready for review, reject closes it")
    comment: str = Field(default="", description="optional reason")


def ask(ticket_id: str) -> Elicit[QaDecision]:
    """The question. It must render the same on every round, so it depends on the ticket id only."""
    return Elicit(f"Approve the Argus fix for {ticket_id}? Choose approve or reject.", QaDecision)


def qa_server(send: Callable[..., str] = send_qa_signal) -> MCPServer:
    """The MCP server with the one tool. `send` is `send_qa_signal`; tests pass a recorder."""
    mcp = MCPServer(SERVER_NAME)

    @mcp.tool(name=TOOL_NAME)
    async def qa_decision(
        ticket_id: str, answer: Annotated[ElicitationResult[QaDecision], Resolve(ask)], ctx: Context
    ) -> dict[str, Any]:
        """Ask the reviewer to approve or reject the Argus fix for a ticket and signal its workflow."""
        log.info("qa_decision ticket=%s spec_version=%s", ticket_id, ctx.protocol_version)
        if not isinstance(answer, AcceptedElicitation):
            return {"status": "no-decision", "action": answer.action, "ticket": ticket_id}
        try:
            key = await anyio.to_thread.run_sync(
                lambda: send(ticket_id, answer.data.decision, "mrtr", str(ctx.request_id), by="mcp-client")
            )
        except DBOSNonExistentWorkflowError:
            raise ToolError(f"no workflow for ticket {ticket_id!r}") from None
        except ValueError as e:  # empty ticket id and similar
            raise ToolError(str(e)) from None
        return {"status": "signal-sent", "decision": answer.data.decision, "ticket": ticket_id, "key": key}

    return mcp
