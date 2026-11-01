# fix-loop

From-scratch fix agent for P3. The package imports no agent framework.

## Install

From the repo root, with Python 3.12:

```
uv sync
```

## Commands

```
uv run --package fix-loop fix-loop replay <file>
uv run --package fix-loop python -m fix_loop.frameworks
uv run pytest packages/fix-loop/tests -q -k "not sandbox and not ast_grep"
```

`fix-loop replay <file>` applies the stored edits in the current directory and prints the diff. It does not call a model and it does not run the shell.

There is no `fix-loop run` subcommand. A task run is `run_baseline` in `src/fix_loop/baseline.py`. The caller passes `complete`. That function does not call a provider. The 30-task resolve rate is not in the phase report.

`create(repo, task_id, commit, root=...)` adds a detached git worktree of `repo` at `commit`. The checkout is clean. `destroy(repo, path)` removes it, and `git worktree list` no longer names that path. `task_id` is one path segment under `root`.

Tools are `read_file`, `list_dir`, `search`, `edit`, `run_cmd`, `submit`, and `ast_grep`. `edit` replaces one exact match. A second match returns `not-unique` and the line numbers. A path outside the worktree returns `outside-worktree`. There is no whole-file write tool. `ast_grep` shells out to `@ast-grep/cli@0.51.0` and returns `file:line`. A pattern the parser rejects is `bad-pattern`. `vim` and a bare `python` or `node` are `not-allowed`. Schemas are in `schemas/`.

`run(worktree, checks, command)` starts `argus-fix-sandbox:p3` with `--network none`, `--cpus 1`, `--memory 512m`, the worktree mounted at `/work`, and the checks directory mounted read-only at `/checks`.

`run_fix` is the loop. Pass `complete` in tests. Pass `execute` when `run_cmd` must run inside the sandbox. Stops are `submit`, `step-cap`, `token-cap`, `QuotaExceeded`, `stuck` (three identical calls), and `consecutive-timeout` (three timeouts). The system message starts with `AGENTS.md`. `user_message` puts the ticket, the repro verdict, and the locate file and line in the first user message. Pass `context_budget` and `strategy` to compact when the run reaches 80% of the window. `cap_text` cuts a tool result to 8000 characters and drops the tail. `offload` writes the body under `.argus/` and leaves a 200-character head plus the path. `rolling_summary` keeps the system prompt and the first user message; a summary that does not shrink stops the run with `summary`. Pass `gates` to turn a failed gate into a JSON message and keep going. `run_gates` returns pass or fail for `build`, `typecheck`, `lint`, `unit`, and `bench`. Pass `verify` to run it after the gates on submit. A rejection is one user message with the verdict reason. A second rejection stops as `verify-reject`.

`run_baseline` is the no-compaction pass over the 30 seeded tasks. It takes a `complete` function. It does not call a provider on its own.

## Claude-session runs (pilot)

The plan's fixer (Devstral on Mistral's free tier) has no key, and the 30 seeded tasks edit private dcortex files, so no hosted free tier is used. `fix_loop.turn` lets a Claude session act as the model. It replays `run_fix` from stored answers in a clean worktree, with `run_cmd` in the Docker sandbox, and the loop's own recorder writes the trajectory. Token counts are chars/4 estimates. This is a substitution for the Devstral row, not comparable with a Groq or Mistral run.

```
.venv/Scripts/python.exe -m fix_loop.turn start packages/bench/tasks/seeded/seed-e01 <run id>
.venv/Scripts/python.exe -m fix_loop.turn answer <run id> < reply.json
```

Output is under `runs/<run id>/`. The index, with variant A on 29 of the 30 seeded tasks (20/29 resolved, Wilson 95% [0.507695, 0.827246]; `bug-17` excluded), is `runs/README.md`. The draft failure labels are in `docs/notes/p3-failures.md`. The log is `docs/notes/p3-finish.md`. Variant E (mini-swe-agent through a Claude-session relay, 19/29 resolved) is run with `swarm/mini/` (`relay.sh`, `mini_run.sh`, `mini_turn.sh`); `swarm/tally.py` prints its row.

## Stateless per-step runs (context ablation)

A Claude session keeps its own memory, so a context strategy applied to the loop's messages cannot shrink what it has already read. For the ablation each loop step is instead one fresh subagent that sees only the message list the strategy leaves. `start` takes an optional strategy (`none`, `cap`, `offload` or `summary`) and an optional token budget (default 32000 estimated tokens; a strategy runs at 80% of it). With a strategy, `answer` prints one status line and not the next turn, and `show` prints the pending turn again. A summary request is plain text, every other turn is one JSON tool call, and `answer` rejects a reply of the wrong kind (exit 3, nothing recorded).

```
.venv/Scripts/python.exe -m fix_loop.turn start packages/bench/tasks/seeded/seed-e07 <run id> cap
.venv/Scripts/python.exe -m fix_loop.turn show <run id>
.venv/Scripts/python.exe -m fix_loop.turn answer <run id> < reply.json
```

`packages/fix-loop/swarm/` holds the scripts that drove the 29-task run. They hard-code the paths of the worktree they were written in, so edit `D`, `W` and the paths inside `step.md` before reuse.

- `turn.sh start|show|answer ...` sets `PYTHONPATH` for the workspace packages and runs `python -m fix_loop.turn`.
- `start_task.sh <task suffix>` (for example `h05`) starts the four runs `p4b-full-{none,cap,offload,summary}-<suffix>`.
- `step.md` is the prompt of one step worker (show, reply with one JSON tool call, answer). `coord_runs.md` is the prompt of a coordinator that starts one worker at a time for each run id until a verdict appears.
- `status.sh` counts finished runs per task. `replies/` holds the saved replies.
- `tally.py` prints the resolve counts, Wilson intervals, turns, stop reasons and token estimates from `verdict.json` and `trajectory.jsonl`:

```
cd packages/fix-loop
PYTHONPATH=src:../argus-core/src:../bench/src:../verify/src ../../.venv/Scripts/python.exe swarm/tally.py
```

Results on the 29 tasks, one run per cell, model `claude-session`: none 18/28, cap 21/28, offload 20/28, summary 17/29 resolved. The scorer excluded one run each for none, cap and offload (exit 2). All four intervals overlap, so the strategies are not ranked. The table is in `phases/P03-fix-loop.md` and the log in `docs/notes/p3-finish.md`. Run ids are `p4b-full-<strategy>-<task>`; e05, e07 and e08 use the `p4b-pilot*` ids listed in `swarm/tally.py`.

