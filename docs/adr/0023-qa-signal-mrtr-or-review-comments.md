# ADR-023: QA signal via MRTR or review comments

Status: proposed (P6-T18), drafted by Claude at the owner's request, for the owner to review. It is accepted when the owner approves it. It depends on P6-T10 and P6-T09, both built; the MRTR cut (PLAN.md cut 5) was not taken.

## Context

After the draft PR is open the workflow waits in `awaiting-qa` for a person to approve or reject (`flow.workflow.await_qa`, a `DBOS.recv` with a stored deadline, P6-T08). Two ways to deliver that answer were built, and both end in the same call, `flow.qa.send_qa_signal`, with the same kind of key (`qa_signal_key`, a DBOS `idempotency_key`):

- **Review comment (P6-T10).** A reviewer writes `/argus approve` or `/argus reject` in a PR review or inline review comment. GitHub's webhook reaches `POST /webhook`, which parses the payload (`flow.review_comment`) and sends the signal after answering 202. No MCP is involved.
- **MRTR elicitation (P6-T09).** An MCP client calls the tool `qa_decision(ticket_id)` (`flow.qa_mcp`). On spec 2026-07-28 the server answers `resultType: "input_required"` with one `elicitation/create`; the client asks its user and retries with `inputResponses`; the tool then sends the signal.

The question is which one the deployed service relies on, given what was actually seen of client support. Details of the evidence: `docs/notes/p6-t09.md` (MRTR) and `docs/architecture/p6.md` sections P6-T08, P6-T10, P6-T09.

## What was seen, and what was not

| | Review comment | MRTR |
|---|---|---|
| Built and tested | Yes. Parser tests on fixture payloads (no database), the webhook path, and one run through the real workflow on Postgres: a signed `pull_request_review` delivered twice resumed the waiting workflow once (one row in `dbos.notifications`) | Yes. The SDK's own in-memory `Client` against the server, and one run through the real workflow on Postgres |
| Real counterpart run | **No real GitHub delivery was made.** Payloads are hand-written fixtures in the documented field names; the HMAC was computed in the test with a test secret | **No real MCP host was run** (not Claude Desktop, Claude Code, Cursor, VS Code or any other). Only the `mcp` 2.3.0 SDK client |
| Who can answer | Any allowed GitHub login (`ARGUS_FLOW_QA_REVIEWERS`; unset allows nobody). GitHub authenticates the commenter and the webhook is HMAC-signed | Anyone who can reach the MCP endpoint. The tool has no login check, and the endpoint is not mounted on any transport yet (T12) |
| Needs | A GitHub account and the webhook | A host that declares the elicitation capability and speaks 2026-07-28 (or 2025-11-25 over a held-open connection) |
| Wait length | Hours or days: the comment arrives whenever it is written | One tool call. The SDK seals `requestState` for 600 s by default, so an answer after that is refused ("Invalid or expired requestState") and the tool must be called again |
| Failure modes seen | A dropped delivery of the comment is not recovered by the signal path itself (see consequences) | A client without elicitation support gets a protocol error and nothing is sent; an old-spec client is asked inside the call instead of through `input_required`; a tampered state is refused |

Client support, found in practice, limited to the SDK: it speaks 2026-07-28 and does the retry loop (`input_required` answered, call finished). It also answers an old-spec client with a standalone elicitation inside the call, which needs a connection that stays open and would not work over stateless HTTP. The MCP release post says the Tier 1 SDKs, Python included, speak 2026-07-28 (`docs/notes/p6-t00-versions.md`); that is SDK support, not host support. Which hosts a reviewer would actually use, whether they declare the elicitation capability, and whether they show the form to a person were **not checked** and cannot be checked without running them.

## Decision

The **review-comment path ships**: it is the QA path the deploy depends on and the one the phase demo uses.

The **MRTR tool is kept and built, but not shipped as a dependency**: it is not mounted in the deployed app and no document claims that a particular host works with it. It becomes a second front door when two things are true: a real MCP host has been run against it end to end (a person answers the form, the workflow resumes), and the endpoint has an authentication check in front of it. Until then it is evidence that the 2026-07-28 round trip works with the SDK, no more.

Both paths stay valid at once. They write the same kind of signal, the workflow takes the first one and drops the rest (`record-qa-signal` in `flow.states`), so turning MRTR on later changes no workflow code.

The fallback direction is therefore: if MRTR is unavailable (no capable host, state expired, no auth yet), the reviewer comments on the PR. If the review-comment path is unavailable (webhook lost or GitHub down), the workflow times out into `timed-out` (PR left open and draft). That workflow has ended, so a command posted afterwards is dropped; the ticket needs a deliberate re-run, which is not built (a finished workflow id is not reused, `docs/notes/p6-t03.md`). The timeout is the only recovery for a lost comment.

## Alternatives

- **MRTR only.** Rejected: nothing seen shows a host that would carry it, a person who is not in an MCP client cannot answer at all, and the answer cannot outlast the 600 s state. The phase's own risk is that the 2026-07-28 spec is new.
- **Review comments only, MRTR deleted.** Rejected: MRTR is already built and tested with the SDK, it costs nothing to keep, and the learning goal of the phase (human-in-the-loop as a protocol feature) is met by it. Deleting it is PLAN.md cut 5 and stays available.
- **The MCP Tasks extension** (`io.modelcontextprotocol/tasks`) for a long approval, with the task id equal to the workflow id. Not built: it is a larger surface than the review comment and has the same unknown about host support (`p6-t01-dbos-mrtr.md`). Revisit if a host supports tasks and approvals must be answered inside an MCP client.
- **A GitHub review state (`approved`, `changes_requested`) instead of a command.** Not chosen: a review state is also the normal code-review verdict and would approve a fix by accident. A command keyword is explicit. The parser could accept both later.

## Consequences

- The deploy (T12) must set `ARGUS_FLOW_QA_REVIEWERS` (otherwise nobody can approve) and `ARGUS_FLOW_QA_TIMEOUT_SECONDS` (the default is 60 s, which is only for tests), and must register the webhook for `pull_request_review` and `pull_request_review_comment` events, and pass `qa_send=flow.review_comment.send_review_signal` to `create_app`. None of that is done or tested against a real deploy yet.
- A review-comment delivery that GitHub loses is not recovered by the webhook path, because the decision is read from the payload. Whether the reconciliation poller (T07, a separate task) reads PR reviews and comments to repair this was not checked here. Without that, a lost comment shows as a timeout.
- `issue_comment` (a plain comment in the PR conversation tab) is not parsed, so a reviewer who writes the command there is ignored with no message. Say it in the PR body, or add the event.
- The MRTR idempotency key uses the JSON-RPC request id, which the SDK client counts per connection. Two clients can reuse an id; for one ticket that is the same key and is dropped, which the state machine would do anyway.
- Nothing in this ADR is a measurement of how long a reviewer takes. The timeout value is a deploy choice, not a result.
