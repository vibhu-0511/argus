"""P6-T09: MRTR elicitation for the QA approval step, over the `mcp` SDK's in-memory transport.

No Postgres (the signal sender is a recorder; test_workflow.py has the end-to-end one), no LLM, no
network. The client is the SDK's own `Client`, not a real MCP host: nothing here shows what Claude
Desktop, Cursor or any other product does with `input_required`.
"""

from __future__ import annotations

import asyncio
import json
import logging

import pytest
from mcp import Client
from mcp.shared.exceptions import MCPError
from mcp_types import ElicitResult, InputRequiredResult

from flow.qa_mcp import SERVER_NAME, TOOL_NAME, qa_server

TICKET = "acme/shop#7"
ARGS = {"ticket_id": TICKET}


class Sent:
    """Stands in for `send_qa_signal` and remembers each call."""

    def __init__(self) -> None:
        self.calls: list[tuple[tuple, dict]] = []

    def __call__(self, *args, **kwargs) -> str:
        self.calls.append((args, kwargs))
        return "key-from-recorder"


def accept(decision: str, comment: str = "") -> ElicitResult:
    return ElicitResult(action="accept", content={"decision": decision, "comment": comment})


def run(coro):
    return asyncio.run(coro)


async def never_called(context, params):
    """The manual-loop tests answer by hand; declaring the callback only declares the capability."""
    raise AssertionError("the SDK loop must not run in a manual-loop test")


def test_round_one_returns_input_required_and_sends_nothing():
    sent = Sent()

    async def go():
        async with Client(qa_server(sent), mode="2026-07-28", elicitation_callback=never_called) as client:
            assert client.protocol_version == "2026-07-28"
            return await client.session.call_tool(TOOL_NAME, ARGS, allow_input_required=True)

    first = run(go())
    assert isinstance(first, InputRequiredResult) and first.result_type == "input_required"
    wire = json.loads(first.model_dump_json(by_alias=True, exclude_none=True))
    assert wire["resultType"] == "input_required"
    (key, request), = wire["inputRequests"].items()
    assert request["method"] == "elicitation/create"
    assert request["params"]["message"] == f"Approve the Argus fix for {TICKET}? Choose approve or reject."
    assert request["params"]["requestedSchema"]["properties"]["decision"]["enum"] == ["approve", "reject"]
    assert wire["requestState"]  # sealed and opaque; the client only echoes it
    assert sent.calls == []  # asking is not deciding


def test_the_retry_with_input_responses_sends_the_signal_and_logs_the_spec_version(caplog):
    sent = Sent()
    caplog.set_level(logging.INFO, logger="flow.qa_mcp")

    async def go():
        async with Client(qa_server(sent), mode="2026-07-28", elicitation_callback=never_called) as client:
            first = await client.session.call_tool(TOOL_NAME, ARGS, allow_input_required=True)
            (key,) = first.input_requests
            return await client.session.call_tool(
                TOOL_NAME, ARGS, input_responses={key: accept("approve", "lgtm")}, request_state=first.request_state
            )

    final = run(go())
    assert not final.is_error and final.structured_content["status"] == "signal-sent"
    assert final.structured_content["decision"] == "approve"
    ((args, kwargs),) = sent.calls
    ticket, decision, source, source_id = args
    assert (ticket, decision, source) == (TICKET, "approve", "mrtr") and source_id  # the JSON-RPC request id
    assert kwargs == {"by": "mcp-client"}
    assert any("spec_version=2026-07-28" in r.getMessage() and TICKET in r.getMessage() for r in caplog.records)


def test_the_sdk_client_loop_answers_the_question_and_finishes_the_call():
    sent = Sent()
    asked: list[str] = []

    async def answer(context, params):
        asked.append(params.message)
        return accept("reject", "breaks the cart")

    async def go():
        async with Client(qa_server(sent), mode="2026-07-28", elicitation_callback=answer) as client:
            return await client.call_tool(TOOL_NAME, ARGS)

    final = run(go())
    assert len(asked) == 1 and final.structured_content["decision"] == "reject"
    assert [(c[0][1], c[0][2]) for c in sent.calls] == [("reject", "mrtr")]


@pytest.mark.parametrize("action", ["decline", "cancel"])
def test_declining_or_cancelling_sends_no_signal(action):
    sent = Sent()

    async def answer(context, params):
        return ElicitResult(action=action)

    async def go():
        async with Client(qa_server(sent), mode="2026-07-28", elicitation_callback=answer) as client:
            return await client.call_tool(TOOL_NAME, ARGS)

    final = run(go())
    assert final.structured_content == {"status": "no-decision", "action": action, "ticket": TICKET}
    assert sent.calls == []


def test_a_retry_without_the_answer_is_asked_again_not_failed():
    sent = Sent()

    async def go():
        async with Client(qa_server(sent), mode="2026-07-28", elicitation_callback=never_called) as client:
            first = await client.session.call_tool(TOOL_NAME, ARGS, allow_input_required=True)
            again = await client.session.call_tool(
                TOOL_NAME, ARGS, request_state=first.request_state, allow_input_required=True
            )
            return first, again

    first, again = run(go())
    assert isinstance(again, InputRequiredResult) and list(again.input_requests) == list(first.input_requests)
    assert sent.calls == []


def test_a_tampered_request_state_is_refused_and_sends_nothing():
    sent = Sent()

    async def go():
        async with Client(qa_server(sent), mode="2026-07-28", elicitation_callback=never_called) as client:
            first = await client.session.call_tool(TOOL_NAME, ARGS, allow_input_required=True)
            (key,) = first.input_requests
            with pytest.raises(MCPError, match="requestState"):  # caught inside: the in-memory server also re-raises on exit
                await client.session.call_tool(
                    TOOL_NAME, ARGS, input_responses={key: accept("approve")}, request_state=first.request_state[:-3] + "abc"
                )

    run(go())
    assert sent.calls == []


def test_a_client_without_elicitation_support_gets_a_protocol_error_and_sends_nothing():
    """The case the review-comment path (T10) exists for."""
    sent = Sent()

    async def go():
        async with Client(qa_server(sent), mode="2026-07-28") as client:  # no elicitation_callback
            with pytest.raises(MCPError, match="elicitation capability"):
                await client.call_tool(TOOL_NAME, ARGS)

    run(go())
    assert sent.calls == []


def test_a_client_at_the_previous_spec_version_is_asked_inside_the_call_instead():
    """mode='legacy' negotiates 2025-11-25: no input_required, a standalone elicitation mid-call."""
    sent = Sent()

    async def answer(context, params):
        return accept("approve")

    async def go():
        async with Client(qa_server(sent), mode="legacy", elicitation_callback=answer) as client:
            return client.protocol_version, await client.call_tool(TOOL_NAME, ARGS)

    version, final = run(go())
    assert version == "2025-11-25" and final.structured_content["status"] == "signal-sent"
    assert len(sent.calls) == 1


def test_bad_tickets_are_tool_errors_not_crashes():
    def refuse(*args, **kwargs):
        raise ValueError("ticket_id must not be empty")

    async def answer(context, params):
        return accept("approve")

    async def go():
        async with Client(qa_server(refuse), mode="2026-07-28", elicitation_callback=answer) as client:
            return await client.call_tool(TOOL_NAME, {"ticket_id": ""})

    final = run(go())
    assert final.is_error and "must not be empty" in final.content[0].text


def test_server_name():
    assert qa_server(Sent()).name == SERVER_NAME
