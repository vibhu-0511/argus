# P0 — argus-bench + bugsmith

**Budget:** 76 h · **Weeks:** W1–4 · **Packages:** `argus-core`, `target-app`, `bench`, `bugsmith`

## Goal
Build a deterministic benchmark of UI bug tasks (hand-seeded plus mutation-generated) against the dcortex Canvas and Postgres named in `config/platform.md`. Score a fix with no LLM in the loop, and keep a quota ledger that holds every later phase inside the free tiers. `target-app` is that binding, not a second UI.

## Done when
- The golden-fix run passes on 100% of the 30 hand-seeded tasks, with zero LLM calls. It runs in GitHub Actions by manual dispatch (`golden.yml`), not on every push, because the golden patches apply to the private dcortex-platform repo, which the default `GITHUB_TOKEN` cannot read. Push-time CI is `repro.yml`.
- `bugsmith` emits 300 or more tasks. Each one fails its Playwright checks on the buggy tree and passes them on the golden-fixed tree, confirmed by the bench scorer, not by eye.
- Two bugsmith runs with the same seed produce an identical task-set hash.
- A call that would exceed a provider's measured daily limit is refused by the quota ledger before any HTTP request is sent (unit test).
- `docs/quotas.md` holds the measured free-tier limits per provider and role, each with a date and a method.
- The Ablation tables below are filled in by you from real runs, with the baseline row of the phase report included. "Filled in" does not cover the $-equivalent cell, which stays "—" until P5-T11. This phase does not create `prices.json`.

## Agentic concepts learned
1. **Ground-truth verification** — a task is only valid if its checks fail before the fix and pass after it.
2. **Synthetic task generation by mutation** — deterministic mutation operators as scalable benchmark data (the SWE-smith idea, applied to JSX/CSS).
3. **Budget as a first-class constraint** — a quota ledger that hard-stops a run, with cached tokens counted separately.
4. **Provider-agnostic model access** — one OpenAI-compatible client, many hosts; the host is configuration, not code.
5. **Flakiness as measurement noise** — a flaky check silently corrupts every resolve rate computed on top of it.

## Interview questions
1. How do you know a benchmark task is valid, and what does one flaky check do to a resolve rate you report with a confidence interval?
2. What bias does a hand-seeded bug set have that a mutation-generated set does not, and what bias does the generated set have in return?

## Prereq reading
- [SWE-smith: scaling data for software engineering agents](https://arxiv.org/abs/2504.21798)
- [SWE-bench Multimodal](https://arxiv.org/abs/2410.03859)
- [Engineering Reliable Coding Agents](https://arxiv.org/abs/2608.13867)

## Tasks
| ID | Title | Owner | Type | Est hrs | Depends on | Acceptance criteria |
|---|---|---|---|---|---|---|
| P0-T00 | Re-verify pinned versions via web search | [CLAUDE] | doc | 1 | — | Every row of the PLAN.md versions table is re-checked against its registry or release page; the "checked on" date is updated and any change is listed in one line |
| P0-T01 | Create monorepo skeleton (uv workspace, pnpm workspace, folders) | [CLAUDE] | build | 2 | P0-T00 | `uv sync` and `pnpm install` exit 0 on a fresh clone; directory tree matches `repo-structure.md` |
| P0-T02 | Read SWE-smith and SWE-bench Multimodal, write one page of design notes | [ME] | learn | 2 | P0-T00 | `docs/notes/p0-bench-design.md` answers: what makes a task valid, what makes it flaky, which bug types are in scope for UI |
| P0-T03 | Define Ticket, Task and Trajectory types and JSON schema in argus-core | [ME] | build | 3 | P0-T01 | JSON schema files exist; a sample of each type round-trips through parse and serialize with a unit test; invalid samples are rejected |
| P0-T04 | Write ADR-001: Task and Trajectory schema | [ME] | doc | 1 | P0-T03 | `docs/adr/0001-*.md` states the decision, alternatives considered and consequences; linked from `PLAN.md` |
| P0-T05 | Build OpenAI-compatible model client with per-provider config | [PAIR] | build | 2 | P0-T03 | One client calls a mock server, Groq, Mistral and local Ollama by changing only `base_url` and key from the active block in `config/profiles.md`; mock-server unit test passes. A profile whose `wire_format` is not `openai-compatible` does not satisfy this task |
| P0-T06 | Measure real free-tier quotas (Groq, Mistral, hosted Gemma check) and record them | [ME] | eval | 4 | P0-T05 | `docs/quotas.md` has requests/day, tokens/day, rate limits and cached-token behaviour per model, with date and method; one line states whether a free hosted Gemma exists |
| P0-T07 | Implement quota ledger with hard stop and cached-token accounting | [ME] | build | 4 | P0-T06 | Unit test: the call after the limit raises `QuotaExceeded` and no HTTP request is made; ledger state survives a process restart |
| P0-T08 | Write ADR-002: Quota ledger semantics | [ME] | doc | 1 | P0-T07 | ADR covers hard stop vs warn, per-model vs per-provider counting, day boundary and cached tokens |
| P0-T09 | Bind target-app to the dcortex Canvas and copa-local Postgres | [CLAUDE] | build | 4 | P0-T01 | `packages/target-app/README.md` matches `config/platform.md`: repo path, `copa-local`, console `http://localhost:19080`, env names only, and the five flows. No Canvas source is copied in. No database password is committed. The package does not start its own Vite app |
| P0-T10 | Define bench task directory format (ticket, bug patch, golden patch, checks, meta) | [ME] | build | 2 | P0-T03, P0-T09 | A sample task directory validates against the Task schema; `bench validate <dir>` exits 0 |
| P0-T11 | Build Playwright check library (pixel diff, bounding-box asserts, computed-style asserts) | [PAIR] | build | 3 | P0-T09 | Each check type passes on a clean worktree of the dcortex repo in `config/platform.md` and fails on a hand-broken copy of that same worktree; demonstrated in one test file. The five flows in that file are the first surfaces |
| P0-T12 | Define 6 UI bug archetypes and 3 difficulty tiers | [PAIR] | doc | 1 | P0-T02 | `docs/bug-archetypes.md` lists archetypes and tier criteria |
| P0-T13 | Generate boilerplate for 30 seeded bug tasks | [CLAUDE] | build | 3 | P0-T10, P0-T11, P0-T12 | 30 task directories exist under `bench/tasks/seeded/`, all pass `bench validate`, 10 per tier, and each task references one archetype |
| P0-T14 | Review and hand-tune the 30 seeded tasks until each is valid | [PAIR] | build | 3 | P0-T13 | For every task, checks fail on the buggy tree and pass on the golden tree, shown by one script run; invalid tasks are fixed or dropped and replaced |
| P0-T15 | Build scorer CLI: run a task's checks against a tree and emit a JSON verdict | [ME] | build | 4 | P0-T10, P0-T11 | `bench score <task> --tree <path>` returns exit 0 on pass, 1 on fail, 2 on infra error; JSON verdict validates; no network access needed; `bench score` keeps the unsliced log |
| P0-T16 | Build golden-fix runner over all tasks | [PAIR] | build | 2 | P0-T14, P0-T15 | `bench golden --all` applies each golden patch, scores it, prints a pass count; exit 0 only if all pass |
| P0-T17 | Add CI workflow: golden-fix run on every push, no LLM calls | [CLAUDE] | deploy | 2 | P0-T16 | A push triggers the workflow; it is green; the workflow file has no secrets and no model-provider env vars |
| P0-T18 | Add flake detection: run each task's checks 5 times on buggy and golden trees | [ME] | test | 2 | P0-T16 | `bench flake --all` lists any task with mixed results; flaky tasks are quarantined into `bench/quarantine/` |
| P0-T19 | Break it: make a golden patch stale | [ME] | test | 2 | P0-T17 | Induced failure reproduced and detected as in the Break it section; fix applied; CI green again |
| P0-T20 | Break it: introduce a nondeterministic animation | [ME] | test | 2 | P0-T18 | Flake detector flags the affected task; task is quarantined; written up in the Break it section |
| P0-T21 | Build bugsmith mutation-operator interface and AST pipeline | [ME] | build | 4 | P0-T10 | An operator takes a source file and a seed and returns a patch; the same seed gives the same patch (unit test) |
| P0-T22 | Implement JSX mutation operators (remove class, swap flex direction, drop prop, change element) | [PAIR] | build | 3 | P0-T21 | At least 4 operators, each with a test showing the changed source and that the app still builds |
| P0-T23 | Implement CSS mutation operators (delete rule, change unit, z-index, overflow) | [PAIR] | build | 3 | P0-T21 | At least 4 operators, each with a test showing the changed source and that the app still builds |
| P0-T24 | Build mutation validity filter: keep only fail-before, pass-after mutants | [ME] | build | 4 | P0-T15, P0-T22, P0-T23 | Filter rejects a mutant with no visual change and a mutant that breaks the build; a mutant is kept only on exit 1 on the mutant then exit 0 on the original, with a non-empty check list |
| P0-T25 | Break it: feed the validity filter an equivalent mutant | [ME] | test | 2 | P0-T24 | Filter rejects the mutant with a reason code; written up in the Break it section |
| P0-T26 | Run bulk generation to 300 or more valid tasks with a fixed seed | [ME] | eval | 2 | P0-T24 | `bench/tasks/mutated/` holds 300 or more validated tasks; running again with the same seed gives an identical task-set hash |
| P0-T27 | Write ADR-003: Mutation validity and flake policy | [ME] | doc | 1 | P0-T26 | ADR states the validity rule, the flake threshold, and that exit 2 and quarantined tasks are excluded from "attempted" |
| P0-T28 | Build one-shot patch baseline (single model call, no tools) | [PAIR] | build | 2 | P0-T05, P0-T14 | `bench baseline <task>` produces a patch from ticket plus file contents in one call; its token use is recorded in the ledger |
| P0-T29 | Run ablation: seeded vs mutated bugs under the one-shot baseline | [ME] | eval | 2 | P0-T26, P0-T28 | Both rows of the Ablation table are filled from a real run, with Wilson 95% intervals; the mutated sample is drawn after quarantine; the $-equivalent cell stays "—" until P5-T11; this task does not create `prices.json`; runs used the ledger and stayed under quota |
| P0-T30 | Break it: exhaust the quota ledger mid-run | [ME] | test | 2 | P0-T07, P0-T28 | The run stops with `QuotaExceeded` before the next request; partial results are saved; written up in the Break it section |
| P0-T31 | Write package README and phase report | [CLAUDE] | doc | 1 | P0-T29 | README shows install, run and scorer commands; the phase report table below has its baseline row filled |

## Break it on purpose
1. **Stale golden patch (P0-T19).** *Induced failure:* edit the target app so a golden patch no longer applies cleanly. *Expected signal:* `bench golden --all` exits non-zero and CI turns red, naming the task. *Fix:* regenerate the golden patch against the new tree, re-run validation.
   On a temporary repo, `golden_all` printed `fail stale-probe` and returned non-zero, then printed `pass stale-probe` and returned 0 after the patch was regenerated; the workflow has no `continue-on-error`, and GitHub red was not observed because there is no remote.
2. **Nondeterministic animation (P0-T20).** *Induced failure:* add a randomised CSS transition delay to one route. *Expected signal:* `bench flake --all` reports mixed pass/fail on that task. *Fix:* disable the animation in the test build, or quarantine the task.
   While the fixture CSS contained `transition-delay: random;`, `flake_all` printed `anim-probe` and moved it into a temp quarantine, and after that line was removed the same call returned 0 and left the task in place.
3. **Equivalent mutant (P0-T25).** *Induced failure:* run an operator that changes a class name which has no visual effect. *Expected signal:* validity filter rejects it with a "no observable change" reason. *Fix:* tighten the operator's applicability rule so it targets visible properties.
   `judge_mutant(0, 0, ["computed_style"])` returned `no-observable-change`, and `removeClass` no longer edits a lone class that is not `flex-row` or `flex-col`.
4. **Quota exhausted mid-run (P0-T30).** *Induced failure:* set the ledger limit to a tiny value and start a baseline run over many tasks. *Expected signal:* `QuotaExceeded` is raised before an HTTP request, the run halts and writes partial results. *Fix:* make the runner resume from the saved partial results the next day.
   With `requests_per_day` set to 1, `baseline_many` raised `QuotaExceeded` before the second task and kept the first patch in the partial file, then resumed the next calendar day and skipped the finished task.

## Ablation
**Hypothesis:** the hand-seeded and mutation-generated tasks give the same resolve rate under a fixed baseline agent; if not, the mutated set cannot stand in for realistic bugs.
**Variants:** A = seeded tasks (30); B = mutated tasks (random sample of 30 from the 300+).
**Metric:** resolve rate with a Wilson 95% interval; also tokens/bug, $-equivalent, p50/p95 latency.

| Variant | Resolve rate (95% CI) | Tokens/bug (in, out, cached) | $-equivalent/bug | Quota share/bug | p50 latency | p95 latency |
|---|---|---|---|---|---|---|
| A | 0/10 [-0.000000, 0.277540] | 4585.0000, 1044.0000, 0.0000 | — | — | 3.652305s | 4.842286s |
| B | 0/1 [0.000000, 0.793457] | 3516.0000, 713.0000, 0.0000 | — | — | — | — |

**Phase report (against previous phase; this is the baseline):**

| Report | Resolve rate | Tokens/bug | $-equivalent | p50 latency | p95 latency |
|---|---|---|---|---|---|
| Baseline | 0/10 [-0.000000, 0.277540] | 4585.0000, 1044.0000, 0.0000 | — | 3.652305s | 4.842286s |

## ADRs to write
All [ME].
- **ADR-001 — Task and Trajectory schema.** What fields make a task reproducible and a trajectory replayable?
- **ADR-002 — Quota ledger semantics.** Should the ledger hard-stop or warn, and how are cached tokens and the day boundary counted?
- **ADR-003 — Mutation validity and flake policy.** What exactly makes a generated mutant a valid task, and what is done with flaky ones?

## Deploy checkpoint
GitHub Actions runs `bench golden --all` by manual dispatch while dcortex-platform is private (it needs a read-only `PLATFORM_REPO_TOKEN` repo secret for that repo; on every push of a public repo once the patches can be read without it). It is a deterministic golden-fix run with no LLM calls and no provider keys in the workflow.

## Portfolio artifact
A public repo with a green CI badge, a task-set hash for the 300+ generated tasks, and the seeded-vs-mutated ablation write-up with intervals.
