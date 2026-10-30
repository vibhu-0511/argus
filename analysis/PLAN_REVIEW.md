# Plan review

Phase 6 of the planning review. Nothing in `PROJECT.md`, `PLAN.md`, `TASKS.md`, `phases/`, or the HTML files has been edited. Apply only after this file is approved.

Source of the verdicts: `analysis/verification_report.md`. 54 APPROVED, 21 NEEDS-NUANCE, 1 REJECTED-breaks-constraint (DESIGN-003), 1 REJECTED-already-covered (FEAT-001).

## Apply before P0 starts

Approved FACT and PLAN items, plus approved High RISK items. Each line is a wording change. Hours delta is 0.

High RISK that is not in this list: RISK-001 and RISK-005 are High and NEEDS-NUANCE, so they wait on the first open question.

- FACT-001 — `PLAN.md` versions: React 19.2.7 becomes 19.3.1, and the React 19 source-mapping note is re-checked rather than assumed.
- FACT-002 — Vite 8.3 becomes 8.3.5.
- FACT-003 — Playwright 1.63.0 becomes 1.64.1. P1-T00 remains the spike check.
- FACT-004 — MCP Python SDK v2.2.0 becomes 2.3.0.
- FACT-005 — Groq row: Developer-plan organization limits, `openai/gpt-oss-20b` and `qwen/qwen3.8-27b`, RPM 30, RPD 1K, TPM 8K, TPD 200K, cached tokens excluded. Drop "free tier" and Qwen3.6-27B. No other number is filled in.
- FACT-006 — Neon: "100 CU-hours/project". Drop "per month".
- FACT-007 — Render cold start: "about one minute". Drop "30 to 60 seconds".
- FACT-008 — Drop "Rolldown-based" until a fetched page states it. Same version cell as FACT-002.
- FACT-009 — Do not say Playwright bundles MCP, and do not treat the 2026-10-01 row as proof the pinned server speaks spec 2026-07-28.
- FACT-010 — OTel GenAI semconv: development status, no stable release, and the June 2026 move stay marked not stated.
- FACT-011 — The fixer row does not cite the Mistral pricing page for Devstral names, Apache-2.0, or 68–72%. No replacement score.
- FACT-012 — Do not cite MIT from the Langfuse pricing page. The 50k Hobby figure stays.
- FACT-013 — Do not state `/dev/kvm` since October 2025 as fetched from the Actions billing page.
- PLAN-001 — Stop equating 28 × 20 h with 556 h. Keep 556 h and 255 tasks.
- PLAN-002 — Name the weeks under 20 h. Keep 556 h and 596 h.
- PLAN-003 — The spec-support note for ADR-004 moves onto P1-T02 and off P2-T00.
- PLAN-004 — P6's weeks line says calendar weeks 22–24.
- PLAN-005 — P9's weeks line names the week-30 tail (5 h). 40 h stays.
- PLAN-006 — P7-T04 in week 24 does not require an App. The task does not move.
- PLAN-007 — Remove the dashed P6-to-P9 edge. No flow task is added.
- PLAN-008 — Draw P5.5 to P6. Drop the P4-to-P6 and P5-to-P6 arrows.
- PLAN-009 — P4-T02 passes when the only difference is inside the mask, and fails when a 4 px shift is outside it. Same row as DESIGN-008.
- PLAN-010 — The archetype check moves onto P0-T13. P0-T12 stays the document.
- PLAN-011 — Risk register gains the single laptop CPU, pointing at P4-T13 and P2-T10. No second computer.
- PLAN-012 — Risk 1 names Actions minutes and public-repo policy as the one execution plane.
- PLAN-013 — Risk register gains the Langfuse 50k cap, pointing at the existing Phoenix swap.
- PLAN-014 — Cut 3 retargets P6-T00 and P7-T07 before P5.5 can be removed. The −28 h stays unbooked.
- PLAN-015 — P7-T13 may leave row C empty when the Firecracker cut is taken. P7-T11 stays. The −3 h stays unbooked.
- PLAN-016 — When the MRTR cut is taken, P6-T18 depends only on P6-T10. The −3 h stays unbooked.
- PLAN-017 — Cut 2 names P8-T07, P8-T14, and P8-T21, and drops P8-T07 from P8-T20. The −6 h stays unbooked.
- PLAN-018 — "Two hosts per role" narrows to the judge and the embeddings. No new fixer or cheap-tier host.
- PLAN-019 — A Playwright MCP no-go is ADR-004. No direct-Playwright build task is added.
- PLAN-021 — The metrics contract lists four numbers. Quota share is not a required fifth. No JSON field is added.
- PLAN-022 — Remove the P9 dashboard second series and the P0 "OTel helpers" placement. Both stay on the P5 tasks that already schedule them.
- PLAN-025 — Checks run first. Best-of-k stays inside the P4-T19 selector. The judge does not override a passed check run.
- PLAN-026 — The production verify step lists warnings with new console errors. The fix gate lists bench checks with the unit tests.
- RISK-002 — P7-T03 forbids a token in a remote URL. P7-T04 states scopes before the first push. Same P7-T04 row as PLAN-006.
- RISK-003 — The agent step has no `GITHUB_TOKEN`. ADR-026 names the principal that pushes.
- RISK-004 — P8-T09 and P8-T20 build the PR through the API, with title and body as JSON, and a `$(...)` title fixture must not execute.

Approved Medium risks, same zero-hour wording, not in the High list above:

- RISK-006 — P3-T06 and P3-T32 name a per-command timeout, a consecutive-timeout stop distinct from `stuck`, and a rejection for interactive commands. No new integer.
- RISK-007 — P6-T21 and P8-T09 use one stable branch, a creator that is not the agent, draft-until-QA, no PR on an empty patch, and a lookup error that leaves the existing PR.

## Per-phase changes

Approved DESIGN and EDGE items only. CUT is empty. FEAT-001 is rejected below.

- P0 — EDGE-001: `bench score` keeps the unsliced log (P0-T15).
- P1 — EDGE-004: a bad image is a typed tool error when the bytes do not match the declared media type (P1-T06). EDGE-006: a server exit between calls is the existing `tool-unavailable` stop (P1-T15).
- P2 — DESIGN-014: repo-relative `file:line:col`, no tag suffix, plugin absent from production, `locate()` stays the Python tool (P2-T02, P2-T08, ADR-006).
- P3 — EDGE-011: a provider payload with no `choices` is a typed error and the run does not crash (P3-T30).
- P4 — DESIGN-008 and PLAN-009: mask, ratio-with-unit, no scaling, fringe cap, repeated fingerprint stays a hard failure (P4-T02, ADR-012). DESIGN-010: order-disagreement rate beside α, a disagreeing pair is not averaged, an unparsed judge string stays in the denominator as `error` (P4-T24, ADR-013). EDGE-001: P4-T23 exits non-zero on a bad pair or a bad verdict file. EDGE-002: keep the font wait, and add a fringe-under-cap pass plus a different font family that still fails (P4-T26).
- P5 — DESIGN-016: the multimodal adapter pins split `dev`, records exclusions, and keeps the gold patch out of the prompt (P5-T19).
- P6 — DESIGN-012: webhook and poller share `SetWorkflowID(ticket_id)`, the handler returns 202, the QA signal carries an idempotency key (P6-T06, P6-T22, ADR-021, ADR-023). DESIGN-013: choose `use_listen_notify` before the first migration, pin app version and executor id, no conductor key on Render, and a second GitHub call only for a kill before the step result is stored (P6-T14, P6-T19, ADR-022).
- P7 — DESIGN-011: three static injection cases, graded by deterministic assertions, no generator and no LLM rubric (P7-T07, ADR-024).
- P8 — EDGE-013: the backport head is a branch the tenant workflow is allowed to test (ADR-027).
- P9 — none.

## Considered and rejected

- DESIGN-003 — REJECTED-breaks-constraint. The proposal writes stuck detection as 3 identical calls and calls that 3 a planning choice. No source link. The task stays unnumbered until you answer question 2.
- FEAT-001 — REJECTED-already-covered. The human wait stays on `awaiting-qa`. No per-edit confirm.
- RISK-001, RISK-005, DESIGN-001, DESIGN-002, DESIGN-004, DESIGN-005, DESIGN-006, DESIGN-007, DESIGN-009, DESIGN-015, EDGE-003, EDGE-005, EDGE-007, EDGE-008, EDGE-009, EDGE-010, EDGE-014, PLAN-020 — NEEDS-NUANCE at review time, because each replacement omitted another clause on the same row. Merged in `analysis/merges.md` and applied. Hours delta 0.
- EDGE-012 — NEEDS-NUANCE at review time. The opened lines show `--force` and a stale-branch retry. The applied test names those two. It does not name `theirs` or committing conflict markers.
- PLAN-023 — NEEDS-NUANCE. The quoted state card drops `locate`, and the remaining locate wires and the production Locate step would still be there.
- PLAN-024 — NEEDS-NUANCE. One opener sentence is right, and `142-fix.html` would still remain as an artifact and an iframe outside the quoted span.

## New totals

| | Hours | Tasks |
|---|---:|---:|
| Core P0–P8, before and after | 556 | 255 |
| P9, before and after | 40 | 17 |
| Grand total, before and after | 596 | 272 |

The calendar stays the one already printed: core work through week 30, with week 30 already holding 5 h of P9, then weeks 31–32 for the rest of P9. No week count is added. The hard cut after P6 still holds: P7 (44 h / 23 tasks) and P8 (60 h / 26 tasks) stay after P6, and no cut is booked.

## Open questions

1. Apply only the 54 APPROVED items now, and hold the 21 NEEDS-NUANCE rows until each shared task row is one merged replacement? Or merge those rows first and apply them in the same pass?
2. DESIGN-003 was rejected because the stuck count of 3 has no source in the proposal. Leave P3's stuck task without a number, or name a count you accept?
3. For the HTML, stop at the quoted card and step, or also remove the remaining locate wires and the `142-fix.html` artifact and iframe?

## Changed files

Applied on approval of the recommendations: the 54 approved wording fixes, the fuller HTML cleanup for PLAN-023 and PLAN-024, and no stuck-detection number. Core totals remain 556 h and 255 tasks.

The 19 NEEDS-NUANCE rows are applied from `analysis/merges.md`, one replacement per shared task. Hours delta 0. EDGE-012's test names a force-push of the bot branch and a stale-branch retry. It does not name `theirs` or committing conflict markers. DESIGN-003's stuck count and FEAT-001's per-edit confirm stay unapplied.

- `PLAN.md`
- `PROJECT.md`
- `PROJECT.html`
- `TASKS.md`
- `phases/P00-argus-bench.md`
- `phases/P01-repro-agent.md`
- `phases/P02-dom2src.md`
- `phases/P03-fix-loop.md`
- `phases/P04-verify.md`
- `phases/P05-argus-eval.md`
- `phases/P06-argus-flow.md`
- `phases/P07-argus-guard.md`
- `phases/P08-argus-app.md`
- `phases/P09-backend-lane.md`
- `architecture.html`
- `production.html`
- `analysis/merges.md` (the 19 shared-row replacements)
