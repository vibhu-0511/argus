# Brief: fix the plan deviations in Phase 3 and Phase 4 (run this in the MAIN checkout)

Open a Claude session whose folder is `C:\Users\vibha\Downloads\data\personal\argus` (branch `p0-bench`), then paste: "Read `C:\Users\vibha\Downloads\data\personal\argus\.claude\worktrees\agent-swarm-verification-b4db5f\analysis\swarm\p3p4-fixer-brief.md` and do what it says."

Start it only after `finish-p3` has written up (it has) **and the P4 finishing session** (`analysis/swarm/p4-finish-brief.md`) **has written up**, because all three sessions edit `TASKS.md` and the same P3/P4 files in that checkout. Never run two of them at once.

Why there: P3 and P4 are uncommitted in the main checkout (P3: `packages/fix-loop/**`, ADRs 0008-0011, `docs/architecture/p3.md`, `.github/workflows/fix-loop.yml`; P4: `packages/verify/**`, ADRs 0012-0014, `docs/architecture/p4.md`, `.github/workflows/verify.yml`; shared edits to `pyproject.toml`, `uv.lock`, `pnpm-*`, `TASKS.md`, `PLAN.md`, `PROJECT.md`, `phases/P03-fix-loop.md`, `phases/P04-verify.md`, `packages/argus-core/**`). A session scoped to another worktree is blocked from editing them. Read them first; never discard or overwrite them.

## The reports you are answering (read-only, in `C:\Users\vibha\Downloads\data\personal\argus\.claude\worktrees\agent-swarm-verification-b4db5f\analysis\swarm\conformance\`)
- `report-2026-10-30-p3.md` (P3: 23 of 27 ticked tasks conform, 4 deviate: T11, T22, T25, T26)
- `report-2026-10-31-p4.md` (P4: 12 of 24 ticked tasks conform, 12 deviate)
Treat each report's "Recommended fixes" as claims to test, not as facts. Reproduce each defect first and keep the failing test as the regression test.

## Fix, in this order

**A. P3 (fix-loop)**
1. Declare `jsonschema` for the fix-loop tests (a test dependency group), and change `.github/workflows/fix-loop.yml` to `uv sync --all-packages --locked` like `repro.yml`. Include the Docker break-it tests (T31, T32) in the CI selection, or say why they are excluded. Reproduce the workflow's commands locally in a fresh environment.
2. Wire the sandbox: `run_cmd` and the gates go through `sandbox.run` by default, or fail closed without it. Add a loop-level test that a destructive command from the model never touches the host checkout. This is the biggest P3 gap against its Done-when 3.
3. Make `offload` a pluggable `Strategy`, or remove it from Done-when 4 and say so openly.
4. Trajectory recorder: write each step as it happens (append), keep the provider payload in `raw_response`, and catch a gate `TimeoutExpired` and record it. Compute the 80% rule from a window-size estimate, not a cumulative sum. Apply the output cap at the dispatch boundary so `run_baseline` is capped too.
5. `fix-loop replay` must operate on a fresh worktree or temp copy, never the current directory.
6. `test_ast_grep` must not parse a local path; use `ARGUS_PLATFORM_REPO` like the P2 fixes.
7. Add an ADR-001 note for the new stop reasons (`summary`, `verify-reject`, `retry-cap`) and the shared `argus_core` enum change.
8. Fix the `packages/verify` workspace member problem (a `pyproject.toml` it lacked) only if it still fails `uv run`; check before touching.

**B. P4 (verify)**
1. Enforce ADR-014 in code: `k` defaults to 1, `MAX_K = 5` raises for more, record usage in the ledger so the quota is real, and add tests for `k=6` and the default. Decide stop-after-first-passing-candidate or document why not. Do not change the ADR's decision (default 1, cap 5).
2. Rewrite the pixel fringe test to be near-linear (a distance transform or a set-based neighbour lookup). Add a test at a realistic size (1280x720, about 2% changed) with a time bound, and a hairline test so you decide thin strokes explicitly.
3. Overflow, axe and console (T03 to T05): add the capture side with Playwright in `packages/verify/src/capture.ts`, or reword T03 to T05 to "data check only" in the README and `p4.md`. Pick the smaller honest option and say which.
4. Put the judge label (or `unjudged`) into `Verdict`. Add a distinct `judge-unavailable` outcome and write the decision table for EC-40/EC-41.
5. Make the prompt-injection defence structural: the rubric and the ticket are separate message parts, and the ticket is marked as data. Keep the phrase flag only as an extra signal.
6. Build the real `verify` callable for `run_fix` (capture, then `pipeline.run_routes`) and pass it from `run_baseline`. Test it end to end on a fixture.
7. Handle the Krippendorff alpha edge cases (constant labels return NaN; ignore NaN bootstrap samples; fix the upper-index off-by-one). Test each.
8. Keep `constructed_as` out of the human label slot in the calibration set. Do not label anything.

**C. Honesty in `TASKS.md` and the phase docs**
- Un-tick the P3 and P4 tasks the reports found ahead of their dependencies (P3: T11, T22, T25, T26; P4: T15, T18, T19, T21, T24, T27, T28, T29), or add "written ahead of dependency, awaiting <task>" next to each. Pick one convention for both phases and apply it everywhere. Keep them out of counts if un-ticked.
- Remove the P2 latency cells copied into the P3 phase table (they have no run id). Fix any `—` cell that has no run id.
- Do not edit `argus-learning.html`.

## Leave alone (owner decisions)
Task ownership of the [ME] and [PAIR] tasks and ADRs 008 to 014; whether `argus-learning.html` stays deleted; the default k and cap values; whether the calibration shots must come from real bench runs; labels (the P4 finishing session drafts them, the owner reviews); Ollama install; ADR-007 order; the private `index.json`; golden policy; push and merge order. Do not tick anything the owner must decide.

## Rules
- Install nothing. No env, key or credential files. No model calls other than through the P3 `turn.py` file-backed driver, and none at all in the tests.
- No `git add -A`; the tree has many other uncommitted files. Commit only your own files with clear messages, in small commits, one fix each, and only when its tests pass. No push, no merge. Do not touch the `p2-conformance-fixes` branch, the swarm/explainer branch, or any other worktree.
- Run the non-live suites before and after (fix-loop, verify, argus-core). Use the repo venv python if `uv run` fails. The bench test `test_golden.py::test_platform_repo_and_seeded_tasks` already fails (330 vs 30 task dirs); it is not yours.
- Log to `docs/notes/p3p4-conformance-fixes.md`: each defect, the failing test, the fix, the result, and what is still open. Mark all work "done by a Claude session, for the owner to review".

## Done when
Every item above is fixed with a test, or left with a one-line reason; the CI commands for `fix-loop.yml` and `verify.yml` pass in a fresh local environment; `TASKS.md` matches what is actually true. Final report, five lines or fewer: items fixed, items left and why, test results, commits.

After this the owner asks the plan verifier to re-check P3 and P4.
