# Proposal for `phases/P06-argus-flow.md`

Plan text only. No new tasks. No hour changes.

### RISK-007
- Severity: Med
- Section: P6-T21
- Owner: [ME]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P6-T21 | Break it: kill the worker after the PR is opened but before state is saved | [ME] | test | 2 | P6-T19 | Restart opens no second PR; written up in the Break it section |
```

```
1. **Crash between side effect and state save (P6-T21).** *Induced failure:* kill the worker right after the PR is opened and before the step result is stored. *Expected signal:* on restart the step runs again but finds the existing PR through its idempotency key; exactly one PR exists. *Fix:* make "open PR" a find-or-create keyed by the ticket id.
```

- Proposed text:

```
| P6-T21 | Break it: kill the worker after the PR is opened but before state is saved | [ME] | test | 2 | P6-T19 | Restart opens no second PR; find-or-create uses one stable branch and stays draft until QA; the lookup does not use a `closes #N` commit heuristic; a lookup error leaves the existing PR untouched; written up in the Break it section |
```

```
1. **Crash between side effect and state save (P6-T21).** *Induced failure:* kill the worker right after the PR is opened and before the step result is stored. *Expected signal:* on restart the step runs again but finds the existing PR through its idempotency key; exactly one PR exists. *Fix:* make "open PR" a find-or-create on one stable branch, draft until QA, with no `closes #N` commit heuristic; a lookup error leaves the existing PR untouched.
```

Delta: the P6-T21 part. One stable branch, draft until QA, no `closes #N` heuristic, and a lookup error leaves the existing PR untouched. The creator, the empty patch, and the API fields are the P8-T09 part.

### DESIGN-012
- Severity: Med
- Section: P6-T06; P6-T07; P6-T08; P6-T10; P6-T22
- Owner: [ME]; P6-T10 is [PAIR]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P6-T06 | Treat webhooks as hints: enqueue a reconcile and return immediately | [ME] | build | 1 | P6-T05 | Handler returns 202 after enqueueing and does no GitHub reads inline; a test measures the handler time |
```

```
| P6-T07 | Build the reconciliation poller that rebuilds state from GitHub | [ME] | build | 3 | P6-T06 | Given only GitHub's state (issue, PR, run), the poller sets the workflow to the right state; tested with a dropped-webhook fixture |
```

```
| P6-T08 | Add the QA signal wait with a timeout | [ME] | build | 2 | P6-T03 | Workflow pauses in `awaiting-qa`, resumes on an approve or reject signal, and times out into a defined state |
```

```
| P6-T10 | Add the plain GitHub review-comment fallback for QA approval | [PAIR] | build | 1 | P6-T08 | A review comment with an approve keyword resumes the workflow; this path works without MCP |
```

```
| P6-T22 | Break it: deliver the same webhook twice | [ME] | test | 2 | P6-T06 | Second delivery is a no-op by idempotency key; written up |
```

```
2. **Duplicate webhook (P6-T22).** *Induced failure:* replay the same delivery id twice. *Expected signal:* the second delivery is dropped as already seen; one workflow exists. *Fix:* store the delivery id and key the workflow by ticket id.
```

- Proposed text:

```
| P6-T06 | Treat webhooks as hints: enqueue a reconcile and return immediately | [ME] | build | 1 | P6-T05 | Webhook and poller share `SetWorkflowID(ticket_id)`; handler returns 202 after enqueueing, without waiting, and does no GitHub reads inline; the delivery id is only a hint-dedup record; a test measures the handler time |
```

```
| P6-T07 | Build the reconciliation poller that rebuilds state from GitHub | [ME] | build | 3 | P6-T06 | Webhook and poller share `SetWorkflowID(ticket_id)`; given only GitHub's state (issue, PR, run), the poller sets the workflow to the right state; tested with a dropped-webhook fixture |
```

```
| P6-T08 | Add the QA signal wait with a timeout | [ME] | build | 2 | P6-T03 | Workflow pauses in `awaiting-qa`, resumes on an approve or reject signal, and times out into a defined state; the QA signal carries an idempotency key |
```

```
| P6-T10 | Add the plain GitHub review-comment fallback for QA approval | [PAIR] | build | 1 | P6-T08 | A review comment with an approve keyword resumes the workflow; this path works without MCP; the QA signal carries an idempotency key |
```

```
| P6-T22 | Break it: deliver the same webhook twice | [ME] | test | 2 | P6-T06 | Second delivery is a no-op; the delivery id is only a hint-dedup record; written up |
```

```
2. **Duplicate webhook (P6-T22).** *Induced failure:* replay the same delivery id twice. *Expected signal:* the second delivery is dropped as already seen; one workflow exists. *Fix:* store the delivery id as a hint-dedup record only, and key the workflow by ticket id.
```

The awaiting-qa sentence in P6-T08 is unchanged. FEAT-001 keeps that sentence.

### DESIGN-013
- Severity: Med
- Section: P6-T11; P6-T19
- Owner: [CLAUDE] (P6-T11); [ME] (P6-T19)
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P6-T11 | Set up Neon free Postgres with reconnect handling for scale-to-zero | [CLAUDE] | deploy | 2 | P6-T03 | Service connects over TLS, reconnects after the database suspends, and a test forces a suspended state |
```

```
| P6-T19 | Run crash-recovery experiment: kill the process at each step boundary | [ME] | eval | 3 | P6-T04, P6-T07 | Ablation table filled from real kills for the DBOS run and the non-durable run, counting completed runs and duplicate side effects |
```

- Proposed text:

```
| P6-T11 | Set up Neon free Postgres with reconnect handling for scale-to-zero | [CLAUDE] | deploy | 2 | P6-T03 | Chooses `use_listen_notify` before the first migration, pins a stable app version and executor id, and sets no conductor key on Render; service connects over TLS, reconnects after the database suspends, and a test forces a suspended state |
```

```
| P6-T19 | Run crash-recovery experiment: kill the process at each step boundary | [ME] | eval | 3 | P6-T04, P6-T07 | Ablation table filled from real kills for the DBOS run and the non-durable run, counting completed runs and duplicate side effects; a second GitHub call is asserted only for the kill that happens before the step result is stored |
```

### PLAN-004
- Severity: Med
- Section: budget line
- Owner: [CLAUDE]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
**Budget:** 52 h · **Weeks:** W20–23 in the base plan (calendar weeks in `TASKS.md` include the buffer) · **Packages:** `flow` (py, FastAPI + DBOS), uses `fix-loop`, `verify`, `repro-agent`
```

- Proposed text:

```
**Budget:** 52 h · **Weeks:** calendar weeks 22–24 · **Packages:** `flow` (py, FastAPI + DBOS), uses `fix-loop`, `verify`, `repro-agent`
```

### PLAN-016
- Severity: Med
- Section: P6-T18
- Owner: [ME]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P6-T18 | Write ADR-023: QA signal via MRTR or review comments | [ME] | doc | 1 | P6-T09, P6-T10 | ADR states which path ships, client support found in practice and the fallback |
```

- Proposed text:

```
| P6-T18 | Write ADR-023: QA signal via MRTR or review comments | [ME] | doc | 1 | P6-T10 when the MRTR cut is taken; otherwise P6-T09, P6-T10 | ADR states which path ships, client support found in practice and the fallback |
```

The −3 h stays unbooked. P6-T09 stays in this file.

### FEAT-001
- Severity: Low
- Section: P6-T08
- Owner: [ME]
- Hours delta: 0
- Replacement or cut: none; unestimated feature is not accepted
- Current text:

```
Workflow pauses in `awaiting-qa`, resumes on an approve or reject signal, and times out into a defined state
```

- Proposed text:

```
Workflow pauses in `awaiting-qa`, resumes on an approve or reject signal, and times out into a defined state
```

No per-edit confirm is added. The human wait stays on `awaiting-qa`.

Hours and tasks in this file: unchanged.
