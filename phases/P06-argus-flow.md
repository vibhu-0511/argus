# P6 — argus-flow

**Budget:** 52 h · **Weeks:** calendar weeks 22–24 · **Packages:** `flow` (py, FastAPI + DBOS), uses `fix-loop`, `verify`, `repro-agent`

## Goal
Run the pipeline as a durable workflow, deployed free on Render and Neon, with GitHub as the source of truth, GitHub Actions as the execution plane, and a human QA signal wait.

## Done when
- The ticket-to-fix workflow is a DBOS workflow whose steps are idempotent, and its state machine (states and transitions) is written down and tested.
- The crash-recovery experiment is run: the process is killed at each step boundary and the run resumes with no duplicated side effect (Ablation table filled).
- The service is deployed on Render free with Neon free Postgres, and the agent job runs on GitHub Actions.
- A webhook returns inside GitHub's 10 s timeout, including after a Render cold start, or the lost webhook is recovered by the reconciliation poller (both measured).
- The reconciliation poller rebuilds a workflow's state from GitHub after a dropped webhook.
- The QA signal wait works through MRTR elicitation (`input_required` / `inputResponses`) or through the plain GitHub review-comment fallback, and ADR-023 says which one ships.
- Neon compute (CU-hours) over a 48-hour polling run is measured and compared with the 100 CU-hour monthly free limit.
- Phase report filled against P5.

## Agentic concepts learned
1. **Durable execution** — workflows that survive crashes by checkpointing each step, and what that demands of the steps.
2. **Idempotency and exactly-once effects** — why "open a PR" must be safe to retry.
3. **Webhooks as hints with reconciliation** — GitHub is the source of truth; a poller repairs lost or duplicated events.
4. **Human-in-the-loop as a protocol feature** — QA wait, plus MRTR (`input_required` / `inputResponses`) in the 2026-07-28 MCP spec.
5. **Operating inside free-tier collisions** — cold starts, scale-to-zero databases and polling cost, measured instead of assumed.

## Interview questions
1. Your worker dies after the PR is opened but before the state is saved. What happens on restart, and which design choices made that safe?
2. Why treat a webhook as a hint rather than as the event itself, and what does your reconciliation poller read to recover state?

## Prereq reading
- [DBOS documentation](https://docs.dbos.dev)
- [MCP 2026-07-28 release post](https://blog.modelcontextprotocol.io/posts/2026-07-28/)

## Tasks
| ID | Title | Owner | Type | Est hrs | Depends on | Acceptance criteria |
|---|---|---|---|---|---|---|
| P6-T00 | Re-verify pinned versions via web search | [CLAUDE] | doc | 1 | P5.5-T17 | Versions table re-checked; DBOS, MCP spec and SDK, Render free plan, Neon free limits and GitHub webhook timeout confirmed; date updated |
| P6-T01 | Read the DBOS docs and the MRTR and Tasks sections of the MCP post, write notes | [ME] | learn | 1 | P6-T00 | Notes cover the DBOS step and workflow model, its recovery guarantee, and what MRTR changes about a human-approval step |
| P6-T02 | Design the workflow state machine: states, transitions, idempotency keys | [ME] | build | 3 | P6-T01 | A table lists every state, transition and the idempotency key of each side effect; a test enumerates all transitions and rejects an illegal one |
| P6-T03 | Implement the workflow with DBOS durable steps against a local Postgres | [ME] | build | 4 | P6-T02 | A full run on a fixture ticket reaches `done`; each step's result is stored; steps re-run safely when repeated |
| P6-T04 | Dispatch agent jobs to GitHub Actions as the execution plane and collect artifacts | [PAIR] | build | 3 | P6-T03 | A workflow_dispatch run executes repro, fix and verify in the sandbox and returns the patch and trajectory as an artifact |
| P6-T05 | Build the FastAPI webhook endpoint with HMAC signature verification | [PAIR] | build | 2 | P6-T03 | Valid signature is accepted, invalid one gets 401; unit test covers both |
| P6-T06 | Treat webhooks as hints: enqueue a reconcile and return immediately | [ME] | build | 1 | P6-T05 | Webhook and poller share `SetWorkflowID(ticket_id)`; handler returns 202 after enqueueing, without waiting, and does no GitHub reads inline; the delivery id is only a hint-dedup record; a test measures the handler time |
| P6-T07 | Build the reconciliation poller that rebuilds state from GitHub | [ME] | build | 3 | P6-T06 | Webhook and poller share `SetWorkflowID(ticket_id)`; given only GitHub's state (issue, PR, run), the poller sets the workflow to the right state; tested with a dropped-webhook fixture |
| P6-T08 | Add the QA signal wait with a timeout | [ME] | build | 2 | P6-T03 | Workflow pauses in `awaiting-qa`, resumes on an approve or reject signal, and times out into a defined state; the QA signal carries an idempotency key |
| P6-T09 | Add MRTR elicitation for the QA approval step | [ME] | build | 3 | P6-T08, P6-T01 | The server returns `input_required`, the client sends `inputResponses`, and the workflow resumes; the spec version in use is logged |
| P6-T10 | Add the plain GitHub review-comment fallback for QA approval | [PAIR] | build | 1 | P6-T08 | A review comment with an approve keyword resumes the workflow; this path works without MCP; the QA signal carries an idempotency key |
| P6-T11 | Set up Neon free Postgres with reconnect handling for scale-to-zero | [CLAUDE] | deploy | 2 | P6-T03 | Chooses `use_listen_notify` before the first migration, pins a stable app version and executor id, and sets no conductor key on Render; service connects over TLS, reconnects after the database suspends, and a test forces a suspended state |
| P6-T12 | Deploy the FastAPI and DBOS service to Render free | [CLAUDE] | deploy | 3 | P6-T05, P6-T11 | Health endpoint answers on the public URL; secrets are Render environment variables; deploy is reproducible from the repo |
| P6-T13 | Measure the Render cold start against the 10 s webhook timeout | [ME] | eval | 2 | P6-T12 | A table of cold-start response times over repeated idle gaps in `docs/notes/p6-render.md`; states which gaps exceed 10 s |
| P6-T14 | Measure Neon CU-hours with DBOS polling over 48 hours | [ME] | eval | 2 | P6-T12 | Measured CU-hours from the Neon dashboard are recorded and compared with 100 CU-hours/project. "per month" is not stated. States whether polling keeps the database awake |
| P6-T15 | Write ADR-020: DBOS vs Temporal (decision only) | [ME] | doc | 2 | P6-T03 | ADR compares the two on operating cost, free hosting, in-process fit and lock-in, and records the decision without building the Temporal variant |
| P6-T16 | Write ADR-021: Webhooks as hints with reconciliation | [ME] | doc | 1 | P6-T07, P6-T13 | ADR uses the cold-start measurement as evidence and states the poll interval and its cost |
| P6-T17 | Write ADR-022: Free-tier deployment topology | [ME] | doc | 1 | P6-T14 | ADR states how Render sleep and Neon compute interact, the chosen poll cadence and the alternatives |
| P6-T18 | Write ADR-023: QA signal via MRTR or review comments | [ME] | doc | 1 | P6-T10 when the MRTR cut is taken; otherwise P6-T09, P6-T10 | ADR states which path ships, client support found in practice and the fallback |
| P6-T19 | Run crash-recovery experiment: kill the process at each step boundary | [ME] | eval | 3 | P6-T04, P6-T07 | Ablation table filled from real kills for the DBOS run and the non-durable run, counting completed runs and duplicate side effects; a second GitHub call is asserted only for the kill that happens before the step result is stored |
| P6-T20 | Add CI job for flow tests with a Postgres service container, no LLM | [CLAUDE] | deploy | 2 | P6-T07 | Workflow green; no secrets; runs the state-transition, webhook and reconcile tests |
| P6-T21 | Break it: kill the worker after the PR is opened but before state is saved | [ME] | test | 2 | P6-T19 | Restart opens no second PR; find-or-create uses one stable branch and stays draft until QA; the lookup does not use a `closes #N` commit heuristic; a lookup error leaves the existing PR untouched; written up in the Break it section |
| P6-T22 | Break it: deliver the same webhook twice | [ME] | test | 2 | P6-T06 | Second delivery is a no-op; the delivery id is only a hint-dedup record; written up |
| P6-T23 | Break it: let Render sleep and drop a webhook | [ME] | test | 2 | P6-T13 | The reconciliation poller recovers the missed event; written up |
| P6-T24 | Break it: suspend Neon mid-run | [ME] | test | 2 | P6-T11 | The service reconnects and the workflow continues; written up |
| P6-T25 | Write package README and phase report against P5 | [CLAUDE] | doc | 1 | P6-T18 | README shows deploy and run steps; phase report has previous-phase, this-phase and delta rows filled |

## Break it on purpose
1. **Crash between side effect and state save (P6-T21).** *Induced failure:* kill the worker right after the PR is opened and before the step result is stored. *Expected signal:* on restart the step runs again but finds the existing PR through its idempotency key; exactly one PR exists. *Fix:* make "open PR" a find-or-create on one stable branch, draft until QA, with no `closes #N` commit heuristic; a lookup error leaves the existing PR untouched.
2. **Duplicate webhook (P6-T22).** *Induced failure:* replay the same delivery id twice. *Expected signal:* the second delivery is dropped as already seen; one workflow exists. *Fix:* store the delivery id as a hint-dedup record only, and key the workflow by ticket id.
3. **Render sleeps and a webhook is lost (P6-T23).** *Induced failure:* let the free service idle past its sleep time and send a webhook that times out at GitHub. *Expected signal:* no immediate reaction, then the poller finds the new ticket and starts the workflow. *Fix:* reconciliation on a schedule, reading GitHub rather than trusting delivery.
4. **Neon suspended (P6-T24).** *Induced failure:* wait for or force the database to suspend during a step. *Expected signal:* the first query fails, the service reconnects and the workflow resumes. *Fix:* connection retry with backoff and a short wake-up timeout.

## Ablation
**Hypothesis:** a durable DBOS workflow completes every run after a crash with no duplicated side effects, while the same pipeline without durability loses runs or duplicates effects. The DBOS-vs-Temporal question is an ADR only; no Temporal variant is built.
**Variants:** A = same pipeline as a plain function, no durability; B = DBOS durable workflow.
**Metric:** runs completed after a crash, duplicate side effects, recovery time p50 and p95 per kill.
**Result (P6-T19, 2026-11-01):** 10 hard kills at each of 15 kill points per variant (150 each), fake runners and GitHub client with a durable ledger, find-before-act the same in A and B. Both variants completed every run; the plain function repeats every earlier call after a restart (4.47 per kill against 0.93 for DBOS) and set the `done` label twice in the 10 kills after it. No model was run, so the last three columns stay empty. Details and limits: `docs/notes/p6-t19.md`.

| Variant | Completed after crash | Duplicate side effects | Recovery p50 | Recovery p95 | Resolve rate (95% CI) | Tokens/bug (in, out, cached) | $-equivalent/bug |
|---|---|---|---|---|---|---|---|
| A | 150 of 150 | 20 (all at one kill point, a label set twice) | 3.03 s | 6.01 s | — | — | — |
| B | 150 of 150 | 0 | 4.92 s | 6.05 s | — | — | — |

**Phase report (against previous phase):**

| Report | Resolve rate | Tokens/bug | $-equivalent | p50 latency | p95 latency |
|---|---|---|---|---|---|
| Previous phase | — | — | — | — | — |
| This phase | — | — | — | — | — |
| Delta | — | — | — | — | — |

## ADRs to write
All [ME].
- **ADR-020 — DBOS vs Temporal.** Which durable-execution engine fits a free, in-process deployment, and what would change the answer?
- **ADR-021 — Webhooks as hints with reconciliation.** What is the source of truth, and how often does the poller read it?
- **ADR-022 — Free-tier deployment topology.** How do Render's sleep and Neon's compute limit constrain polling and cold starts?
- **ADR-023 — QA signal via MRTR or review comments.** Which path ships, given real client support for the 2026-07-28 spec?

## Deploy checkpoint
Render free web service (FastAPI with DBOS in-process) plus Neon free Postgres, with GitHub Actions as the execution plane. Webhooks are treated as hints, and a reconciliation poller restores state from GitHub. Earlier CI jobs and the dashboard keep running.

## Portfolio artifact
A deployed, free-tier durable workflow with a crash-recovery write-up and a measured account of the Render and Neon constraints. This is the hard cut line: everything up to here is the deployed core.
