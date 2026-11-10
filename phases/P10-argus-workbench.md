# P10 — argus-workbench

**Budget:** 42 h (estimate, not in the base plan) · **Packages:** `workbench` (py: FastAPI app on 127.0.0.1 plus a static page), uses `argus-core`, `verify`, `flow`, `app`, `fix-loop`, `eval`/`dashboard`

## Goal
Build the five-screen web UI from the explainer (`docs/notes/p10-spec.json`, key `finalUi` of `argus-explainer.html`, tab "UI by phase") as far as it can be real on one machine: type an issue, watch a run, review and decide, see the PR, read the history. Runs are scripted or replayed, never model runs. No real PR is created.

## Done when
- `argus-workbench serve` starts a local server on 127.0.0.1 with the five screens, each labelled BUILT / PARTLY BUILT / PLANNED from the spec.
- A typed issue becomes a ticket that passes `bench validate`, a scripted run plays on screen, the reviewer decides, a PR is built against the mock GitHub transport, and the run shows in the history.
- Every run the workbench makes is tagged SIMULATED or REPLAY and is in no aggregate. Metrics show a dash unless a real result file backs them.
- No model is called anywhere in P10, in code or in tests.
- Four break-its (inert rendering, upload refusal, request forgery, double approve) each fail on a mutated build.
- ADR-031 records that the workbench is local, file-backed and unauthenticated, and what that does not defend.
- Phase report filled against P8.

## Decisions made before the phase started
Owner can change any of these; a change is stated in the PR text.
1. Local only: FastAPI on 127.0.0.1 plus a static page (plain HTML, CSS, JS, no build step, like `packages/dashboard`). No login. Not a hosted service.
2. New package `packages/workbench` (`argus_workbench`, command `argus-workbench serve`). The run store is files under `.local/workbench/runs/<run_id>/` (git-ignored): `ticket.json`, `state.json`, `trajectory.jsonl`, `verdict.json`, `report.html`, `patch.diff`, `decision.json`, `pr.json`. Schemas come from `argus-core`, `verify` and `flow`; nothing is copied.
3. Runs are SCRIPTED or REPLAYED: `ScriptedRunner` (5 scenarios: normal, quota, stuck, verifier failed, judge disagrees), `ReplayRunner` (plays a stored `trajectory.jsonl`), and a `FixLoopRunner` adapter over `fix_loop.run_fix` tested with a scripted model only. Everything they produce is tagged SIMULATED or REPLAY and is in no aggregate.
4. No real PR: the PR screen uses the mock GitHub transport (`argus_app.pr`, `flow.github_write`). A real PR needs the registered App (owner step).
5. State names come from `flow.states`, not the explainer's proposed list. `quota-wait` and `stuck` are display states derived from the stop reason.
6. The ADR number is ADR-031 (ADR-030 is reserved for P9).

## Tasks
| ID | Title | Owner | Type | Est hrs | Depends on | Acceptance criteria |
|---|---|---|---|---|---|---|
| P10-T00 | Copy the spec into the repo, write the phase file and the waves note | [CLAUDE] | doc | 1 | P8-T25 | `docs/notes/p10-spec.json` holds `finalUi` (meta, triggers, stages, workflowStates, scenarios, sim, targets, screens, differsFromPlan); this file and `docs/notes/p10-waves.md` exist; one commit |
| P10-T01 | Scaffold `packages/workbench`, the run store and the run record | [CLAUDE] | build | 3 | P10-T00 | `argus-workbench --help` works; creating a run writes `ticket.json` and `state.json`, validated against `argus-core` and `flow.states`; a run id outside `[a-z0-9-]{1,64}` is refused (no path traversal); an unknown state is refused; the file layout is written in `docs/architecture/p10.md` as "Run folder contract" |
| P10-T02 | API server and page shell | [CLAUDE] | build | 3 | P10-T01 | Binds 127.0.0.1 only, with no option to bind elsewhere; five tabs, each labelled BUILT / PARTLY BUILT / PLANNED from the spec; every POST needs a per-start token; a Host header other than 127.0.0.1 or localhost is refused; CSP is `default-src 'self'` with no inline script; tests use the FastAPI test client |
| P10-T03 | Screen 1: New issue (typed intake) | [CLAUDE] | build | 3 | P10-T01 | Text is required and capped; a screenshot is optional, PNG or JPEG only, max 5 MB, checked by magic bytes; repo and route come from the allowed list in the spec; the free-tier acknowledgement is required; the stored ticket directory passes `bench validate`; each refusal is a typed error shown by its field |
| P10-T04 | Runner protocol, `ScriptedRunner`, `ReplayRunner`, scenarios | [CLAUDE] | build | 4 | P10-T01 | Each scenario ends in the state and stop reason the spec names; `trajectory.jsonl` validates against the trajectory schema; tokens in, out and cached per step; the quota scenario hard-stops through `argus_core.ledger` (`QuotaExceeded`); Stop ends a run; Retry makes a NEW run id and never mutates the old one; a SIMULATED or REPLAY tag is on every file |
| P10-T05 | `FixLoopRunner` adapter (scripted model only) | [CLAUDE] | build | 2 | P10-T04 | Wraps `fix_loop.run_fix`; no key, URL or model is read at import; the docstring and README say "never run against a real model"; a test drives it with a scripted model and the run folder validates; ticked only if shown |
| P10-T06 | Screen 2: Live run | [CLAUDE] | build | 3 | P10-T04 | The stage bar and step timeline update while a scripted run plays (poll or SSE; the code says which); tokens per step; the quota meter reads the ledger; stuck and quota-exhausted look different and say why; Retry is disabled in quota-wait; Stop works |
| P10-T07 | Screen 3: Review and decision | [CLAUDE] | build | 4 | P10-T01 | Four checks in order (pixel, overflow, axe, console) with the first failure reason; the judge label is advisory while alpha is uncalibrated; the before/after report is shown in a sandboxed frame; Approve is disabled when the verifier failed; when the judge disagrees, Approve needs a written reason; Request changes starts a new run with the note; Reject takes a listed reason; a decision is stored once per idempotency key |
| P10-T08 | Screen 4: PR raised | [CLAUDE] | build | 3 | P10-T07 | On approve the PR is built through `argus_app.pr` and the mock transport; title, one stable branch, draft, body (verdict, judge label, trajectory link, before/after), CI state ("not run" unless known), backport follow-up; an empty patch gives no PR; approving again updates the same PR; no network call |
| P10-T09 | Screen 5: History and dashboard | [CLAUDE] | build | 3 | P10-T01 | Run list with state and stop reason; four metrics (resolve rate with Wilson 95% interval, tokens per bug, latency, quota share) from real result files via the P5 dashboard data, a dash where none exists; simulated and replay runs are listed with a badge and are in no aggregate (tested); per-tenant quota share from the ledger tenant dimension |
| P10-T10 | Break it: script and markup render inert | [CLAUDE] | test | 2 | P10-T03, P10-T07 | Script and markup in ticket text, run id, reviewer note, report and PR body render inert on every screen; the test fails on a mutated build; write-up `docs/notes/p10-break-it-t10.md` |
| P10-T11 | Break it: hostile uploads | [CLAUDE] | test | 2 | P10-T03 | HTML named `.png`, an oversize file, SVG, a name with "..", and a zero-byte file are each refused with a typed error and nothing is stored; the test fails on a mutated build; write-up `docs/notes/p10-break-it-t11.md` |
| P10-T12 | Break it: forged requests | [CLAUDE] | test | 2 | P10-T02 | A POST without the token, with a wrong Origin, or with `Host: evil.example` (DNS rebinding) is refused and changes nothing; no CORS header for another origin; the test fails on a mutated build; write-up `docs/notes/p10-break-it-t12.md` |
| P10-T13 | Break it: double approve | [CLAUDE] | test | 2 | P10-T08 | Two approves with one key give one decision and one PR; two with different keys at once give one PR and a typed conflict; an approve after a failed verifier is refused by the SERVER; the test fails on a mutated build; write-up `docs/notes/p10-break-it-t13.md` |
| P10-T14 | End-to-end browser run | [CLAUDE] | test | 3 | P10-T03, P10-T06, P10-T07, P10-T08, P10-T09 | A browser walks issue, run, review, PR, history in the normal scenario and opens the quota, stuck, verifier-failed and judge-disagrees views; screenshots in `packages/workbench/docs/shots/` come from that run; if no browser is available the box stays unticked and the HTTP-level walk is the evidence |
| P10-T15 | Write ADR-031: the workbench is local, file-backed and unauthenticated | [CLAUDE] | doc | 1 | P10-T00 | ADR says the workbench is local, file-backed, unauthenticated; what is not defended (a hosted workbench); the typed-intake trust boundary; why runs are scripted by default; status proposed, "written by Claude, owner to decide" |
| P10-T16 | Package README, `docs/architecture/p10.md`, phase report against P8 | [CLAUDE] | doc | 1 | P10-T14 | README shows install, `serve`, the five screens and a table of each control and its state; `p10.md` has a `## P10-Txx` section per task; the phase report has previous, this and delta rows, with a dash where P8 has no number (P8 has no resolve rate, tokens or latency) |

## Break it on purpose
1. **Hostile text (P10-T10).** *Induced failure:* put `<script>`, an `onerror` image and `$(...)` in ticket text, a run id, a reviewer note, the report and the PR body. *Expected signal:* each renders as plain text on every screen; nothing runs. *Fix:* `textContent` only, a CSP with no inline script, a sandboxed frame for the report.
2. **Hostile uploads (P10-T11).** *Induced failure:* HTML named `.png`, 6 MB file, SVG, a name with "..", a zero-byte file. *Expected signal:* a typed error each, nothing on disk. *Fix:* magic bytes, size cap and a server-chosen file name.
3. **Forged requests (P10-T12).** *Induced failure:* POST without the token, with a foreign Origin, with `Host: evil.example`. *Expected signal:* refused, state unchanged, no CORS header. *Fix:* per-start token, Host and Origin allow-list.
4. **Double approve (P10-T13).** *Induced failure:* two approves with one key, two with different keys at once, an approve after a failed verifier. *Expected signal:* one decision and one PR; a typed conflict; a server refusal. *Fix:* idempotency key plus a lock around decide-and-open-PR; the server checks the verdict, not the button.

## ADRs to write
All [CLAUDE], status proposed, owner decides.
- **ADR-031 — The workbench is local, file-backed and unauthenticated.** What it defends, what it does not, and why runs are scripted by default.

## Deploy checkpoint
None. The workbench runs on 127.0.0.1 only. A hosted workbench, a login, and a real PR through the registered App are owner steps and out of scope for P10.

## Phase report (against previous phase)

| Report | Resolve rate | Tokens/bug | $-equivalent | p50 latency | p95 latency |
|---|---|---|---|---|---|
| Previous phase (P8) | — | — | — | — | — |
| This phase (P10) | — | — | — | — | — |
| Delta | — | — | — | — | — |

*Every cell is a dash until P10-T16 fills it from stored results only. P8 has no resolve rate, tokens or latency (see its report), and P10 makes no model run, so P10 has none either.*
