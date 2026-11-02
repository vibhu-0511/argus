# P7 waves and rules for every task session

Source of truth for the tasks: `phases/P07-argus-guard.md` (acceptance criteria) and `TASKS.md` (checkboxes). Integration branch: `stack/p7-guard`, cut from `stack/p6-flow` (`fed0ad2`, local), then `stack/p5.5-skills` (local `b24d160`) merged in, because P7 red-teams "injection through a skill" and needs the P5.5 skills code. Templates: `docs/notes/p6-waves.md`, `docs/notes/p5-waves.md`.

## Starting state, waivers and gaps

| Item | Status |
|---|---|
| `P7-T00` depends on `P6-T25` | waived. P6 still has 7 open tasks (T04, T13, T14, T16, T17, T23, T25; PR #12 is a draft). T00 re-checks versions on its own date. |
| Real GitHub Actions run of `agent-job` | cannot run the default steps on a runner: the workflow does not check out the platform repo or start the Docker rig (P6-T04). Anything in P7 that needs a real Actions run is built and tested locally and left unticked, with owner steps. |
| Local `stack/p5.5-skills` is 12 commits behind `origin/stack/p5.5-skills` | PRs #13 and #14 are merged into `main` on GitHub (the brief said open). The 12 extra commits are P5 follow-up data and a merge of `main`; `git diff` shows none of them touch `packages/skills`. The local branch was merged as asked. Merging `main` into the stack is left to the owner. |
| Local `stack/p6-flow` is 2 commits ahead of `origin/stack/p6-flow` | the 2 commits are not pushed. The P7 PR base is `stack/p6-flow`; push it first. |
| P5 cells in the P6 phase report | still dashes (P6-T25 open). The P7 phase report is "against P6", so its previous-phase row may also be dashes. |

Things that must not be touched from P7: other checkouts, other phases' branches, `packages/eval/runs/`, and the repro rig (Docker containers) on this machine.

## Machine load

At most 3 task sessions run at the same time until the owner says otherwise. Windows 11, Git Bash and PowerShell, Docker Desktop (slow under load; wait for `pg_isready` after starting Postgres).

## Waves

A wave is a set of sessions that run at the same time. The next wave starts when the one before it is merged into `stack/p7-guard`. Two changes against the first plan, both forced by the task table: `P7-T12` depends on `P7-T05`, so T05 and T12 share a session in wave 2; `P7-T10` needs only `P3-T05`, so it moves up into wave 3 to use the third slot.

| Wave | Sessions (tasks in order inside a session) | Why they can run together |
|---|---|---|
| 1 | A: T00, T01, T02 (docs; T02 needs T01) | Everything else needs the threat model (T02). |
| 2 | A: T03 secrets · B: T06 audit log · C: T05, T12 egress probe, then escape-test suite | Different folders: redaction and CI scan, `packages/guard` audit log, sandbox probes. |
| 3 | A: T04 App token · B: T07, T08, T09 red-team (promptfoo) · C: T10 gVisor | T04 in `flow`, red-team in `packages/guard` and `fix-loop`, gVisor in the sandbox runner. |
| 4 | A: T11, T13 Firecracker, then ablation · B: T17 CI job | T13 needs T11 and T12; T17 needs T12 and T06. |
| 5 | ADRs T14, T15, T16 · break-its T18 to T21 · T22 README and phase report · final diagram · the PR | Needs everything. |

### What cannot be finished locally

Only the owner can: create and install the GitHub App, handle its private key, set branch protection, provide a KVM-capable runner and install gVisor or Firecracker on a real Linux host, run real Actions runs, spend model quota beyond the allowance, and push. Build the code and config for them, document the exact owner steps in `docs/notes/p7-<task>.md`, leave the box unticked and report them as not run. Never invent a number, a URL, a latency, a pass rate or a "green" run.

## Rules for a task session

1. Read `phases/P07-argus-guard.md` for the task rows. The acceptance criteria are the definition of done. Check each with a command and keep the output.
2. One commit per task. Do not push. No PR from task sessions.
3. Commit message: one plain sentence ending with a full stop, then bullets in plain language of each important change, then `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
4. Add a `## P7-Txx <title>` section to `docs/architecture/p7.md` per task (components, links to existing ones, files, the command that proves it). Do not edit the diagram in `docs/architecture/overview.md`.
5. Tick the `TASKS.md` box only when EVERY acceptance criterion holds and was seen. If a task needs an account, key, deploy, push, a real Actions run, a GitHub App, a KVM runner or a long wait, build and test what can be tested locally, leave the box unticked, and write the gap and the exact owner steps in `docs/notes/p7-<task>.md`.
6. Never invent a number, a URL, a latency, a pass rate or a "green" run. Every result table cell comes from a real run or is a dash.
7. No LLM calls in tests. The promptfoo red-team (T08) needs a model: build the config and the runner, run it only against what is available locally and say exactly what model and how many cases ran; if no model is available, leave T08 unticked with owner steps.
8. Run each package's tests separately, never in one pytest run across packages: `uv run --all-packages python -m pytest packages/<name>/tests -q` (Windows Application Control blocks `pytest.exe`). Known failure from before P5: `packages/fix-loop/tests/test_ast_grep.py`. Run `uv lock --check` when dependencies change. Install nothing outside the uv workspace except in a throwaway folder outside the repo, and say so in the notes. Repo files are CRLF: keep line endings when editing.
9. Secrets are environment variables only. Nothing secret goes in a file, a log, a span, a commit or a PR. Fake test secrets must be obviously fake.
10. Pytest plus Postgres tests: use your own throwaway container name and port (not `argus-p6-*`), a generated password, and remove it afterwards.
11. Final message of a task session: tasks done, commit hashes, test output, and anything not done or not verified, said plainly.

The `guard` package is already scaffolded (`packages/guard`, `guard` command in `guard.cli`, workspace member, lock updated). Add sub-commands in your own module and register them in `cli.py` with the smallest edit; do not touch `pyproject.toml` unless a new dependency is needed.

## After each wave (orchestrator)

1. Read each session's report, check its commits and run its tests (a report is not proof).
2. Merge the wave's branches into `stack/p7-guard` with merge commits. Conflicts are resolved by keeping both sides. Run each package's tests (flow with a throwaway Postgres) and `uv lock --check`.
3. Fold the new components and links into the P7 box of `docs/architecture/overview.md` (own commit): P7 thick border and the label `NEW IN THIS PR`, P0 to P6 thin, thick arrows for P7 links.
4. Report the progress bar (ticked of 23, the wave) and the open owner steps.
