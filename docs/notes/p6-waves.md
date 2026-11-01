# P6 waves and rules for every task session

Source of truth for the tasks: `phases/P06-argus-flow.md` (acceptance criteria) and `TASKS.md` (checkboxes). Integration branch: `stack/p6-flow`, cut from the P5 integration tip `stack/p5-eval` (`1cba1a0`). Template: `docs/notes/p5-waves.md`.

## Why P6 starts before P5.5 and before P5 has finished

The plan says P6 starts after P5.5. The owner chose to start it early, while the P5 routing ablation is still running in another session. This is allowed because P6 uses only parts that already exist: the fix loop (P3), verify (P4) and the repro agent (P1). It needs nothing from P5.5.

Waived or deferred because of the early start:

| Item | Status |
|---|---|
| `P6-T00` depends on `P5.5-T17` | waived. T00 re-checks the P6 version rows on its own date. |
| `P6-T25` phase report "against P5" | deferred. It needs P5's final numbers. Cells stay as dashes until P5 is final. |

Things that must not be touched from P6, because the P5 ablation uses them right now: the other worktrees and the P5 branches, `packages/eval/runs/`, and the repro rig (Docker containers) on this machine.

## Machine load

The ablation is running Docker jobs. At most 3 task sessions run at the same time until the owner says the ablation has finished.

## Waves

A wave is a set of sessions that run at the same time. The next wave starts when the one before it is merged into `stack/p6-flow`.

| Wave | Sessions (tasks in order inside a session) | Why they can run together |
|---|---|---|
| 1 | A: T00, T01 (docs only) · B: T02 (state machine, transition test) · C: T05, T06, T22 (HMAC endpoint, 202 hint-only handler, duplicate-delivery break-it; enqueue is an interface until T03 lands) | Docs vs `flow/states.py` vs `flow/webhook.py` and `flow/enqueue.py`. The package scaffold is committed first so nobody edits `pyproject.toml`. |
| 2 | T03 (DBOS durable workflow on local Postgres) | The choke point. Runs alone. |
| 3 | A: T04 (dispatch to GitHub Actions) · B: T07 (reconciliation poller) · C: T08, T10, T09, then T18 (QA wait, review-comment fallback, MRTR, ADR-023) · D: T11, T24 (Neon config, suspend break-it) · E: T15 (ADR-020) | All need T03. Five sessions, but only 3 at a time while the ablation runs, so A, B, C first, then D, E. |
| 4 | T19 (crash-recovery experiment, variants A plain function and B DBOS), T21, T20 (CI job with a Postgres service container), T12 (Render deploy config), T23 | Need T04, T07, T11. |
| 5 | T13, T14 (measurements), T16, T17, T25, final diagram, PR | Needs everything. |

Dependencies are those in the task table of `phases/P06-argus-flow.md`; the wave plan may be adjusted but never against them.

### What cannot be finished locally

Only the owner can: create the Render and Neon accounts and services, enable GitHub Actions dispatch tokens and webhooks, push the branch, run the 48-hour Neon measurement (T14) and the cold-start measurement (T13) against a real deploy. Build the code and config for them, document the exact owner steps in `docs/notes/p6-<task>.md`, leave the box unticked and report them as not run. Never invent a number, a URL, a latency, a CU-hour figure or a "green" run.

## Rules for a task session

1. Work in your own worktree, cut from `stack/p6-flow`. Touch only the files your task needs. Other sessions edit other files at the same time.
2. Read `phases/P06-argus-flow.md` for your task rows. The acceptance criteria are the definition of done. Check each one with a command and keep the output.
3. Follow the repo style: small modules, a module docstring, `ponytail:` comments for known ceilings, no unrequested abstractions. Python 3.12, `uv`, `pytest`. Tests need no LLM call. Secrets are environment variables only: nothing secret goes in a file, a log, a span, a commit or a PR.
4. Run the package's tests on their own, never in one pytest run across packages (test file names collide): `uv run pytest packages/<name>/tests -q`. Also run `packages/argus-core/tests` if you touched it. Run `uv lock --check` when dependencies change. Known failure from before P5: `packages/fix-loop/tests/test_ast_grep.py`. Install nothing outside the uv workspace except in a throwaway folder outside the repo, and say so in the notes.
5. One commit per task. Do not push. Do not open a PR.
6. Commit message format (plain language, bullets):

   ```
   <One plain sentence ending with a full stop, same style as "Add local pgvector search over Canvas files.">

   - What changed, in one line per bullet.
   - Why it matters or how to use it.
   - Task: P6-Txx
   - Tests: <command> -> <result>

   Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
   ```

7. Architecture grows with each task. In the same commit, add a section `## P6-Txx <title>` to `docs/architecture/p6.md`: new components, links to existing ones, files, and the command that proves it. Do not edit the diagram in `docs/architecture/overview.md`; the orchestrating session folds the sections into it after each wave.
8. Tick the task's checkbox in `TASKS.md` only when EVERY acceptance criterion holds and you have seen it. If a task needs an account, a key, a deploy, a push or a long wait, build and test what can be tested locally, leave the box unticked, and write the gap and the exact owner steps in `docs/notes/p6-<task>.md`.
9. Final message: tasks done, commit hashes, test output, and anything not done or not verified, said plainly.

## After each wave (orchestrator)

1. Read each session's report and check its commits and tests (a report is not proof).
2. Merge the wave's branches into `stack/p6-flow` with merge commits. Conflicts are resolved by keeping both sides (usually `TASKS.md` and `docs/architecture/p6.md`). Run each package's tests and `uv lock --check`.
3. Fold the new components and links into the P6 box of `docs/architecture/overview.md` (own commit).
4. Report the progress bar (ticked of 26, the wave) and the open owner steps.
