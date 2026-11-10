# P10 groups and rules for every task session

Source of truth for the tasks: `phases/P10-argus-workbench.md` (acceptance criteria) and `TASKS.md` (checkboxes, section `## P10`). The design: `docs/notes/p10-spec.json` (key `finalUi` of the explainer). Integration branch: `stack/p10-workbench`, cut from `stack/p8-app` (`5561a09`, not pushed). Templates: `docs/notes/p8-waves.md`, `docs/notes/p8-pr-body.md`.

## Starting state and gaps

| Item | Status |
|---|---|
| Base | `stack/p8-app` is not pushed, and P8 has open tasks (T02, T03, T04, T06, T12, T16 to T20). P10 uses what P8 built locally: `argus_app.pr`, `flow.github_write`, `flow.states`, the tenant ledger. |
| P9 | optional lane, not built. ADR-030 is reserved for it, so the P10 ADR is ADR-031. |
| Real GitHub App | not registered. The PR screen uses the mock transport only. A real PR is an owner step. |
| Model | none. P10 makes no model call, in code or in tests. Nothing in P10 can produce a resolve rate, a token count per bug or a latency from a model. |
| Judge | alpha is uncalibrated, so the judge label is advisory (ADR-013). |
| Phase report "against P8" | P8 has no resolve rate, tokens or latency, so the previous-phase row stays dashes. |

Things that must not be touched from P10: `stack/p8-app` and other phases' branches, other checkouts, `packages/eval/runs/`, and the Docker containers on this machine that are not ours (`argus-t14-proxy`, `argus-canvas-embed`, `clever_neumann`).

## Machine load

At most 3 task agents run at the same time. Windows 11, Git Bash and PowerShell, Docker Desktop (slow under load; wait for `pg_isready` after starting Postgres).

## Groups

Each group is one build agent in its own worktree, then an independent skeptic verify, then one repair if the verifier finds a blocking problem. Task agents cut `p10/<group>` from `stack/p10-workbench` and merge the branches of the groups they depend on. They do not merge into the integration branch; the integrator does.

| Group | Tasks | Depends on |
|---|---|---|
| core | T01, T02 | none |
| adr | T15 | none |
| issue | T03 | core |
| runner | T04, T05 | core |
| hist | T09 | core |
| review | T07 | core |
| live | T06 | runner |
| pr | T08 | review |
| breaks1 | T10, T11 | issue, review |
| breaks2 | T12, T13 | core, pr |
| e2e | T14 | issue, live, review, pr, hist |

Then the integrator, then T16, then the draft PR text `docs/notes/p10-pr-body.md` (base `stack/p8-app`, head `stack/p10-workbench`). Nothing is pushed.

## Run folder contract (summary; T01 writes the exact version in `docs/architecture/p10.md`)

Run store: `.local/workbench/runs/<run_id>/`, git-ignored. `<run_id>` matches `[a-z0-9-]{1,64}`. Files:

| File | What | Schema |
|---|---|---|
| `ticket.json` | the typed ticket | `argus-core` Ticket (`id`, `text`, optional `screenshot`); the repo, route and acknowledgement go in a sidecar `intake.json`, not in the ticket |
| `state.json` | run state | `run_id`, `state` (a `flow.states.State` value), `stop_reason` (an `argus-core` StopReason or null), `display_state` (derived: `quota-wait` when the stop reason is `QuotaExceeded`, `stuck` when it is `stuck`, otherwise the state), `origin` (`SIMULATED` or `REPLAY`), `scenario`, `created_by_retry_of` (the old run id or null), timestamps from an injected clock |
| `trajectory.jsonl` | one step per line | the `argus-core` trajectory schema; tokens in, out and cached per step |
| `verdict.json` | the four checks in order (pixel, overflow, axe, console), the first failure, the judge label and note | the `verify` verdict types where they exist |
| `report.html` | before/after report | shown only in a sandboxed frame |
| `patch.diff` | the patch | empty file means no PR |
| `decision.json` | approve, request-changes or reject, the reason, the idempotency key | written once per key |
| `pr.json` | the mock PR | the `argus_app.pr` result |

Every file a runner writes carries the origin tag (SIMULATED or REPLAY) in its own content or in `state.json`; no file is ever tagged as a real model result. Groups that depend on `core` merge its branch and build against these files; a group that needs a folder before a runner exists writes a fixture folder in its own tests.

## Rules for a task session

1. Read `phases/P10-argus-workbench.md` for the task rows. The acceptance criteria are the definition of done. Check each with a command and keep the output.
2. One commit per task. Do not push. No PR from task sessions.
3. Commit message: one plain sentence ending with a full stop, then bullets in plain language of each important change, then `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. No other AI lines.
4. Add a `## P10-Txx <title>` section to `docs/architecture/p10.md` per task (components, links to existing ones, files, the command that proves it). Do not edit the diagram in `docs/architecture/overview.md` from task sessions; only the integrator does.
5. Tick the `TASKS.md` box only when EVERY acceptance criterion holds and was seen. If a task needs a browser, the real App, an account, a key, a push or a long wait that is not there, build and test what can be tested, leave the box unticked, and write the gap and the exact owner steps in `docs/notes/p10-<task>.md`.
6. Never invent a number, URL, latency, pass rate or green run. Every metric cell comes from a real result file or is a dash. If a measurement tool shows an odd failure, find out whether the tool or the thing measured is at fault before reporting it.
7. NO MODEL CALLS AT ALL in P10, not in code and not in tests. No key, URL or model name is read at import. A scripted model (a plain Python function) is the only model stand-in.
8. Run each package's tests separately, never in one pytest run across packages: `uv run --all-packages python -m pytest packages/<name>/tests -q` (Windows Application Control blocks `pytest.exe`). Known failures that are not ours: `packages/fix-loop/tests/test_ast_grep.py` (pre-existing), and `test_break_skill_exfil` and the `repro-agent` `test_against_app` (environment or load flaky). Run `uv lock --check` when dependencies change (re-run `uv lock` after a lock conflict). Install nothing outside the uv workspace except in a throwaway folder outside the repo, and say so in the notes. Repo files are CRLF: keep line endings when editing (sed patterns must allow `\r`).
9. Secrets are environment variables only. Nothing secret goes in a file, a log, a response, a commit or a PR. Fake test secrets must be obviously fake. Never print a token or key; the per-start server token is never logged in full.
10. Postgres tests only in a throwaway container with its own name (`argus-p10-<group>`) and port, a generated password, `pg_isready` waited for, removed afterwards.
11. Local server only: `127.0.0.1`. Stop any server you start. Final message of a task session: tasks done, commit hashes, test output, and anything not done or not verified, said plainly.

Tool quirk: a bash heredoc that contains backslash sequences (like `\n`) is expanded before Python sees it. Write such files with the Write or Edit tool, not a heredoc.

## After the groups (integrator)

1. Merge the groups' branches into `stack/p10-workbench` with merge commits. Conflicts are resolved by keeping both sides (usually `TASKS.md`, `docs/architecture/p10.md`, `uv.lock`; after a lock conflict run `uv lock` and `uv lock --check`).
2. Run each package's tests (flow with a throwaway Postgres) and `uv lock --check`.
3. Fold the P10 components and links into `docs/architecture/overview.md` as its own commit: P10 box thick border and the label `NEW IN THIS PR`, P0 to P8 thin (P8 loses its thick border and label), thick arrows for P10 links, `linkStyle` indices recounted by script (P8's links are indices 181 to 220), Mermaid source parses.
4. Index the break-it write-ups in `docs/notes/p10-break-its.md`.
