# P5 waves and rules for every task session

Source of truth for the tasks: `phases/P05-argus-eval.md` (acceptance criteria) and `TASKS.md` (checkboxes). Integration branch: `stack/p5-eval`, cut from the P4 tip `stack/p4-verify`.

## Waves

A wave is a set of sessions that run at the same time. The next wave starts when the one before it is merged into `stack/p5-eval`.

| Wave | Sessions (tasks in order inside a session) | Why they can run together |
|---|---|---|
| 1 | A: T00, T01 (docs only) · B: T02, T03, T04 (`packages/eval`: metrics, runner) · C: T11 (price table in `argus-core`) | Three different folders. T04 fixes the results JSON that wave 2 reads. |
| 2 | A: T05 report · B: T06 OTel spans · C: T12, T13 router and caching · D: T16 gate · E: T19 multimodal adapter | Each reads wave 1 output and adds its own module. |
| 3 | A: T08, T09, T10 normalizer, swap proof, ADR-015 · B: T07 Langfuse export config · C: T17, T18 CI gate and ADR-017 · D: T21 dashboard | Need T06, T04, T16 and T05. |
| 4 | A: T14, T15 routing ablation, ADR-016 · B: T20 multimodal run · C: T22 Pages workflow · D: T24, T25, T26, T27 break-its | Need the router, the runner, the gate and the dashboard. |
| 5 | T23 trace check, T28 README and phase report, final architecture, PR | Needs everything. |

Tasks that need an outside account, key or a real model run (T07, T14, T20, T22, T23) are built and tested as far as local work allows. What could not be run is written down in the task's notes file. Never invent a number, a trace link or a URL.

## Rules for a task session

1. Work in your own worktree. Touch only the files your task needs. Another session is editing other files at the same time.
2. Read `phases/P05-argus-eval.md` for your task rows. The acceptance criteria are the definition of done. Check each one with a command and keep the output.
3. Follow the repo style: small modules, a module docstring, `ponytail:` comments for known ceilings, no unrequested abstractions. Python 3.12, `uv`, `pytest`. Tests need no model call and no network.
4. Run `uv run pytest packages/<your package>/tests -q` (and `packages/argus-core` tests if you touched it) before each commit.
5. One commit per task (a doc task and its build task can be one commit only if the task rows say so). Do not push. Do not open a PR.
6. Commit message format (plain language, bullets, no jargon without a gloss):

   ```
   <One plain sentence ending with a full stop, same style as "Add local pgvector search over Canvas files.">

   - What changed, in one line per bullet.
   - Why it matters or how to use it.
   - Task: P5-Txx
   - Tests: <command> -> <result>

   Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
   ```

7. Architecture grows with each task. In the same commit, add a section `## P5-Txx <title>` to `docs/architecture/p5.md` with: the new components (name and one line), the links to existing components (name -> name), the files, and the command that proves it. Do not edit the diagram in `docs/architecture/overview.md`; the orchestrating session folds the sections into it after each wave.
8. Tick the task's checkbox in `TASKS.md` only when every acceptance criterion holds. Do not tick one you could not meet; write the gap in `docs/notes/p5-<task>.md` instead.
9. Final message: one list of tasks done, the commit hashes, the test output, and anything not done or not verified. Say so plainly.
