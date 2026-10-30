# verify-p0p1: claim ledger for P0 and P1

Lane `verify-p0p1`. Checkout: worktree `agent-swarm-verification-b4db5f`, 2026-10-30. No model API was called. Docker, the dcortex repo and the network were not used by my test runs (one read-only `gh run` query was made, see C).

Labels: **REAL** = backed by a live run or a deterministic test I could re-run. **REAL†** = the author recorded a live run (`docs/notes/*`), but I could not re-run it here (needs the external dcortex repo, Chromium or a provider key). **FIXTURE-ONLY** = wiring proven, quality not. **UNVERIFIED** = no artifact, or the artifact contradicts the claim. **REFUTED** = evidence says the claim is false.

## A. Verdict on the four claims you asked about

| Claim | Verdict | Evidence |
|---|---|---|
| P1 "28/30 valid" is fixture replay | **CONFIRMED, and stronger: it is true by construction.** | `packages/repro-agent/src/repro_agent/batch.py:67` `host="fixture"`. `:80-86` `_complete` returns one hard-coded script `VALID` (`:24-27`) for every task except `seed-h01` (`LOOSE`, `:28-30`), with `Usage(1,1,0)`. `:89-97` `_trees` decides the tree outcome from `"Welcome" in script`, not from any browser, any task, or any tree. `:100-106` `_verdict` re-derives the same answer and passes it to `verify(...)` with hard-coded `"fail"`/`"pass"` strings. So 28 tasks are `valid`, `seed-e01` is a scripted crash, `seed-h01` is a scripted loose selector. Nothing in the 30 depends on the task. Artifacts agree: `runs/text-only` = 28 valid/submit, 1 error/tool-unavailable, 1 passes-on-bug/retry-cap; `runs/text-plus-image` is byte-identical in verdicts (`diff` of all 30 `verdict.json`: identical). Every trajectory has `"host": "fixture"` (30/30 in both dirs). |
| P0 baseline 0/10 | **CONFIRMED as a live Groq run, but it measures patch-application failure and a tiny sample, not model skill.** | `docs/notes/p0-t29.md`: model `openai/gpt-oss-20b`, host `api.groq.com`, A k=0 n=10. The per-task list shows all 10 attempted tasks ended `not_applied`; the other 20 of 30 seeded tasks were never attempted: 11 `exit2_unfit` (prompt over the 8000 TPM minute cap), 8 `call_error` (HTTP 413), 1 `exit2_bug` (bug-17 patch did not apply). Variant B is n=1 of 30 (28 `exit2_unfit`, 1 `call_error` 429, 1 `not_applied`). The ablation harness is not in the repo (only the notes survive), so the table cannot be regenerated. |
| Only BUG-17 has a screenshot | **CONFIRMED.** | `find` shows one image file in the repo: `packages/bench/tasks/seeded/bug-17/shots/radar-card.png` (103,536 bytes = 101.1 KB, matches `docs/adr/0005-screenshot-in-ticket-context.md:11`). Only `bug-17/ticket.json` has a `screenshot` key (`grep -l` over seeded tickets). No mutated ticket has one. |
| `.github/workflows/golden.yml` cannot pass on a clean ubuntu runner | **CONFIRMED by code and by GitHub's own logs.** | See C. All 5 recorded `golden` runs failed; latest run 41058615064: `fatal: cannot change to 'C:\Users\vibha\Downloads\data\dcortex\dcortex_claude\dcortex-platform': No such file or directory` then `exit code 2`. The `repro` workflow also fails on every run (2/2), which is a second finding. |

## B. Tests I ran (exact commands, results)

Environment: Windows 11, uv 0.12.2, CPython 3.12.10, node v24.16.0. The worktree had no `node_modules` (I did not run `pnpm install`).

| # | Command (repo root) | Result |
|---|---|---|
| 1 | `uv run pytest packages/argus-core/tests -q` | **13 passed** (3.8 s) |
| 2 | `uv run pytest packages/bench/tests -q` | **27 passed, 2 failed** (11.9 s). Failure 1: `test_golden.py::test_platform_repo_and_seeded_tasks` asserts `len(task_dirs()) == 30` but got **330** (30 seeded + 300 mutated; `golden.py:28-35` walks both dirs). The test is stale and fails on the committed code. Failure 2: `test_score.py::test_score_pass_fail_and_unsliced_reasons` got exit 2, `Cannot find package '@playwright/test'`. That one is my environment (no `pnpm install`), not a code bug; I did not retry after installing. |
| 3 | `uv run pytest packages/repro-agent/tests/{test_replay,test_loop,test_tools,test_prompt,test_tool_unavailable,test_batch,test_break}.py -q` (the exact list CI uses, plain `uv run`) | **5 collection errors**: `ModuleNotFoundError: No module named 'repro_agent'` in test_replay, test_loop, test_tool_unavailable, test_batch, test_break. Reproduced in a fresh venv (`UV_PROJECT_ENVIRONMENT` in the temp dir). Cause: root `pyproject.toml` depends only on `argus-core` and `argus-bench`, so plain `uv run` never installs `repro-agent`. |
| 4 | Same list with `uv run --package repro-agent pytest ...` | **24 passed** (5.9 s). So the tests are fine; the CI command is wrong. |
| 5 | `cd packages/bugsmith && node --test test/apply-operator.test.ts test/operators.test.ts` | **3 passed, 0 failed.** (`pnpm test` runs exactly these two files, `packages/bugsmith/package.json`.) `remove-class.test.ts` is not in the `test` script. |
| not run | `packages/repro-agent/tests/test_docker.py`, `test_verify.py` (shells out to `docker run`, `verify.py:33-45` (`run_fixture_scripts`)), `test_against_app.py` (needs the Playwright MCP server via `npx`), `packages/bench/tests/checks.spec.ts` (needs `pnpm install`, Chromium and a dcortex worktree), `bench golden --all` (would `git worktree add` on the external dcortex repo, `golden.py:45-50`) | Skipped per lane rules (no Docker/network/external repo writes). Claims that depend only on these stay REAL† or UNVERIFIED below. |

## C. CI on GitHub (read-only `gh run list/view --log-failed --repo vibhu-0511/argus`)

`.github/workflows/golden.yml:14` runs `uv run bench golden --all`; `repro.yml:14` runs plain `uv run pytest ...`. There is now an `origin` remote (the P0 notes say "no remote"; `docs/notes/p0-t19.md` is stale on this point).

- 7 runs listed: `golden` 5 failures, `repro` 2 failures, **0 successes**. Runs: `golden` on commits "Add the later phase plans" through "Finish the screenshot run and close P1".
- `golden` fails with exit 2 on the first git call. `platform_repo()` (`golden.py:15-25`) reads the Windows path from `config/platform.md` (`| Repo |` row). The workflow never checks out dcortex, never runs `pnpm install`, `playwright install` or sets up Node, and `golden_all` returns 2 when `git worktree add` fails (`golden.py:51-53`). Even with the repo present, it would run 330 tasks (`task_dirs()`), not the 30 the Done-when names.
- `repro` fails with 5 `ModuleNotFoundError: repro_agent` collection errors in the runner log (same as B3).
- So P0 "Done when" #1, "Deploy checkpoint" (P0), P0-T17 "it is green", P1-T09 "Workflow green on push" and the "CI badge" portfolio artifact are all **REFUTED**. TASKS.md still has them `[x]`.

## D. Claim ledger: P0 "Done when" (`phases/P00-argus-bench.md:8-14`)

| # | Claim | Evidence | Label |
|---|---|---|---|
| P0-D1 | Golden-fix run passes 100% of the 30 seeded tasks in GitHub Actions on every push, zero LLM calls | No stored `30/30` output anywhere in the repo. Workflow has no LLM keys (true, `golden.yml`). CI is red 5/5 (C). Locally unrun by me. Stale test (B2) asserts 30 but the command now runs 330. | **REFUTED** (CI) / **UNVERIFIED** (local pass) |
| P0-D2 | bugsmith emits ≥300 tasks, each fails on buggy and passes on golden per the scorer | 300 dirs exist under `packages/bench/tasks/mutated/` (counted). Run recorded in `docs/notes/p0-t26.md:1-18` (kept 300, dropped 517: 396 empty-checks, 2 no-observable-change, 119 not-fail-then-pass). Not re-run by me (needs dcortex + Chromium). Scope limits, all measured by me from the task dirs: every one of the 300 has exactly 1 check, all `computed_style` on one CSS property; archetypes are only `missing-style` (189) and `font-size` (111); all 300 are tier `easy`; they come from CSS operators only (`css-candidates.mjs:9` imports `cssOperators`; the JSX operators are unused in bulk generation). | **REAL†**, narrow |
| P0-D3 | Two runs, same seed, identical task-set hash | `packages/bench/tests/test_mutate.py::test_same_seed_hash_and_cache_miss_on_new_patch` passes (inside B2's 27). Hash `6547a4dc…e023` recorded in `docs/notes/p0-t26.md:5` and ADR-003; I did not recompute it from the 300 dirs. | **REAL** (determinism test) / **REAL†** (the recorded hash) |
| P0-D4 | A call over the measured daily limit is refused before any HTTP request (unit test) | `packages/argus-core/tests/test_ledger.py:23` `test_call_after_the_limit_makes_no_request`, `:37` restart test; 13/13 pass (B1). | **REAL** |
| P0-D5 | `docs/quotas.md` holds measured limits per provider and role, each with date and method | `docs/quotas.md`: `measured: partial`. Groq: requests/day and tokens/min are header-measured; tokens/day and RPM are published figures only. Mistral: not measured (Free plan, key creation disabled). Hosted Gemma: exists, but no numeric limits. Roles are not broken out. `docs/adr/0002-quota-ledger-semantics.md` ("Groq's own reset header was not read, because no API key was available", "`measured: false`") contradicts quotas.md, which says Groq was probed with a key on 2026-10-29. | **REAL** for 2 of 4 Groq fields; **UNVERIFIED** for the rest |
| P0-D6 | Ablation tables filled from real runs, baseline row included | `phases/P00-argus-bench.md:85-86,92` filled. Run is live (Groq, `p0-t29.md`). But A is n=10 attempted of 30, B n=1 of 30; all 10 A attempts were `not_applied`; lower CI bound prints as `-0.000000` (`p0-t29.md` Wilson `-2.77e-17`). The hypothesis (seeded vs mutated give the same rate) is not tested by n=1. The harness script is not in the repo. | **REAL†** run; ablation **UNVERIFIED** as evidence |

## E. Claim ledger: P0 checked boxes (TASKS.md:12-52) not covered above

| Task / claim | Evidence | Label |
|---|---|---|
| T03 types + JSON schema, invalid samples rejected | `argus-core/tests/test_types.py:51,74,93` pass (B1) | **REAL** |
| T04, T08, T27 ADR-001/002/003 exist, state decision, alternatives, consequences | Read all three in full. ADR-001 `stop_reason` enum matches P1 usage. Drift: ADR-002 vs quotas.md (D5). I did not check "linked from PLAN.md" (the `PLAN.md` grep for `adr/0001` found no link line in my sample, so treat as **UNVERIFIED**). | **REAL** (docs exist) |
| T05 one client works against mock, Groq, Mistral, Ollama by changing base_url/key | `test_client.py:41,65,86` pass. Only the mock server is exercised; Groq appears live only through the T29 run; Mistral key cannot be created (quotas.md); Ollama never exercised in any artifact I found. | **REAL** (mock), **UNVERIFIED** (Mistral, Ollama) |
| T06 quotas measured | See D5 | partial |
| T09 target-app README matches platform.md | `packages/target-app/README.md` diffed by eye against `config/platform.md`: repo path, tenant, console, ports, env names, five flows, no password. | **REAL** |
| T10 task dir format validates | `test_validate.py:10,20,31` pass | **REAL** |
| T11 check library passes on clean dcortex worktree and fails on a broken one | `packages/bench/tests/checks.spec.ts` not run (needs pnpm/Chromium/dcortex). Important design fact: `run-checks.ts:94-104` (`pageHtml`) and `:244-281` (`scoreInput`) build a **synthetic HTML page** (`pageHtml`: a `<span id="probe">` plus one `<span>` per selector) and loads the tree's CSS file into it; `serve()` never starts Canvas, never opens the real `/login` or `/ops/radar`. Each "flow" route (`:20,280`) returns the same synthetic page, only the flow id text differs. README (`bench/README.md`) says "Both trees serve the five flows", which is misleading. So checks measure "does this CSS file, loaded on a fake DOM, produce this computed style", not "does the real UI show the bug". | **REAL†**, scope far narrower than the claim |
| T13 30 seeded tasks, 10 per tier, one archetype each | Counted: easy 10, medium 10, hard 10; 6 archetypes (font-size 7, flex-direction 6, overflow 6, z-index 5, missing-style 3, wrong-element 3); all pass `validate` shape (test only covers `bug-17`). | **REAL** (structure) |
| T14 each seeded task fails on buggy and passes on golden, shown by one script run | No saved run output. Spot check: `seed-h01/bug.patch` edits 2 files but `checks.json` has one check on `.landing-brand` only, so the second edit is not tested. `seed-m01` check uses `#probe`, the injected fake element. | **UNVERIFIED** |
| T15 scorer exit codes 0/1/2, JSON verdict, no network | `test_score.py:48` passes; `:69` failed only for the missing `node_modules`. `run-checks.ts:300-304` aborts non-localhost requests. | **REAL** (2 paths), pass/fail path not re-run |
| T16 golden runner | `test_golden.py:5` passes; `:9` fails (stale 30 vs 330). Runner only proven in the T19 temp-repo probe. | **FIXTURE-ONLY** |
| T17 CI workflow green | C | **REFUTED** |
| T18 flake detection 5×5, quarantine into `bench/quarantine/` | `test_flake.py:26,43,60` pass on temp fixtures. `packages/bench/quarantine/` does not exist and `p0-t29.md` says "packages/bench/quarantine was missing". `p0-t20.md` says "`bench flake --all` was not run". No evidence that any real seeded or mutated task was ever flake-tested, so the "300 valid" set and the baseline sample draw are unchecked for flakiness. | **FIXTURE-ONLY** |
| T19 stale golden, T20 animation, T25 equivalent mutant, T30 quota exhaustion (Break it) | `test_break_stale.py:37`, `test_break_animation.py:13`, `test_validity.py` (11), `test_break_quota.py:11` all pass (B2). They run against temp-dir fake tasks and a stub model call. `p0-t19.md` correctly says red CI was not observed; it has since been observed red, for an unrelated reason (C). | **FIXTURE-ONLY** (wiring) |
| T21-23 bugsmith: deterministic operators, ≥4 JSX and ≥4 CSS, "app still builds" | `node --test` 3 pass (B5). The tests assert determinism and that the edited snippet "still parses" (`bugsmith/README.md`), not that the app builds. JSX operators were never exercised against the real tree. | **REAL** (determinism), **UNVERIFIED** (builds), JSX **FIXTURE-ONLY** |
| T24 validity filter | `test_validity.py` (11) pass; used for the 300 (D2) | **REAL** |
| T28 one-shot baseline records tokens in the ledger | `test_baseline.py:94,126,136,146` pass; live use in T29 (D6) | **REAL** |
| T31 README with install/run/scorer commands | `packages/bench/README.md` lists commands. `bench README` says `uv sync` + pnpm 10.12.1 but gives no `pnpm install`/`playwright install` step, which is the same gap that breaks CI. | **REAL** (doc), incomplete |

## F. Claim ledger: P1 "Done when" (`phases/P01-repro-agent.md:8-13`)

| # | Claim | Evidence | Label |
|---|---|---|---|
| P1-D1 | Interop spike has a written go/no-go | `docs/notes/p1-mcp-spike.md`: go, `mcp==2.3.0`, `@playwright/mcp@0.0.83`, initialize at protocol `2025-11-25`, tool list recorded. ADR-004 matches. Spike script `packages/repro-agent/spike_playwright_mcp.py` not re-run (needs npx/network). Note the negotiated protocol is not 2026-07-28 (documented honestly). | **REAL†** |
| P1-D2 | repro-agent runs over all 30 seeded tasks, one verdict each, from the repro verifier (fail on buggy, pass on golden), not by reading the script | 30 verdicts and 30 trajectories exist (`runs/*`, 28/1/1). But the "tree runner" is `batch.py:89-97` (string match on the script), and `verify()` is called with those hard-coded strings (`:104-106`). The verifier proper (`verify.py`) is only run against 4 hand-made scripts on a toy HTML page (`fixtures/verify/{buggy,golden}.html`) in Docker. No seeded task was ever run in a browser against its buggy and golden tree by repro-agent. | **FIXTURE-ONLY** |
| P1-D3 | Both Ablation rows (text only, text+screenshot) filled from real runs | The doc itself says they are recorded-reply batches (`phases/P01-repro-agent.md:69`). The rows are identical because the harness ignores the prompt: `_complete` (`batch.py:80-86`) never reads `_messages`. Image mode can't change a verdict. The Done-when text "from real runs" is therefore not met. | **FIXTURE-ONLY** (wiring), claim as worded **REFUTED** |
| P1-D4 | CI job runs repro-agent tests on recorded fixtures, no LLM calls, no secrets | Workflow has no secrets (true). It fails on every push (C). Tests pass locally only with `--package repro-agent` (B4). Replay test is in `test_replay.py` (passes under B4). | **REFUTED** (CI), tests **REAL** |
| P1-D5 | Phase report filled against the P0 baseline | `phases/P01-repro-agent.md:73-79`: Delta +0.933333 compares fixture 28/30 vs live 0/10. The text under the table admits the token/latency deltas are blank, but the resolve delta stays. Apples to oranges (different tasks attempted, fixture vs live, scripts vs patches). | **FIXTURE-ONLY**; delta **UNVERIFIED** as a measure |

## G. Claim ledger: P1 checked boxes and `docs/architecture/p1.md`

| Claim | Evidence | Label |
|---|---|---|
| T04 six tools, `browser_run_code_unsafe` off, `page.evaluate` not added, typed errors `stale-target`/`not-unique`, depth/byte cap | `test_tools.py` passes in the CI list (B4). `test_against_app.py` hits a locally served sign-in page via the real MCP server; not re-run (npx). Schemas in `packages/repro-agent/schemas/*.json` (7 files). | **REAL** (tool-layer tests), against a toy page, not dcortex |
| T05 sandbox image has no egress beyond the app (`p1.md:82`: cannot open `1.1.1.1:443`) | `test_docker.py:61` runs `probe-net.mjs`; `repro.yml` omits this test so CI never checks it. Not run by me (Docker build is large). | **REAL†** |
| T06 prompt: image only in image mode; bad image is a typed tool error | `test_prompt.py` passes (B4) | **REAL** |
| T07 loop: stops on submit, `retry-cap`, `QuotaExceeded`; saved script uses role+name, symptom assertion; one valid trajectory per run | `test_loop.py`, `test_break.py` pass (B4), with an injected fake `run_trees` and fake `complete`; the loop was never driven by a live model | **FIXTURE-ONLY** |
| T08 verifier four verdicts; skip/`fixme` = `error` | `test_verify.py:8` (no Docker needed for the `error` cases) plus `:15` (Docker). Not run. Four toy scripts, one page. | **REAL†**, toy scope |
| T09 fixture replay returns the stored trajectory | `test_replay.py` passes (B4); `fixtures/replay/sign-in/` | **REAL** (locally), CI red |
| T10/T11 30 verdicts + 30 trajectories, `seed-e01` crash then `seed-e02` still gets a verdict; same seeds and model | `test_batch.py` passes (B4); the doc is honest that `host` is `fixture` (`p1.md:88`). The ledger shows 30 requests, 60 tokens (`runs/*/ledger.json`), i.e. 2 tokens per task, not a provider bill. | **FIXTURE-ONLY** |
| T12 / ADR-005 "Text is the default. Do not attach the screenshot." | `docs/adr/0005-screenshot-in-ticket-context.md:15-17` cites the 28/30 vs 28/30 table, which is a no-op comparison. The ADR names the fixture caveat (line 9) and concedes "A later live run can overturn this" (line 19), but still states a rule. `p1.md:92` "the image bytes did not buy a verdict" is a non sequitur for a harness that never sends the image to a model. | **UNVERIFIED** (decision), stands as a placeholder |
| T13 vague ticket → `retry-cap`; T14 loose selector → `passes-on-bug` | `test_break.py` passes (B4); two empty scripted replies, a hand-made script. Valid wiring probes. | **FIXTURE-ONLY** |
| T15 dead server → `tool-unavailable` within timeout | `test_tool_unavailable.py` passes (B4) with `_Dead`/`_Hang` fakes (`:14-26`); never killed a real Playwright MCP process. | **FIXTURE-ONLY** |
| T16 README run command | `packages/repro-agent/README.md`: `uv run --package repro-agent python -m repro_agent.batch text-only`. Works (B4 used the same `--package`). README Install says plain `uv sync`; CI doesn't use `--package`. | **REAL** |
| p1.md wave diagram "T00-T16 done" | Matches TASKS.md `[x]` (P1-T00..T16 all checked, lines 53-75). | consistent, but see above |

## H. Package READMEs and ADR spot-check

| File | Headline claim | Label |
|---|---|---|
| `packages/bugsmith/README.md` | Same operator+source+seed → same patch; 8 operators; tests check determinism and parse | **REAL** (B5) |
| `packages/argus-core/README.md` | Types, client, ledger; ADR links | **REAL** (B1) |
| `packages/bench/README.md` | Commands exist in `cli.py`; "kept task-set hash in `docs/notes/p0-t26.md`" | **REAL**; "serve the five flows" overstated (E, T11) |
| `packages/target-app/README.md` | Binding to dcortex; no vendored Canvas | **REAL** |
| `packages/repro-agent/README.md` | "reply is recorded in the runner, so these commands do not call a model provider" | **REAL**, and a plain admission that the numbers are fixture |
| P2-P9 package READMEs | Stubs (e.g. `packages/dashboard/README.md` is 53 bytes) | out of scope |
| ADR-001..005 | All exist, all accepted; internal drift found only between ADR-002 and `docs/quotas.md` (D5) | **REAL** (docs) |

## I. Additional findings (not asked, but they matter)

1. `bench golden --all` scores 330 tasks, the stale unit test and the P0 doc both say 30. Either restrict the CI run to `seeded/` or fix the test and the Done-when.
2. The scorer's synthetic page means a CSS-only "bug" is detected if the CSS file's computed style on a fake element changes. Anything that depends on DOM structure, JSX, state, routing or real data is not representable. This bounds every claim built on bench scores, including the 300.
3. `TASKS.md` has P0-T17, P0-T19 (CI green again), P1-T09 as `[x]` while CI has never been green.
4. Quota notes are internally dated 2026-10-29/30 and the P0 baseline was run the same day it was measured; limits were taken from response headers of one short call each.
5. The only evidence behind "P0 baseline" is a markdown note: no committed per-task model outputs, no committed ablation script, no raw ledger. Re-running it would give a different number.

## J. What must be re-done with a real model before P2 builds on it

1. **Fix CI first, then re-claim it.** `golden.yml` needs a dcortex checkout (or a pinned fixture tree committed to this repo), Node ≥22.6, `pnpm install`, `playwright install chromium`, and a decision between 30 and 330 tasks. `repro.yml` needs `uv run --package repro-agent` (or add `repro-agent` to the root dependencies). Then get one green run on GitHub and a CI badge.
2. **Re-run P1 for real.** Replace `batch.py`'s `_complete`/`_trees` with a live model call (through the ledger, Groq `gpt-oss-20b` or another measured model) and the sandboxed two-tree runner. Run all 30 seeded tasks text-only, record real verdicts (`valid`, `passes-on-bug`, `fails-on-golden`, `error`), real token counts, real latency. Expect far below 28/30 and treat that as the true P1 baseline.
3. **Redo the screenshot ablation with a live model.** Only BUG-17 has an image today. Either add screenshots to more tickets or limit the claim to n=1. ADR-005 must be rewritten from the live numbers (or marked "provisional").
4. **Redo the P0 baseline so it measures the model, not the harness.** Fix prompt size against the 8000 TPM cap (18 of 30 never got a call), fix patch-application (all 10 attempts `not_applied`), then rerun on all 30 seeded and a ≥30-task mutated sample. Commit the harness, the per-task outputs and the ledger. Report Wilson intervals on `n`≥30 per arm.
5. **Prove the scorer on the real app.** Run at least the 30 seeded tasks (buggy vs golden) against the actual dcortex Canvas via its dev server, not the synthetic probe page, and keep the log. Check at least that seeded `h`-tier tasks with multi-file patches (like `seed-h01`) have checks that cover every edited file.
6. **Run `bench flake --all` on the real 330 tasks** and store the quarantine result; today flake detection exists only as a unit test, and `packages/bench/quarantine/` was never created.
7. **Widen the mutated set before using it as a stand-in for real bugs.** 300/300 are one CSS property, tier `easy`, two archetypes. Run the JSX operators through the same validity filter, or re-label the set as "CSS property mutants".
8. **Kill a real Playwright MCP process mid-run** and run the loop against a live model once (T15 and the loop are only proven with fakes).
9. **Sync stale docs/tests** (owner: `docs-drift` lane): `test_golden.py:11`, ADR-002 `measured: false` text, P1 "Delta +0.933333", and the P0-T19 note "no remote".

## Verification log

- Corrected a miscount (12/7 → 11 `exit2_unfit` / 8 `call_error`, totals 10+11+8+1 = 30) and the `run-checks.ts`/`test_golden.py` line numbers after a second grep. Re-opened `batch.py` lines 67, 80-106 (cited), `golden.py` 15-35 and 45-53, `golden.yml`/`repro.yml` line 14 via `grep -n run:`, `test_ledger.py` lines 23 and 37, `ADR-005` lines 9, 11, 15-19 (confirmed 103,536 and the "fixture" admission), `run-checks.ts` for the `pageHtml`/`serve` synthetic page, `score.py:181-231` browser lookup.
- Confirmed by commands: argus-core 13 pass; bench 27 pass/2 fail; repro-agent 5 collection errors with plain `uv run` and 24 pass with `--package`; bugsmith 3 pass; `gh run` shows 5 `golden` + 2 `repro` failures and the exact failing log lines for the latest pair.
- Corrections made while verifying: (a) first assumed `golden.yml` failed only on the missing dcortex path; the log and code showed it would also lack Node/pnpm/Chromium, and that `repro.yml` independently fails; (b) first read `test_golden` failure as a code bug, then confirmed it is a stale test (330 vs 30) and the bench `score` failure as an environment gap (no `node_modules`); (c) corrected "P0 baseline is live and weak" to "live, but 20/30 never attempted and 10/10 attempted `not_applied`" after reading the per-task list in `p0-t29.md`; (d) removed an early claim that the Docker tests fail without Docker; I did not run them, so they are marked REAL†/not run.
- Not re-checked: whether `PLAN.md` links ADR-001 (grep sample found none, left as UNVERIFIED), the recorded task-set hash (not recomputed), the Docker egress probe, and the live MCP spike (needs network/npx). These stay REAL† or UNVERIFIED as labelled.
- `.venv/` and a temp-dir venv were created by `uv`; `.venv/` is gitignored. No tracked file was changed and nothing was committed.
