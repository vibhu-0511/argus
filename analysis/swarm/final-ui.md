# Final product UI: five screens, one flow

As of 2026-10-30. Lane: final-product. Data contract: `analysis/swarm/final-ui.json`. Prototype: `analysis/explainer-src/60-product.html` (route `#plan/product`).

**Honesty.** Nothing on these screens is a model result. P0 (bench) and P1 (repro, fixture replay) are the only built phases. Every screen is labelled BUILT TODAY, PARTLY BUILT or PLANNED (Pn). Mock values carry an ILLUSTRATIVE or SIMULATED tag. Metrics are '—' unless a run id backs them. No real PR is ever created by the prototype.

## The owner's flow vs the plan's flow

- **Owner flow (target).** Owner types an issue (text, optionally a screenshot) -> agent returns an HTML report with before and after on the UI -> owner verifies -> on satisfaction the agent raises the PR.
- **Plan flow (PLAN.md / PROJECT.md).** Labelled GitHub issue -> webhook hint -> durable DBOS workflow (Render + Neon) -> job on GitHub Actions -> draft PR -> QA signal (MRTR or review comment) -> ready PR -> backport bot.

Main path in the prototype is the owner flow. Each place where the plan differs carries a "differs from plan" note (D1 to D6 below).

```
1 Issue ──► 2 Run ──────────────────────────► 3 Review ──► 4 PR ──► 5 History
  text +     Reproduce  Locate  Fix  Verify     checks +     draft PR   resolve rate (Wilson),
  shot       (P1 fix.)  (P2)    (P3) (P4)       judge +      + CI +     tokens/bug, p50/p95,
  or label   quota, stop, retry, stuck          report       backport   gate; "—" unless real
```

## Build status at a glance

| Screen | Label | What exists today | Delivered by |
|---|---|---|---|
| 1 New issue | PARTLY BUILT | The Ticket schema and 30 seeded tickets exist (P0). No intake UI and no endpoint exist. | P0, P1, P8, P6, none |
| 2 Live run | PARTLY BUILT | Trajectory schema, StopReason enum, quota ledger and the repro stage exist today (fixture replay). Locate, Fix, Verify, workflow state and any UI do not. | P0, P1, P2, P3, P4, P5, P6 |
| 3 Review | PARTLY BUILT | Two real verdict types exist (bench scorer, repro). The four-check verifier verdict, judge and QA signal are planned. | P0, P1, P4, P6, P8, lane |
| 4 PR raised | PLANNED P8 | No PR-creation code exists. The prototype never calls GitHub. | P8, P6, P7 |
| 5 History + dashboard | PARTLY BUILT | One real aggregate exists (P0 one-shot baseline). Wilson interval code exists in bench. The dashboard (P5), regression gate (P5-T16) and run list (P6) do not. | P0, P1, P5, P6, P8 |

Stages inside screen 2: Reproduce = BUILT TODAY (fixture replay); Locate = PLANNED P2; Fix = PLANNED P3; Verify = PLANNED P4.

## 1. New issue

**Label:** PARTLY BUILT. The Ticket schema and 30 seeded tickets exist (P0). No intake UI and no endpoint exist.

**Purpose.** Turn a bug report into a Ticket. Text is required. A screenshot is optional. Pick the repo and the route to test, and acknowledge that only public or synthetic code goes through free tiers.

**Delivered by**

| Phase | Status | What | Source |
|---|---|---|---|
| P0 | BUILT TODAY | Ticket schema (id, text, optional screenshot); 30 seeded tickets; `bench validate <dir>` checks a task directory | `packages/argus-core/schemas/ticket.schema.json; packages/bench/README.md` |
| P1 | BUILT TODAY | Screenshot-in-ticket variant (text-plus-image) runs through repro, as fixture replay | `PLAN.md:352 (ADR-005); packages/repro-agent/README.md` |
| P8 | PLANNED | Labelled-issue intake (P8-T08); `.argus.yml` config with start command, test command, routes, budget (P8-T05); least-privilege App (P8-T02/T03) | `phases/P08-argus-app.md:38-44` |
| P6 | PLANNED | Webhook as hint, 202 return, reconcile poller (P6-T05..T07) | `phases/P06-argus-flow.md:41-43` |
| none | GAP (no task) | Typed-issue form with screenshot drop zone: no task owns it | `DESIGN-product.md owner flow` |

**Data fields** (real = schema name in the repo today; proposed = named by a phase task, schema does not exist yet)

| Field | Kind | Source |
|---|---|---|
| `ticket.id` | real | ticket.schema.json: string, minLength 1, required |
| `ticket.text` | real | ticket.schema.json: string, minLength 1, required |
| `ticket.screenshot.media_type` | real | ticket.schema.json Screenshot: string, minLength 1 |
| `ticket.screenshot.path` | real | ticket.schema.json Screenshot: string, minLength 1; relative to the task directory |
| `repo` | proposed | P8-T05 .argus.yml / config/platform.md binding |
| `target.route / viewport` | proposed | checks.json params.flow (e.g. /ops/radar); P4-T03 checks at 375 px |
| `meta.tier / archetype / source` | real | task.schema.json TaskMeta; set by bench, not by the person filing the issue |
| `ack.public_or_synthetic` | proposed | PLAN.md:14 free-tier training caveat |

**Actions**

- Type or paste the issue text
- Attach or drop a screenshot (read locally, never uploaded)
- Pick repo and route
- Switch trigger: type here / labelled GitHub issue
- Load the real BUG-17 ticket
- Start run (disabled until text and acknowledgement exist)

**States**

- `empty`: Start disabled; hint names what is missing (text, acknowledgement).
- `filled`: Ticket JSON preview shows exactly the schema fields that would be written.
- `bad-file`: Non-image or oversized file is refused with the reason; the form keeps the text.
- `github`: Trigger = labelled issue: no form; shows the label, the webhook-as-hint note and the reconcile fallback.
- `waking`: Render cold start (about one minute): 'service waking', not an error (PLAN.md:302).

**Edge cases**

- Ticket text is untrusted data for every later prompt; render as plain text, never HTML (ops-console E-notes; production.html:186).
- A ticket that contains `$(...)` or markup must not be executed or rendered (P8-T09 fixture).
- Screenshot may contain PII; free-tier prompts may be used for training, so the acknowledgement is mandatory on the personal profile.
- Duplicate submit of the same text: one workflow, keyed by ticket id (P6-T06 SetWorkflowID).
- Missing .argus.yml field (e.g. no test command): typed config error, no guessing (P8-T22).
- File size limit is not in any schema. 5 MB in the prototype is a proposal.

**Differs from plan**

- Owner flow types the issue here. PLAN.md has no typed intake; the labelled GitHub issue is the only intake (P8-T08). (`phases/P08-argus-app.md:44`)
- Pre-flight acknowledgement is not in the owner's description; it is forced by the free-tier training caveat. (`PLAN.md:14`)

## 2. Live run

**Label:** PARTLY BUILT. Trajectory schema, StopReason enum, quota ledger and the repro stage exist today (fixture replay). Locate, Fix, Verify, workflow state and any UI do not.

**Purpose.** Show where the run is: Reproduce, Locate, Fix, Verify. Step timeline with tool, tokens and stop reason, a quota meter, and Stop / Retry. Make stuck and quota-exhausted visible and different.

**Delivered by**

| Phase | Status | What | Source |
|---|---|---|---|
| P0 | BUILT TODAY | Trajectory schema (meta + steps, tokens_in/out/cached, stop_reason); quota ledger that hard-stops before a provider limit | `packages/argus-core/schemas/trajectory.schema.json; packages/argus-core/src/argus_core/ledger.py` |
| P1 | BUILT TODAY | Reproduce stage as fixture replay (host=fixture); real files: trajectory.jsonl, repro.spec.ts, verdict.json | `packages/repro-agent/runs/text-only/bug-17/` |
| P2 | PLANNED | Locate stage: data-src plugin + locate() MCP server | `PLAN.md:218` |
| P3 | PLANNED | Fix stage: agent loop, worktree + Docker sandbox, gates, context manager | `PLAN.md:219` |
| P4 | PLANNED | Verify stage | `PLAN.md:220` |
| P5 | PLANNED | Trajectory metrics, OTel spans, Langfuse trace link (P5-T07) | `PLAN.md:221` |
| P6 | PLANNED | Durable workflow and state machine; run list needs the FastAPI backend; stop and retry are workflow signals | `phases/P06-argus-flow.md:38-39` |

**Data fields** (real = schema name in the repo today; proposed = named by a phase task, schema does not exist yet)

| Field | Kind | Source |
|---|---|---|
| `meta.run_id / task_id` | real | trajectory.schema.json TrajectoryMeta |
| `meta.model / host / prompt_hash / git_commit / seed` | real | TrajectoryMeta; host=fixture marks a replay |
| `step.index / tool_name / tool_error / message / raw_response` | real | TrajectoryStep |
| `step.tokens_in / tokens_out / tokens_cached` | real | TrajectoryStep; cached defaults 0 |
| `step.stop_reason` | real | StopReason enum: submit, step-cap, token-cap, QuotaExceeded, stuck, consecutive-timeout, retry-cap, tool-unavailable |
| `ledger.models[model].requests / tokens / cached` | real | packages/repro-agent/runs/text-only/ledger.json; limits in docs/quotas.md |
| `workflow.state` | proposed | P6-T02 owns the list; only awaiting-qa and done are named |
| `run.attempt / elapsed / next_reset_utc` | proposed | ledger rolls on the UTC date (ledger.py) |

**Actions**

- Stop run (confirm)
- Retry (new run_id; the old run is never mutated)
- Open a stage to see its step detail
- Copy run_id
- Skip to end (prototype only)

**States**

- `normal`: Stages advance; tokens and meter update per step.
- `quota`: stop_reason QuotaExceeded; meter red; state quota-wait; Retry disabled with 'resets 00:00 UTC'.
- `stuck`: Repeated identical tool call highlighted; stop_reason stuck; Stop and Retry offered.
- `stopped`: Owner stopped the run: state failed with reason 'stopped by owner'.
- `replay`: host=fixture shows a permanent REPLAY badge and 'token counts not real'.

**Edge cases**

- Last step with null stop_reason: run still live or crashed; check freshness before saying running.
- Day roll (UTC midnight) in flight: meters show two segments.
- Duplicate webhook: one run row, toast 'duplicate delivery ignored'.
- Reconciled state differs from the webhook's: tag 'reconciled from GitHub'.
- Unknown model: ledger refuses, board says 'no quota row', not 0%.
- raw_response may carry page text: render as text only.
- Retry after quota exhaustion before reset is refused by the ledger, not by the button alone.

**Differs from plan**

- Plan runs the job on GitHub Actions; the owner's flow shows it live in one UI. A live feed from an Actions job to this page is not designed (the control plane is P6; artifacts return at the end, P6-T04). (`phases/P06-argus-flow.md:40`)
- Quota meter and quota-wait are on this screen; PLAN.md treats quota as a ledger and a doc, with a dashboard tile at P5. (`PLAN.md:288`)

## 3. Review

**Label:** PARTLY BUILT. Two real verdict types exist (bench scorer, repro). The four-check verifier verdict, judge and QA signal are planned.

**Purpose.** Give the owner enough to decide: the structured verdict (four checks), the judge label and its limits, the before/after fix report, then Approve, Request changes or Reject with reasons.

**Delivered by**

| Phase | Status | What | Source |
|---|---|---|---|
| P0 | BUILT TODAY | Bench Verdict {task_id, ok, checks[{type, ok, reason}], log}; scorer exit 0/1/2 | `packages/bench/src/argus_bench/verdict.py:13-24` |
| P1 | BUILT TODAY | Repro verdict enum valid | passes-on-bug | fails-on-golden | error | `packages/repro-agent/src/repro_agent/verify.py:16-20` |
| P4 | PLANNED | Structured verdict with per-check results and first-failure reason (P4-T06); judge (P4-T13/T14); best-of-k (P4-T19); retry on rejection (P4-T22) | `phases/P04-verify.md:41` |
| P6 | PLANNED | QA signal wait with timeout and idempotency key (P6-T08); MRTR elicitation (P6-T09) or review-comment fallback (P6-T10); ADR-023 picks | `phases/P06-argus-flow.md:44-46` |
| P8 | PLANNED | Before and after screenshots in the PR (P8-T09) | `phases/P08-argus-app.md:45` |
| lane | PLANNED | Standalone HTML fix report, designed in the fix-report lane | `#plan/report; 142-fix.html (hand-made sample)` |

**Data fields** (real = schema name in the repo today; proposed = named by a phase task, schema does not exist yet)

| Field | Kind | Source |
|---|---|---|
| `verdict.checks[].name` | proposed | P4-T06: pixel | overflow | axe | console |
| `verdict.checks[].status` | proposed | pass | fail | error | skipped; error is never shown green (P4-T28) |
| `verdict.checks[].route / detail / rule_ids` | proposed | P4-T04 axe rule ids; P4-T25 names the route |
| `verdict.first_failure / short_circuited` | proposed | P4-T06 |
| `verdict.checks[].type / ok / reason` | real | bench Verdict: pixel_diff | bounding_box | computed_style |
| `judge.label / family / model` | proposed | PLAN.md:33; label pass | fail | error |
| `judge.alpha / order_disagreement` | proposed | P4-T14; shown as '—' until a calibration run exists |
| `qa.decision / reason / reviewer / idempotency_key / ts` | proposed | P6-T08: signal carries an idempotency key |

**Actions**

- Approve (optional note; required note when the judge disagrees)
- Request changes (reason required; re-runs with your note)
- Reject (reason required, min 10 characters)
- Choose the QA signal channel: MRTR or review comment (ADR-023)
- Open the fix report (#plan/report)
- Open the trajectory (screen 2)

**States**

- `normal`: Four checks pass; judge pass labelled advisory until alpha is calibrated; Approve enabled.
- `verifier`: A check fails: verdict fail, first failure named with its route, Approve disabled; one retry or Reject.
- `judge`: Checks pass, judge fails: red judge card, Approve needs a written reason; the verdict itself is not changed by the judge.
- `error`: A check or the judge is `error` (backend down): amber, never green; decide on checks only.
- `timed-out`: awaiting-qa past the QA timeout: buttons replaced by 'Re-request review' (P6-T08).
- `decided`: 409: another reviewer already decided; show the winner and close the pane.

**Edge cases**

- Judge disagrees with passed checks: label shown, verdict unchanged (P4 goal).
- alpha below 0.80: judge card says advisory only (ADR-013).
- Font-loading flake: pixel diff red but the diff shows text only: offer one re-run and count it (P4-T26).
- Missing before or after image: the check is `error`, never `pass`.
- Ticket text carrying an injected instruction is shown as plain text; flagged if the judge output echoes it (P4-T27).
- Confidence limits: a resolve rate on n tasks is shown with its Wilson interval; a difference smaller than the interval is 'no difference' (PLAN.md:286).

**Differs from plan**

- Owner reviews a before/after HTML report before any PR exists. In the plan the review happens on a draft PR via MRTR or a review comment. (`phases/P06-argus-flow.md:44-46,57`)
- 'Request changes' has no task; the plan's QA signal is approve or reject. (`phases/P06-argus-flow.md:44`)
- Before/after in the owner's description is on the production UI. The plan screenshots the synthetic dcortex cell; see D4. (`config/platform.md; PLAN.md:14`)

## 4. PR raised

**Label:** PLANNED P8. No PR-creation code exists. The prototype never calls GitHub.

**Purpose.** After approval, show the pull request the agent raises: title, one stable branch, body with verdict, judge label, trajectory link and before/after, CI state, and the backport follow-up.

**Delivered by**

| Phase | Status | What | Source |
|---|---|---|---|
| P8 | PLANNED | PR creation through the API with title and body as JSON fields; one stable branch; one creator that is not the agent; draft until QA; no PR when the patch is empty; re-run updates the same PR (P8-T09) | `phases/P08-argus-app.md:45` |
| P6 | PLANNED | find-or-create PR on one stable branch, survives a crash between side effect and state save (P6-T21) | `phases/P06-argus-flow.md:57` |
| P8 | PLANNED | Backport bot: PR to a configured branch on a merged fix; comment on conflict, never force (P8-T10, P8-T23) | `phases/P08-argus-app.md:46,59` |
| P7 | PLANNED | Least-privilege token scopes, audit log (ADR-026) | `PLAN.md:373` |

**Data fields** (real = schema name in the repo today; proposed = named by a phase task, schema does not exist yet)

| Field | Kind | Source |
|---|---|---|
| `pr.title / pr.body` | proposed | P8-T09: JSON fields, never shell-interpolated |
| `pr.branch` | proposed | P6-T21 / P8-T09: one stable branch |
| `pr.draft` | proposed | P6-T21: draft until QA |
| `pr.body.verdict / judge label / trajectory link / before / after` | proposed | PROJECT.md:19; P8-T09 |
| `pr.ci[]` | proposed | tenant CI; Argus gate P5-T17 |
| `backport.target / status / conflict` | proposed | P8-T10, P8-T23 |

**Actions**

- Mark ready for review (owner flow step)
- Open the trajectory link
- Simulate: owner merges the PR
- Backport to a configured branch (simulated; conflict toggle)
- Back to history

**States**

- `no-pr`: Rejected, not approved, or empty patch: 'No PR'; no PR is created for an empty patch (P8-T09).
- `draft`: Draft PR; CI pending/running/passed (simulated).
- `ready`: Ready for review; merge is the owner's action, not Argus's.
- `merged`: Backport button becomes available.
- `conflict`: Backport conflict: the bot comments and leaves branches untouched.

**Edge cases**

- Re-running updates the same PR; no second PR (P8-T09, P6-T21).
- A lookup error leaves the existing PR untouched (P6-T21).
- PR title containing `$(...)` is not executed (P8-T09, P8-T20).
- Worker crash after the PR is opened but before state is saved: restart finds the PR by its stable branch (P6-T21).
- Backport head is a branch the tenant workflow is allowed to test (ADR-027).

**Differs from plan**

- Owner flow raises the PR after approval. The plan opens the PR as a draft before QA and QA happens on it. (`phases/P06-argus-flow.md:57; P08:45`)
- No task makes Argus merge. Merge is shown as the owner's action. (`phases/P08-argus-app.md:34-62 (no merge task)`)

## 5. History + dashboard

**Label:** PARTLY BUILT. One real aggregate exists (P0 one-shot baseline). Wilson interval code exists in bench. The dashboard (P5), regression gate (P5-T16) and run list (P6) do not.

**Purpose.** Past runs with their stop reasons, and the four contract metrics with their limits. Everything is '—' unless a real run backs it. Simulated runs are listed but excluded from every aggregate.

**Delivered by**

| Phase | Status | What | Source |
|---|---|---|---|
| P0 | BUILT TODAY | Wilson 95% interval in batch scoring; one-shot baseline row 0/10; quota ledger.json | `phases/P00-argus-bench.md:85; analysis/swarm/ops-console.md section 5` |
| P1 | BUILT TODAY | Repro batch verdicts (fixture replay) under a REPLAY badge | `packages/repro-agent/runs/` |
| P5 | PLANNED | Results JSON (P5-T04), report generator (P5-T05), regression gate (P5-T16/T17), static dashboard (P5-T21), GitHub Pages (P5-T22) | `phases/P05-argus-eval.md:42,53-54,58-59` |
| P6 | PLANNED | Run board with ticket states needs the FastAPI backend; the static dashboard cannot list live runs | `analysis/swarm/ops-console.md section 7` |
| P8 | PLANNED | Per-tenant quota share per bug | `phases/P08-argus-app.md:74` |

**Data fields** (real = schema name in the repo today; proposed = named by a phase task, schema does not exist yet)

| Field | Kind | Source |
|---|---|---|
| `resolve rate (resolved/attempted) + Wilson 95% CI` | real | PLAN.md:278; batch.py |
| `tokens/bug in, out, cached (separate)` | real | PLAN.md:279 |
| `$-equivalent` | proposed | '—' until P5-T11 (prices.json) |
| `p50 / p95 latency` | real | PLAN.md:281; quota wait excluded |
| `regression gate result` | proposed | P5-T16: fails below baseline lower bound |
| `run.run_id / task_id / model / host / stop_reason` | real | trajectory.schema.json |

**Actions**

- Open a run (drawer)
- Include simulated runs in the table (never in aggregates)
- Filter by host (live / replay / simulated)
- Start another issue

**States**

- `empty`: All cells '—' with the banner 'no run id backs any number yet' (P5-T05 empty template).
- `partial`: Real P0 row and P1 replay row shown, each with its label.
- `gate-fail`: Gate red names the rule and numbers; no override unless ADR-017 names who.
- `stale`: Static dashboard older than the latest results commit: stale pill.

**Edge cases**

- n too small: 0/1 gives [0.000, 0.793]; a difference smaller than the interval is 'no difference' (PLAN.md:286).
- Recorded -0.000000 lower bound is clamped at 0 on screen.
- Fixture replay must never be merged with live runs in an aggregate (ops-console E1).
- Mixed hosts in one table: split by host.
- Cached tokens appear in their own column even when they do not count against the cap.
- Quota resets on the UTC date while the provider's daily window may differ (docs/quotas.md); show both.

**Differs from plan**

- The plan's dashboard is a static GitHub Pages site; a live run history from the product needs the P6 backend, so History and Dashboard are two surfaces in the plan. (`PLAN.md:45; analysis/swarm/ops-console.md section 7`)
- Owner flow puts history next to the issue form; the plan places it at P5, before the workflow exists. (`phases/P05-argus-eval.md:58`)

## Differs from plan, consolidated

| # | Topic | Owner flow | Plan | Source | How the prototype shows it |
|---|---|---|---|---|---|
| D1 | Trigger | Owner types the issue in Argus. | A labelled GitHub issue on an installed repo is the only intake. | `phases/P08-argus-app.md:44; PROJECT.md:11` | Shown as a two-way trigger switch on screen 1. Typed intake has no task and needs a backend (the dashboard is static). |
| D2 | Where the report goes | Owner reads an HTML before/after report first, then PR is raised. | The PR body carries verdict, judge label, trajectory link and two screenshots; the report file is attached to the PR. | `phases/P08-argus-app.md:45; production.html:377` | Screen 3 links the report lane (#plan/report) as a pre-PR artifact; screen 4 shows the plan's PR body. |
| D3 | PR timing | PR is raised after the owner approves. | PR is opened as a draft by one stable branch find-or-create and stays draft until the QA signal. | `phases/P06-argus-flow.md:57; P08:45` | Screen 4 opens the PR on approve as a draft with a 'Mark ready' step, and names the plan's earlier-draft alternative. |
| D4 | 'Production UI' vs the synthetic-only rule | Before and after are shown on the production UI. | Free-tier prompts may be used for training, so only synthetic or public code goes through them; the P8 target is one of your own public repos; bench runs the dcortex synthetic cell. | `PLAN.md:14; config/platform.md; phases/P08-argus-app.md:94` | Screen 1 requires a 'public or synthetic only' acknowledgement. Real production screenshots would break this rule; this is a gap to decide, not to hide. |
| D5 | Request changes | Owner can ask for changes. | The QA signal is approve or reject. Only one verifier-driven retry exists inside the loop. | `phases/P06-argus-flow.md:44; phases/P04-verify.md:57` | 'Request changes' re-runs with the reviewer note as extra context. It is new; no task owns it. |
| D6 | Quota is a first-class screen state | Not mentioned. | A shared ledger hard-stops a run before a provider limit; P8 adds per-tenant budgets. | `PLAN.md:288; phases/P08-argus-app.md:57` | Screen 2 shows a quota meter and the quota-wait state. |

## State switcher (prototype)

| Scenario | Effect | Source |
|---|---|---|
| Normal | All four stages finish; four checks pass; judge label pass. Approve is enabled. | `PROJECT.md:13-19` |
| Quota exhausted | Run stops in Fix with stop_reason QuotaExceeded. State quota-wait. Retry is disabled until the UTC reset; no retry spam. | `PLAN.md:288; packages/argus-core/src/argus_core/ledger.py (QuotaExceeded message)` |
| Stuck | Run repeats one tool call in Locate until stop_reason stuck. Stop and Retry (new run_id) are offered; the old run is never mutated. | `trajectory.schema.json StopReason; ops-console.md section 2 'Stuck run'` |
| Verifier failed | Overflow check fails on a second route (collateral damage). Verdict is fail, Approve is disabled, no PR is offered; one retry with the reason in context is allowed. | `phases/P04-verify.md:60 (P4-T25), :57 (P4-T22)` |
| Judge disagrees | All four checks pass, judge says fail. The judge does not override a passed check run, so Approve stays enabled but needs a written reason; the card says advisory while alpha is not calibrated. | `phases/P04-verify.md:6,12` |

## Real artifacts used

- Ticket: `packages/bench/tasks/seeded/bug-17/ticket.json` (id BUG-17). The prototype's "Load BUG-17" shortens the text; Shortened for the form: the real ticket.json text is longer (it also lists Horizon, Flights, Control Tower and admin tags).
- Before image: `packages/bench/tasks/seeded/bug-17/shots/radar-card.png`, loaded by relative path with a drawn fallback. There is no real "after" image in the repo; the after panel is illustrative.
- Fixture trajectory: `packages/repro-agent/runs/text-only/bug-17/trajectory.jsonl` (host=fixture, 1 step, tokens 1/1). This is the canned fixture reply: one hard-coded 'Sign in' script for every task, unrelated to the font-size bug. 'valid' is a fixture outcome, not a model result.
- Quota limits for `openai/gpt-oss-20b`: requests/day 1000, tokens/day 200000, requests/min 30, tokens/min 8000 (`docs/quotas.md`). requests_per_day and tokens_per_minute from response headers 2026-10-29; tokens_per_day and requests_per_minute are the published table, not measured.
- P0 one-shot baseline, variant A (seeded tasks): 0/10, recorded CI [-0.000000, 0.277540], shown clamped [0.000, 0.278]; tokens/bug 4585/1044/0; p50 3.652305 s, p95 4.842286 s (`phases/P00-argus-bench.md:85`). The recorded lower bound -0.000000 is a formatting artefact; batch.py clamps at 0. 'attempted' excludes tasks never applied. Not a fixer result, a one-shot baseline.
- P1 repro verdicts (fixture replay): {"valid":28,"passes-on-bug":1,"error":1} of 30. Same counts in text-only and text-plus-image because the reply is canned. Never shown as a resolve rate.

## Open decisions this prototype surfaces

1. **Typed intake has no owner.** Pick: a form on the P6 FastAPI service, or keep labelled-issue-only and have the owner file a GitHub issue (D1, D6 backend need).
2. **PR timing** (D3): draft before QA (plan) or after approval (owner). Affects P6-T08 and P8-T09 acceptance wording.
3. **"On the production UI"** (D4) conflicts with the synthetic-or-public-only rule on free tiers. Decide whether before/after is ever taken from a real production page.
4. **Request changes** (D5) needs a task and a state-machine edge (P6-T02).
5. **Live run feed**: Actions jobs return artifacts at the end (P6-T04); a live timeline needs a streaming design that is not planned.

## Dcortex patterns borrowed

From `analysis/swarm/ops-console.md` section 0.2 (read-only sibling files, no credential files): Shell + rail (`Shell.tsx`), KPI strip (`radar.css`), review queue and decision pane (`ReviewSidebar`, `radar-locked`), run detail with log lines (`RunDetailPage`), stuck-run recovery (`recoverStaleJobRuns.ts`), orphan-stop confirm (`AdminHealth.tsx`), usage tiles with UTC-day quota note (`MyUsage.tsx`), 409 already-decided path (`DeskCasePane.tsx`). Not found in dcortex: a before/after screenshot review; that part is new for Argus.
