# P6-T01 DBOS and MRTR notes

Read on 2026-11-01 (DBOS Python 3.4.0, MCP spec 2026-07-28; versions in `p6-t00-versions.md`). Everything below is my summary of the pages listed under Sources. Short quoted phrases are marked with quotation marks. Where a page did not say something, the note says "not confirmed". Lines marked **My reading** are inferences for Argus, not statements from a source.

## 1. DBOS workflow and step model

- A **workflow** is an ordinary Python function marked `@DBOS.workflow()`. A **step** is a function marked `@DBOS.step()` that the workflow calls. DBOS keeps a checkpoint in Postgres (the "system database") for the workflow's input, for the output of every step, and for the workflow's final outcome. [architecture], [workflows]
- The cost model is plain: one database write per step, plus two per workflow (input at the start, outcome at the end). Step outputs are stored, so large outputs should be kept elsewhere and the step should return a pointer. **My reading:** a step that fetches a diff or a log should return an id or a URL, not the text. [architecture]
- Anything non-deterministic belongs in a step: calls to GitHub or an LLM, reading a file, the clock, random numbers, reading the database. The workflow function itself must be deterministic: given the same inputs and the same step results, it must call the same steps with the same inputs in the same order. If DBOS sees a different recorded result for the same step position it raises `DBOSStepNondeterminismError`. [workflows], [steps]
- Steps cannot start or enqueue workflows; only workflow code can. A step called from another step is folded into the caller. A step called outside any workflow is a plain function with no checkpoint and no retry. [steps]
- Steps can retry on their own (`retries_allowed`, `max_attempts`, `interval_seconds`, `backoff_rate`, optional `should_retry`). When all attempts fail the step raises `DBOSMaxStepRetriesExceeded` into the workflow. If the workflow does not catch it, the workflow ends. [steps]
- An uncaught exception in a workflow is treated as non-recoverable: the status becomes `ERROR` and DBOS does not recover it. Transient failures are meant to be handled by step retries. **My reading:** the Argus state machine (T02) needs an explicit failed or needs-human state that the workflow catches and records, so that "the code raised" and "the world said no" are different. [workflows]
- Other documented parts of the model: durable `DBOS.sleep` (the wake-up time is stored in the database and survives restarts), workflow timeouts (stored, and counted from when the workflow leaves the queue and starts), messages and events (section 5). [workflows]

## 2. Recovery guarantee: what is exactly-once and what is at-least-once

How recovery works [architecture], [recovery]:

1. On start, DBOS looks for workflows still `PENDING`. On a single server without Conductor, each restart recovers all of them. With several servers, each executor has an `executor_id` and a restarted process recovers only the pending workflows tagged with its own id. With Conductor, a control plane notices a dead executor (default wait 60 s) and has another executor recover its workflows.
2. A recovered workflow is called again with its checkpointed input.
3. Before each step, DBOS checks for a stored output. If there is one, the step returns it and does not run. The first step with no stored output is where the crash happened; that step runs for real, and the workflow continues.
4. Recovery only happens for workflows whose application version equals the running version (version is a hash of the workflow source unless you set it).

The documented guarantees [workflows]:

| Thing | Guarantee | What it means for a side effect |
|---|---|---|
| Workflow | Runs to completion, resumed from the last completed step | |
| Step | Tried **at least once**; **never re-executed after it completed** | The *recorded result* is exactly-once. The *effect* inside the step is at-least-once, because a crash can land after the effect and before the checkpoint write |
| Database transaction | Commits **exactly once**: once committed, it is never retried | Applies to writes DBOS itself runs as a transaction. A call to GitHub is not a transaction, so it gets the step row, not this one |
| `DBOS.send` from inside a workflow | Exactly-once delivery | Messages are stored, so a `send` that returned can be received |
| `DBOS.send` from outside a workflow | At-least-once unless you pass an `idempotency_key` | The key makes it once per destination |

Why steps must be idempotent: the three crash windows of a step that calls GitHub.

| Crash happens | State on disk | After restart |
|---|---|---|
| Before the GitHub call | No checkpoint | Step runs, call happens once |
| After the GitHub call, before the step output is stored | No checkpoint | Step runs again, so the call happens a **second** time unless the step is safe to repeat |
| After the step output is stored | Checkpoint exists | Step is skipped, call is not repeated |

The middle row is the only one that can duplicate a side effect, and it is exactly the interview question in `phases/P06-argus-flow.md` ("worker dies after the PR is opened but before the state is saved"). The docs say it directly: steps should be idempotent, a failed step is retried during recovery, and a completed step is never re-run. **My reading:** for Argus this means find-or-create on the GitHub side (look up the PR or branch for the ticket first, create only if absent, or treat "already exists" as success), keyed by something stable such as the ticket id. T02's table lists that key per side effect; T19 kills the process in each window and counts GitHub calls.

Two further conditions on recovery, both from the docs: the workflow code must be deterministic (section 1), and the application version must be stable across the redeploy, otherwise the new process does not pick up the old `PENDING` workflows. `use_listen_notify` is fixed at database creation (see `p6-t00-versions.md`).

Not confirmed: whether a database outage in the middle of the checkpoint write has any case not covered by the table above (the docs say the guarantees assume the database may crash and always comes back).

## 3. Queues and `SetWorkflowID` as the dedup key

Two different dedup mechanisms exist. They answer different questions.

**Workflow ID (idempotency key for the whole run).**
- Every workflow run has a unique id (a UUID unless you choose one). `SetWorkflowID("...")` around a call sets it. Ids are globally unique per application, and an id "acts as an idempotency key": calling again with the same id runs the workflow once. [workflows]
- Default behaviour on reuse: DBOS returns the existing run (a handle, or for a direct call its result) instead of starting a new one. `workflow_id_reuse_policy="reject"` makes it raise `DBOSWorkflowIDInUseError` instead. [workflows]
- The id stays reserved for the life of the run record. The DBOS Client's `EnqueueOptions` has `workflow_id` and `workflow_id_reuse_policy` (default "return-existing") and the docs say it applies "whatever its status", i.e. also after completion. [client reference]
- Not confirmed: whether the in-process `SetWorkflowID` context manager also wraps `DBOS.enqueue_workflow` in 3.4.0. The pages I read show it around a direct call, and show `workflow_id` on the Client's enqueue options. T03 must test this with a duplicate enqueue before the webhook code depends on it.

**Queue deduplication ID (at most one *active* run per key on a queue).**
- `SetEnqueueOptions(deduplication_id=...)`: while a workflow with that id on that queue is `ENQUEUED`, `DELAYED` or `PENDING`, another enqueue raises `DBOSQueueDeduplicatedError`; with `duplication_policy="return-existing"` it returns the existing handle and discards the second caller's arguments. When the run finishes, the id is released and the next enqueue starts a new run. Not available on partitioned queues. [queues], [queue reference]

**Which one for Argus (My reading):**

| Need | Mechanism | Why |
|---|---|---|
| Same GitHub delivery arrives twice (redelivery, retry) | Workflow id derived from the delivery or the ticket event | Stays reserved after the run ends, so a late duplicate cannot start a second run |
| One in-flight fix per ticket at a time, but a later re-label may start a new run | Queue `deduplication_id` = ticket id | Released on completion |
| Webhook and reconciliation poller both notice the same ticket | Same key in both code paths | Both call the same enqueue function; the second call returns the first run (T05, T06, T07, T22) |

The choice of key is T02's job. `X-GitHub-Delivery` is unique per delivery and stays the same on a redelivery ([GitHub best practices], see `p6-t00-versions.md`); it does not de-duplicate two different events about one ticket.

Queue basics worth keeping: queues live in the system database and are first-in-first-out; each process polls them; flow control is per queue (worker concurrency, global concurrency, rate limit, priority, delay). A workflow enqueued to a queue nobody has registered stays `ENQUEUED`. Another service can enqueue into the application through `DBOSClient` using the system database URL. [queues] **My reading:** the webhook handler returns 202 after the enqueue write commits; the write is a database insert, not the whole run, so it fits inside GitHub's 10 s provided the Neon compute is awake (T13, T24).

## 4. Conductor, executor id and version, in one place

- Conductor is optional. With no `conductor_key` the application runs standalone and recovers its own pending workflows on restart. [recovery], [configuration]
- On Render free the single process is replaced on each deploy and may be restarted at any time (`p6-t00-versions.md`). **My reading:** set `executor_id` and `application_version` explicitly in config so a restarted container claims the previous container's pending workflows.

## 5. MRTR and Tasks in the MCP 2026-07-28 post, and what they change for a human-approval step

### What the sources say

- The 2026-07-28 spec makes the protocol core stateless: no handshake and no protocol-level session; every request carries its own metadata. [post]
- **MRTR (Multi Round-Trip Requests, SEP-2322)** replaces the old server-initiated `elicitation/create`, `sampling/createMessage` and `roots/list` requests, which needed a stream held open from server to client. Now: the server answers the client's request with `resultType: "input_required"` plus the questions it needs answered (`inputRequests`, a map of server-chosen keys to request objects) and optionally an opaque `requestState`. The client collects the answers and sends the **original request again**, with `inputResponses` (same keys) and the `requestState` echoed back unchanged. The server then finishes or asks again. [post], [MRTR spec]
- It is allowed only on `tools/call`, `prompts/get` and `resources/read`. A server must not send an input request of a kind the client did not declare support for. A server must not assume the client will answer or retry. If answers are missing, the server should ask again instead of failing. [MRTR spec]
- The stated aim is to let the server ask without keeping server-side state between rounds: each retry is self-contained, and the server needs nothing beyond what is in that retry. [MRTR spec]
- `requestState` passes through the client, so it is attacker-controlled input. If it influences authorization or logic the server must protect its integrity (HMAC or AEAD) and reject state that fails the check. The spec suggests binding it to the authenticated principal, a short expiry and the originating request. It says these measures bound replay but "do not by themselves guarantee single-use"; a server that needs at-most-once use must enforce that itself. [MRTR spec]
- **Tasks** left the experimental core and became the extension `io.modelcontextprotocol/tasks` (SEP-2663), with poll-based `tasks/get` and a new `tasks/update`. [post] The extension page describes a task as a durable handle for work that is too long to block on (CI pipelines and human approvals are named as examples): the server returns a task id with `resultType: "task"`, the client polls `tasks/get`, a task can move to the status `input_required` and carry `inputRequests`, and the client answers through `tasks/update`. Statuses are working, input_required, completed, failed, cancelled. Cancellation is cooperative. The task must be durably created before the response is sent. [Tasks overview]

### Compared with a plain signal wait

A plain signal wait here means the DBOS workflow calls `DBOS.recv(topic, timeout)` and something else calls `DBOS.send(workflow_id, decision, topic)`.

| | Signal wait (`recv` / `send`) | MRTR `input_required` | Tasks `input_required` |
|---|---|---|---|
| Who holds the "waiting" | The workflow, in Postgres | Nobody on the server. The client holds the pending retry | The server's task record (must be durable) |
| Survives server restart | Yes: workflow is checkpointed and the message is stored | Yes in the sense that there is nothing to lose, but the pause is only as long as the client keeps the round open | Yes if the task record is durable |
| Length of wait | Hours or days are fine; `recv` takes a timeout (default 60 s per call, a loop or longer value is needed) | Meant for a prompt in the middle of one tool call. The spec read says nothing about a time limit; not confirmed. Clients and proxies commonly time out requests (the Tasks page makes that point about blocking) | Meant for long waits |
| Who can answer | Anything that can reach the database or the app and knows the workflow id: a webhook, a review-comment poller, a CLI | Only an MCP client that declared elicitation support and is talking to the server at that moment | An MCP client that polls or reconnects with the task id |
| Delivery guarantee | `send` is stored; exactly-once from inside a workflow, `idempotency_key` from outside | None by itself. The server may see zero, one or several retries | Task state is stored by the server |
| What it is not | A protocol between a human's tool and the server | A durable wait. It stores no decision and times out nothing | A workflow engine |

What MRTR changes: before, a tool that wanted a human's confirmation held a stream open to the client and asked over it, which needs either shared storage across server instances or sticky routing. With MRTR the question travels in the *response* and the answer in the *next request*, so a stateless server can ask. For an approval step, that moves the human prompt into the normal request and response. It does not make the approval durable. Nothing in MRTR remembers the answer, retries for the user, or resumes a half-finished fix.

**My reading for Argus (inputs to T08, T09, T10, ADR-023):**
- Keep the durable wait in DBOS (`recv` with a long timeout, or a loop of shorter ones). That is what survives Render restarts and Neon sleeping.
- Treat MRTR as the *front door* of the approval, not the wait: an MCP tool such as "approve this fix" returns `input_required` with an elicitation (approve or reject, plus an optional comment). When the retry arrives with `inputResponses`, the tool translates it to `DBOS.send(workflow_id, decision, topic)`, with an `idempotency_key` so a repeated retry does not deliver twice, and returns the result. That matches T09's acceptance text (server returns `input_required`, client sends `inputResponses`, workflow resumes, spec version logged).
- `requestState` should carry little more than the workflow id plus an expiry and a signature. The decision must not be single-use by trusting `requestState`; single-use comes from the signal key.
- If the QA reviewer is not an MCP client (a person reading GitHub), MRTR cannot reach them. That is the review-comment fallback in T10. Both paths end in the same `send`.
- If an approval needs to stay open for days from the client's point of view, the Tasks extension fits that shape better than MRTR, with the task id equal to the workflow id. Whether the Python SDK 2.3.0 ships helpers for either feature: not confirmed (T09 reads the SDK).

## Sources

All read 2026-11-01.

- [architecture] DBOS Architecture: https://docs.dbos.dev/architecture
- [workflows] DBOS Python, Workflows: https://docs.dbos.dev/python/tutorials/workflow-tutorial
- [steps] DBOS Python, Steps: https://docs.dbos.dev/python/tutorials/step-tutorial
- [queues] DBOS Python, Queues & Concurrency: https://docs.dbos.dev/python/tutorials/queue-tutorial
- [queue reference] DBOS Python, Queues reference (`SetEnqueueOptions`): https://docs.dbos.dev/python/reference/queues
- [client reference] DBOS Python, DBOS Client reference (`EnqueueOptions`): https://docs.dbos.dev/python/reference/client
- Communicating with workflows (`send`, `recv`, idempotency key): https://docs.dbos.dev/python/tutorials/workflow-communication
- [recovery] Workflow Recovery: https://docs.dbos.dev/production/workflow-recovery and Distributed Recovery (Conductor): https://docs.dbos.dev/conductor/distributed-recovery
- [configuration] DBOS Python configuration: https://docs.dbos.dev/python/reference/configuration
- Upgrading workflow code (versions): https://docs.dbos.dev/python/tutorials/upgrading-workflows
- [post] MCP 2026-07-28 release post: https://blog.modelcontextprotocol.io/posts/2026-07-28/
- [MRTR spec] Multi Round-Trip Requests: https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/mrtr
- [Tasks overview] https://modelcontextprotocol.io/extensions/tasks/overview
- [GitHub best practices] https://docs.github.com/en/webhooks/using-webhooks/best-practices-for-using-webhooks
