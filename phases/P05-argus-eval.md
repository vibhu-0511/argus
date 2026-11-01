# P5 — argus-eval

**Budget:** 64 h · **Weeks:** W16–19 in the base plan (calendar weeks in `TASKS.md` include the buffer) · **Packages:** `eval` (py), `dashboard` (static), OTel helpers in `argus-core`

## Goal
Measure the whole pipeline at trajectory level with traces and a CI regression gate, then test whether routing cheap and strong models beats a single strong model.

## Done when
- Trajectory metrics (steps, tool-error rate, redundant-call rate, stuck rate, recover-after-gate-failure rate) are computed for every stored P3 and P4 trajectory.
- Spans for one full run appear in Langfuse Cloud Hobby, and the same spans load in a second OTLP backend through the attribute normalizer (the swap proof).
- Prompt caching is designed so cached tokens are counted separately in the ledger, and the router sends stages to a cheap or strong tier by written policy.
- The routing ablation is run on the 30-task subset and the table is filled.
- A CI regression gate fails on a deliberately worse stored run and passes on the baseline run.
- A SWE-bench Multimodal subset of 10 to 20 tasks is run, with excluded tasks and reasons listed.
- The dashboard is live on GitHub Pages and shows the phase-over-phase report.
- Phase report filled against P4.

## Agentic concepts learned
1. **Trajectory-level evaluation** — scoring how the agent got there, not only whether it did.
2. **OTel GenAI semantic conventions** — development status is not stated; how to keep traces portable with a normalizer.
3. **Routing** — which stages can go to a cheap model without losing the result.
4. **Prompt caching as a quota lever** — on a free tier where cached tokens don't count against the cap, a stable prefix is a measurable saving.
5. **Regression gating with statistics** — comparing a run to a baseline using intervals, not point estimates.

## Interview questions
1. Why evaluate trajectories and not only the final resolve rate? Give two failure patterns that an outcome metric hides.
2. The GenAI semantic conventions are still in development. How do you keep traces and dashboards from breaking when an attribute is renamed or the backend changes?

## Prereq reading
- [OpenTelemetry GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
- [Engineering Reliable Coding Agents](https://arxiv.org/abs/2608.13867)
- [SWE-bench Multimodal](https://arxiv.org/abs/2410.03859)

## Tasks
| ID | Title | Owner | Type | Est hrs | Depends on | Acceptance criteria |
|---|---|---|---|---|---|---|
| P5-T00 | Re-verify pinned versions via web search | [CLAUDE] | doc | 1 | P4-T29 | Versions table re-checked; OTel GenAI semconv status and repo location, Langfuse Hobby limits and Groq free-tier limits confirmed; date updated |
| P5-T01 | Read the OTel GenAI conventions and the reliable-agents paper, write notes | [ME] | learn | 1 | P5-T00 | Notes list the span and attribute names this project will use and which are still marked development |
| P5-T02 | Define trajectory metrics with exact formulas | [ME] | eval | 3 | P5-T01, P3-T08 | `docs/metrics.md` defines each metric as a formula over a trajectory file, with one worked example from a stored trajectory |
| P5-T03 | Implement trajectory metrics over stored JSONL | [ME] | build | 3 | P5-T02 | CLI prints all metrics for a trajectory directory; unit test matches the worked example from T02 |
| P5-T04 | Build eval runner with aggregation and Wilson confidence intervals | [ME] | build | 3 | P5-T03, P0-T15 | Runner takes a task list and an agent config, writes one results JSON with resolve rate, interval, tokens and latency percentiles; tested on a stub agent |
| P5-T05 | Build phase-over-phase report generator (markdown from results JSON) | [PAIR] | build | 2 | P5-T04 | Given two results files it prints the previous, this and delta rows; given none it prints the empty template |
| P5-T06 | Instrument the loop and tools with OTel spans using GenAI attributes | [ME] | build | 3 | P5-T01, P3-T06 | A run emits a span per model call and per tool call with model, token counts and stop reason; spans are visible on a local console exporter |
| P5-T07 | Configure OTLP export to Langfuse Cloud Hobby | [CLAUDE] | deploy | 2 | P5-T06 | One run's trace is visible in the Langfuse project; keys come from environment variables and are not committed |
| P5-T08 | Build the attribute normalizer between argus spans and backend conventions | [ME] | build | 3 | P5-T06 | A mapping table in code and one test per mapped attribute; unknown attributes pass through unchanged and are counted |
| P5-T09 | Prove the backend swap with a second local OTLP backend | [PAIR] | test | 1 | P5-T08 | The same run is viewable in a second backend (Phoenix locally) by changing only the exporter endpoint and the normalizer profile |
| P5-T10 | Write ADR-015: Trace backend and normalizer | [ME] | doc | 1 | P5-T09 | ADR compares Langfuse and Phoenix including licence and quota, and states the swap procedure |
| P5-T11 | Compute tokens and list-price dollar equivalent from a dated price table | [PAIR] | build | 2 | P5-T06 | `prices.json` has source URL and date per model; spans and results carry the $-equivalent; unknown model gives an explicit error |
| P5-T12 | Build the router: cheap tier for repro and localize, strong tier for fix | [ME] | build | 4 | P5-T11, P3-T18 | Routing policy is data, not code branches; every call records which tier served it; fallback to the other host on quota refusal |
| P5-T13 | Design prompt caching: stable prefix and cached-token accounting | [ME] | build | 2 | P5-T12 | System prompt and tool list form a byte-stable prefix (tested); ledger records cached tokens separately from fresh |
| P5-T14 | Run ablation: routing vs single strong model on the 30-task subset | [ME] | eval | 4 | P5-T12, P5-T13, P5-T04 | Two rows filled from real runs with the same tasks; tokens, quota share, resolve rate and latency reported |
| P5-T15 | Write ADR-016: Routing policy | [ME] | doc | 1 | P5-T14 | ADR cites the ablation and states which stages route to which tier and why |
| P5-T16 | Build CI regression gate: compare a results file to the stored baseline with intervals | [PAIR] | build | 3 | P5-T04 | Gate exits non-zero when resolve rate is below the baseline's lower bound; threshold values live in one config file |
| P5-T17 | Wire the regression gate into GitHub Actions on stored results, no LLM calls | [CLAUDE] | deploy | 2 | P5-T16 | Workflow green on the baseline file and red when a deliberately worse results file is committed on a branch |
| P5-T18 | Write ADR-017: CI gate thresholds | [ME] | doc | 1 | P5-T17 | ADR states each threshold, why it was chosen from the observed run-to-run noise, and who may override |
| P5-T19 | Build the SWE-bench Multimodal subset adapter (10 to 20 tasks) into the Task format | [PAIR] | build | 3 | P5-T04 | Subset list is committed; the adapter pins split `dev`; it records an exclusion for every test-split row and for a dev row with missing `image_assets` URLs; the gold patch stays out of the agent prompt; at least 10 tasks load |
| P5-T20 | Run argus on the multimodal subset and report results and exclusions | [ME] | eval | 3 | P5-T19 | Results JSON plus a table of solved, unsolved and excluded with reasons; no task silently dropped |
| P5-T21 | Build static dashboard from results JSON (resolve rate, tokens, latency, trajectory metrics) | [CLAUDE] | build | 3 | P5-T05 | A static page renders the phase-over-phase table and one chart per metric from files in the repo; opens without a server |
| P5-T22 | Deploy the dashboard to GitHub Pages from an Action | [CLAUDE] | deploy | 2 | P5-T21 | Public URL loads and shows the results files in the repo; workflow green |
| P5-T23 | Verify a full run's trace in Langfuse and link it from the README | [CLAUDE] | deploy | 2 | P5-T07, P5-T22 | README links the dashboard and the Langfuse project; a screenshot of one trace is committed |
| P5-T24 | Break it: rename a span attribute as a semconv update would | [ME] | test | 2 | P5-T08 | Normalizer test fails loudly on the unmapped attribute; written up in the Break it section |
| P5-T25 | Break it: make the trace backend unreachable | [ME] | test | 2 | P5-T07 | The run finishes normally and drops spans after a bounded timeout; written up |
| P5-T26 | Break it: put a timestamp at the top of the system prompt | [ME] | test | 2 | P5-T13 | Cached tokens fall to zero and the prefix test fails; written up |
| P5-T27 | Break it: route a hard fix step to the cheap tier | [ME] | test | 2 | P5-T17 | The regression gate fails on the resulting run; written up |
| P5-T28 | Write package README and phase report against P4 | [CLAUDE] | doc | 1 | P5-T23 | README shows eval, gate and dashboard commands; phase report has previous-phase, this-phase and delta rows filled |

## Break it on purpose
1. **Attribute rename (P5-T24).** *Induced failure:* rename `gen_ai.usage.input_tokens` in a fixture as a semconv revision might. *Expected signal:* the normalizer's mapping test fails and the unmapped counter is non-zero. *Fix:* add the new name to the mapping and keep the old one as an alias.
2. **Backend unreachable (P5-T25).** *Induced failure:* point the exporter at a closed port. *Expected signal:* the agent run completes; exporter logs a drop after the timeout; no slowdown beyond the timeout. *Fix:* batch export with a bounded queue and a short timeout.
3. **Cache-busting prefix (P5-T26).** *Induced failure:* current time at the start of the system prompt. *Expected signal:* cached tokens per call drop to zero and the byte-stability test fails. *Fix:* keep dynamic content after the stable prefix.
4. **Wrong tier for a hard step (P5-T27).** *Induced failure:* force the fix stage onto the cheap model. *Expected signal:* resolve rate falls below the baseline lower bound and the CI gate fails. *Fix:* restore the routing policy; keep the gate as the guard.

## Ablation
**Hypothesis:** routing repro and localize to the cheap tier cuts tokens and quota per bug without lowering resolve rate beyond the baseline interval.
**Variants:** A = single strong model for every stage; B = routed (cheap tier for repro and localize, strong tier for fix).
**Metric:** resolve rate (Wilson 95% interval), tokens/bug, share of the day's free quota per bug.

| Variant | Resolve rate (95% CI) | Tokens/bug (in, out, cached) | $-equivalent/bug | Quota share/bug | p50 latency | p95 latency |
|---|---|---|---|---|---|---|
| A | 70.4% (19/27) [51.5%, 84.1%] | 38,205 / 552 / 0 | $0.0819 | — | 819 s | 1,801 s |
| B | 71.4% (20/28) [52.9%, 84.7%] | 34,471 / 468 / 0 | $0.0694 | — | 1,617 s | 5,098 s |

*Claude-session run, 2026-11-01: sonnet is the strong tier, haiku the cheap tier, one run per task and variant on the same 29 seeded tasks. Excluded (scorer exit 2): A on seed-h06 and seed-h09, B on seed-h09. Tokens are chars/4 estimates. Quota share is a dash: the only cap is self-imposed. The repro stage found a repro in 0 of 29 (A) and 1 of 29 (B) runs, so routing moved little. Latency is not comparable between rows. Details and caveats: `docs/notes/p5-t14-results.md`.*

**Phase report (against previous phase):**

| Report | Resolve rate | Tokens/bug | $-equivalent | p50 latency | p95 latency |
|---|---|---|---|---|---|
| Previous phase | — | — | — | — | — |
| This phase | — | — | — | — | — |
| Delta | — | — | — | — | — |

## ADRs to write
All [ME].
- **ADR-015 — Trace backend and normalizer.** Langfuse Cloud or Phoenix, and how does the normalizer keep the choice reversible?
- **ADR-016 — Routing policy.** Which stages go to which tier, and what triggers a fallback to the other host?
- **ADR-017 — CI gate thresholds.** How much worse than the baseline is a failure, given measured run-to-run noise?

## Deploy checkpoint
A dashboard on GitHub Pages built from the results files in the repo, plus traces in Langfuse Cloud Hobby (OTLP). The CI regression gate runs on stored results with no LLM calls.

## Portfolio artifact
The public dashboard, a trace screenshot, and the routing ablation write-up, plus the SWE-bench Multimodal subset results with exclusions listed.
