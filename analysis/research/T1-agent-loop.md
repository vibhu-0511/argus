# T1 — agent loop

Planning notes only. Argus still writes the loop, tools, context manager, and trajectory recorder. No library dependency is proposed for those. SHAs verified with `git rev-parse HEAD` on the local clones.

| Repo | SHA | Licence |
|---|---|---|
| SWE-agent/mini-swe-agent | `04d809ceab9df28f9adaed044884180159172930` | MIT (`LICENSE.md`) |
| SWE-agent/SWE-agent | `3ea751c087f32b16e039a2233dd6eefecef325d5` | MIT (`LICENSE`) |
| Aider-AI/aider | `5dc9490bb35f9729ef2c95d00a19ccd30c26339c` | Apache-2.0 (`LICENSE.txt`) |
| OpenHands/software-agent-sdk | `46b1fa5cb91ada17e6ec938c7e8624a4fa19fa98` | MIT (`LICENSE`) |

Issue search used `gh api` search (`is:issue` / `is:pr`, sort `comments` and `reactions`, no state filter, because `gh search --state all` is rejected). Counts below are `comments` and `reactions.total_count` from that response.

### T1-01 Baseline ACI is one bash tool, not six
- Topic: tool schemas
- Their approach: mini-swe-agent exposes a single function tool named `bash` with one required string, `command`. There is no `read_file`, `edit`, or `submit` tool. The prompt tells the model to edit with `sed` and to finish by echoing a marker. [CODE]

```11:18:src/minisweagent/models/utils/actions_toolcall.py
BASH_TOOL = {
    "type": "function",
    "function": {
        "name": "bash",
        "description": "Execute a bash command",
        "parameters": {
            "type": "object",
```

https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/models/utils/actions_toolcall.py#L11-L27

https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/config/mini.yaml#L16-L18
- Argus plan: `PROJECT.md` § Fix-loop tools, and `phases/P03-fix-loop.md` task P3-T02. "Each tool has a typed schema, description and typed error results." The listed tools are `read_file`, `list_dir`, `search`, `edit`, `run_cmd`, `submit`, plus ast-grep.
- Evidence: [CODE]
- Licence: MIT
- Affected: P3-T01, P3-T02, P3-T17, ADR-008, ADR-011. The head-to-head is a different computer interface. ADR-011 has to say that, or a resolve-rate gap is not evidence for or against a framework.

### T1-02 The scored "patch" is stdout after a magic echo
- Topic: submit and what the baseline comparison scores
- Their approach: any environment treats the run as submitted only when stdout's first line is `COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT` and the return code is 0. `submission` is the rest of that stdout, not `git diff`. The SWE-bench runner writes that string into `model_patch`. [CODE]

```46:53:src/minisweagent/environments/local.py
        """Raises Submitted if the output indicates task completion."""
        lines = output.get("output", "").lstrip().splitlines(keepends=True)
        if lines and lines[0].strip() == "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT" and output["returncode"] == 0:
            submission = "".join(lines[1:])
            raise Submitted(
                {
                    "role": "exit",
                    "content": submission,

https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/environments/local.py#L45-L55

https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/run/benchmarks/swebench.py#L154-L156
- Argus plan: `PLAN.md` § Metrics contract. "A task is resolved when the bench scorer passes on the agent's final patch, no bench check file was touched." P3-T17 says the mini-swe-agent trajectory "is converted to the Trajectory format." It does not say whether the scored patch is `submission` or a worktree diff.
- Evidence: [CODE]
- Licence: MIT
- Affected: P3-T17, P3-T20, ADR-011. If the model only echoes the marker, `submission` is empty and the worktree diff is never captured by this loop. The conversion task needs an explicit rule, or variant E is not comparable.

### T1-03 Mini stops on dollars and consecutive format errors, not on a token cap or a repeated command
- Topic: stop conditions
- Their approach: `step_limit` and `cost_limit` are checked before the model call. A limit of 0 disables that check, so the default `step_limit: 0` is unlimited. Default `cost_limit` is 3.0. Three `FormatError`s in a row append an exit message `RepeatedFormatError`. There is no check for an identical bash command. A separate `wall_time_limit_seconds` raises `TimeExceeded`. [CODE]

```130:137:src/minisweagent/agents/default.py
    def query(self) -> dict:
        """Query the model and return model messages. Override to add hooks."""
        if 0 < self.config.step_limit <= self.n_calls or 0 < self.config.cost_limit <= self.cost:
            raise LimitsExceeded(
                {
                    "role": "exit",
                    "content": "LimitsExceeded",
                    "extra": {"exit_status": "LimitsExceeded", "submission": ""},
                }
            )
```

```32:33:src/minisweagent/agents/default.py
    max_consecutive_format_errors: int = 3
    """Exit after this many format errors in a row (0 = no limit)."""
```

https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/agents/default.py#L26-L33

https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/agents/default.py#L100-L112

https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/agents/default.py#L130-L147
- Argus plan: `PROJECT.md` § Stop conditions (P3). "The loop stops on `submit`, a step cap, a token cap, `QuotaExceeded`, or stuck detection (the same tool call repeated)." P3-T17: "through the same ledger and sandbox." P3-T20: "the same model and seed policy."
- Evidence: [CODE]
- Licence: MIT
- Affected: P3-T06, P3-T17, P3-T20, P3-T28, P3-T30, ADR-008, ADR-011. P3-T17 must set mini's `cost_limit` to 0 (or the run dies at $3) and must say whether Argus stuck-detection is on during the head-to-head. `RepeatedFormatError` is a different reason from `stuck`. P3-T30 says repeated malformed calls end the run and does not name the reason code. The break-it for stuck says "N identical consecutive calls" and does not set N.

### T1-04 A zero cost from litellm aborts the baseline
- Topic: free-model cost tracking
- Their approach: `LitellmModel._calculate_cost` requires `cost > 0`. If the model is missing from litellm's price table, or the computed cost is 0, it raises `RuntimeError` unless `cost_tracking` is `ignore_errors`. The trajectory's `info.model_stats` stores `instance_cost` and `api_calls` only. The raw response is nested at `extra.response` on a successful message, and also on `FormatError`. [CODE]

```108:115:src/minisweagent/models/litellm_model.py
    def _calculate_cost(self, response) -> dict[str, float]:
        try:
            cost = litellm.cost_calculator.completion_cost(response, model=self.config.model_name)
            if cost <= 0.0:
                raise ValueError(f"Cost must be > 0.0, got {cost}")
        except Exception as e:
            cost = 0.0
            if self.config.cost_tracking != "ignore_errors":

https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/models/litellm_model.py#L87-L98

https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/models/litellm_model.py#L108-L126

https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/agents/default.py#L163-L178
- Argus plan: `phases/P03-fix-loop.md` P3-T08. "it includes tokens in, out and cached per step." P3-T17 uses the same ledger. `PLAN.md` § Models: the fixer is Devstral on the Mistral free tier, behind one OpenAI-compatible client.
- Evidence: [CODE]
- Licence: MIT
- Affected: P3-T08, P3-T17, ADR-001, ADR-011. Whether Devstral is in litellm's price table was not verified. The conversion task has to say where cached tokens come from, because this serializer does not have that field.

### T1-05 Context control in the baseline is head-plus-tail of each observation
- Topic: context compaction
- Their approach: the observation template always elides an output of 10000 characters or more to the first 5000 and the last 5000, plus `elided_chars` and the string "Output too long." It does not wait for 80% of the window, does not write the body to a file, and does not summarize. [CODE]

```119:126:src/minisweagent/config/mini.yaml
    {
      "returncode": {{ output.returncode }},
      "output_head": {{ output.output[:5000] | tojson }},
      "output_tail": {{ output.output[-5000:] | tojson }},
      "elided_chars": {{ output.output | length - 10000 }},
      "warning": "Output too long."
      {%- if output.exception_info %}, "exception_info": {{ output.exception_info | tojson }}{% endif %}
    }

https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/config/mini.yaml#L112-L127
- Argus plan: `phases/P03-fix-loop.md` P3-T09 and P3-T10. "calls a pluggable strategy when 80% of the budget is reached." "A 50k-character tool output is cut to the cap with a visible truncation marker."
- Evidence: [CODE]
- Licence: MIT
- Affected: P3-T09, P3-T10, P3-T29, ADR-009. Variant B drops the tail unless the acceptance test says otherwise. The baseline truncates every observation, so variant A ("no compaction") is not what mini-swe-agent runs. ADR-011 should say which mini config is variant E.

### T1-06 Mini's trajectory is one JSON document, rewritten every step, with no replay command
- Topic: trajectory format and replay
- Their approach: `save` writes `trajectory_format: "mini-swe-agent-1.1"`, an `info` object, and the whole `messages` list, as one indented JSON file. `save` runs in a `finally` after every step. A search of `src/` for `replay` hit only that format string. [CODE]

```173:178:src/minisweagent/agents/default.py
                "mini_version": __version__,
                "exit_status": last_extra.get("exit_status", ""),
                "submission": last_extra.get("submission", ""),
            },
            "messages": self.messages,
            "trajectory_format": "mini-swe-agent-1.1",

https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/agents/default.py#L120-L124

https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/agents/default.py#L159-L190
- Argus plan: `phases/P03-fix-loop.md` Done when, and P3-T08 / P3-T27. "A recorded trajectory replays deterministically with no LLM call." "`fix-loop replay <file>` reproduces the final patch byte for byte from the stored model responses."
- Evidence: [CODE]
- Licence: MIT
- Affected: P3-T08, P3-T17, P3-T27, ADR-001. Conversion is a real task: one JSON message list into JSONL steps. Mini does not implement the byte-for-byte replay Argus wants. That replay stays [ME].

### T1-07 Default Docker is networked, and each command has a 30s timeout
- Topic: sandbox flags the baseline does not set
- Their approach: `DockerEnvironmentConfig.run_args` defaults to `["--rm"]`. The `docker run` invocation in `_start_container` adds `-d`, `--name`, `-w`, those args, the image, and `sleep`. No `--network` flag is in that file. `timeout` defaults to 30 seconds per `docker exec`. [CODE]

```26:33:src/minisweagent/environments/docker.py
    timeout: int = 30
    """Timeout for executing commands in the container."""
    executable: str = os.getenv("MSWEA_DOCKER_EXECUTABLE", "docker")
    ...
    run_args: list[str] = ["--rm"]
```

https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/environments/docker.py#L26-L33

https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/environments/docker.py#L74-L89
- Argus plan: `phases/P03-fix-loop.md` Done when. "Every run executes in a git worktree plus a Docker container with `--network none`, and the bench checks are mounted read-only." P3-T17: "through the same ledger and sandbox."
- Evidence: [CODE]
- Licence: MIT
- Affected: P3-T05, P3-T17, ADR-010. The task does not say whether mini uses Argus's runner or its own `DockerEnvironment`. If it uses its own, `run_args` must add `--network none`, the CPU and memory caps, and the read-only checks mount, or variant E is a different sandbox. A per-command timeout is not in P3-T05.

### T1-08 SWE-agent function-call errors are a closed code set, then `exit_format`
- Topic: typed errors
- Their approach: `FunctionCallingFormatError` carries `error_code` of `missing`, `multiple`, `incorrect_args`, `invalid_json`, `invalid_command`, `missing_arg`, or `unexpected_arg`. The function-calling parser requires exactly one tool call. Format, blocklist, and bash-syntax failures are retried up to `max_requeries` (default 3) and then become exit status `exit_format`. The template text is fed back as the next history, not raised out of the process. [CODE]

```17:24:sweagent/exceptions.py
        error_code: Literal[
            "missing", "multiple", "incorrect_args", "invalid_json", "invalid_command", "missing_arg", "unexpected_arg"
        ],
        **extra_info: Any,
    ):
        super().__init__(message + f" [error_code={error_code}]")
        self.message = message
        self.extra_info = {"error_code": error_code, **extra_info}

https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/exceptions.py#L10-L24

https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/tools/parsing.py#L441-L451

https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/agent/agents.py#L1106-L1124

https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/agent/agents.py#L1211-L1218
- Argus plan: `phases/P03-fix-loop.md` P3-T02 and P3-T07 and P3-T30. "Malformed arguments return a typed error to the model rather than raising." "A typed error goes back to the model, the run does not crash, and repeated errors end the run." The break-it says to put required fields in the message. It does not name an error-code enum or a distinct stop reason from `stuck`.
- Evidence: [CODE]
- Licence: MIT
- Affected: P3-T02, P3-T07, P3-T30, ADR-008. One code for "missing required field" versus "unknown tool" versus "two tool calls" changes the unit test in P3-T07 ("5 bad inputs") and the label list in P3-T21.

### T1-09 SWE-agent's failure labels are exit statuses, and a failed run still tries to save a diff
- Topic: failure taxonomy
- Their approach: handled exits include `exit_forfeit`, `exit_total_execution_time`, `exit_command_timeout`, `exit_context`, `exit_cost`, `exit_api`, `exit_environment_error`, `exit_error`, and `exit_format`. `exit_command` is the literal action `exit`. On these errors `attempt_autosubmission_after_error` runs `git add -A && git diff --cached > /root/model.patch` and, if that file is non-empty, rewrites the status to `submitted (<previous>)`. A qualitative taxonomy (wrong file, bad edit, and so on) was not in the Python modules opened. `AgentInfo` has `exit_status` and a `summarizer` field; the reviewer summarizer calls are commented out. [CODE]

```823:826:sweagent/agent/agents.py
    def attempt_autosubmission_after_error(self, step: StepOutput) -> StepOutput:
        """For most exceptions, we attempt to still extract the patch and submit that.
        This means we send the `submit` command to the runtime and parse the output.
        """
```

https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/agent/agents.py#L1152-L1218

https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/agent/agents.py#L852-L856

https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/types.py#L82-L86
- Argus plan: `phases/P03-fix-loop.md` P3-T21. "Every failed trajectory has one label from a written list." The list is not in the phase file. `PLAN.md` § Metrics contract scores "the agent's final patch" and does not say a token-cap or stuck stop still scores the worktree diff.
- Evidence: [CODE]
- Licence: MIT
- Affected: P3-T18, P3-T21, ADR-008. P3-T21's list should include the stop reasons from P3-T06, or the counts are not comparable to SWE-agent's `exit_*` rollup. Scoring a partial diff after a cap changes resolve rate. That choice is not specified.

### T1-10 SWE-agent compacts by clipping and by deleting old observations, and says that breaks the cache
- Topic: context compaction
- Their approach: an observation longer than `max_observation_length` (default 100_000 characters) is rendered with `observation[:max_observation_length]` and the marker `<response clipped>`, and the note tells the model to use head, tail, grep, or a redirect. `LastNObservations` replaces older observations with "Old environment output: (n lines omitted)". Its docstring says this breaks prompt caching because every query changes the history. `ClosedWindowHistoryProcessor` replaces older windows of a file with "Outdated window with N lines omitted". `CacheControlHistoryProcessor` sets cache marks on the last n user/tool messages. No live summarizer is called from the processors that were opened. [CODE]

```69:74:sweagent/agent/agents.py
    next_step_truncated_observation_template: str = (
        "Observation: {{observation[:max_observation_length]}}<response clipped>"
        "<NOTE>Observations should not exceeded {{max_observation_length}} characters. "
        "{{elided_chars}} characters were elided. Please try a different command that produces less output "
        "or use head/tail/grep/redirect the output to a file. Do not use interactive pagers.</NOTE>"
    )

https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/agent/agents.py#L69-L82

https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/agent/history_processors.py#L85-L111

https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/agent/history_processors.py#L157-L175

https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/agent/models.py#L292-L298
- Argus plan: `phases/P03-fix-loop.md` § Ablation. Variants are none, output caps, offload-to-files, summarize, and mini-swe-agent. `PROJECT.md` § Models: on Groq, "Cached tokens do not count against the cap." `InstanceStats` stores `tokens_sent` and `tokens_received` and does not split cached tokens. A search of `sweagent/agent/models.py` for `cached_tokens` and `prompt_tokens` returned no matches.
- Evidence: [CODE]
- Licence: MIT
- Affected: P3-T09, P3-T10, P3-T11, P3-T12, P3-T17, ADR-009, ADR-002. Last-N elision is a fifth strategy and it invalidates a cached prefix. P3-T12 does not say the system message and the first user message (repro result and `locate()` hint, P3-T16) are kept. P3-T17's token conversion cannot fill "cached" from `InstanceStats`.

### T1-11 SWE-agent replay re-executes stored actions in a fresh environment
- Topic: trajectory format and replay
- Their approach: a `.traj` file holds `trajectory`, `history`, `info`, and `replay_config`. `docs/usage/trajectories.md` defines each step as `response`, `thought`, `action`, `observation`, `state`, and `query`. `ReplayModel` feeds those stored actions back to a live `SWEEnv`. The module docstring says this is for building demos and debugging tools, and it re-executes. If the action list ends without submit, it synthesizes a submit call. [CODE] [DOCS]

```1:8:sweagent/run/run_replay.py
"""[cyan][bold]Replay a trajectory file.[/bold][/cyan]

[cyan][bold]=== DESCRIPTION ===[/bold][/cyan]

We will take all actions in the trajectory and execute them in an environment.

This has two main use cases:

https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/types.py#L44-L52

https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/agent/agents.py#L762-L787

https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/run/run_replay.py#L1-L11

https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/agent/models.py#L464-L468

https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/docs/usage/trajectories.md#L9-L24
- Argus plan: `phases/P03-fix-loop.md` P3-T27. "`fix-loop replay <file>` reproduces the final patch byte for byte from the stored model responses."
- Evidence: [CODE] [DOCS]
- Licence: MIT
- Affected: P3-T08, P3-T27, ADR-001. Re-execution can drift if a command is not deterministic. Argus's acceptance test is the stricter one and should keep storing the model message that produced each action. Do not implement replay by shelling the actions again.

### T1-12 Three edit contracts, and they disagree on the second match
- Topic: edit format
- Their approach: SWE-agent's windowed `edit` docstring says replace the first occurrence in the displayed lines. `WindowedFile.replace_in_window` then calls `str.replace`, which replaces every occurrence in the window. A miss raises `TextNotFound` (or prints and `exit(1)` when `_exit_on_exception` is set). The `str_replace_editor` docstring, and OpenHands `FileEditor.str_replace`, refuse the edit when `old_str` matches more than one place and name the line numbers. Aider's reminder says a SEARCH block replaces only the first match and must match character for character. `perfect_replace` does an exact line-tuple match; a miss becomes `SearchReplaceNoExactMatch` and includes similar lines. `replace_most_similar_chunk` returns before the fuzzy `replace_closest_edit_distance` call, so that fallback is unreachable in this function. Aider's unified-diff coder has two different errors, `UnifiedDiffNoMatch` and `UnifiedDiffNotUnique`. `WholeFileCoder.apply_edits` overwrites the file with the new line list. [CODE]

```215:216:tools/windowed/lib/windowed_file.py
        new_window_text = window_text.replace(search, replace)
        self.set_window_text(new_window_text)
```

```236:241:openhands-tools/openhands/tools/file_editor/editor.py
        if len(occurrences) > 1:
            line_numbers = sorted(set(line for line, _, _ in occurrences))
            raise ToolError(
                f"No replacement was performed. Multiple occurrences of old_str "
                f"`{old_str}` in lines {line_numbers}. Please ensure it is unique."
            )

```180:187:aider/coders/editblock_coder.py
    except ValueError:
        pass

    return
    # Try fuzzy matching
    res = replace_closest_edit_distance(whole_lines, part, part_lines, replace_lines)
    if res:
        return res

https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/tools/windowed_edit_replace/config.yaml#L1-L8

https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/tools/windowed/lib/windowed_file.py#L208-L216

https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/tools/edit_anthropic/config.yaml#L15-L17

https://github.com/OpenHands/software-agent-sdk/blob/46b1fa5cb91ada17e6ec938c7e8624a4fa19fa98/openhands-tools/openhands/tools/file_editor/editor.py#L214-L241

https://github.com/Aider-AI/aider/blob/5dc9490bb35f9729ef2c95d00a19ccd30c26339c/aider/coders/editblock_prompts.py#L134-L137

https://github.com/Aider-AI/aider/blob/5dc9490bb35f9729ef2c95d00a19ccd30c26339c/aider/coders/editblock_coder.py#L84-L97

https://github.com/Aider-AI/aider/blob/5dc9490bb35f9729ef2c95d00a19ccd30c26339c/aider/coders/editblock_coder.py#L146-L154

https://github.com/Aider-AI/aider/blob/5dc9490bb35f9729ef2c95d00a19ccd30c26339c/aider/coders/editblock_coder.py#L175-L187

https://github.com/Aider-AI/aider/blob/5dc9490bb35f9729ef2c95d00a19ccd30c26339c/aider/coders/udiff_coder.py#L16-L39

https://github.com/Aider-AI/aider/blob/5dc9490bb35f9729ef2c95d00a19ccd30c26339c/aider/coders/wholefile_coder.py#L124-L128
- Argus plan: `phases/P03-fix-loop.md` P3-T02. The `edit` tool "has a typed schema, description and typed error results." First-match, unique-match, window-only, and whole-file are not specified.
- Evidence: [CODE]
- Licence: MIT for SWE-agent and OpenHands; Apache-2.0 for Aider
- Affected: P3-T02, P3-T07, ADR-008. Pick one contract in the schema test: exact unique match, with the line numbers in the error, is the contract both SWE-agent's str_replace notes and OpenHands implement. Do not add Aider's whitespace flex or the unreachable fuzzy matcher, and do not add a second whole-file tool. The windowed docstring and `str.replace` disagree; copying the docstring without a test would hide that.

### T1-13 Interactive commands and consecutive timeouts are their own stop
- Topic: stop conditions for `run_cmd`
- Their approach: a default blocklist rejects commands that start with `vim`, `vi`, `emacs`, `nano`, `less`, `tail -f`, and a few others, and exact commands `python`, `python3`, `bash`, `sh`. A blocked action is a retry, then counts toward `exit_format`. `execution_timeout` defaults to 30 seconds. Three consecutive timeouts raise, and the handler maps that to `exit_command_timeout`. `total_execution_timeout` defaults to 1800 seconds and does not interrupt the running command. [CODE]

```139:146:sweagent/tools/tools.py
    execution_timeout: int = 30
    """Timeout for executing commands in the environment"""

    install_timeout: int = 300
    """Timeout used for each of the installation commands"""

    total_execution_timeout: int = 1800
    """Timeout for executing all commands in the environment.

https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/tools/tools.py#L29-L66

https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/tools/tools.py#L139-L152

https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/agent/agents.py#L946-L975
- Argus plan: `phases/P03-fix-loop.md` P3-T32. "The command only affects the disposable worktree and container; the host tree is unchanged." Stuck detection is "the same tool call repeated," which does not fire on one hung `vim` or `python`.
- Evidence: [CODE]
- Licence: MIT
- Affected: P3-T06, P3-T32, ADR-008. A per-command timeout and a consecutive-timeout reason are missing. Without them a single interactive process holds the sandbox until the outer step cap, if a step cap is even checked during a blocking call. That check is not specified.

### T1-14 OpenHands stuck detection nudges once, then stops, and it is more than one repeated call
- Topic: stuck detection
- Their approach: `StuckDetectionThresholds` defaults are 4 identical action/observation pairs, 3 identical action/error pairs, 3 agent messages for a monologue, and 6 for an alternating pattern. A fifth check looks for a context-window error loop once 10 events have accumulated. `get_action_error_nudge` returns a user message when the error streak first equals the threshold. The next repeat sets `execution_status` to `STUCK` and the run loop stops. `stuck_detection` defaults to true. `max_iterations` defaults to 500 and the loop records `MaxIterationsReached`. [CODE]

```150:157:openhands-sdk/openhands/sdk/conversation/types.py
    action_observation: int = Field(
        default=4, ge=1, description="Threshold for action-observation loop detection"
    )
    action_error: int = Field(
        default=3, ge=1, description="Threshold for action-error loop detection"
    )
    monologue: int = Field(
        default=3, ge=1, description="Threshold for agent monologue detection"

```242:248:openhands-sdk/openhands/sdk/conversation/stuck_detector.py
        return (
            f"You've called `{action.tool_name}` with the same arguments "
            f"{threshold} times in a row and gotten the same error each "
            f"time: {error.error}. Repeating the exact same call again "
            "will not work — review the error message and either correct "
            "the arguments or try a different approach."
        )
```

https://github.com/OpenHands/software-agent-sdk/blob/46b1fa5cb91ada17e6ec938c7e8624a4fa19fa98/openhands-sdk/openhands/sdk/conversation/types.py#L136-L161

https://github.com/OpenHands/software-agent-sdk/blob/46b1fa5cb91ada17e6ec938c7e8624a4fa19fa98/openhands-sdk/openhands/sdk/conversation/stuck_detector.py#L131-L152

https://github.com/OpenHands/software-agent-sdk/blob/46b1fa5cb91ada17e6ec938c7e8624a4fa19fa98/openhands-sdk/openhands/sdk/conversation/stuck_detector.py#L218-L248

https://github.com/OpenHands/software-agent-sdk/blob/46b1fa5cb91ada17e6ec938c7e8624a4fa19fa98/openhands-sdk/openhands/sdk/conversation/impl/local_conversation.py#L787-L808

https://github.com/OpenHands/software-agent-sdk/blob/46b1fa5cb91ada17e6ec938c7e8624a4fa19fa98/openhands-sdk/openhands/sdk/conversation/state.py#L108-L122

https://github.com/OpenHands/software-agent-sdk/blob/46b1fa5cb91ada17e6ec938c7e8624a4fa19fa98/openhands-sdk/openhands/sdk/conversation/impl/local_conversation.py#L2104-L2125
- Argus plan: `phases/P03-fix-loop.md` Break it on purpose, item 1. "detect N identical consecutive calls and end the run or inject a 'you are repeating yourself' message once." P3-T28 expects stop reason `stuck` and does not mention a one-time nudge. P5 trajectory metrics include stuck rate, defined later in `docs/metrics.md`.
- Evidence: [CODE]
- Licence: MIT
- Affected: P3-T06, P3-T28, P3-T30, ADR-008. The break-it allows either an immediate stop or one nudge. Those produce different stuck rates. ADR-008 should pick one and set N. Alternating calls and a monologue are not specified, so P3-T28's fake model (the same `read_file` forever) does not cover them.

### T1-15 A summary that does not shrink the view is a failed condensation, and the head of the log is kept
- Topic: context compaction
- Their approach: `LLMSummarizingCondenser` uses its own LLM. It keeps the first `keep_first` events (default 2). It condenses when an explicit request is pending, when token count exceeds the smaller of its `max_tokens` and the agent model's input limit, or when the view is longer than `max_size` (default 240). Token pressure and requests are hard. Event-count pressure is soft. `minimum_progress` (default 0.1) treats a condensation that forgets less than that fraction of events as an error. The summary call disables streaming so the summary is one response. A leading `SystemPromptEvent` is not forgotten. [CODE]

```67:74:openhands-sdk/openhands/sdk/context/condenser/llm_summarizing_condenser.py
    keep_first: int = Field(default=2, ge=0)
    """Minimum number of events to preserve at the start of the view. The first
    `keep_first` events in the conversation will never be condensed or summarized.
    """

    minimum_progress: float = Field(default=0.1, gt=0.0, lt=1.0)
    """Minimum fraction of events that must be condensed (0.0-1.0). If fewer than
    this proportion of events would be forgotten, condensation is treated as an error.

https://github.com/OpenHands/software-agent-sdk/blob/46b1fa5cb91ada17e6ec938c7e8624a4fa19fa98/openhands-sdk/openhands/sdk/context/condenser/llm_summarizing_condenser.py#L54-L76

https://github.com/OpenHands/software-agent-sdk/blob/46b1fa5cb91ada17e6ec938c7e8624a4fa19fa98/openhands-sdk/openhands/sdk/context/condenser/llm_summarizing_condenser.py#L31-L44

https://github.com/OpenHands/software-agent-sdk/blob/46b1fa5cb91ada17e6ec938c7e8624a4fa19fa98/openhands-sdk/openhands/sdk/context/condenser/llm_summarizing_condenser.py#L140-L207
- Argus plan: `phases/P03-fix-loop.md` P3-T12. "Older turns are replaced by a summary produced by the cheap-tier model; summary tokens are counted in the ledger." The trigger is "when 80% of the budget is reached" (P3-T09).
- Evidence: [CODE]
- Licence: MIT
- Affected: P3-T09, P3-T12, P3-T16, ADR-009. P3-T12 already uses the cheap model and the ledger. It does not say the system prompt and the first user message survive, and it does not say a summary that fails to shrink the window is a stop rather than another model call. That is how a summary loop spends the Groq day cap. 80% of the window is a hard trigger; OpenHands treats event-count as soft. ADR-009 should say which.

### T1-16 Tool failures are observations with `is_error`, and the log is one JSON file per event
- Topic: typed errors, trajectory format
- Their approach: `Observation.from_text(..., is_error=True)` stores the text and, when sent to the model, prepends `"[An error occurred during execution.]\n"`. The file editor catches `ToolError` and returns that observation. `EditorToolParameterMissingError` names the command and the parameter. The durable log is `events/event-{idx:05d}-{event_id}.json` plus `base_state.json`, not one JSONL file. `FailureKind` is `auth`, `quota`, `rate_limit`, `config`, `transient`, `agent_action`, `internal`, `unknown`. Context-window errors are classified `agent_action` and retryable, because condensation is the recovery. This enum is not a bug-fix taxonomy (wrong file, bad edit). [CODE]

```365:372:openhands-sdk/openhands/sdk/tool/schema.py
class Observation(Schema, ABC):
    """Base schema for output observation."""

    ERROR_MESSAGE_HEADER: ClassVar[str] = "[An error occurred during execution.]\n"

    content: list[TextContent | ImageContent] = Field(
        default_factory=list,
        description=(

```20:25:openhands-tools/openhands/tools/file_editor/exceptions.py
    def __init__(self, command: str, parameter: str):
        self.command = command
        self.parameter = parameter
        self.message: str = (
            f"Parameter `{parameter}` is required for command: {command}."
        )

https://github.com/OpenHands/software-agent-sdk/blob/46b1fa5cb91ada17e6ec938c7e8624a4fa19fa98/openhands-tools/openhands/tools/file_editor/impl.py#L68-L71

https://github.com/OpenHands/software-agent-sdk/blob/46b1fa5cb91ada17e6ec938c7e8624a4fa19fa98/openhands-sdk/openhands/sdk/tool/schema.py#L365-L380

https://github.com/OpenHands/software-agent-sdk/blob/46b1fa5cb91ada17e6ec938c7e8624a4fa19fa98/openhands-sdk/openhands/sdk/tool/schema.py#L420-L425

https://github.com/OpenHands/software-agent-sdk/blob/46b1fa5cb91ada17e6ec938c7e8624a4fa19fa98/openhands-tools/openhands/tools/file_editor/exceptions.py#L1-L25

https://github.com/OpenHands/software-agent-sdk/blob/46b1fa5cb91ada17e6ec938c7e8624a4fa19fa98/openhands-sdk/openhands/sdk/conversation/persistence_const.py#L3-L10

https://github.com/OpenHands/software-agent-sdk/blob/46b1fa5cb91ada17e6ec938c7e8624a4fa19fa98/openhands-sdk/openhands/sdk/event/error_classification.py#L9-L17

https://github.com/OpenHands/software-agent-sdk/blob/46b1fa5cb91ada17e6ec938c7e8624a4fa19fa98/openhands-sdk/openhands/sdk/event/error_classification.py#L82-L85
- Argus plan: `phases/P03-fix-loop.md` P3-T07 and P3-T08. "Malformed arguments return a typed error to the model rather than raising." "A run writes one JSONL file that validates against the Trajectory schema." P3-T21's labels are for failed fix attempts, which this `FailureKind` enum does not cover.
- Evidence: [CODE]
- Licence: MIT
- Affected: P3-T07, P3-T08, P3-T21, ADR-001, ADR-008. Keep JSONL. Borrow the boolean: a tool error is a normal step with a flag, so P5's tool-error rate has something to count. Do not copy `FailureKind` into `docs/notes/p3-failures.md`.

## Lessons from their issue tracker

Search was `gh api` on `search/issues` with `sort=comments` and `sort=reactions`, `is:issue` and `is:pr`, `per_page` 8 for issues and 6 for pull requests, no state flag. `gh search --state all` failed (`valid values are {open|closed}`). Counts are from that JSON.

### SWE-agent/mini-swe-agent

- [Issue 737](https://github.com/SWE-agent/mini-swe-agent/issues/737) (closed, 10 comments, 1 reaction). A `FormatError` left the assistant message out of `traj.json`, so the inspector's step count was wrong and the model never saw the bad output. The plan's P3-T27 replay needs stored model responses, and P3-T30 returns a typed error, but `phases/P03-fix-loop.md` P3-T08 does not say a rejected tool call is still a Trajectory record that contains the raw response. At this SHA, `LitellmModel.query` does persist `extra.response` on `FormatError` (see T1-04). The acceptance test still does not require that field.
- [Issue 773](https://github.com/SWE-agent/mini-swe-agent/issues/773) (closed, 7 comments, 4 reactions). Setting `environment.interpreter` to `["bash", "-c"]` dropped the login environment, so commands could not find the testbed; `-lc` sourced it. Not specified. P3-T17 says "the same sandbox" and does not pin mini's interpreter flags. `DockerEnvironmentConfig.interpreter` at this SHA defaults to `["bash", "-lc"]` (`docker.py` lines 38–42).
- [Issue 382](https://github.com/SWE-agent/mini-swe-agent/issues/382) (closed, 15 comments). `OPENAI_API_KEY` was set and the SWE-bench run still raised `litellm.AuthenticationError`. Not specified. P3-T17 says "the OpenAI-compatible endpoint" and does not name which environment variable mini reads.
- [Issue 303](https://github.com/SWE-agent/mini-swe-agent/issues/303) (closed, 11 comments, 3 reactions). Local models needed better support. Related to T1-04: an unpriced model aborts unless `cost_tracking` is `ignore_errors`. P3-T17 does not say to set that. `PLAN.md` § Risk register item 1 covers a host disappearing, not a $0 price-table lookup.

### SWE-agent/SWE-agent

- [Issue 717](https://github.com/SWE-agent/SWE-agent/issues/717) (closed, 18 comments). The trajectory showed a fix and a submit, then "no patch to save," and no diff file was written. `PLAN.md` § Metrics contract scores the bench on the final patch, so an empty diff is unresolved. `phases/P03-fix-loop.md` P3-T21 does not name an "empty patch after submit" label. Current autosubmit behaviour is T1-09; whether this old `run.py` path still exists was not verified beyond the issue body.
- [Issue 20](https://github.com/SWE-agent/SWE-agent/issues/20) (closed, 17 comments). Docker Desktop was incompatible. `PROJECT.md` § Constraints names Docker 29.5 on WSL2. A Docker Desktop-specific check is not specified.
- [Issue 64](https://github.com/SWE-agent/SWE-agent/issues/64) (closed, 15 comments, 8 reactions). Request for LiteLLM so more model hosts work. Already guarded: `PLAN.md` § Models, "one thin client covers them," and the host is `base_url` and key. Do not add LiteLLM to the loop (ADR-011, constraint 4 in `analysis/CONSTRAINTS.md`).

### Aider-AI/aider

- [Issue 649](https://github.com/Aider-AI/aider/issues/649) (open, 39 comments, 41 reactions). Each atomic edit should be shown and applied only after the user approves. Not specified in P3. `PROJECT.md` § P6 puts the human wait in `awaiting-qa` after the pull request, not on every edit. Adding a per-edit confirm in P3 would be new scope.
- [Issue 3314](https://github.com/Aider-AI/aider/issues/3314) (open, 25 comments, 244 reactions) and [pull 3937](https://github.com/Aider-AI/aider/pull/3937) (closed, 79 comments, 224 reactions). MCP support, including a LiteLLM MCP pull request. The fix loop stays in-process: `phases/P03-fix-loop.md` Goal, "from scratch with no agent framework," and `analysis/CONSTRAINTS.md` item 3. MCP is already the plan for `locate()` and the Playwright spike, not for `edit` / `run_cmd`.
- [Issue 3550](https://github.com/Aider-AI/aider/issues/3550) (closed, 52 comments, 12 reactions). An OpenRouter response raised `OpenrouterException` about `choices`. Not specified. P3-T30 covers malformed tool arguments, not a provider payload missing `choices`.
- [Issue 3005](https://github.com/Aider-AI/aider/issues/3005) (closed, 40 comments, 18 reactions). The DeepSeek API was slow or down. Partially guarded: `PLAN.md` § Risk register item 1 (two hosts, quota ledger) and the stop reason `QuotaExceeded`. A hang that is not a quota refusal has no timeout in P3-T06 (see T1-13).

### OpenHands/software-agent-sdk

- [Issue 1782](https://github.com/OpenHands/software-agent-sdk/issues/1782) (closed, 27 comments). Resuming a conversation wrote a second observation with the same `tool_call_id`, and the provider then rejected every later call. Not specified. P3-T27 replays stored responses in one shot; it does not say a resumed log must have one observation per tool-call id. ADR-008 should, if the tool-call format uses ids.
- [Issue 1063](https://github.com/OpenHands/software-agent-sdk/issues/1063) (closed, 17 comments, 3 reactions). With condensation on, a browsing task entered a loop after feedback. Not specified beyond P3-T12 counting summary tokens. Nothing in `phases/P03-fix-loop.md` § Ablation requires the summary to shrink the window or stops a summary that does not (see T1-15).
- [Issue 581](https://github.com/OpenHands/software-agent-sdk/issues/581) (closed, 6 comments, 3 reactions). The str-replace editor started by walking the filesystem root. Partially guarded later: `PROJECT.md` § P7 lists a host-filesystem escape probe. P3-T05 mounts the worktree and read-only checks; it does not say `read_file` / `edit` reject a path outside the worktree.
- [Pull 5169](https://github.com/OpenHands/software-agent-sdk/pull/5169) (open, 7 comments, 3 reactions). Token-usage buckets can omit cache fields. `PROJECT.md` § Quota ledger says cached tokens are counted apart from fresh tokens. It does not say a missing cache field is zero rather than a crash. That belongs in P3-T08's schema test and ADR-002.
