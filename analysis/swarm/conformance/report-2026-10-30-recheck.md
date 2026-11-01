# Plan-conformance re-check of the P2 fixes (UTC 2026-10-30 evening; commits dated 2026-10-31 IST)

Follows `report-2026-10-30.md`. Read-only: nothing pushed, merged or edited outside this folder; the fixer's branch was only read. The fixer's own log (`docs/notes/p2-conformance-fixes.md`) was treated as a claim and tested.

## What was checked

| Ref | SHA | Notes |
|---|---|---|
| `claude/p2-conformance-fixes-593529` (local only, no GitHub run) | `cefd018` | 14 commits after `97719bd`: a clean merge of PR 2 (`069f9c5`) plus 13 fix commits. Cut from local `p0-bench` `97719bd` |
| `origin/p0-bench` | `bc52e16` | unchanged |
| PR 1 | `ecdaf6f` | unchanged |
| PR 2 | `069f9c5` | unchanged; now contained in the fix branch |

Method: temp detached worktree at `cefd018`, then `uv sync --all-packages --locked` and `pnpm install --frozen-lockfile` from scratch (both succeeded). Short venv path (Windows MAX_PATH). A throwaway Docker compose project (`verifier-embed`, port 5439, removed afterwards; the owner's `argus-canvas-embed` container was not touched). The dcortex-platform checkout (HEAD `ac86acc75`, dirty tree) was only read.

## What I re-ran

| Run | Result |
|---|---|
| `uv run pytest packages/dom2src-mcp/tests -m "not live"`, platform path unset (as CI) | **51 passed**, 3 deselected (129 s) |
| `test_repo_map.py` with `ARGUS_PLATFORM_REPO` set (includes the committed-index staleness test and the live match against the checkout) | **4 passed** |
| `test_embed.py` against a fresh pgvector container from the new compose file | **3 passed** (94 s) |
| `pnpm --filter @argus/dom2src-plugin test` (`transform.test.ts`) | platform unset: 6 pass, 1 skipped. platform set: **7 pass** |
| `pnpm --filter @argus/dom2src-plugin run test:attribute` (Playwright, Chromium) | **2 passed** (29 s). It could not run in my first pass |
| Ablation runner, `--reindex`, fresh run id `p2-abl-20261030T211746Z` | top-1 / top-3: A 0/30, 0/30; B 15/30 [0.331539, 0.668461], 19/30 [0.455132, 0.781263]; C 0/30, 0/30. **Accuracy reproduces the committed run exactly.** Latency does not (B p50 0.068 s vs 0.415 s committed) |
| Wrapper-button and unsupported-selector tests through the stdio MCP client (inside the 51) | pass; ranked candidates validated against the schema |

**Not run:** `pnpm --filter @argus/dom2src-plugin run test:canvas` (the 12-route Canvas run). Its `setup.mjs` adds a git worktree to the private dcortex-platform repo, which I treat as outside my read-only scope. I read `canvas.spec.ts` and `setup.mjs` instead. Also not run: anything on Linux, the CPU-torch source in `uv.lock`, the repro/bench suites, and any GitHub Actions run (the branch is not pushed; `gh run list` for it is empty). Leftover `node_modules` directories under my scratchpad worktree path could not be deleted (path length); harmless.

## Verdicts: earlier deviations

| # | Earlier finding | Verdict | Evidence |
|---|---|---|---|
| 1 | T06/T08: ambiguous lost over MCP; schema had no candidates | **fixed** | `server._result` has an `Ambiguous` branch; schema has `Candidate` and requires `candidates` for `ambiguous`; stdio test passes and validates. Note: candidates carry `rank`, not `why` (see E2). Typed `unsupported-selector` replaces the `ValueError` |
| 2 | T17: committed index had no `content_hashes` | **fixed** | `index.json` has 395 files and 395 hashes (5052 symbols). Non-live test `test_committed_index_is_checked_for_staleness` passes. The live test confirms no file is stale against the checkout. Hashes fold CRLF to LF |
| 3 | T10: undeclared deps, no DB setup, `test_embed` uncollectable | **fixed** | `psycopg[binary]`, `sentence-transformers`, `jsonschema` (+ `torch` for a CPU index source) declared; lock installs clean with `--locked`; `docker-compose.yml` (loopback, trust auth) brought up a working DB; 3 tests pass. Caveat: the Linux CPU-torch source is untested |
| 4 | T14: CI step failed on `mcp`; never run; box ticked | **partly fixed** | Workflow rewritten to match `repro.yml` (all-packages, locked, pnpm, `-m "not live"`, `transform.test.ts`, attribute test). Every step reproduces green locally from a clean install. Box now unticked with a "needs a green run id" note. Still never run on GitHub |
| 5 | T02: plugin never run on the Canvas | **partly fixed** | New `canvas/` spec serves the plugin through a wrapper config in a throwaway worktree and asserts, per route, that each `data-src` points at an opening `<tag` at that line and column. The fixer reports 12/12 routes passing. I reviewed the assertions (strong) but did not run them. Limits are disclosed in ADR-006: elements from the prebuilt `@dcortex/canvas-ui` and lucide SVGs are unstamped, and the console tab had no rows. Done-when #1 is unchanged and holds for `apps/canvas/src` only. The Canvas run is not in CI |
| 6 | T03: attribute tests on a fixture; could not run | **partly fixed** | Now run and pass under pnpm (the old failure was a pnpm-strict `require.resolve` in `installed-browser.cjs`, fixed). Still fixture-based; the Canvas spec is the real-app evidence |
| 7 | T12: no run id, no raw output | **fixed** (provenance) | Runner `dom2src_mcp.ablation`, raw output `docs/notes/results/p2-abl-20261030T204633Z.txt`, command and SHAs recorded. I reproduced the accuracy cells with a new run |
| 8 | T12: experiment cannot compare the variants (all CSS goldens) | **not fixed** | Documented in the phase file and ADR-007 as a "Verifier finding"; the redo on JSX-origin tasks is listed as open and not done. The latency cells changed to the new run's values; my run shows latency is not reproducible (6x spread), so treat those cells as single-run |
| 9 | T13/E1: ADR-007 default order contradicts HLD edge 9 | **not fixed** (open owner decision) | A note was added; decision text unchanged, as asked |
| 10 | T19/H2: 28/30 not labelled fixture | **fixed** | Phase file now says it is fixture replay |
| 11 | H3 (T14 ticked without a run), H4 (stale "Nothing is done yet") | **fixed** | `TASKS.md` T14 unticked; `p2.md` header and CI paragraph corrected |
| 12 | Hazard 1: PR 2's `platform.md` row broke `embed.py` and `repo_map.py` | **fixed** | Both resolve through `repo_map.platform_repo()`, which reads `ARGUS_PLATFORM_REPO`; the live tests pass with it. The hard-coded user path in the header is gone |
| 13 | Hazard 2: `pnpm-lock.yaml` lacked the plugin | **fixed** | `pnpm install --frozen-lockfile` succeeds from a clean tree |
| 14 | Hazard 3: `dom2src.yml` lacked all-packages | **fixed** | See #4 |
| 15 | Hazard 4: PR 1 vs P2 textual conflicts | **fixed (no conflict found)** | `git merge-tree` of PR 1 (`ecdaf6f`) and the fix branch merges cleanly |
| 16 | PR 2: golden is manual-only | **open (owner decision)**; docs changed ahead of it | The fixer edited P0 Done-when #1, the P0 deploy checkpoint, `PLAN.md`, `PROJECT.md` and the P02 checkpoint to say "manual dispatch". That weakens a plan acceptance criterion before you decided. It left P0-T17 and the P01/P03/P04 checkpoints saying "on every push", so the plan is now inconsistent. Revert or finish, once you choose |
| 17 | E3: locate input is `#id`/`[data-testid]` on a static HTML file | **not fixed** | Unchanged (typed error now, but the scope is the same). Design gap vs HLD S2 |
| 18 | E1/E2: explainer data | **not touched** (as instructed) | Still needed: see below |

Tally of items 1-18: fixed 11, partly fixed 3 (#4, #5, #6), not fixed 3 (#8, #9, #17), open owner decision 1 (#16), with 0 new regressions found in what I ran.

## New observations (not regressions)

1. **Provenance depends on a dirty tree.** The index and the ablation record platform SHA `ac86acc75`, but the fixer says that checkout had 150 modified files. Hashes and results reflect the working tree, not the commit. Record `git status --porcelain` or the diff hash in the run output, or regenerate from a clean commit.
2. **CI skips the strong tests.** `transform.test.ts` runs 6/7 in CI (the Canvas flow test is skipped without the platform path) and `test:canvas` is not in the workflow. So no CI run will check the Canvas claims. That is unavoidable while the platform repo is private, but T02's AC stays locally verified only.
3. **Fourth error code.** The schema now has `unsupported-selector` beside the three in T06's acceptance criteria and the HLD stop list. Reasonable, but the explainer's `Stops: not-found, ambiguous, no-source-info` and edge 9 should add it.
4. **Latency cells.** The phase table's p50/p95 changed between runs by up to 6x on the same code. Do not compare them across runs.
5. **New dependency weight.** Direct `torch` (CPU wheel source on Linux) plus `sentence-transformers` in the lock. CI install time and the Linux CPU source are unmeasured.
6. **TASKS.md** is now 68 `[x]` / 204 `[ ]` (P2 19/20). `tracker.json` and the explainer still say 49 / 223.

## Still open for the owner (not decided by anyone)

- Task ownership: 13 [ME] and 3 [PAIR] tasks (and both ADRs) were done by an agent; the fixes were also done by an agent.
- The committed `index.json` of private dcortex symbols (now 395 files with hashes).
- ADR-007 default order vs HLD edge 9.
- Push and merge order of the fix branch, PR 1 and PR 2 (the fix branch already contains PR 2).
- Whether golden stays manual-only, and if so, finishing the plan edits consistently.

## Explainer data changes now due (proposed only)

Same list as the first report, adjusted: mark `d2s-plugin`, `d2s-mcp`, S2 and EC-50/EC-52 as "partly built" (not "built"); in `hld-edges.json` and `report.json` add `unsupported-selector` to the locate errors and note that `candidates` carry `rank` and no `why`; set `final-ui.json`/`phase-ui.json` P2 to 19/20 with T14 waiting on a green run, and keep EC-51 as "partial" with the CSS-only ablation as evidence; update tracker counts to 68/204 only after the branch merges.

## Recommended next steps

1. Push the fix branch (or its PR) so `dom2src.yml` and `repro.yml` actually run; tick T14 only with that run id. Watch the Linux torch install.
2. Decide the golden policy, then make P0-T17 and the P01/P03/P04 checkpoints match it (or revert the Done-when edits).
3. Redo T12 on JSX-origin tasks with a ticket and rendered HTML, or state in ADR-007 that the three-way comparison was not run (already noted in a finding box).
4. Record the platform tree state (clean SHA or diff hash) in the ablation and index outputs.
5. Re-run this check after the push and CI run.
