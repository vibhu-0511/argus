# P8 — argus-app

**Budget:** 60 h · **Weeks:** W25–28 in the base plan (calendar weeks in `TASKS.md` include the buffer) · **Packages:** `app` (py: GitHub App plus the reusable workflow), uses `flow`, `guard`, `eval`

## Goal
Package Argus as a public GitHub App where each tenant runs a reusable workflow in their own repo, with per-tenant quota budgets, a backport bot and a demo.

## Done when
- A labelled issue on one of your own public repos produces a pull request end to end through the installed App, with a documented real run (links to the issue, PR and trace).
- The agent job runs as a reusable workflow in the tenant's repo, not on your infrastructure, and ADR-027 records why.
- The quota ledger has a tenant dimension, and one tenant exhausting its budget does not stop another (tested).
- The backport bot opens a backport PR for a merged fix, and comments instead of forcing when a cherry-pick conflicts.
- The landing README and a demo video exist, and the README states the free-tier data caveat: prompts sent to free tiers may be used for training, so only synthetic or public code is used.
- Single agent vs planner plus subagents is run on 20 tasks, and the variant is kept only if it wins on both resolve rate and tokens/bug (rule in ADR-029; Ablation table filled).
- Phase report filled against P7.

## Agentic concepts learned
1. **Multi-agent trade-offs** — when a planner plus subagents beats one agent, and what it costs in tokens.
2. **Tenancy for agent systems** — whose compute, whose quota and whose credentials, and the reusable-workflow model that keeps code in the tenant's repo.
3. **Fairness under a shared quota** — per-tenant budgets on a single set of free-tier provider limits.
4. **Agents as repo citizens** — issue intake, PR creation with evidence, and backports that fail safe.
5. **Shipping an agent product** — onboarding config, limits written down, a demo that shows the failure cases too.

## Interview questions
1. When would you add subagents to a coding agent, and what measurement would make you remove them again?
2. Why run the agent job in the tenant's repo through a reusable workflow instead of on your own servers, and what does each choice do to your threat model and quota?

## Prereq reading
- [How we built our multi-agent research system (Anthropic)](https://www.anthropic.com/engineering/multi-agent-research-system)
- [Building effective agents (Anthropic)](https://www.anthropic.com/engineering/building-effective-agents)
- [mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent)

## Tasks
| ID | Title | Owner | Type | Est hrs | Depends on | Acceptance criteria |
|---|---|---|---|---|---|---|
| P8-T00 | Re-verify pinned versions via web search | [CLAUDE] | doc | 1 | P7-T22 | Versions table re-checked; GitHub App and reusable-workflow limits and free-tier model limits confirmed; date updated |
| P8-T01 | Read the multi-agent and building-effective-agents posts, write notes | [ME] | learn | 1 | P8-T00 | Notes state the claimed token overhead of multi-agent systems and the conditions where it pays |
| P8-T02 | Create the GitHub App manifest with the P7 least-privilege permissions | [PAIR] | build | 3 | P8-T00, P7-T04 | The App registers from the manifest; its permission list matches ADR-026; webhook URL points at the P6 service |
| P8-T03 | Build installation flow and installation-token minting in the flow service | [PAIR] | build | 3 | P8-T02, P6-T05 | After installing on a test repo, the service mints a short-lived token scoped to that repo only; a call on another repo fails |
| P8-T04 | Write the reusable workflow that runs the agent job in the tenant's repo | [CLAUDE] | build | 3 | P8-T02, P6-T04 | A tenant workflow of five lines calls it with `workflow_call` and runs repro, fix and verify; the agent step's environment has no `GITHUB_TOKEN`; ADR-026 names whether the tenant workflow token or the App installation token is the principal that pushes; no secret is passed except through the tenant's own secrets |
| P8-T05 | Define the tenant config file and write the onboarding doc | [PAIR] | build | 3 | P8-T04 | `.argus.yml` fields (start command, test command, routes, budget) are validated; a missing field gives a typed error; onboarding doc is under one page |
| P8-T06 | Make the runner target-agnostic using the tenant config | [PAIR] | build | 3 | P8-T05 | The same runner works on the dcortex repo in `config/platform.md` and on a second small repo with a different layout, without code changes |
| P8-T07 | Add per-tenant quota budgets to the ledger with a fair-share rule | [ME] | build | 3 | P8-T03, P0-T07 | Ledger keys include tenant id; one tenant at its budget is refused while a second proceeds; unit test covers both |
| P8-T08 | Build ticket intake: a labelled issue starts a workflow | [PAIR] | build | 2 | P8-T03, P6-T07 | Adding the label starts exactly one workflow; a label added by a user without write access is ignored |
| P8-T09 | Build PR creation with verdict, trajectory link and before and after screenshots | [PAIR] | build | 3 | P8-T08, P4-T22 | The PR body has the verifier verdict, the judge label, a trajectory link and two screenshots; the PR is built through the API with title and body as JSON fields; a fixture title containing `$(...)` is not executed; one stable branch; one creator that is not the agent; draft until QA; no PR when the patch is empty; a lookup error leaves the existing PR untouched; re-running updates the same PR |
| P8-T10 | Build the backport bot with conflict handling | [PAIR] | build | 3 | P8-T09 | On a merged fix, the bot opens a backport PR to a configured branch; on conflict it comments and does nothing destructive |
| P8-T11 | Build the planner and subagents variant of the loop | [ME] | build | 4 | P3-T06, P5-T12 | A planner emits sub-tasks; subagents run with their own context budget; total tokens across all agents are counted in the ledger |
| P8-T12 | Run ablation: single agent vs planner and subagents on 20 tasks | [ME] | eval | 4 | P8-T11, P5-T04 | Two rows filled from real runs on the same 20 tasks; tokens counted across all agents; Wilson 95% intervals |
| P8-T13 | Write ADR-027: Tenancy via a reusable workflow in the tenant's repo | [ME] | doc | 1 | P8-T06 | ADR compares running in the tenant repo vs on your servers on quota, trust boundary and cost, and says the backport head is a branch the tenant workflow is allowed to test |
| P8-T14 | Write ADR-028: Per-tenant quota budgets | [ME] | doc | 1 | P8-T07 | ADR states the fair-share rule and what happens at a provider limit |
| P8-T15 | Write ADR-029: Single agent vs planner and subagents | [ME] | doc | 1 | P8-T12 | ADR states the keep rule (must win on both success and tokens) and applies it to the measured rows |
| P8-T16 | Install the App on one of your own public repos and run one issue end to end | [PAIR] | deploy | 3 | P8-T10, P8-T06 | A real issue produces a PR; the issue, PR and trace links are in the README; the repo is public and holds no private code |
| P8-T17 | Write the landing README: what it does, quickstart, limits, security model, free-tier caveat | [CLAUDE] | doc | 3 | P8-T16 | A reader can install and run it in under 10 minutes by following the README; limits and the training-data caveat are stated |
| P8-T18 | Record the demo video including one failure and its recovery | [PAIR] | deploy | 2 | P8-T16 | A video under 4 minutes is linked in the README; it shows a success, a verifier rejection and a quota refusal |
| P8-T19 | Complete the public release checklist | [CLAUDE] | doc | 2 | P8-T17 | Licence file present, secret scan green, no private data in fixtures, quota limits documented; checklist is committed |
| P8-T20 | Add CI job for app tests and reusable-workflow lint, no LLM | [CLAUDE] | deploy | 2 | P8-T04 when the multi-tenancy cut is taken; otherwise P8-T07, P8-T04 | Workflow green; lint passes on the reusable workflow; tests cover token minting and label permissions; the budget assertion is included only when P8-T07 is kept; the PR is built through the API with title and body as JSON fields; a fixture title containing `$(...)` is not executed; ADR-027 says the backport head is a branch the tenant workflow is allowed to test |
| P8-T21 | Break it: let one tenant exhaust its budget while another runs | [ME] | test | 2 | P8-T07 | The first tenant is refused with a typed quota message and the second tenant's run completes; written up in the Break it section |
| P8-T22 | Break it: install on a repo with no test command configured | [ME] | test | 2 | P8-T05 | The App comments a typed config error and does not crash or guess; written up |
| P8-T23 | Break it: force a cherry-pick conflict in a backport | [ME] | test | 2 | P8-T10 | The bot comments the conflict and leaves branches untouched; the test fails on a force-push of the bot branch and on a failed push that still retries pull-request creation from a stale branch; it refuses a tenant conflict command and a checkout of the PR head under the installation token; a second run finds the existing PR or no-ops; written up |
| P8-T24 | Break it: add the intake label as a user without write access | [ME] | test | 2 | P8-T08 | The label is ignored and the ignore is logged; written up |
| P8-T25 | Write package README and phase report against P7 | [CLAUDE] | doc | 1 | P8-T19 | Package README shows App setup and workflow usage; phase report has previous-phase, this-phase and delta rows filled |

## Break it on purpose
1. **Tenant exhausts its budget (P8-T21).** *Induced failure:* set one tenant's budget low and start two tenants' runs. *Expected signal:* the first gets a typed quota refusal; the second finishes. *Fix:* ledger keys per tenant with a fair-share cap on each provider.
2. **Missing test command (P8-T22).** *Induced failure:* install on a repo whose config has no test command. *Expected signal:* a comment with a typed config error, not a crash or a guessed command. *Fix:* validate `.argus.yml` at intake and say what is missing.
3. **Backport conflict (P8-T23).** *Induced failure:* backport a fix onto a branch that has diverged. *Expected signal:* a comment describing the conflict; the test fails on a force-push of the bot branch and on a failed push that still retries pull-request creation from a stale branch. *Fix:* abort the cherry-pick, leave the branch alone, refuse a tenant conflict command and a checkout of the PR head under the installation token, and on a second run find the existing PR or no-op.
4. **Label from an untrusted user (P8-T24).** *Induced failure:* a non-collaborator adds the intake label to an issue. *Expected signal:* ignored and logged. *Fix:* check the actor's permission before starting a workflow.

## Ablation
**Hypothesis:** a planner plus subagents solves more of the 20 tasks than a single agent but costs more tokens; it is kept only if it wins on both resolve rate and tokens/bug.
**Variants:** A = single agent (fix-loop); B = planner plus subagents.
**Metric:** resolve rate (Wilson 95% interval), tokens/bug across all agents, quota share per bug, subagent calls per bug.

| Variant | Resolve rate (95% CI) | Tokens/bug (in, out, cached) | $-equivalent/bug | Quota share/bug | p50 latency | p95 latency | Subagent calls per bug |
|---|---|---|---|---|---|---|---|
| A | — | — | — | — | — | — | — |
| B | — | — | — | — | — | — | — |

**Status (2026-11-04):** not measured, 0 of 20 tasks run for either variant. The local `gemma4:e4b` is not installed on the build machine. The harness, configs and owner steps are in `docs/notes/p8-t12.md`. When filled, say the model (`gemma4:e4b`, a small local model, not the production model) and the run counts.

**Phase report (against previous phase):**

| Report | Resolve rate | Tokens/bug | $-equivalent | p50 latency | p95 latency |
|---|---|---|---|---|---|
| Previous phase (P7) | — | — | — | — | — |
| This phase (P8) | — | — | — | — | — |
| Delta | — | — | — | — | — |

*Every cell is a dash on purpose; filled on 2026-11-04 (P8-T25) from stored results only, and no stored result exists for these columns.*
- **Previous phase (P7): dashes.** P7 has no resolve-rate, token or latency numbers: it measured sandbox cold start, escape probes and a red-team on a small local model, not the fix loop (see its report in `phases/P07-argus-guard.md`). No P7 baseline was made up.
- **This phase (P8): dashes.** The only P8 task that would give these columns is P8-T12 (single agent vs planner, 20 tasks). It ran 0 of 20 tasks for either variant: no Ollama server, no `ollama` binary and no `gemma4:e4b` on the build machine (checked again on 2026-11-04: no answer on `http://localhost:11434`, no `packages/eval/results/p8-t12/`), and the rules allow no other model for it (`docs/notes/p8-t12.md`). No other P8 task runs the fix loop against a model: the runner tests use a fake fix agent and nothing has run on GitHub. A resolve rate from those would be invented.
- **Delta: dashes**, because both sides are dashes. When T12 runs, `python -m eval.ablation table A.json B.json` fills the Ablation table above; `python -m eval report <previous.json> <this.json>` fills this one, and needs a P7 results file that does not exist, so its previous row stays dashes unless P7 is measured.
- **What P8 did measure, kept out of the table because it answers other questions:**

| Measure | Value | Source and limit |
|---|---|---|
| App package tests | 248 passed in 787 s | `uv run --all-packages python -m pytest packages/app/tests -q`, run on 2026-11-04 on Windows 11, no Postgres set; no test calls a model |
| Ledger, planner and ablation-harness tests | 30 passed (`argus-core` ledger and `fix-loop` planner together), 7 passed (`eval` ablation run) | same day; stub models only |
| Flow tests for token minting, intake and the label break-it | 80 passed | `test_app_token.py`, `test_intake.py`, `test_break_it_t24.py`; mock GitHub; the Postgres-backed installation and tenant-ledger tests were not run for this report |
| Tenant at its budget while another runs | refused with a typed message; the second tenant finished with `submit` | `packages/app/tests/test_break_tenant_quota.py`; scripted fake model, not a real provider |
| Release checklist | 2 of 4 items done | `docs/release-checklist.md`: secret scan and quota limits done; licence and the private-data sweep of `docs/` open |
| Open P8 tasks | T02, T03, T04, T06, T12, T16, T17, T18, T19, T20 | each needs an owner step or a real GitHub run; see `TASKS.md` and `packages/app/README.md` |

## ADRs to write
All [ME].
- **ADR-027 — Tenancy via a reusable workflow in the tenant's repo.** Whose compute, quota and credentials does a run use?
- **ADR-028 — Per-tenant quota budgets.** What is the fair-share rule, and what happens when the provider limit itself is hit?
- **ADR-029 — Single agent vs planner and subagents.** Does the measured gain on both success and tokens justify the extra moving parts?

## Deploy checkpoint
A public GitHub App, a landing README, and a demo video. The install target for the demo is one of your own public repos only, because prompts on free tiers may be used for training.

## Portfolio artifact
The public App repo with the landing README, the demo video, the tenant-isolation and quota design, and the single-vs-multi-agent ablation with its keep rule.
