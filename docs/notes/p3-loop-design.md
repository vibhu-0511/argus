# P3 loop design notes

Read on 2026-10-31.

- [mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) at `04d809ceab9df28f9adaed044884180159172930`: `src/minisweagent/agents/default.py`, `src/minisweagent/environments/local.py`, `src/minisweagent/models/utils/actions_toolcall.py`, and `src/minisweagent/config/mini.yaml`.
- [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents), Anthropic, 2025-09-29.

## Loop

`DefaultAgent.run` renders a system message and one user message, then calls `step` until the last message has role `exit`. `step` is `query` then `execute_actions`. `query` checks the limits, increments the call count, asks the model, and appends that message. `execute_actions` runs each action from `message["extra"]["actions"]` in the environment and appends the observation messages.

A clean step resets the consecutive format-error count. A `FormatError` is appended as a user message and the loop continues. Three in a row append an exit message `RepeatedFormatError`. `LimitsExceeded`, `TimeExceeded`, and `Submitted` are `InterruptAgentFlow` and become the exit message. Any other exception is an exit whose status is the exception class name, and then the exception is re-raised.

The saved trajectory is one JSON object (`trajectory_format` `mini-swe-agent-1.1`). `info.model_stats` stores `instance_cost` and `api_calls`. It does not store tokens in, out, or cached.

## Tools

There is one tool, `bash`, with one required string, `command`. `parse_toolcall_actions` rejects an empty tool-call list, a tool whose name is not `bash`, arguments that are not JSON, and a call that has no `command`. The error text is rendered from `format_error_template` and returned to the model as a user message.

`LocalEnvironment.execute` runs that string in a new subshell. The default timeout is 30 seconds. Stdout and stderr are combined. The prompt says directory changes do not persist. There is no `read_file`, `edit`, or `submit` tool. The prompt tells the model to edit with `sed` and to finish by running `echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT` alone.

Finish is not a tool result. If the first line of stdout is that marker and the return code is 0, the environment raises `Submitted`. `submission` is the rest of that stdout. The worktree diff is not what this loop records.

## Termination

Checked in `query`, before the model call:

- `step_limit`: stop only when `0 < step_limit <= n_calls`. The config sets `step_limit: 0`, and 0 disables the check, so the default is unlimited steps. The exit content is `LimitsExceeded`.
- `cost_limit`: stop when `0 < cost_limit <= cost`. The config sets `cost_limit: 3.0`. The same exit content is `LimitsExceeded`.
- `wall_time_limit_seconds`: stop when the limit is greater than 0 and elapsed seconds have reached it. The default is 0, which disables the check. The exit content is `TimeExceeded`.

Also:

- `max_consecutive_format_errors` defaults to 3. The exit content is `RepeatedFormatError`. 0 disables that check.
- The marker echo exits with `Submitted`.

There is no check for the same command repeated, no token cap, and no quota stop. A zero limit means "do not check", not "stop immediately".

## Context

`observation_template` in `mini.yaml` keeps an output under 10000 characters whole. At 10000 or more it keeps the first 5000 and the last 5000, plus `elided_chars` and the string "Output too long." That cut happens on every observation. It does not wait for a fraction of the window, it does not write the body to a file, and it does not summarize older turns.

The Anthropic post says context is a finite attention budget, and that the useful set is the smallest high-signal set. For a long run it names three techniques: compaction (summarize the history and start a new window; Claude Code also keeps the five most recently accessed files), structured note-taking (notes outside the window, pulled back later), and sub-agents (a sub-agent returns a short summary). It also describes just-in-time retrieval: keep a path or a query, and load the body with a tool when it is needed. Tool results deep in the history are called a light form of compaction when they are cleared.

## Three choices this repo will make differently

1. **Tools.** Six typed tools: `read_file`, `list_dir`, `search`, `edit`, `run_cmd`, `submit`, plus ast-grep later. `edit` is an exact unique match whose error names the line numbers. No `sed` as the editor, and no second whole-file write tool. `submit` is a tool. The scored artifact is the worktree diff the bench checks run on, not the stdout after the echo marker.

2. **Stops.** The loop stops on `submit`, a step cap, a token cap, `QuotaExceeded`, stuck detection (the same tool call repeated), and a consecutive-timeout stop that is not `stuck`. There is no dollar `cost_limit`. A cap of zero is not the mini convention of "disabled". Repeated malformed arguments end the run, and that reason stays distinct from `stuck`.

3. **Context.** Four strategies, chosen per run: none, output caps, offload-to-files, and a rolling summary. The budget manager calls the strategy at 80% of the window. Offload writes the body to a file and leaves a path plus a short head, which the model reads back with `read_file`. That is the post's note-taking and just-in-time pointer, not mini's head-plus-tail cut. The summary is produced by the cheap-tier model, the system prompt and the first user message survive, and a summary that does not shrink the window is a stop. Last-N elision, including the post's "five most recent files", is not added. Summary tokens count in the ledger.
