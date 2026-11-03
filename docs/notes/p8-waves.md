# P8 waves and rules for every task session

Source of truth for the tasks: `phases/P08-argus-app.md` (acceptance criteria) and `TASKS.md` (checkboxes). Integration branch: `stack/p8-app`, cut from `stack/p7-guard` (`215bee0`, pushed; its PR is #15). Templates: `docs/notes/p7-waves.md`, `docs/notes/p6-waves.md`.

## Starting state, waivers and gaps

| Item | Status |
|---|---|
| `P8-T00` depends on `P7-T22` | done. P7 is complete (23 of 23). |
| P6 is not complete | open tasks include T04 (dispatch to Actions), T13, T14, T16, T17, T23, T25; PR #12 is a draft. `P8-T04` lists `P6-T04` as a dependency: it is waived. T04 builds the reusable workflow on its own and does not use the P6 dispatch code. `agent-job.yml` from P6 stays as it is. |
| Real GitHub App | the P7-T20 test App existed; the owner deletes it. `P8-T02` creates the real manifest; registering it is an owner step. |
| Reused from P7 | the App permission list (`docs/notes/p7-t04-app-permissions.md`, ADR-026), `flow.app_token` (minting), `guard` (escape suite, audit log, redaction), the three sandbox tiers and ADR-025. |
| Phase report "against P7" | P7 has no resolve-rate, token or latency numbers (all dashes), so the previous-phase row stays dashes. |

Things that must not be touched from P8: other checkouts, other phases' branches, `packages/eval/runs/`, and the Docker containers on this machine that are not ours (`argus-t14-proxy`, `argus-canvas-embed`, `clever_neumann`). The local `stack/p6-flow` is not touched or pushed (it has a commit, `059e422`, that is not on the remote).

## Machine load

At most 3 task sessions run at the same time until the owner says otherwise. Windows 11, Git Bash and PowerShell, Docker Desktop (slow under load; wait for `pg_isready` after starting Postgres).

## Waves

A wave is a set of sessions that run at the same time. The next wave starts when the one before it is merged into `stack/p8-app`. The `argus-app` package is scaffolded in the first commit (`packages/app`, module `argus_app`, command `argus-app`, dependencies `argus-core`, `fix-loop`, `flow`, `guard`, `pydantic`, `pyyaml`, `httpx`), so no task session edits `pyproject.toml` unless it needs a new dependency.

| Wave | Sessions (tasks in order inside a session) | Why they can run together |
|---|---|---|
| 1 | A: T00, T01, T02 (versions, notes, App manifest; T01 and T02 need T00) · B: T11 (planner and subagents) | T11 needs only `P3-T06` and `P5-T12` and lives in `fix-loop`. |
| 2 | A: T03 (installation flow and token minting, in `flow`) · B: T04, T05, T06 (reusable workflow, tenant config, target-agnostic runner; each needs the one before) | Different folders: `packages/flow` vs `.github/workflows` and `packages/app`. |
| 3 | A: T07 (per-tenant quota), then T21 (break-it) · B: T08, T09, T10 (intake, PR creation, backport bot), then T24 and T23 (break-its) · C: T22 (break-it), T13 (ADR-027), T20 (CI job) | T07 in the ledger, intake and PR in `packages/app`, break-it and docs elsewhere. |
| 4 | A: T12 (ablation, single agent vs planner on 20 tasks) · B: T16 (install on a public repo, one real issue) · C: T18 (demo video) | Mostly owner-dependent: a model and a quota decision for T12, the real App for T16 and T18. |
| 5 | ADRs T14, T15 · T17 landing README · T19 release checklist · T25 README and phase report · final diagram · the PR | Needs everything. |

### What cannot be finished locally

Only the owner can: register the real GitHub App and install it on a public repo, hold the App private key, create the Render service and secrets, set branch protection, record the demo video (T18), push, and spend model quota beyond the allowance. Build the code and config for them, document the exact owner steps in `docs/notes/p8-<task>.md`, leave the box unticked and report them as not run. Never invent a number, a URL, a latency, a pass rate or a "green" run.

A manual-only workflow cannot be started before it reaches `main`. Lesson from P7 (`docs/notes/p7-github-tier-runs.md`): to get a real run on GitHub, give the workflow a `pull_request` trigger limited to its own file, push, and read the job log.

### Model use

Free-tier model quota is shared. Use only the local Ollama (`gemma4:e4b`, `http://localhost:11434`) for any model run unless the owner says otherwise. Every report says the model name and the number of runs.

## Rules for a task session

1. Read `phases/P08-argus-app.md` for the task rows. The acceptance criteria are the definition of done. Check each with a command and keep the output.
2. One commit per task. Do not push. No PR from task sessions.
3. Commit message: one plain sentence ending with a full stop, then bullets in plain language of each important change, then `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
4. Add a `## P8-Txx <title>` section to `docs/architecture/p8.md` per task (components, links to existing ones, files, the command that proves it). Do not edit the diagram in `docs/architecture/overview.md` from task sessions.
5. Tick the `TASKS.md` box only when EVERY acceptance criterion holds and was seen. If a task needs an account, key, deploy, push, a real Actions run, the real App or a long wait, build and test what can be tested locally, leave the box unticked, and write the gap and the exact owner steps in `docs/notes/p8-<task>.md`.
6. Never invent a number, a URL, a latency, a pass rate or a "green" run. Every result table cell comes from a real run or is a dash. If a measurement tool shows an odd failure, find out whether the tool or the thing measured is at fault before reporting it (in P7 two "sandbox failures" were bugs in the timing code).
7. No LLM calls in tests. Any real model run uses the local Ollama model only, and the report says the model name and the number of runs.
8. Run each package's tests separately, never in one pytest run across packages: `uv run --all-packages python -m pytest packages/<name>/tests -q` (Windows Application Control blocks `pytest.exe`). Known failure from before P5: `packages/fix-loop/tests/test_ast_grep.py`. Run `uv lock --check` when dependencies change. Install nothing outside the uv workspace except in a throwaway folder outside the repo, and say so in the notes. Repo files are CRLF: keep line endings when editing (sed patterns must allow `\r`).
9. Secrets are environment variables only. Nothing secret goes in a file, a log, a span, a commit or a PR. Fake test secrets must be obviously fake. Never print a token or a key; run output through `argus_core.redact`.
10. Pytest plus Postgres tests: use your own throwaway container name and port (not `argus-p6-*`), a generated password, and remove it afterwards.
11. Final message of a task session: tasks done, commit hashes, test output, and anything not done or not verified, said plainly.

Tool quirk: a bash heredoc that contains backslash sequences (like `\n`) is expanded before Python sees it. Write such files with the Write or Edit tool, not a heredoc.

## After each wave (orchestrator)

1. Read each session's report, check its commits and run its tests (a report is not proof). Open the result files.
2. Merge the wave's branches into `stack/p8-app` with merge commits. Conflicts are resolved by keeping both sides (usually `TASKS.md`, `docs/architecture/*.md`, `uv.lock`; after a lock conflict run `uv lock` and `uv lock --check`). Run each package's tests (flow with a throwaway Postgres: wait for `pg_isready`, set `ARGUS_FLOW_DATABASE_URL`) and `uv lock --check`.
3. Fold the new components and links into the P8 box of `docs/architecture/overview.md` (own commit): P8 thick border and the label `NEW IN THIS PR`, P0 to P7 thin, thick arrows for P8 links, `linkStyle` indices recounted by script, Mermaid source parses.
4. Report the progress bar (ticked of 26, the wave) and the open owner steps.
5. If a CI workflow fails because it does not install all workspace packages, the usual fix is `uv sync --all-packages --locked` before the tests; report it.
