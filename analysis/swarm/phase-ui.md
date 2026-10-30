# phase-ui: how the Argus UI grows, P0 to P9

Lane `ui-growth`, 2026-10-30. Source of truth for the `#plan/growth` view (`analysis/explainer-src/70-ui-growth.html`). Generated from `analysis/swarm/phase-ui.json`; hours and status come from `analysis/swarm/tracker.json` (11 phases, 596 h with P9, 49 of 272 tasks checked done).

**Honesty.** BUILT TODAY = a real file or a command captured today, shown verbatim. P1's 28/30 `valid` is fixture replay (`host: "fixture"`, `batch.py:67`), not a model result (see `analysis/swarm/verify-p0p1.md`). P0's golden CI workflow is red (0 green of 7 recorded runs). Everything else is PLANNED and illustrative: angle-bracket placeholders, dashes for results. The only real image is `packages/bench/tasks/seeded/bug-17/shots/radar-card.png`; no real "after" image exists.

## Growth at a glance

| Phase | Name | Hours | Cum. h | Status | New surfaces | Built today |
|---|---|---|---|---|---|---|
| P0 | argus-bench + bugsmith | 76 | 76 | done | 6 | 6 |
| P1 | repro-agent | 32 | 108 | done | 5 | 5 |
| P2 | dom2src | 44 | 152 | open | 3 | 0 |
| P3 | fix-loop | 84 | 236 | open | 3 | 0 |
| P4 | verify | 72 | 308 | open | 3 | 0 |
| P5 | argus-eval | 64 | 372 | open | 3 | 0 |
| P5.5 | argus-skills | 28 | 400 | open | 2 | 0 |
| P6 | argus-flow | 52 | 452 | open | 3 | 0 |
| P7 | argus-guard | 44 | 496 | open | 3 | 0 |
| P8 | argus-app | 60 | 556 | open | 4 | 0 |
| P9 | backend lane (optional) | 40 | 596 | open | 2 | 0 |
| final | Final product | — | 596 | planned | 2 | 0 |

## P0 argus-bench + bugsmith (76 h, W1–4)

**Status:** done (checked done in TASKS.md). **Evidence:** REAL_RECORDED; REFUTED (CI golden is red 5/5).

**Newly visible (delta):** Everything. The first rung is a command line and some files: a task directory format, a bench CLI, a quota ledger and a CI badge. There is no web UI yet.

**The owner can:**
- Run bench validate / score / golden / flake / baseline / mutate from the repo root.
- Open a task directory (ticket.json, bug.patch, golden.patch, checks.json, meta.json) and read the ticket the way an agent would.
- Read docs/quotas.md to see how many model calls the free tier allows before a run is refused.
- Read the 0/10 baseline: how a single model call from ticket + file text fares (and why that number mostly measures harness limits).

**Screenshot-able moment:** The BUG-17 task directory: the ticket text beside its one real screenshot (radar-card.png) and the check that decides pass or fail. (`undefined`)

**Depends on:** nothing earlier

| Surface | Kind | Label | Artifact |
|---|---|---|---|
| bench validate <task dir> | cli | BUILT TODAY | `packages/bench/src/argus_bench/cli.py:57-65` |
| bench mutate --seed 1 | cli | BUILT TODAY | `docs/notes/p0-t26.md` |
| tasks/seeded/bug-17/ | file | BUILT TODAY | `packages/bench/tasks/seeded/bug-17` |
| docs/quotas.md (machine-readable limits) | file | BUILT TODAY | `docs/quotas.md` |
| docs/notes/p0-t29.md (one-shot baseline) | file | BUILT TODAY | `docs/notes/p0-t29.md` |
| GitHub Actions: golden + repro | github | BUILT TODAY | `.github/workflows/golden.yml` |

## P1 repro-agent (32 h, W5–6)

**Status:** done (checked done in TASKS.md). **Evidence:** FIXTURE_ONLY (28/30 valid is by construction); REFUTED (repro CI is red 2/2).

**Newly visible (delta):** A second command (the repro batch) and a runs/ tree: one verdict.json and one trajectory.jsonl per task, a quota ledger file, and a wave board for how the phase was built. Still no web UI.

**The owner can:**
- Run the repro batch and read one verdict per task (valid / passes-on-bug / error with a stop reason).
- Open a run directory: the saved script, the verdict and the trajectory.
- Check the quota ledger after a run: how many requests and tokens were charged today.
- Read the P1 wave board to see which tasks could run in parallel.

**Screenshot-able moment:** runs/text-only/bug-17: a Sign-in script saved against a font-size ticket. The same script is saved for every ticket, because the replies are fixtures. (`undefined`)

**Depends on:** P0 (builds on argus-core types, the quota ledger and the bench task dirs (phases/P01-repro-agent.md:3))

| Surface | Kind | Label | Artifact |
|---|---|---|---|
| repro_agent.batch text-only | cli | BUILT TODAY | `packages/repro-agent/runs/text-only` |
| runs/text-only/bug-17/ | file | BUILT TODAY | `packages/repro-agent/runs/text-only/bug-17` |
| runs/text-only/ledger.json | file | BUILT TODAY | `packages/repro-agent/runs/text-only/ledger.json` |
| docs/architecture/p1.md (wave board) | file | BUILT TODAY | `docs/architecture/p1.md` |
| GitHub Actions: repro (fixture replay) | github | BUILT TODAY | `.github/workflows/repro.yml` |

## P2 dom2src (44 h, W6–8)

**Status:** open. **Evidence:** PLANNED.

**Newly visible (delta):** The first web-visible thing: every DOM element in a test build carries a data-src attribute, and a locate() tool turns a selector into file:line:col (or a typed "ambiguous" with candidates).

**The owner can:**
- Inspect any element of the Canvas test build and read its source file and line off data-src.
- Call locate(selector) from an MCP client and get a file and line, or the candidate list when a wrapper component is involved.
- Read the three-way retrieval ablation (repo-map + LSP, pgvector, data-src) once the 30-task run is filled.

**Screenshot-able moment:** A DOM inspector with data-src on a host element, next to the locate() answer for the same selector. (`undefined`)

**Depends on:** P0 (target-app binding to the dcortex Canvas (phases/P02-dom2src.md:3))

| Surface | Kind | Label | Artifact |
|---|---|---|---|
| Canvas test build, inspector view | web | PLANNED (P2), illustrative | — |
| locate() over MCP | cli | PLANNED (P2), illustrative | — |
| Retrieval ablation table | file | PLANNED (P2), illustrative | — |

## P3 fix-loop (84 h, W8–12)

**Status:** open. **Evidence:** PLANNED.

**Newly visible (delta):** The agent itself: a fix-loop that turns ticket + repro + locate hint into a patch inside a sandbox, with a trajectory file per run and a replay command that needs no model.

**The owner can:**
- Run the loop on one task and watch each tool call stream (read_file, edit, run_cmd, submit).
- Read the stop reason and decide whether to retry, raise the cap or take over by hand.
- Replay a stored trajectory deterministically, with no LLM call.
- Compare the four context strategies and the mini-swe-agent baseline in the ablation table.

**Screenshot-able moment:** A terminal streaming one fix run to a recorded stop reason, with the patch it produced. (`undefined`)

**Depends on:** P0 (bench checks and quota ledger); P1 (repro script feeds the task prompt (P3-T16)); P2 (locate() hint feeds the task prompt (P3-T16))

| Surface | Kind | Label | Artifact |
|---|---|---|---|
| fix-loop run <task> | cli | PLANNED (P3), illustrative | — |
| trajectory.jsonl + patch | file | PLANNED (P3), illustrative | — |
| Stop reasons (what the owner acts on) | cli | PLANNED (P3), illustrative | `packages/argus-core/src/argus_core/types.py:74-82` |

## P4 verify (72 h, W12–16)

**Status:** open. **Evidence:** PLANNED.

**Newly visible (delta):** A verdict view: four deterministic checks in a fixed order, then an advisory judge, on a before / after pair, plus the calibration and best-of-k tables.

**The owner can:**
- Open a verdict and see which check failed first (pixel diff, overflow, axe, console).
- Compare before and after screenshots for one candidate fix.
- Read the judge calibration (alpha against 100 hand labels) before deciding to trust the judge.
- Choose k for best-of-k from the cost curve.

**Screenshot-able moment:** The before / after review: the ticket screenshot on the left, the candidate fix on the right, the check ladder beside them. (`undefined`)

**Depends on:** P3 (verifier is the final gate of fix-loop (P4-T22)); P0 (bench scorer and screenshots)

| Surface | Kind | Label | Artifact |
|---|---|---|---|
| Verdict review: before / after | web | PLANNED (P4), illustrative | — |
| Verifier pipeline | cli | PLANNED (P4), illustrative | — |
| Judge calibration and best-of-k | file | PLANNED (P4), illustrative | — |

## P5 argus-eval (64 h, W16–19)

**Status:** open. **Evidence:** PLANNED.

**Newly visible (delta):** The first deployed web page: a static dashboard on GitHub Pages with resolve rate and intervals, tokens per bug, latency and trajectory metrics, plus a trace link and a CI regression gate.

**The owner can:**
- Open the dashboard and read the phase-over-phase report (resolve rate with Wilson intervals).
- Click through to a full-run trace in Langfuse.
- See a PR blocked by the regression gate when a stored run is deliberately worse.
- Read the routing ablation: cheap tier for repro and localize, strong tier for fix.

**Screenshot-able moment:** The dashboard cards: resolve rate with interval, tokens per bug, latency, and the quota share. (`undefined`)

**Depends on:** P3 (stored trajectories feed the metrics); P4 (verdicts feed resolve rate); P0 (ledger and quotas feed the quota cell)

| Surface | Kind | Label | Artifact |
|---|---|---|---|
| Dashboard (GitHub Pages) | web | PLANNED (P5), illustrative | — |
| Trace of one run (Langfuse) | web | PLANNED (P5), illustrative | — |
| CI regression gate | github | PLANNED (P5), illustrative | — |

## P5.5 argus-skills (28 h, W19–20)

**Status:** open. **Evidence:** PLANNED.

**Newly visible (delta):** Skill files and one more dashboard row. Skill descriptions load up front; bodies load on demand; a lint job guards the files.

**The owner can:**
- Read the skill list (name + description only) the way the agent sees it.
- Open one reviewed skill and edit it.
- Read the with-vs-without-skills row on the held-out set.
- See the poisoned-skill break-it outcomes.

**Screenshot-able moment:** A SKILL.md with its short front matter on top and the body that loads only when selected. (`undefined`)

**Depends on:** P3 (skill loader lives inside fix-loop); P5 (ablation row lands on the dashboard)

| Surface | Kind | Label | Artifact |
|---|---|---|---|
| skills/<name>/SKILL.md | file | PLANNED (P5.5), illustrative | — |
| Dashboard: with vs without skills | web | PLANNED (P5.5), illustrative | — |

## P6 argus-flow (52 h, W22–24)

**Status:** open. **Evidence:** PLANNED.

**Newly visible (delta):** A control plane: a deployed run board (Render + Neon) listing runs by workflow state, a QA wait that pauses a run for the owner, and a quota meter. Runs now happen without a terminal.

**The owner can:**
- Open the run board and see every ticket by state, including stuck and quota-wait.
- Approve or reject a run waiting for QA (review comment, or MRTR if ADR-023 ships it).
- Kill the worker mid-run and watch the run resume without a duplicate PR.
- See the quota meter before starting another run.

**Screenshot-able moment:** The run board with the QA-wait row highlighted and the quota meter. (`undefined`)

**Depends on:** P3 (fix-loop runs as the execution plane); P4 (verifier verdict is what QA reviews); P1 (repro-agent is a workflow step); P5 (dashboard keeps running beside it)

| Surface | Kind | Label | Artifact |
|---|---|---|---|
| Run board (control plane) | web | PLANNED (P6), illustrative | — |
| Workflow state machine | web | PLANNED (P6), illustrative | — |
| QA signal as a review comment | github | PLANNED (P6), illustrative | — |

## P7 argus-guard (44 h, W23–25)

**Status:** open. **Evidence:** PLANNED.

**Newly visible (delta):** Safety surfaces: a public threat model (ASI01 to ASI10), a tamper-evident audit log with a verify command, red-team results and a sandbox-tier comparison.

**The owner can:**
- Run the audit-verify command and see it detect an edited line.
- Read the threat model row by row: threat, control, residual risk.
- Read red-team outcomes for injection through the ticket, a repo file and a skill.
- Compare Docker, gVisor and Firecracker on cold start and escape-test pass rate.

**Screenshot-able moment:** The audit verify command catching a tampered line. (`undefined`)

**Depends on:** P6 (hardening across flow (phases/P07-argus-guard.md:3)); P3 (hardening across fix-loop and its sandbox); P5.5 (skill injection path (P7-T07; conditional on the P5.5 cut))

| Surface | Kind | Label | Artifact |
|---|---|---|---|
| audit log verify | cli | PLANNED (P7), illustrative | — |
| Threat model, ASI01 to ASI10 | file | PLANNED (P7), illustrative | — |
| Sandbox tiers | file | PLANNED (P7), illustrative | — |

## P8 argus-app (60 h, W25–28)

**Status:** open. **Evidence:** PLANNED.

**Newly visible (delta):** The GitHub-native product: install the App on a repo, label an issue, receive a pull request with verdict, trajectory link and before / after screenshots, and a backport bot.

**The owner can:**
- Install the App on one of your own public repos with the least-privilege permissions.
- Label an issue and watch a PR appear with its evidence.
- Review the PR and merge, or leave a comment for the agent.
- See the backport bot comment instead of forcing a conflicted cherry-pick.
- Check one tenant's quota without touching another's.

**Screenshot-able moment:** The pull request the App opens for a labelled issue: verdict, trajectory link and the before / after pair. (`undefined`)

**Depends on:** P6 (flow service dispatches the job and holds state); P7 (least-privilege token, audit log (P8-T02)); P5 (eval and quota ledger feed tenant budgets)

| Surface | Kind | Label | Artifact |
|---|---|---|---|
| GitHub App install | github | PLANNED (P8), illustrative | — |
| Labelled issue to PR | github | PLANNED (P8), illustrative | — |
| Backport bot | github | PLANNED (P8), illustrative | — |
| Per-tenant quota | web | PLANNED (P8), illustrative | — |

## P9 backend lane (optional) (40 h, W30–32)

**Status:** open. **Evidence:** PLANNED (optional; first on the cut list, PLAN.md:320).

**Newly visible (delta):** A second lane, optional and first on the cut list: a Sentry-style error event becomes a failing pytest, then a verified fix, on a small FastAPI target backend.

**The owner can:**
- Feed an exported Sentry event JSON and get a Ticket.
- Watch the lane produce a failing pytest, a fix and a verifier verdict.
- Read the reuse ratio by module and by lines.

**Screenshot-able moment:** One backend run end to end: event, failing pytest, fix, verdict. (`undefined`)

**Depends on:** P8 (reuses loop, verifier, eval and flow (phases/P09-backend-lane.md:3)); P3 (fixer reused with a pytest gate); P4 (verifier interface reused)

| Surface | Kind | Label | Artifact |
|---|---|---|---|
| Backend lane run | cli | PLANNED (P9), illustrative | — |
| Reuse ratio report | file | PLANNED (P9), illustrative | — |

## final Final product

**Status:** planned. **Evidence:** PLANNED (end state).

**Newly visible (delta):** The owner's flow closes: type an issue (text or screenshot), receive an HTML report with before and after on the production UI, verify it, and only then have the agent raise the PR.

**The owner can:**
- Type an issue, with or without a screenshot.
- Open the generated before / after report and verify it.
- Approve, and have the PR raised.

**Screenshot-able moment:** The whole path on one screen: issue in, report out, PR after approval. (`undefined`)

**Depends on:** P8 (GitHub issue and PR plumbing); P6 (durable workflow and QA wait); P4 (verdict behind the report); P3 (the fix); P1 (the repro)

| Surface | Kind | Label | Artifact |
|---|---|---|---|
| The owner's flow, source phase per step | web | PLANNED (final), illustrative | — |
| Open the finished screens | web | PLANNED (final), illustrative | — |

## Where the owner's flow differs from PLAN.md

- Trigger: the owner types an issue (text or screenshot). The plan starts from a labelled GitHub issue (P8-T08, `phases/P08-argus-app.md`).
- Output: the owner gets an HTML before / after report first. The plan opens a PR with the evidence attached (P8-T09) and uses a QA signal as a review comment or MRTR (P6-T08..T10).
- PR timing: the owner wants the PR raised after approval. The plan opens it as a draft before approval.

## Notes for the fragment

- Panes are rendered newest-phase first; earlier panes stay.
- Re-generate with the throwaway script kept outside the repo; the JSON is the contract for `70-ui-growth.html`.
