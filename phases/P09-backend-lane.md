# P9 — backend lane (optional)

**Budget:** about 40 h · **Weeks:** the week-30 tail, then weeks 31–32 (first on the cut list) · **Packages:** reuses `argus-core`, `fix-loop`, `verify`, `eval`, `flow`; adds a small backend target and lane-specific tools

## Goal
Run a second lane, from a Sentry-style error event to a failing pytest to a verified fix, as a local loop, and measure how much was reused.

## Done when
- A small FastAPI target backend exists with 30 seeded or mutated bugs, each with a pytest that fails on the bug and passes on the golden fix, and the golden-fix run is green in CI with no LLM calls.
- A Sentry-style event (stack trace, request, breadcrumbs) is parsed into a Ticket from an exported JSON fixture; live Sentry is optional.
- The lane runs end to end on the 30 tasks: event, generated failing pytest, fix, verifier verdict.
- The reuse ratio is measured by a script (by module and by lines) and reported.
- Phase report filled against P8, with this lane reported separately from the UI lane.

## Agentic concepts learned
1. **Reuse across lanes** — what belongs in shared packages (loop, ledger, verifier interfaces) and what is lane-specific (tools, checks).
2. **Production signal as a ticket** — turning an error event into a reproducible test.
3. **Test generation as the repro step** — a pytest that fails on the bug, and why failing for the right reason matters.
4. **Verification for backends** — new test fails before and passes after, existing tests still pass, no new exception types.
5. **PII in observability data** — error events carry user data, so redaction comes before any model call.

## Interview questions
1. Which of your components were reused unchanged for the backend lane, which needed an interface change, and what does that say about your original boundaries?
2. A stack trace's top frame is in a library, not your code. How does the lane find the code that actually needs fixing?

## Prereq reading
- [SWE-agent: agent-computer interfaces](https://arxiv.org/abs/2405.15793)
- [ast-grep](https://ast-grep.github.io)
- [Building effective agents (Anthropic)](https://www.anthropic.com/engineering/building-effective-agents)

## Tasks
| ID | Title | Owner | Type | Est hrs | Depends on | Acceptance criteria |
|---|---|---|---|---|---|---|
| P9-T00 | Re-verify pinned versions via web search | [CLAUDE] | doc | 1 | P8-T25 | Versions table re-checked; FastAPI, pytest and Sentry event format notes updated; date updated |
| P9-T01 | Read the SWE-agent paper and the ast-grep docs, write notes | [ME] | learn | 1 | P9-T00 | Notes list which SWE-agent tool ideas apply to a Python backend and which ast-grep rules would find a null-dereference |
| P9-T02 | Define the backend Task variant: event, request payload and failing pytest as the check | [ME] | build | 3 | P9-T01, P0-T03 | Task schema extension validates a sample; existing UI tasks still validate unchanged |
| P9-T03 | Build the small FastAPI target backend with 6 endpoints and its test suite | [CLAUDE] | build | 3 | P9-T00 | `pytest` passes on the clean backend; endpoints cover auth, CRUD and one background job |
| P9-T04 | Build Python mutation operators (off-by-one, wrong status code, missing await, swapped arguments) | [PAIR] | build | 3 | P9-T02, P9-T03 | Each operator has a test; a validity filter keeps only mutants whose pytest fails before and passes after the golden fix |
| P9-T05 | Parse an exported Sentry event JSON into a Ticket | [PAIR] | build | 3 | P9-T02 | Parser handles stack trace, request and breadcrumbs from 5 fixture events; missing fields give typed errors; no live service is needed |
| P9-T06 | Build the trace-to-pytest agent: tool schemas and generator reusing the repro-agent loop | [ME] | build | 4 | P9-T05, P1-T07 | Given an event, it writes a pytest; the repro verifier from P1 is reused to confirm it fails on the bug and passes on the golden fix |
| P9-T07 | Reuse the P3 fixer with a pytest gate instead of the browser gates | [PAIR] | build | 3 | P9-T06, P3-T14 | The fixer runs on a backend task with only a new gate and new tool configs; no copy of the P3 code |
| P9-T08 | Build the backend verifier: new test fails before, passes after, old tests pass, no new exception types | [ME] | build | 3 | P9-T07, P4-T06 | Verdict has per-check results; four hand-broken patches exercise each failure |
| P9-T09 | Build 30 backend tasks and a golden-fix CI run | [PAIR] | build | 3 | P9-T04 | 30 tasks validate; CI runs all golden fixes with no LLM calls and is green |
| P9-T10 | Run the lane end to end on the 30 tasks and report | [ME] | eval | 3 | P9-T08, P9-T09 | Results JSON for the lane, produced with the P5 eval runner; resolve rate with interval, tokens/bug and latency percentiles |
| P9-T11 | Measure the reuse ratio by module and by lines | [ME] | eval | 2 | P9-T10 | A script walks imports and prints shared vs lane-specific modules and lines; output is committed |
| P9-T12 | Write ADR-030: Reuse boundary between lanes | [ME] | doc | 1 | P9-T11 | ADR names the interfaces that held, the ones that changed, and what moves into shared packages |
| P9-T13 | Break it: give an event whose top stack frame is in a library | [ME] | test | 2 | P9-T06 | The lane walks to the first application frame or fails with a typed reason; written up in the Break it section |
| P9-T14 | Break it: use a race-condition bug that fails intermittently | [ME] | test | 2 | P9-T09 | The flake detector flags the task and it is quarantined; written up |
| P9-T15 | Break it: put an email address and token in the event payload | [ME] | test | 2 | P9-T05 | Redaction removes both before any model call, checked on the stored prompt; written up |
| P9-T16 | Write package README and phase report against P8 | [CLAUDE] | doc | 1 | P9-T12 | README shows lane run commands and the reuse numbers script; phase report has previous-phase, this-phase and delta rows filled |

## Break it on purpose
1. **Library frame on top (P9-T13).** *Induced failure:* a stack trace whose top frame is inside a dependency. *Expected signal:* the lane skips to the first application frame, or returns a typed "no application frame" reason. *Fix:* frame filtering by project path, with the skipped frames shown in the ticket.
2. **Intermittent race (P9-T14).** *Induced failure:* a bug that only fails under timing. *Expected signal:* the flake detector marks mixed results and the task is quarantined. *Fix:* keep such tasks out of the resolve-rate set and report them separately.
3. **PII in the event (P9-T15).** *Induced failure:* an event with an email and a bearer token in the request. *Expected signal:* neither appears in the prompt stored in the trajectory. *Fix:* redact at ingestion, before the Ticket is built.

## Ablation
**Hypothesis:** most of the backend lane is shared code, which would show the P3 to P6 boundaries were drawn in the right places.
**Variants:** A = reuse measured by module (shared modules imported divided by all modules in the lane); B = reuse measured by lines of code.
**Metric:** reuse ratio, with resolve rate and tokens/bug reported alongside for the lane.

| Variant | Shared units | Lane-specific units | Reuse ratio | Resolve rate (95% CI) | Tokens/bug (in, out, cached) | $-equivalent/bug |
|---|---|---|---|---|---|---|
| A | — | — | — | — | — | — |
| B | — | — | — | — | — | — |

**Phase report (against previous phase):**

| Report | Resolve rate | Tokens/bug | $-equivalent | p50 latency | p95 latency |
|---|---|---|---|---|---|
| Previous phase | — | — | — | — | — |
| This phase | — | — | — | — | — |
| Delta | — | — | — | — | — |

## ADRs to write
All [ME].
- **ADR-030 — Reuse boundary between lanes.** Which interfaces held, which had to change, and what moves into shared packages?

## Deploy checkpoint
The golden-fix run for the backend tasks joins the existing GitHub Actions jobs. No new hosting.

## Portfolio artifact
A short write-up of the second lane with the reuse-ratio script output, showing the architecture generalised beyond UI bugs.
