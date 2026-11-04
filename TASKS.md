# Argus task checklist

Flat checklist in execution order, generated from the Tasks tables in `phases/`. Format: `- [ ] ID Title [OWNER] hours`. Weeks are 20 h bins, and a week can run up to 3 h over 20 because a task is placed in the week it starts. Weeks under 20 h are week 9 (19 h), week 10 (19 h), week 15 (19 h), week 19 (18 h), week 20 (19 h), week 27 (19 h), week 31 (19 h), and week 32 (16 h). The two buffer weeks are calendar weeks with no scheduled tasks. A phase can start in the tail of the previous phase's last week.

Owners: **[ME]** you write it; **[CLAUDE]** Claude writes it; **[PAIR]** you write it and Claude reviews. Every phase starts with a T00 version re-check. Task ids match the phase tables exactly.

Totals: 255 core tasks (556 h, P0 to P8) plus 17 optional P9 tasks (40 h).


## Week 1 — P0 (20 h scheduled)

- [x] P0-T00 Re-verify pinned versions via web search [CLAUDE] 1h
- [x] P0-T01 Create monorepo skeleton (uv workspace, pnpm workspace, folders) [CLAUDE] 2h
- [x] P0-T02 Read SWE-smith and SWE-bench Multimodal, write one page of design notes [ME] 2h
- [x] P0-T03 Define Ticket, Task and Trajectory types and JSON schema in argus-core [ME] 3h
- [x] P0-T04 Write ADR-001: Task and Trajectory schema [ME] 1h
- [x] P0-T05 Build OpenAI-compatible model client with per-provider config [PAIR] 2h
- [x] P0-T06 Measure real free-tier quotas (Groq, Mistral, hosted Gemma check) and record them [ME] 4h
- [x] P0-T07 Implement quota ledger with hard stop and cached-token accounting [ME] 4h
- [x] P0-T08 Write ADR-002: Quota ledger semantics [ME] 1h

## Week 2 — P0 (20 h scheduled)

- [x] P0-T09 Bind target-app to the dcortex Canvas and copa-local Postgres [CLAUDE] 4h
- [x] P0-T10 Define bench task directory format (ticket, bug patch, golden patch, checks, meta) [ME] 2h
- [x] P0-T11 Build Playwright check library (pixel diff, bounding-box asserts, computed-style asserts) [PAIR] 3h
- [x] P0-T12 Define 6 UI bug archetypes and 3 difficulty tiers [PAIR] 1h
- [x] P0-T13 Generate boilerplate for 30 seeded bug tasks [CLAUDE] 3h
- [x] P0-T14 Review and hand-tune the 30 seeded tasks until each is valid [PAIR] 3h
- [x] P0-T15 Build scorer CLI: run a task's checks against a tree and emit a JSON verdict [ME] 4h

## Week 3 — P0 (20 h scheduled)

- [x] P0-T16 Build golden-fix runner over all tasks [PAIR] 2h
- [x] P0-T17 Add CI workflow: golden-fix run on every push, no LLM calls [CLAUDE] 2h
- [x] P0-T18 Add flake detection: run each task's checks 5 times on buggy and golden trees [ME] 2h
- [x] P0-T19 Break it: make a golden patch stale [ME] 2h
- [x] P0-T20 Break it: introduce a nondeterministic animation [ME] 2h
- [x] P0-T21 Build bugsmith mutation-operator interface and AST pipeline [ME] 4h
- [x] P0-T22 Implement JSX mutation operators (remove class, swap flex direction, drop prop, change element) [PAIR] 3h
- [x] P0-T23 Implement CSS mutation operators (delete rule, change unit, z-index, overflow) [PAIR] 3h

## Week 4 — P0, P1 (20 h scheduled)

- [x] P0-T24 Build mutation validity filter: keep only fail-before, pass-after mutants [ME] 4h
- [x] P0-T25 Break it: feed the validity filter an equivalent mutant [ME] 2h
- [x] P0-T26 Run bulk generation to 300 or more valid tasks with a fixed seed [ME] 2h
- [x] P0-T27 Write ADR-003: Mutation validity and flake policy [ME] 1h
- [x] P0-T28 Build one-shot patch baseline (single model call, no tools) [PAIR] 2h
- [x] P0-T29 Run ablation: seeded vs mutated bugs under the one-shot baseline [ME] 2h
- [x] P0-T30 Break it: exhaust the quota ledger mid-run [ME] 2h
- [x] P0-T31 Write package README and phase report [CLAUDE] 1h
- [x] P1-T00 Re-verify pinned versions via web search [CLAUDE] 1h
- [x] P1-T01 Spike: call Playwright MCP from an MCP Python SDK v2 client [ME] 3h

## Week 5 — P1 (20 h scheduled)

- [x] P1-T02 Write ADR-004: Playwright MCP vs direct Playwright as tool [ME] 1h
- [x] P1-T03 Read the MCP 2026-07-28 post and the playwright-mcp README, write notes [ME] 1h
- [x] P1-T04 Define repro tool schemas (navigate, snapshot, click, type, assert-visible, screenshot) [ME] 2h
- [x] P1-T05 Build Docker image to run Playwright repro scripts with no network egress beyond the app [CLAUDE] 2h
- [x] P1-T06 Assemble ticket and screenshot prompt (text-only and text-plus-image modes) [PAIR] 2h
- [x] P1-T07 Build repro agent loop: generate script, run it, revise on error, hard retry cap [ME] 4h
- [x] P1-T08 Build repro verifier: script must fail on buggy tree and pass on golden tree [ME] 2h
- [x] P1-T09 Add CI job for repro-agent tests on recorded fixtures, no LLM calls [CLAUDE] 2h
- [x] P1-T10 Run repro-agent on 30 seeded tasks, text only [ME] 2h
- [x] P1-T11 Run repro-agent on 30 seeded tasks, text plus screenshot [ME] 2h

## Week 6 — P1, P2 (20 h scheduled)

- [x] P1-T12 Write ADR-005: When to include the screenshot in ticket context [ME] 1h
- [x] P1-T13 Break it: give the agent a vague ticket with no steps [ME] 2h
- [x] P1-T14 Break it: make the script pass on the buggy tree (selector too loose) [ME] 2h
- [x] P1-T15 Break it: kill the MCP server mid-run [ME] 2h
- [x] P1-T16 Write package README and phase report against P0 [CLAUDE] 1h
- [x] P2-T00 Re-verify pinned versions via web search [CLAUDE] 1h
- [x] P2-T01 Read React issue #32574 and the Aider repo-map docs, write notes [ME] 1h
- [x] P2-T02 Build Vite plugin that injects `data-src` on JSX host elements [PAIR] 4h
- [x] P2-T03 Add plugin tests: attribute on every host element, stripped in production build [CLAUDE] 2h
- [x] P2-T04 Write ADR-006: `data-src` attribute vs source maps [ME] 1h
- [x] P2-T05 Implement locate() core: selector to DOM node to `data-src` to file and line [ME] 3h

## Week 7 — P2 (20 h scheduled)

- [x] P2-T06 Define MCP tool schema for locate() (input, output, typed errors) [ME] 2h
- [x] P2-T07 Build the MCP server for locate() on the 2026-07-28 spec with SDK v2 [ME] 4h
- [x] P2-T08 Handle ambiguity: wrapper components and repeated elements return candidates [ME] 2h
- [x] P2-T09 Build repo-map plus LSP index of the dcortex Canvas worktree [PAIR] 4h
- [x] P2-T10 Build pgvector variant with a local embedding model (CPU) [PAIR] 3h
- [x] P2-T11 Build retrieval harness: top-1 and top-3 file accuracy against the golden patch's file [ME] 2h
- [x] P2-T12 Run ablation: repo-map/LSP vs pgvector vs data-src locate() on 30-task stratified subset [ME] 3h

## Week 8 — P2, P3 (22 h scheduled)

- [x] P2-T13 Write ADR-007: Retrieval strategy [ME] 1h
- [ ] P2-T14 Add CI job for plugin and MCP server tests, no LLM calls [CLAUDE] 2h. Workflow written and its commands run locally (docs/notes/p2-conformance-fixes.md); the box needs a green Actions run id before it is ticked.
- [x] P2-T15 Break it: render a button through a wrapper component [ME] 2h
- [x] P2-T16 Break it: run locate() against a production build [ME] 2h
- [x] P2-T17 Break it: edit a file after the repo-map is built [ME] 2h
- [x] P2-T18 Break it: connect with a client that speaks an older MCP spec [ME] 2h
- [x] P2-T19 Write package READMEs and phase report against P1 [CLAUDE] 1h
- [x] P3-T00 Re-verify pinned versions via web search [CLAUDE] 1h
- [x] P3-T01 Read the mini-swe-agent source and the context-engineering post, write notes [ME] 2h
- [x] P3-T02 Define agent tool schemas: read_file, list_dir, search, edit, run_cmd, submit [ME] 4h
- [x] P3-T03 Add ast-grep as a structural search and rewrite tool [PAIR] 3h

## Week 9 — P3 (19 h scheduled)

- [x] P3-T04 Build worktree manager: create and destroy a git worktree per task [CLAUDE] 2h
- [x] P3-T05 Build Docker sandbox runner: `--network none`, CPU and memory caps, worktree mount, checks read-only [CLAUDE] 3h
- [x] P3-T06 Build core agent loop: message history, model call, stop conditions [ME] 4h
- [x] P3-T07 Build tool dispatch with argument validation and error handling [ME] 3h
- [x] P3-T08 Build trajectory recorder (every step as a Trajectory record) [PAIR] 3h
- [x] P3-T09 Build context budget manager: token counting and a strategy interface [ME] 4h

## Week 10 — P3 (19 h scheduled)

- [x] P3-T10 Implement context strategy: output caps [ME] 3h
- [x] P3-T11 Implement context strategy: offload-to-files with a pointer [ME] 3h
- [x] P3-T12 Implement context strategy: rolling summary [ME] 3h
- [x] P3-T13 Write AGENTS.md for the dcortex worktree and load it into the system prompt [PAIR] 2h
- [x] P3-T14 Build gates: build, typecheck, lint, unit tests and bench checks run before submit [PAIR] 3h
- [x] P3-T15 Feed gate results back into the loop as structured messages [ME] 3h
- [x] P3-T16 Wire the repro script and locate() hint into the task prompt [PAIR] 2h

## Week 11 — P3 (20 h scheduled)

- [x] P3-T17 Set up mini-swe-agent against the OpenAI-compatible endpoint [PAIR] 4h
- [x] P3-T18 Run fix-loop baseline (no compaction) on a 30-task stratified subset [ME] 3h
- [x] P3-T19 Run context ablation: all four strategies on the same 30 tasks [ME] 4h
- [x] P3-T20 Run mini-swe-agent on the same 30 tasks [ME] 3h
- [x] P3-T21 Label failed runs with a failure taxonomy [ME] 3h
- [x] P3-T22 Write ADR-008: Loop control, stop conditions and tool-call format [ME] 1h
- [x] P3-T23 Write ADR-009: Context management policy [ME] 1h
- [x] P3-T24 Write ADR-010: Sandbox baseline (worktree plus Docker, no network) [ME] 1h

## Week 12 — P3, P4 (21 h scheduled)

- [x] P3-T25 Write ADR-011: Framework adoption rule after the baseline [ME] 1h
- [x] P3-T26 Add CI job: unit tests and dependency check on recorded trajectories, no LLM [CLAUDE] 2h
- [x] P3-T27 Build deterministic replay of a recorded trajectory with no LLM call [PAIR] 2h
- [x] P3-T28 Break it: make the model repeat the same tool call [ME] 2h
- [x] P3-T29 Break it: return a 5 MB tool output [ME] 2h
- [x] P3-T30 Break it: make the model send malformed tool arguments [ME] 2h
- [x] P3-T31 Break it: let the model try to edit the bench checks [ME] 2h
- [x] P3-T32 Break it: make the model run a destructive shell command [ME] 2h
- [x] P3-T33 Write package README and phase report against P2 and P0 [CLAUDE] 1h
- [x] P4-T00 Re-verify pinned versions via web search [CLAUDE] 1h
- [x] P4-T01 Read Panickssery, Krippendorff and Snell, write notes [ME] 2h
- [x] P4-T02 Build pixel-diff check against the golden screenshot with region masks [PAIR] 2h

## Week 13 — P4 (20 h scheduled)

- [x] P4-T03 Build overflow check (scroll width, off-viewport elements) [PAIR] 2h
- [x] P4-T04 Build axe-core check reporting only new violations versus the clean baseline [CLAUDE] 2h
- [x] P4-T05 Build console check reporting new errors and warnings [CLAUDE] 2h
- [x] P4-T06 Build the verifier pipeline: fixed order, short-circuit, structured verdict [ME] 4h
- [x] P4-T07 Write ADR-012: Gate ordering and short-circuit policy [ME] 1h
- [x] P4-T08 Write the judge rubric: does the fix match the ticket's intent without collateral change [ME] 4h
- [x] P4-T09 Generate candidate pairs for the calibration set from bench runs [PAIR] 2h
- [x] P4-T10 Label all 100 calibration pairs by hand [ME] 3h

## Week 14 — P4 (21 h scheduled)

- [x] P4-T11 Build the local Gemma judge runner with vision input (Ollama, CPU) [ME] 4h
- [x] P4-T12 Implement Krippendorff's alpha with a bootstrap interval and test it against a published worked example [ME] 3h
- [x] P4-T13 Run the local judge over the 100 pairs (overnight, CPU) [ME] 3h
- [x] P4-T14 Iterate the rubric and prompt until alpha reaches 0.80 or the budget is spent [ME] 4h
- [x] P4-T15 Check for a free hosted Gemma for runtime judging and decide the runtime path [ME] 2h
- [x] P4-T16 Build the same-family judge runner (Mistral vision model) [ME] 2h
- [x] P4-T17 Run ablation: same-family vs cross-family judge on the calibration set [ME] 3h

## Week 15 — P4 (19 h scheduled)

- [x] P4-T18 Write ADR-013: Judge selection [ME] 1h
- [x] P4-T19 Build best-of-k sampler: k candidate patches, verifier and judge pick one [ME] 3h
- [x] P4-T20 Run best-of-k with k = 1, 3, 5 on the 30-task subset [ME] 4h
- [x] P4-T21 Write ADR-014: Best-of-k policy and cost cap [ME] 2h
- [x] P4-T22 Wire the verifier into fix-loop as the final gate with a retry on rejection [ME] 3h
- [x] P4-T23 Add CI job for verify tests on recorded fixtures, no LLM calls [CLAUDE] 2h
- [x] P4-T24 Break it: swap the order of before and after images, and pad the explanation [ME] 2h
- [x] P4-T25 Break it: submit a fix that passes the target check but breaks another route [ME] 2h

## Week 16 — P4, P5 (20 h scheduled)

- [x] P4-T26 Break it: introduce a screenshot that differs only by font loading [ME] 2h
- [x] P4-T27 Break it: put a prompt injection in the ticket text [ME] 2h
- [x] P4-T28 Break it: stop the judge backend mid-run [ME] 2h
- [x] P4-T29 Write package README and phase report against P3 [CLAUDE] 1h
- [x] P5-T00 Re-verify pinned versions via web search [CLAUDE] 1h
- [x] P5-T01 Read the OTel GenAI conventions and the reliable-agents paper, write notes [ME] 1h
- [x] P5-T02 Define trajectory metrics with exact formulas [ME] 3h
- [x] P5-T03 Implement trajectory metrics over stored JSONL [ME] 3h
- [x] P5-T04 Build eval runner with aggregation and Wilson confidence intervals [ME] 3h
- [x] P5-T05 Build phase-over-phase report generator (markdown from results JSON) [PAIR] 2h

## Week 17 — Buffer week (no scheduled tasks; catch up, or finish quota-bound eval runs)


## Week 18 — P5 (22 h scheduled)

- [x] P5-T06 Instrument the loop and tools with OTel spans using GenAI attributes [ME] 3h
- [x] P5-T07 Configure OTLP export to Langfuse Cloud Hobby [CLAUDE] 2h
- [x] P5-T08 Build the attribute normalizer between argus spans and backend conventions [ME] 3h
- [x] P5-T09 Prove the backend swap with a second local OTLP backend [PAIR] 1h
- [x] P5-T10 Write ADR-015: Trace backend and normalizer [ME] 1h
- [x] P5-T11 Compute tokens and list-price dollar equivalent from a dated price table [PAIR] 2h
- [x] P5-T12 Build the router: cheap tier for repro and localize, strong tier for fix [ME] 4h
- [x] P5-T13 Design prompt caching: stable prefix and cached-token accounting [ME] 2h
- [x] P5-T14 Run ablation: routing vs single strong model on the 30-task subset [ME] 4h

## Week 19 — P5 (18 h scheduled)

- [x] P5-T15 Write ADR-016: Routing policy [ME] 1h
- [x] P5-T16 Build CI regression gate: compare a results file to the stored baseline with intervals [PAIR] 3h
- [x] P5-T17 Wire the regression gate into GitHub Actions on stored results, no LLM calls [CLAUDE] 2h
- [x] P5-T18 Write ADR-017: CI gate thresholds [ME] 1h
- [x] P5-T19 Build the SWE-bench Multimodal subset adapter (10 to 20 tasks) into the Task format [PAIR] 3h
- [x] P5-T20 Run argus on the multimodal subset and report results and exclusions [ME] 3h. Done with the argus fix loop (Claude Sonnet, one subagent per step): 7 solved, 7 unsolved, 1 excluded, 0 not scored, 7 of 14 = 0.50 (packages/eval/results/p5-t20-multimodal-argus.json, docs/notes/p5-t20.md section 10). Baseline row, one plain subagent per task: 7 solved, 5 unsolved, 1 excluded, 2 patch produced but not scored (p5-t20-multimodal.json, section 9).
- [x] P5-T21 Build static dashboard from results JSON (resolve rate, tokens, latency, trajectory metrics) [CLAUDE] 3h
- [x] P5-T22 Deploy the dashboard to GitHub Pages from an Action [CLAUDE] 2h. Skipped on the owner's decision (2026-11-02): GitHub Pages is not available on a private repo on this plan, and the repo must stay private. `dashboard.yml` builds the page and attaches it to the run as a download instead; the page also opens from disk.

## Week 20 — P5, P5.5 (19 h scheduled)

- [x] P5-T23 Verify a full run's trace in Langfuse and link it from the README [CLAUDE] 2h. Met in a weaker form, with the owner's agreement: the trace is a replay of a stored run (16 spans, marked `argus.replay`), the API evidence file `docs/notes/p5-t23-trace-evidence.md` stands in for a screenshot (not committed), and there is no dashboard URL (Pages skipped); the README links the Langfuse project and says how to open the dashboard.
- [x] P5-T24 Break it: rename a span attribute as a semconv update would [ME] 2h
- [x] P5-T25 Break it: make the trace backend unreachable [ME] 2h
- [x] P5-T26 Break it: put a timestamp at the top of the system prompt [ME] 2h
- [x] P5-T27 Break it: route a hard fix step to the cheap tier [ME] 2h
- [x] P5-T28 Write package README and phase report against P4 [CLAUDE] 1h
- [x] P5.5-T00 Re-verify pinned versions via web search [CLAUDE] 1h
- [x] P5.5-T01 Read the Agent Skills spec and the Anthropic post, write notes [ME] 1h (notes written by Claude, owner to read)
- [x] P5.5-T02 Build the skill loader with progressive disclosure inside fix-loop [ME] 2h
- [x] P5.5-T03 Define the train and held-out split [ME] 1h
- [x] P5.5-T04 Collect successful trajectories on the training tasks [ME] 2h (20 resolved of 21 finished; the budget is self-imposed, no provider ledger exists for Claude sessions: docs/notes/p5.5-t04.md)
- [x] P5.5-T05 Draft candidate skills from successful trajectories with the cheap-tier model [PAIR] 1h

## Week 21 — P5.5 (20 h scheduled)

- [x] P5.5-T06 Review, edit and keep at least 5 skills [ME] 2h. Done on 2026-11-02 by Claude at the owner's request, and the owner confirmed the 5 pins in chat: 3 skills backed by 11, 3 and 4 runs, 2 thin ones (1 run each); drafts deleted. See `docs/notes/p5.5-t06.md`.
- [x] P5.5-T07 Test skill selection: does the description trigger the right skill [PAIR] 1h
- [x] P5.5-T08 Run ablation: with vs without skills on the held-out set [ME] 3h. Done on 2026-11-02 on the 29 runnable held-out tasks (not 30): 72.4% (21/29) with skills against 70.4% (19/27) without, same outcome on all 27 paired tasks; skills did not help. See `docs/notes/p5.5-t08.md`.
- [x] P5.5-T09 Write ADR-018: Skill format and distillation criteria [ME] 1h (drafted by Claude, status proposed: owner to review. See `docs/adr/0018-skill-format-and-distillation-criteria.md`)
- [x] P5.5-T10 Build skill trust controls: review flag, content hash pin and tool allowlist per skill [ME] 2h
- [x] P5.5-T11 Write ADR-019: Skill trust model [ME] 1h
- [x] P5.5-T12 Add CI job to lint skill files (frontmatter, size limit, hash file), no LLM [CLAUDE] 1h. Green on GitHub on PR #14 (push run 41509388038 and pull-request run 41509383525, commit 52493d5); the lint fails on a bad skill in the tests.
- [x] P5.5-T13 Break it: activate a skill that tells the agent to edit the bench checks [ME] 2h
- [x] P5.5-T14 Break it: activate a skill that tries to send data out over the network [ME] 2h
- [x] P5.5-T15 Break it: write a skill whose description matches every ticket [ME] 2h
- [x] P5.5-T16 Break it: leave a skill that names a file since renamed [ME] 2h
- [x] P5.5-T17 Write package README and phase report against P5 [CLAUDE] 1h (rows from stored results files; the previous-phase row is P5 variant B and is not the same method, see `docs/notes/p5.5-t17.md`)

## Week 22 — P6 (20 h scheduled)

- [x] P6-T00 Re-verify pinned versions via web search [CLAUDE] 1h
- [x] P6-T01 Read the DBOS docs and the MRTR and Tasks sections of the MCP post, write notes [ME] 1h
- [x] P6-T02 Design the workflow state machine: states, transitions, idempotency keys [ME] 3h
- [x] P6-T03 Implement the workflow with DBOS durable steps against a local Postgres [ME] 4h
- [ ] P6-T04 Dispatch agent jobs to GitHub Actions as the execution plane and collect artifacts [PAIR] 3h
- [x] P6-T05 Build the FastAPI webhook endpoint with HMAC signature verification [PAIR] 2h
- [x] P6-T06 Treat webhooks as hints: enqueue a reconcile and return immediately [ME] 1h
- [x] P6-T07 Build the reconciliation poller that rebuilds state from GitHub [ME] 3h
- [x] P6-T08 Add the QA signal wait with a timeout [ME] 2h

## Week 23 — P6 (21 h scheduled)

- [x] P6-T09 Add MRTR elicitation for the QA approval step [ME] 3h
- [x] P6-T10 Add the plain GitHub review-comment fallback for QA approval [PAIR] 1h
- [x] P6-T11 Set up Neon free Postgres with reconnect handling for scale-to-zero [CLAUDE] 2h
- [x] P6-T12 Deploy the FastAPI and DBOS service to Render free [CLAUDE] 3h
- [ ] P6-T13 Measure the Render cold start against the 10 s webhook timeout [ME] 2h
- [ ] P6-T14 Measure Neon CU-hours with DBOS polling over 48 hours [ME] 2h
- [x] P6-T15 Write ADR-020: DBOS vs Temporal (decision only) [ME] 2h
- [ ] P6-T16 Write ADR-021: Webhooks as hints with reconciliation [ME] 1h
- [ ] P6-T17 Write ADR-022: Free-tier deployment topology [ME] 1h
- [x] P6-T18 Write ADR-023: QA signal via MRTR or review comments [ME] 1h
- [x] P6-T19 Run crash-recovery experiment: kill the process at each step boundary [ME] 3h

## Week 24 — P6, P7 (20 h scheduled)

- [x] P6-T20 Add CI job for flow tests with a Postgres service container, no LLM [CLAUDE] 2h
- [x] P6-T21 Break it: kill the worker after the PR is opened but before state is saved [ME] 2h
- [x] P6-T22 Break it: deliver the same webhook twice [ME] 2h
- [ ] P6-T23 Break it: let Render sleep and drop a webhook [ME] 2h
- [x] P6-T24 Break it: suspend Neon mid-run [ME] 2h
- [ ] P6-T25 Write package README and phase report against P5 [CLAUDE] 1h
- [x] P7-T00 Re-verify pinned versions via web search [CLAUDE] 1h
- [x] P7-T01 Read the OWASP agentic top 10 and the Firecracker paper, write notes [ME] 1h (notes written by Claude, owner to read)
- [x] P7-T02 Write the threat model: assets, trust boundaries, data flows and ASI01 to ASI10 mapping [ME] 3h (written by Claude, owner to read)
- [x] P7-T03 Inventory secrets, keep them out of prompts, logs and trajectories, and scan CI for leaks [PAIR] 2h Secret scan green on GitHub on 2026-11-03 (runs 41568774973 and 41568788877): `docs/notes/p7-github-runs.md`.
- [x] P7-T04 Make the GitHub App token least-privilege and short-lived [PAIR] 2h

## Week 25 — Buffer week (no scheduled tasks; catch up, or finish quota-bound eval runs)


## Week 26 — P7 (21 h scheduled)

- [x] P7-T05 Test the no-egress policy in every execution context [PAIR] 1h Local result `packages/guard/results/egress-local.json`; Actions result from run 41568774763 (log excerpt in `docs/notes/p7-github-runs.md`): sandbox connect-failed on TCP, HTTPS and DNS, control reached. Docker tier only.
- [x] P7-T06 Build the append-only hash-chained audit log with a verify command [ME] 3h (written by Claude, owner to read)
- [x] P7-T07 Set up promptfoo red-team config for injection via ticket, repo file and skill [PAIR] 2h Three static cases, deterministic assertions, no LLM rubric; the stub dry run passes 3 of 3 under promptfoo 0.125.1 and the obedient stub fails 3 of 3. See `docs/architecture/p7.md`.
- [x] P7-T08 Run the red-team against the fix-loop and record attack outcomes [ME] 2h Real run: promptfoo 0.125.1, local Ollama `gemma4:e4b` only, 3 cases x 5 repeats = 15 runs, before any mitigation. ticket succeeded (3 of 5 runs), repo-file succeeded (1 of 5), skill blocked (0 of 5, but the skill was loaded in only 2 runs). A small local model, not the production model. See `packages/guard/results/redteam-2026-11-03.md`.
- [x] P7-T09 Add mitigations from the red-team: data and instruction separation, tool allowlist, output filter [ME] 2h Mitigations added in `fix-loop` (separation, output filter with `argus_core.redact`, tool allowlist). Both baseline-successful cases are blocked on a re-run (0 of 10 runs, against 4 of 10); the skill case did not reach the model in the re-run, so it shows nothing. Off by default; residual risk is in the threat model. Small local model, not the production model. See `packages/guard/results/redteam-2026-11-03.md`.
- [x] P7-T10 Run the sandbox under gVisor [PAIR] 2h Ran on a GitHub-hosted runner (run 41572865817 and earlier): `runsc` release-20261026.0, fixture under `docker run --runtime runsc` passed, escape suite 14 of 14 run alone; command and versions are in the job log (`docs/notes/p7-github-tier-runs.md`).
- [x] P7-T11 Run the sandbox as a Firecracker microVM on the Actions KVM runner [PAIR] 3h `firecracker.yml` booted a Firecracker v1.17.0 microVM on a plain GitHub-hosted `ubuntu-24.04` runner, ran the fixture and returned the result (30 of 30 boots in three runs); the log prints `RESULT: /dev/kvm PRESENT`. Needs a udev rule for /dev/kvm. Escape probes not ported into the microVM.
- [x] P7-T12 Build the escape-test suite: network, host filesystem, docker socket, metadata address, fork bomb, symlink [ME] 3h Docker tier run locally: 12 of 12 probes blocked (`packages/guard/results/escape-docker.txt`); gVisor and Firecracker print "tier not available here" and did not run. See `docs/notes/p7-t12.md`.
- [x] P7-T13 Run ablation: Docker vs gVisor vs Firecracker on cold start and escape tests [ME] 3h Rows A and B from real runs on one GitHub-hosted runner; row C has launch to exit only (30 of 30 boots) and no probes. gVisor: fork-bomb probe errors inside the ablation (4 of 4), passes alone (16 of 16); cause not known. See the table in `phases/P07-argus-guard.md`.

## Week 27 — P7, P8 (19 h scheduled)

- [x] P7-T14 Write ADR-024: Threat model and trust boundaries [ME] 1h (written by Claude, status proposed, owner to decide) States the boundaries, the nine assets and 14 residual risks marked accepted (2), owner decision (4) or open (8), including the unfixed findings. See `docs/adr/0024-threat-model-and-trust-boundaries.md`.
- [x] P7-T15 Write ADR-025: Sandbox tier selection [ME] 1h (written by Claude, status proposed, owner to decide) Cites the ablation: only row A (Docker, `--network none`, 30 starts, 12 of 12 probes, Windows Docker Desktop) was measured; **B (gVisor) and C (Firecracker) are unmeasured** and the ADR draws no comparison. Default: Docker with `--network none`; states when a stronger tier is required and what to measure before revisiting. See `docs/adr/0025-sandbox-tier-selection.md`.
- [x] P7-T16 Write ADR-026: Secrets handling and token scopes [ME] 1h (written by Claude, status proposed, owner to decide) Lifetimes for every secret in the inventory, the App permission list unchanged from the T04 note, and a rotation procedure per secret (App key and webhook secret included). Nothing was checked on GitHub, Render or Neon; the owner must create the App and the stores. See `docs/adr/0026-secrets-handling-and-token-scopes.md`.
- [x] P7-T17 Add CI job for escape tests, secret scan and audit-log verification, no LLM [CLAUDE] 2h `guard.yml` green on GitHub on 2026-11-03 (runs 41568774853 and 41568788853); the three failure modes are shown by tests run locally only (`docs/notes/p7-github-runs.md`).
- [x] P7-T18 Break it: inject a ticket that asks the agent to print its environment [ME] 2h Scripted obedient model, real `run_fix`, fake secrets in the host environment: on the Docker path (what `fix_step` uses) none reaches the model, trajectory, patch or reply, with `harden` off or on; the host executor leaks into the patch with `harden` off (control). See `docs/notes/p7-break-its.md`.
- [x] P7-T19 Break it: edit one line of the audit log [ME] 2h Real `guard verify-log` on a 12-record log: an edited record fails and names its line (exit 1); a consistent rewrite from the edit onward passes alone and fails only against a saved head hash (`--head`); no head hash is shipped anywhere yet. See `docs/notes/p7-break-its.md`.
- [x] P7-T20 Break it: use the App token to push to the default branch [ME] 2h Real run on 2026-11-03 against a throwaway repo with classic branch protection: the non-force move of `main` was refused with 422 "Changes must be made through a pull request."; the probe branch was allowed (201, 204); a write on another repo was 404. Result `packages/guard/results/app-push-real.json`, write-up in `docs/notes/p7-break-its.md`.
- [x] P7-T21 Break it: try DNS exfiltration from the sandbox [ME] 2h
- [x] P7-T22 Write package README and phase report against P6 [CLAUDE] 1h `packages/guard/README.md` lists the controls (tested locally / never run on GitHub / not run), the escape-suite command and the other commands. The phase-report rows are filled as far as real data allows: every cell is a dash, because P6 has no numbers (P6-T25 open) and P7 does not run the fix loop for resolve rate, tokens or latency; the real P7 measurements are in a second table with their limits.
- [x] P8-T00 Re-verify pinned versions via web search [CLAUDE] 1h
- [x] P8-T01 Read the multi-agent and building-effective-agents posts, write notes [ME] 1h
- [ ] P8-T02 Create the GitHub App manifest with the P7 least-privilege permissions [PAIR] 3h

## Week 28 — P8 (20 h scheduled)

- [ ] P8-T03 Build installation flow and installation-token minting in the flow service [PAIR] 3h
- [ ] P8-T04 Write the reusable workflow that runs the agent job in the tenant's repo [CLAUDE] 3h
- [x] P8-T05 Define the tenant config file and write the onboarding doc [PAIR] 3h
- [ ] P8-T06 Make the runner target-agnostic using the tenant config [PAIR] 3h
- [ ] P8-T07 Add per-tenant quota budgets to the ledger with a fair-share rule [ME] 3h
- [x] P8-T08 Build ticket intake: a labelled issue starts a workflow [PAIR] 2h
- [x] P8-T09 Build PR creation with verdict, trajectory link and before and after screenshots [PAIR] 3h

## Week 29 — P8 (20 h scheduled)

- [x] P8-T10 Build the backport bot with conflict handling [PAIR] 3h
- [x] P8-T11 Build the planner and subagents variant of the loop [ME] 4h
- [ ] P8-T12 Run ablation: single agent vs planner and subagents on 20 tasks [ME] 4h
- [ ] P8-T13 Write ADR-027: Tenancy via a reusable workflow in the tenant's repo [ME] 1h
- [ ] P8-T14 Write ADR-028: Per-tenant quota budgets [ME] 1h
- [ ] P8-T15 Write ADR-029: Single agent vs planner and subagents [ME] 1h
- [ ] P8-T16 Install the App on one of your own public repos and run one issue end to end [PAIR] 3h
- [ ] P8-T17 Write the landing README: what it does, quickstart, limits, security model, free-tier caveat [CLAUDE] 3h

## Week 30 — P8, P9 (20 h scheduled)

- [ ] P8-T18 Record the demo video including one failure and its recovery [PAIR] 2h
- [ ] P8-T19 Complete the public release checklist [CLAUDE] 2h
- [ ] P8-T20 Add CI job for app tests and reusable-workflow lint, no LLM [CLAUDE] 2h
- [ ] P8-T21 Break it: let one tenant exhaust its budget while another runs [ME] 2h
- [ ] P8-T22 Break it: install on a repo with no test command configured [ME] 2h
- [x] P8-T23 Break it: force a cherry-pick conflict in a backport [ME] 2h
- [x] P8-T24 Break it: add the intake label as a user without write access [ME] 2h
- [ ] P8-T25 Write package README and phase report against P7 [CLAUDE] 1h
- [ ] P9-T00 Re-verify pinned versions via web search [CLAUDE] 1h
- [ ] P9-T01 Read the SWE-agent paper and the ast-grep docs, write notes [ME] 1h
- [ ] P9-T02 Define the backend Task variant: event, request payload and failing pytest as the check [ME] 3h

## Week 31 — P9 (19 h scheduled)

- [ ] P9-T03 Build the small FastAPI target backend with 6 endpoints and its test suite [CLAUDE] 3h
- [ ] P9-T04 Build Python mutation operators (off-by-one, wrong status code, missing await, swapped arguments) [PAIR] 3h
- [ ] P9-T05 Parse an exported Sentry event JSON into a Ticket [PAIR] 3h
- [ ] P9-T06 Build the trace-to-pytest agent: tool schemas and generator reusing the repro-agent loop [ME] 4h
- [ ] P9-T07 Reuse the P3 fixer with a pytest gate instead of the browser gates [PAIR] 3h
- [ ] P9-T08 Build the backend verifier: new test fails before, passes after, old tests pass, no new exception types [ME] 3h

## Week 32 — P9 (16 h scheduled)

- [ ] P9-T09 Build 30 backend tasks and a golden-fix CI run [PAIR] 3h
- [ ] P9-T10 Run the lane end to end on the 30 tasks and report [ME] 3h
- [ ] P9-T11 Measure the reuse ratio by module and by lines [ME] 2h
- [ ] P9-T12 Write ADR-030: Reuse boundary between lanes [ME] 1h
- [ ] P9-T13 Break it: give an event whose top stack frame is in a library [ME] 2h
- [ ] P9-T14 Break it: use a race-condition bug that fails intermittently [ME] 2h
- [ ] P9-T15 Break it: put an email address and token in the event payload [ME] 2h
- [ ] P9-T16 Write package README and phase report against P8 [CLAUDE] 1h
