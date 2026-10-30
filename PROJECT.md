# Argus

Argus is a pipeline that turns a UI bug ticket into a verified fix. It reproduces the bug, finds the source, edits the code inside a sandbox, checks that the fix matches the ticket and breaks nothing else, and opens a pull request. The point of building it is to learn the agentic layer at architect level, coming from backend engineering, on a budget of zero dollars and about 20 hours a week.

This folder is the plan. It holds documents only. No application code is written here, and every results cell stays empty until a real run fills it. Nothing in this description is a measured number.

The source of this description is [`PLAN.md`](PLAN.md), [`TASKS.md`](TASKS.md), [`repo-structure.md`](repo-structure.md), and the phase files in [`phases/`](phases/). Three companion pages already exist: [`architecture.html`](architecture.html) (the block diagram), [`production.html`](production.html) (one ticket through the deployed system), and [`142-fix.html`](142-fix.html) (a sample fix report).

## What a finished run looks like

GitHub is the source of truth: issues in, pull requests out. A labelled issue starts a durable workflow. The control plane (FastAPI with DBOS, on Render free, state in Neon free Postgres) treats the webhook as a hint and returns immediately. A reconciliation poller rebuilds state by reading GitHub, because a free Render service can sleep longer than GitHub's 10 second webhook timeout.

The actual agent job runs on GitHub Actions, and from P8 it runs as a reusable workflow inside the tenant's own repository. Inside that job:

1. **Reproduce.** `repro-agent` writes a Playwright script from the ticket (text, and optionally a screenshot). The script is kept only if it fails on the buggy tree and passes on the golden fix.
2. **Locate.** A Vite plugin stamps `data-src="file:line:col"` on JSX host elements in dev and test builds. `locate()` maps a DOM selector back to a source location and returns candidates when the mapping is ambiguous. React 19 removed `_debugSource`, so a build-time attribute is the robust route.
3. **Fix.** `fix-loop` is an agent loop written from scratch, with no agent framework. It reads, searches, edits, and submits inside a git worktree mounted in Docker with `--network none`. Bench check files are read-only. Gates (build, typecheck, lint, unit tests, bench checks) run before submit, and failures come back as structured messages.
4. **Verify.** Cheap deterministic checks run first: pixel diff, overflow, axe-core (new violations only), and new console errors. A cross-family vision judge (Gemma, not the Mistral fixer) asks whether the fix matches the ticket without collateral change. The judge does not override a passed check run. Best-of-k (k = 1, 3, 5) sits inside the selector and picks among candidate patches.
5. **Hand back.** The workflow waits for a human QA signal, either MCP MRTR elicitation (`input_required` / `inputResponses` from the 2026-07-28 spec) or a plain GitHub review comment. The pull request carries the verifier verdict, the judge label, a trajectory link, and before/after screenshots. A backport bot opens a follow-up PR, and comments instead of forcing when the cherry-pick conflicts.

Traces leave as OTLP spans. Langfuse Cloud Hobby is the default viewer. An attribute normalizer keeps the backend swappable. A static dashboard on GitHub Pages shows resolve rate, tokens, latency, and trajectory metrics. A CI regression gate compares a new results file to the stored baseline using confidence intervals, with no model call in CI.

P9, which is optional and first on the cut list, runs the same loop on a second lane: a Sentry-style error event becomes a failing pytest, then a verified backend fix. Live Sentry is not required.

## Constraints that shape the design

- **Profile.** `config/profiles.md` selects `personal` or `company`. `personal` is the default: $0, free and open-source tools only, every model open-weight, on a free hosted tier or on the local CPU. The tables below are that profile. `company` may name a paid model API and a paid host. Empty company fields stay empty until a source fills them. Hours stay 556 / 255.
- **20 hours a week**, on a 13th-gen Intel i7-13620H with 16 GB RAM, no discrete GPU, Docker 29.5, and WSL2 Ubuntu.
- **Free-tier prompts may be used for training.** Only synthetic or public code goes through them. The P8 install target is one of your own public repositories.
- **No agent framework before the P3 baseline.** Adopting one later requires an ADR. ADR-011 sets that bar against a mini-swe-agent comparison.
- **Every phase ends with an ablation** and reports resolve rate, tokens/bug, $-equivalent, and p50/p95 latency against the previous phase. Every phase starts with a T00 task that re-checks pinned versions, because phases begin months apart.
- **No invented numbers.** A results cell stays `—` until a run id backs it.

## Who writes what

| Owner | Owns |
|---|---|
| **[ME]** | The agent loop, tool schemas, context manager, verifier, judge rubric and calibration, eval scorer, workflow state machine, threat model, and every ADR |
| **[CLAUDE]** | The target-app binding to dcortex (`config/platform.md`), seeded-bug boilerplate, CI YAML, Dockerfiles, dashboards, and glue |
| **[PAIR]** | You write it, and Claude reviews |

## Monorepo

This folder becomes the root. Python packages share one uv workspace. TypeScript packages share one pnpm workspace.

| Package | Language | Phase | What it holds |
|---|---|---|---|
| `argus-core` | Python | P0 | Ticket, Task, and Trajectory types; OpenAI-compatible model client; quota ledger |
| `target-app` | TypeScript | P0 | Binding to the dcortex Canvas and copa-local Postgres in `config/platform.md`. Not a second UI |
| `bench` | Python + TypeScript | P0 | Scorer CLI and Playwright checks |
| `bugsmith` | TypeScript | P0 | Deterministic JSX and CSS mutation generator. No LLM |
| `repro-agent` | Python | P1 | Reproduction agent and the fail-before / pass-after verifier |
| `dom2src-plugin` | TypeScript | P2 | Vite plugin that injects `data-src` and strips it from production builds |
| `dom2src-mcp` | Python | P2 | `locate()` MCP server on MCP Python SDK v2 and the 2026-07-28 spec |
| `fix-loop` | Python | P3 | Agent loop, tools, context manager, sandbox runner, gates |
| `verify` | Python + TypeScript | P4 | Deterministic checks, judge, best-of-k |
| `eval` | Python | P5 | Eval runner, trajectory metrics, regression gate |
| `dashboard` | Static | P5 | GitHub Pages site built from results JSON |
| `skills/` | Markdown | P5.5 | Reviewed skill files in the agentskills.io format |
| `flow` | Python | P6 | FastAPI + DBOS control plane and the reconciliation poller |
| `guard` | Docs + config | P7 | Threat model, promptfoo configs, escape-test suite, audit-log verifier |
| `app` | Python | P8 | GitHub App and the reusable workflow |

P9 adds a small FastAPI target backend and lane-specific tools. It reuses `argus-core`, `fix-loop`, `verify`, `eval`, and `flow`.

Planned layout, once code exists:

```
argus/
├── PLAN.md  TASKS.md  repo-structure.md  PROJECT.md  PROJECT.html
├── pyproject.toml
├── pnpm-workspace.yaml
├── phases/
├── docs/
│   ├── adr/          # ADR-001 to ADR-030
│   ├── notes/
│   └── quotas.md     # measured free-tier limits (P0-T06)
├── .github/workflows/
└── packages/
    ├── argus-core/  target-app/  bench/  bugsmith/
    ├── repro-agent/  dom2src-plugin/  dom2src-mcp/
    ├── fix-loop/  verify/  eval/  dashboard/
    └── skills/  flow/  guard/  app/
```

Today only the planning documents and the three HTML companions are present.

## Models

One thin OpenAI-compatible client covers every host. The host is configuration (`base_url` and key), not a code branch.

| Role | Model | Host | Why this one |
|---|---|---|---|
| Fixer (strong) | Devstral 2 / Devstral Small 2 | Mistral free tier | A coding-agent model. The Mistral pricing page does not state these names, Apache-2.0 for Small, or 68–72% on SWE-bench Verified. No replacement number is written here |
| Cheap tier (repro, localize, summaries) | openai/gpt-oss-20b, qwen/qwen3.8-27b | Developer-plan base limits, organization level: RPM 30, RPD 1K, TPM 8K, TPD 200K. Cached tokens do not count. "free tier" is not stated. Qwen3.6-27B is not stated | Prompt caching becomes a quota lever, not only a cost lever |
| Intent judge (cross-family, vision) | Gemma 4 | Local Ollama `gemma4:e4b` on CPU for the ~100-pair calibration. A free hosted Gemma at runtime only if a P0 check finds one | A different family from the Mistral fixer, so self-preference can be measured |
| Same-family judge (ablation control) | A Mistral vision model | Mistral free tier | The comparison the self-preference ablation needs |
| Embeddings | A local open embedding model | Ollama or sentence-transformers on CPU | Offline, and free |

Mistral no longer publishes its free-tier numbers. **P0-T06 measures every limit** and records it in `docs/quotas.md`. That file wins over the table above.

## Infrastructure

| Concern | Choice |
|---|---|
| CI and execution plane | GitHub Actions on a public repo. Standard minutes are free, Docker is available, and Linux runners have exposed `/dev/kvm` since October 2025, which allows Firecracker and gVisor measurements at no cost |
| Control plane (P6) | Render free web service running FastAPI with DBOS in-process, plus Neon free Postgres. Render's free Postgres expires after 30 days, so it is not used |
| Traces | OTLP to Langfuse Cloud Hobby (free, 50k units/month). MIT is not stated on the pricing page. The pricing page says Langfuse is open source and can be self-hosted for free. Phoenix stays an alternative; its ELv2 licence is noted in ADR-015 |
| Dashboard | GitHub Pages, static |
| Sandboxes | Docker `--network none` locally and on Actions, then gVisor, then Firecracker on the Actions KVM runner. Each tier is measured in P7 and written up in ADR-025 |

### Versions checked on 2026-10-30

Each phase's T00 task re-checks this table before work starts. The source table is in [`PLAN.md`](PLAN.md).

| Component | Version |
|---|---|
| React | 19.3.1 |
| Vite | 8.3.5 (npm description: "Native-ESM powered web dev build tool". README: the production build bundles with Rolldown) |
| Tailwind | 4.3.3 |
| Playwright | 1.64.1 (npm dependencies: `playwright-core` only. Whether `playwright-core` embeds an MCP server is not stated. MCP is the separate `@playwright/mcp` package) |
| `@playwright/mcp` | 0.0.83 |
| MCP spec | **2026-07-28**: stateless core, MRTR `input_required` / `inputResponses`, Tasks moved to the `io.modelcontextprotocol/tasks` extension |
| MCP Python SDK | 2.3.0 |
| DBOS Python | 3.x |
| OTel GenAI semconv | `model/manifest.yaml` stability: development. Manifest `schema_url`: `https://opentelemetry.io/schemas/gen-ai-dev/1.42.0-dev`. README schema URL: TODO. Core semconv dependency: v1.44.0. Core semconv v1.42.0 (2026-06-12) moved `gen_ai.*` to this repo. README: "This repository extends the OpenTelemetry Semantic Conventions with GenAI-specific conventions." |

2026-10-30: version pins unchanged. React 19.3.1, Vite 8.3.5, Tailwind 4.3.3, Playwright 1.64.1, `@playwright/mcp` 0.0.83, MCP spec 2026-07-28, MCP Python SDK 2.3.0, and DBOS Python 3.x (PyPI `dbos` latest stable 3.4.0) match the previous check. Vite's npm description is still "Native-ESM powered web dev build tool", and the v8.3.5 README still says the production build bundles with Rolldown. Playwright 1.64.1's npm dependency list is still `playwright-core` only. Whether `playwright-core` 1.64.1 embeds an MCP server is still not stated: the v1.64.1 README does not mention MCP. `@playwright/mcp` stays its own row. The pinned rows use each registry's `latest` tag. The Playwright `next` dist-tag is `1.65.0-alpha-2026-10-29`, and `@playwright/mcp` 0.0.83's own npm dependencies are `playwright` and `playwright-core` at `1.64.0-alpha-1790635538000`; tool schemas from those trees stay off these rows. The MCP spec's latest stable GitHub release is still 2026-07-28, and the three changes named in that row are unchanged. The MCP Python SDK 2.3.0 package page does not name a spec date. OTel GenAI `stability: development` and the README schema URL TODO are unchanged. The row now also records the manifest `schema_url` and the core semconv dependency v1.44.0. The v1.42.0 move on 2026-06-12 is unchanged. The manifest's last commit is 2026-08-04.

2026-10-30, P2-T00: pins re-checked. React 19.3.1, Vite 8.3.5, Tailwind 4.3.3, Playwright 1.64.1, `@playwright/mcp` 0.0.83, MCP spec 2026-07-28, MCP Python SDK 2.3.0, and DBOS Python 3.x (PyPI `dbos` latest stable 3.4.0) are unchanged. Vite's npm description is still "Native-ESM powered web dev build tool", and the v8.3.5 README still says the production build bundles with Rolldown. Playwright 1.64.1 still depends only on `playwright-core`. The v1.64.1 `playwright-core` README still does not mention MCP. `@playwright/mcp` 0.0.83 still depends on `playwright` and `playwright-core` at `1.64.0-alpha-1790635538000`. The Playwright `next` dist-tag is now `1.65.0-alpha-2026-10-30`. That tag stays off the pinned row. The MCP spec's latest stable GitHub release is still tag `2026-07-28`, not a draft and not a prerelease, with `updated_at` `2026-07-28T16:47:49Z`. The MCP Python SDK 2.3.0 page still does not name a spec date. OTel GenAI `stability: development`, manifest `schema_url` `https://opentelemetry.io/schemas/gen-ai-dev/1.42.0-dev`, README schema URL TODO, core semconv dependency v1.44.0, and the manifest's last commit on 2026-08-04 are unchanged.

Re-check the React 19.2 removal of `source` and `self` from `jsxDEV` against React 19.3.1. The build-time `data-src` attribute remains the P2 route (ADR-006). Checked 2026-10-29: Babel's jsx-development docs still say those arguments were removed in React 19.2, and the React 19.3 changelog index lists no reversal. Checked again 2026-10-30 for P2-T00: Babel's `sourceSelf` option still says those arguments were removed since React 19.2. The React 19.3 blog's notable-changes list does not mention `jsxDEV` or `_debugSource`.

## Shared types

Defined in `argus-core` (ADR-001):

- **Ticket.** The bug report the agent sees: text, and optionally a screenshot.
- **Task.** A reproducible bench item: ticket, bug patch, golden patch, checks, and meta. A task directory is valid only when checks fail on the buggy tree and pass on the golden tree.
- **Trajectory.** One record per step of a run, including tokens in, out, and cached, plus a stop reason. A recorded trajectory must replay with no model call.

### Fix-loop tools

`read_file`, `list_dir`, `search`, `edit`, `run_cmd`, `submit`, plus ast-grep for structural search and rewrite. Repro tools are `navigate`, `snapshot`, `click`, `type`, `assert-visible`, and `screenshot`. `locate()` is a separate MCP server.

### Stop conditions (P3)

The loop stops on `submit`, a step cap, a token cap, `QuotaExceeded`, or stuck detection (the same tool call repeated). Malformed tool arguments return a typed error to the model. They do not crash the process.

### Context strategies (P3 ablation)

None (no compaction), output caps, offload-to-files with a pointer the model can `read_file`, and a rolling summary from the cheap-tier model. The budget manager calls the active strategy at 80% of the window.

### Quota ledger

A shared ledger in `argus-core` hard-stops a run before an HTTP request would cross a provider's measured daily cap. Cached tokens are counted apart from fresh tokens. State survives a process restart. From P8 the key includes a tenant id, so one tenant exhausting its share does not stop another.

## Metrics contract

Every phase reports the same four numbers listed in the learning rules (resolve rate, tokens/bug, $-equivalent, and p50/p95 latency), on the same evaluation set, against the previous phase. A number may appear only if a run id backs it.

| Metric | Definition |
|---|---|
| Resolve rate | Resolved over attempted, with a Wilson 95% interval. Resolved means the bench scorer passes on the final patch, no bench check file was touched, and (from P4) the verifier accepts. ADR-003 excludes exit 2 and tasks in `bench/quarantine/` from attempted, draws the ablation sample after quarantine, and keeps a mutant only on exit 1 then exit 0 with a non-empty check list |
| Tokens/bug | Mean, over tasks, of input, output, and cached tokens, summed over every agent, retry, judge call, and best-of-k sample for that bug. The three counts are reported separately |
| $-equivalent | Tokens times published list prices from `prices.json` (source URL and date per model). A comparison unit, not money spent. Cached tokens use the published cached rate when one exists, otherwise the input rate, and the choice is stated. P0 through P4 leave this cell as "—" until P5-T11, and "filled in" does not cover this column |
| Latency p50 and p95 | Wall-clock from task start to final patch. Time waiting for a quota reset is excluded and reported separately |

Rules that keep the numbers comparable:

- Ablations use a 30-task stratified subset. P8's single-agent vs planner comparison uses 20 tasks.
- Every run records model name, host, seed, prompt hash, and git commit.
- A difference smaller than the Wilson interval is reported as no difference.
- From P5, trajectory metrics are fixed in `docs/metrics.md`: steps, tool-error rate, redundant-call rate, stuck rate, and recover-after-gate-failure rate.

## Phases

Hours are at 20 h/week. Core work is P0 through P8: **556 hours, 255 tasks**, the sum of the phase table, in 28 weeks of work plus 2 buffer weeks, so 30 weeks. P9 adds about 40 hours and 17 tasks, two more weeks. The earlier sketch of ~23 weeks and ~180 tasks does not hold at $0, because Developer-plan caps (for example Groq's published TPD 200K and TPM 8K) stretch eval runs across nights. Quota-bound evals run overnight while the next phase's tasks are built during the day.

The hard cut line is the end of P6. That is the deployed core. P7, P8, and P9 can be dropped in the order in the cut list.

| Phase | Package | Hours | Tasks | What it adds | Ablation |
|---|---|---|---|---|---|
| P0 | argus-bench + bugsmith | 76 | 32 | Quota ledger; deterministic JSX/CSS mutations toward 300+ tasks | Seeded vs mutated bugs under a one-shot baseline |
| P1 | repro-agent | 32 | 17 | Playwright MCP (or direct Playwright if the interop spike fails) | Ticket text only vs text plus screenshot |
| P2 | dom2src | 44 | 20 | Vite `data-src` plugin; `locate()` MCP server | Repo-map/LSP vs pgvector vs `locate()`, top-1 file accuracy |
| P3 | fix-loop | 84 | 34 | Loop from scratch; worktree + Docker sandbox; context budget; gates | No compaction vs caps vs offload vs summarize, plus mini-swe-agent |
| P4 | verify | 72 | 30 | Pixel, overflow, axe, console; Gemma judge; Krippendorff's alpha | Same-family vs cross-family judge; best-of-k at k = 1, 3, 5 |
| P5 | argus-eval | 64 | 29 | Trajectory metrics; OTel + normalizer; router; CI gate; dashboard | Routing vs a single strong model |
| P5.5 | argus-skills | 28 | 18 | Skills distilled from successful trajectories; poisoned-skill red team | With vs without skills on held-out bugs |
| P6 | argus-flow | 52 | 26 | DBOS on Neon; QA wait; MRTR; Render deploy; reconciliation | Crash recovery: durable vs plain function. DBOS vs Temporal is an ADR only |
| P7 | argus-guard | 44 | 23 | OWASP ASI01–ASI10 threat model; audit log; promptfoo; sandbox tiers | Docker vs gVisor vs Firecracker: cold start and escape tests |
| P8 | argus-app | 60 | 26 | GitHub App; reusable workflow in the tenant repo; backport bot; planner | Single agent vs planner plus subagents on 20 tasks. Kept only if it wins on both resolve rate and tokens |
| P9 | backend lane (optional) | 40 | 17 | Sentry-style event to pytest to fix | Reuse ratio, by module and by lines |
| | **Core P0–P8** | **556** | **255** | | |

### P0 — bench and bugsmith (weeks 1–4)

Build a deterministic benchmark that scores a fix with no model in the loop, and a quota ledger that keeps later phases inside free tiers.

Done when the golden-fix run passes on all 30 hand-seeded tasks in GitHub Actions with zero model calls; `bugsmith` emits 300 or more tasks that fail their Playwright checks before the fix and pass after, and two runs with the same seed hash identically; the ledger refuses a call that would exceed a measured daily limit before any HTTP request; `docs/quotas.md` holds the measured limits with a date and a method.

Six UI bug archetypes and three difficulty tiers. Ten seeded tasks per tier. Flake detection runs each task's checks five times on the buggy tree and on the golden tree, and quarantines mixed results. A one-shot patch baseline (one model call, no tools) is the agent the seeded-vs-mutated ablation is measured against.

ADRs: 001 task and trajectory schema, 002 quota ledger semantics, 003 mutation validity and flake policy.

### P1 — repro-agent (weeks 4–6)

Turn a ticket into a Playwright script that fails on the buggy tree and passes on the golden tree.

A spike (P1-T01) calls Playwright MCP from an MCP Python SDK v2 client and writes a go or no-go. If it is no-go, direct Playwright is the tool (ADR-004). The loop generates a script, runs it, and revises on error, with a hard retry cap. The verifier returns `valid`, `passes-on-bug`, `fails-on-golden`, or `error`. CI replays recorded fixtures with no model calls.

ADRs: 004 Playwright MCP vs direct Playwright, 005 when a screenshot earns its tokens.

### P2 — dom2src (weeks 6–8)

Map a rendered element back to a source file and line, and measure that against text retrieval.

The Vite plugin adds `data-src` on every JSX host element in dev and test builds and strips it from production. `locate()` errors are typed: `not-found`, `ambiguous`, `no-source-info`. Wrapper components return ranked candidates, not a confident wrong file. The other two retrievers are a repo-map plus LSP index, and pgvector with a local CPU embedding model. The harness scores top-1 and top-3 file accuracy against the file the golden patch touches.

ADRs: 006 `data-src` vs source maps, 007 which retriever is the default.

### P3 — fix-loop (weeks 8–12)

The largest phase. Write the loop from scratch, run it in a sandbox, and compare it with mini-swe-agent on the same 30 tasks and the same model.

The sandbox is a git worktree per task inside Docker with `--network none`, CPU and memory caps, and bench checks mounted read-only. `AGENTS.md` for target-app is loaded into the system prompt. A recorded trajectory replays byte for byte from stored model responses, with no model call. CI fails if an agent-framework package appears in the dependency list. Failed runs get a written failure taxonomy.

ADRs: 008 loop control and stop conditions, 009 context management, 010 sandbox baseline, 011 the rule for adopting a framework later.

### P4 — verify (weeks 12–16)

Decide whether a patch fixed the bug and broke nothing else. Deterministic checks first, then a calibrated judge, then a measurement of what extra samples buy.

Check order is fixed and short-circuits on the first hard failure (ADR-012). The rubric asks whether the fix matches the ticket's intent without collateral change. You label 100 pairs (ticket, before, after) before seeing any judge output. Rubric edits are made on a dev split and checked on a held-out split. Target agreement is Krippendorff's alpha of at least 0.80, with a bootstrap interval, implemented and tested against a published worked example. If the budget runs out below 0.80, ADR-013 records the shortfall and the judge is advisory only. A same-family Mistral vision judge is the self-preference control. Best-of-k runs at k = 1, 3, and 5. k = 5 is the biggest quota consumer in the plan, because it multiplies fixer calls by five per bug. A rejected patch gets one retry with the verdict in context.

ADRs: 012 gate order, 013 judge selection, 014 best-of-k policy and cost cap.

### P5 — eval (weeks 16–20, with a buffer week at 17)

Measure how the agent got there, not only whether the patch passed, and test whether routing cheap and strong models beats one strong model.

Spans use OTel GenAI attributes, which are still in development. The normalizer maps argus attribute names onto a backend and lets unknown attributes pass through, counted. The same run must be viewable in Langfuse and in a second local OTLP backend (Phoenix) by changing the endpoint and the normalizer profile. The router is data, not code branches: cheap tier for repro and localize, strong tier for fix, with a fallback host when the ledger refuses. The system prompt and tool list form a byte-stable prefix so prompt caching can hit. A CI gate fails when resolve rate drops below the stored baseline's lower bound. A SWE-bench Multimodal subset of 10 to 20 tasks is adapted into the Task format; excluded tasks are listed with a reason, never dropped silently. The dashboard is a static page deployed to GitHub Pages.

ADRs: 015 trace backend and normalizer, 016 routing policy, 017 CI gate thresholds.

### P5.5 — skills (weeks 20–21)

Distil at least five reviewed skills from successful trajectories, in the agentskills.io format, and show that a poisoned skill cannot take over the agent.

The loader puts only name and description in the prompt and loads the body through `load_skill` (progressive disclosure). Skills are distilled from a train set that does not overlap the 30-task held-out subset. Trust controls: a review flag, a content-hash pin, and a per-skill tool allowlist. An unreviewed or hash-changed skill is refused. CI lints frontmatter, size, and the hash file.

ADRs: 018 skill format and distillation criteria, 019 skill trust model.

### P6 — flow (weeks 22–24)

The deployed core. Run the pipeline as a durable workflow that survives crashes, free-tier sleep, and lost webhooks.

DBOS checkpoints each step against Postgres. Steps are idempotent: opening a pull request is find-or-create, keyed by ticket id, so a kill between the side effect and the state save does not open a second PR. The FastAPI webhook checks an HMAC signature, enqueues a reconcile, and returns 202 without reading GitHub inline. The poller rebuilds state from the issue, the pull request, and the Actions run. QA waits in `awaiting-qa` until approve, reject, or timeout. MRTR elicitation is built, and so is the plain review-comment fallback; ADR-023 says which one ships. Render cold start is measured against the 10 second webhook timeout. Neon CU-hours are measured over 48 hours of polling and compared with 100 CU-hours/project. "per month" is not stated. DBOS vs Temporal is a written decision only. Temporal is not built.

ADRs: 020 DBOS vs Temporal, 021 webhooks as hints, 022 free-tier topology, 023 QA signal path.

This phase is the hard cut line. A portfolio that stops here is a deployed, free-tier, crash-recoverable workflow.

### P7 — guard (weeks 24–27, with a buffer week at 25)

Write the threat model, harden the pipeline, red-team it, and measure isolation tiers.

`guard/threat-model.md` maps assets, trust boundaries, and data flows onto OWASP agentic risks ASI01 through ASI10, each with a threat, a control, and a residual risk, or an explicit reason it does not apply. Secrets stay out of prompts, logs, trajectories, and traces. The GitHub App token is least-privilege and short-lived; negative tests show that a push to a protected branch and a call on another repo are refused. The audit log is append-only and hash-chained; `guard verify-log` names the first bad line. promptfoo covers injection through the ticket, through a repo file, and through a skill. Escape probes cover network, host filesystem, the Docker socket, the metadata address, a fork bomb, and symlinks. Tiers: Docker with `--network none`, gVisor (`runsc`), and a Firecracker microVM on the Actions KVM runner. If Firecracker is cut, that row stays empty and ADR-025 says why.

ADRs: 024 threat model, 025 sandbox tier, 026 secrets and token scopes.

### P8 — app (weeks 27–30)

Package Argus as a public GitHub App. Each tenant runs a reusable workflow in their own repo, so the agent job, the code, and the tenant's secrets stay off your servers (ADR-027).

Tenant config is `.argus.yml`: start command, test command, routes, budget. A missing field is a typed error, not a guess. Intake starts on a label, and ignores the label when the actor lacks write access. The pull request body has the verdict, the judge label, a trajectory link, and two screenshots. Re-running updates the same PR. The backport bot comments on conflict and does not force-push. A planner-plus-subagents variant is kept only if it beats the single agent on both resolve rate and tokens per bug (ADR-029). The demo install is one of your own public repos. The landing README states the free-tier training-data caveat. The demo video, under four minutes, shows a success, a verifier rejection, and a quota refusal.

ADRs: 027 tenancy via a reusable workflow, 028 per-tenant quota budgets, 029 single agent vs planner and subagents.

### P9 — backend lane (weeks 30–32, optional, cut first)

A second lane, to test whether the P3–P6 boundaries were drawn in the right place. A small FastAPI backend (six endpoints: auth, CRUD, one background job) gets Python mutations: off-by-one, wrong status code, missing await, swapped arguments. An exported Sentry event JSON (stack, request, breadcrumbs) becomes a Ticket. No live Sentry. The repro step is a pytest that fails on the bug and passes on the golden fix, reusing the P1 verifier. The P3 fixer is reused with a pytest gate instead of browser gates. No copy of the P3 code. The backend verifier checks that the new test fails before and passes after, old tests still pass, and no new exception types appear. PII (email, bearer token) is redacted at ingestion, before any model call. A script reports reuse by module and by lines (ADR-030).

## Week by week

Weeks are 20 hour bins in task order, and a week can run up to 3 h over 20 because a task is placed in the week it starts. Weeks under 20 h are week 9 (19 h), week 10 (19 h), week 15 (19 h), week 19 (18 h), week 20 (19 h), week 27 (19 h), week 31 (19 h), and week 32 (16 h). A phase may start in the tail of the previous phase's last week. Buffer weeks have no scheduled tasks. The exact checklist is [`TASKS.md`](TASKS.md).

| Week | Focus |
|---|---|
| 1 | Skeleton, types, model client, measure real quotas, quota ledger |
| 2 | target-app, task format, check library, 30 seeded tasks, scorer CLI |
| 3 | Golden-fix CI, flake detection, bugsmith operators |
| 4 | Validity filter, 300+ tasks, seeded-vs-mutated ablation. **P0 done.** MCP interop spike |
| 5 | Repro tools, repro loop, text vs text-plus-screenshot |
| 6 | **P1 done.** Vite `data-src` plugin starts |
| 7 | `locate()` server, repo-map/LSP, pgvector, retrieval ablation |
| 8 | **P2 done.** P3 tool schemas |
| 9 | Worktree, Docker sandbox, agent loop, recorder, context manager |
| 10 | Three context strategies, AGENTS.md, gates |
| 11 | mini-swe-agent baseline, context ablation, failure taxonomy |
| 12 | **P3 done.** Pixel-diff check starts |
| 13 | Deterministic checks, verifier pipeline, rubric, label 100 pairs |
| 14 | Local Gemma judge, Krippendorff's alpha, same-family vs cross-family |
| 15 | best-of-k, verifier wired into the loop |
| 16 | **P4 done.** Trajectory metrics and eval runner |
| 17 | Buffer. Catch up, or finish quota-bound runs |
| 18 | OTel, Langfuse, normalizer, router, prompt caching, routing ablation |
| 19 | CI regression gate, SWE-bench Multimodal subset, dashboard |
| 20 | **P5 done.** Skills loader, train and held-out split |
| 21 | **P5.5 done.** Reviewed skills, ablation, poisoned-skill break-its |
| 22 | State machine, DBOS, Actions dispatch, webhook, reconcile, QA wait |
| 23 | MRTR, Neon and Render, cold-start and CU-hour measurements, crash recovery |
| 24 | **P6 done: deployed core.** Threat model starts |
| 25 | Buffer |
| 26 | Audit log, promptfoo, gVisor, Firecracker, escape suite |
| 27 | **P7 done.** GitHub App manifest |
| 28 | Installation tokens, reusable workflow, tenant config, per-tenant budgets, PR creation |
| 29 | Backport bot, planner ablation, install on your own public repo |
| 30 | Demo, release checklist. **P8 done.** Optional P9 starts |
| 31–32 | Backend target, Sentry parser, pytest lane, reuse ratio. **P9 done** |

## Known free-tier collisions

Measured in P6, not assumed.

- An always-on Render service with DBOS polling would keep Neon awake, which likely exceeds Neon's 100 CU-hours/project. "per month" is not stated.
- Render cold starts take about one minute. "30 to 60" seconds is not stated. That is longer than GitHub's 10 second webhook timeout.
- The design that follows: webhooks are hints, and a reconciliation poller restores state from GitHub.

Langfuse Hobby is 50k units per month. Neon free compute is 100 CU-hours/project. "per month" is not stated. Groq's published Developer-plan organization limits are RPM 30, RPD 1K, TPM 8K, and TPD 200K, and cached tokens do not count. "free tier" is not stated. All of these are re-verified by each phase's T00, and the Groq and Mistral numbers are replaced by `docs/quotas.md` once P0-T06 is done.

## Risks

| # | Risk | What is done about it |
|---|---|---|
| 1 | Free-tier quotas change or disappear. GitHub Models was reportedly retired in July 2026. GitHub Actions minutes and public-repo policy are the single execution plane | Provider-agnostic client, quota ledger, a local Ollama host for the judge and for embeddings, the roles that already have a second host. P0-T05, P0-T06, P0-T07, every T00 |
| 2 | The open-weight fixer resolves too few bugs for ablations to show a signal | Seeded set tiered by difficulty; confidence intervals; a 30-task stratified subset. P0-T12, P0-T14, P3-T18 |
| 3 | Neon CU-hours and Render sleep collide with DBOS polling | Measure in P6; reconciliation; ADR-021 and ADR-022 |
| 4 | Playwright MCP may not speak the 2026-07-28 spec that the SDK v2 client expects | Spike in P1. If it fails, Playwright is called directly as a tool. P1-T01, P1-T02, P2-T00 |
| 5 | Scope and fatigue at 20 h/week for about seven months | Hard cut after P6. Buffer weeks after P4 and after P6. The cut list below |
| 6 | One laptop CPU. The machine is a 13th-gen Intel i7-13620H with 16 GB RAM and no discrete GPU. Judge calibration and embeddings run on that CPU | P4-T13 and P2-T10 stay on this machine |
| 7 | Langfuse Cloud Hobby at 50k units/month is the default trace viewer. A full quota can drop the traces the dashboard links | Phoenix is the scheduled swap. P5-T09, ADR-015 |

## Cut list

Cut in this order when time or quota runs out:

1. P9, the whole backend lane
2. P8 multi-tenancy, down to a single-tenant App
3. P5.5, argus-skills
4. The Firecracker tier, reduced to an ADR plus a gVisor measurement
5. MRTR elicitation, replaced by plain GitHub review comments
6. SWE-bench Multimodal, keeping the synthetic set only

Never cut: the P3 loop, the P4 judge calibration, the bugsmith generator, the P5 OTel work, or best-of-k.

## What is deployed, and when

| Phase | Deployed |
|---|---|
| P0–P3 | GitHub Actions runs the bench as a deterministic golden-fix run, by manual dispatch while dcortex-platform is private. No model calls; push-time checks are the other workflows |
| P4 | The same, plus verify tests on stored screenshots |
| P5 | Dashboard on GitHub Pages, traces in Langfuse, CI regression gate on stored results |
| P5.5 | Skill-file lint in CI |
| P6 | Render free (FastAPI + DBOS) and Neon free, with Actions as the execution plane |
| P7 | Secrets outside the repo, `--network none` tested on Actions, append-only audit log verified in CI |
| P8 | A public GitHub App, a landing README, and a demo video |
| P9 | Backend golden-fix joins the existing Actions jobs. A second series on the dashboard. No new host |

## ADR index

All of them are written by [ME]. Files land in `docs/adr/` as `NNNN-title.md`.

| ADR | Phase | Decision |
|---|---|---|
| 001 | P0 | Task and Trajectory schema |
| 002 | P0 | Quota ledger semantics: hard stop, cached tokens, day boundary |
| 003 | P0 | Mutation validity and flake policy |
| 004 | P1 | Playwright MCP vs direct Playwright as a tool |
| 005 | P1 | When the screenshot is worth its tokens |
| 006 | P2 | `data-src` attribute vs source maps |
| 007 | P2 | Retrieval strategy |
| 008 | P3 | Loop control, stop conditions, tool-call format |
| 009 | P3 | Context management policy |
| 010 | P3 | Sandbox baseline: worktree plus Docker, no network |
| 011 | P3 | What evidence would justify an agent framework |
| 012 | P4 | Gate order and short-circuit |
| 013 | P4 | Which judge ships, and what happens if alpha stays below 0.80 |
| 014 | P4 | Best-of-k policy and cost cap |
| 015 | P5 | Trace backend and the attribute normalizer |
| 016 | P5 | Which stages go to which model tier |
| 017 | P5 | CI gate thresholds, from measured run-to-run noise |
| 018 | P5.5 | Skill format and what a trajectory must show before it becomes a skill |
| 019 | P5.5 | Skill trust: review flag, hash pin, tool allowlist |
| 020 | P6 | DBOS vs Temporal (decision only) |
| 021 | P6 | Webhooks as hints, GitHub as source of truth |
| 022 | P6 | How Render sleep and Neon compute constrain the topology |
| 023 | P6 | QA via MRTR or via a review comment |
| 024 | P7 | Threat model and trust boundaries |
| 025 | P7 | Which sandbox tier is the default |
| 026 | P7 | Secret lifetimes and token scopes |
| 027 | P8 | Tenancy via a reusable workflow in the tenant's repo |
| 028 | P8 | Per-tenant quota budgets |
| 029 | P8 | Single agent vs planner and subagents, kept only if both metrics win |
| 030 | P9 | Which interfaces held when a second lane was added |

## The three tasks most likely to force a redesign

1. **P0-T24, the bugsmith validity filter.** It has to keep only mutations whose Playwright checks fail on the bug and pass on the golden fix. The 300-task set (P0-T26) depends on it.
2. **P4-T14, judge calibration.** Reaching alpha of 0.80 with a CPU-bound open judge may not be possible. ADR-013 defines the advisory-only fallback.
3. **P6-T12 and P6-T14, the DBOS deployment on Render and Neon.** The CU-hour measurement may force a different poll cadence or topology.

## How this folder is meant to be read

| File | Use it for |
|---|---|
| [`PROJECT.md`](PROJECT.md) / [`PROJECT.html`](PROJECT.html) | This description |
| [`PLAN.md`](PLAN.md) | Stack, architecture diagram, metrics contract, risks, cut list |
| [`TASKS.md`](TASKS.md) | The flat checklist, week by week, with owner and hours |
| [`repo-structure.md`](repo-structure.md) | Package layout |
| [`phases/P00-argus-bench.md`](phases/P00-argus-bench.md) through [`phases/P09-backend-lane.md`](phases/P09-backend-lane.md) | Tasks, acceptance criteria, break-it cases, empty ablation tables, ADRs |
| [`architecture.html`](architecture.html) | Interactive block diagram |
| [`production.html`](production.html) | One ticket through the deployed system |
| [`142-fix.html`](142-fix.html) | A sample fix report |
