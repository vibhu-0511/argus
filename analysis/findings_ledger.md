# Findings ledger

Phase 3 synthesis of T1–T6. One issue, one ID. Hours are text-change deltas already stated in the research. No new estimates.

Net hours delta: **0**.

T5's cut sizes are not in that sum. They are alternative, and each cut is inconsistent as published: P5.5 −28 h (T5-14), Firecracker −3 h (T5-15), MRTR −3 h (T5-16), multi-tenancy −6 h (T5-17). Booking them would add the same hours the plan already counts, and would add them together.

Deduped on purpose:

- T3-07 and T5-09 are PLAN-009 only.
- T2-08 and the T6 rows "Playwright bundles MCP" and "Playwright MCP versus the 2026-07-28 spec" are FACT-009. The spike's missing protocol check is EDGE-014.
- T4-07 (token in the agent job) and T4-09 (shell interpolation) stay RISK-003 and RISK-004.

| Category | Count | High | Med | Low |
|---|---|---|---|---|
| RISK | 7 | 5 | 2 | 0 |
| DESIGN | 16 | 1 | 15 | 0 |
| EDGE | 14 | 0 | 13 | 1 |
| FACT | 13 | 1 | 2 | 10 |
| PLAN | 26 | 2 | 16 | 8 |
| CUT | 0 | 0 | 0 | 0 |
| FEAT | 1 | 0 | 0 | 1 |
| **Total** | **77** | **9** | **48** | **20** |

## RISK

### RISK-001
- Category: RISK
- Severity: High
- Claim: A go on Playwright MCP turns on `browser_run_code_unsafe`, which that server's README calls RCE-equivalent, and P1-T05 only blocks container egress. ADR-004 does not allow-list the six repro tools, and the direct-Playwright fallback is not barred from growing a `page.evaluate` tool.
- Argus IDs: P1-T01, P1-T04, P1-T05, ADR-004
- Evidence: [CODE] [DOCS] https://github.com/microsoft/playwright-mcp/blob/0c4107acbecb75472b23c05c0e42471a0011874f/README.md#L1082-L1084 and https://github.com/microsoft/playwright-mcp/blob/0c4107acbecb75472b23c05c0e42471a0011874f/tests/capabilities.spec.ts#L19-L47 (T2-07, T2-04). Licence Apache-2.0.
- Plan today: `phases/P01-repro-agent.md` P1-T05 and P1-T01
- Hours delta: 0
- If accepted: ADR-004's go uses an allow-list of the six repro tools, leaves `browser_run_code_unsafe` off, and does not add `page.evaluate` in P1.

### RISK-002
- Category: RISK
- Severity: High
- Claim: SWE-agent interpolates the GitHub token into the fork remote URL, and a failed push only tells the operator to check permissions. Argus redacts a planted secret from trajectories and traces, and never says the git remote itself must not contain the token.
- Argus IDs: P7-T03, P7-T04, P7-T16, ADR-026
- Evidence: [CODE] https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/run/hooks/open_pr.py#L73-L90 (T4-04). Related idea, no snippet: https://github.com/sorenlouv/backport/pull/165 (Apache-2.0). Licence MIT for the SWE-agent path.
- Plan today: `phases/P07-argus-guard.md` P7-T03
- Hours delta: 0
- If accepted: P7-T03 forbids a token in a remote URL, and P7-T04 states the scopes before the first push.

### RISK-003
- Category: RISK
- Severity: High
- Claim: The OpenHands example puts `GITHUB_TOKEN` in the agent process, with `contents: write`, and tells the model to run `gh pr create`. P8-T04 still allows an Actions-injected token on the agent step, including when the job's permissions are only read.
- Argus IDs: P8-T04, P7-T04, P7-T18, P7-T20, ADR-026, ADR-027
- Evidence: [CODE] [DOCS] https://github.com/OpenHands/software-agent-sdk/blob/46b1fa5cb91ada17e6ec938c7e8624a4fa19fa98/examples/03_github_workflows/03_todo_management/workflow.yml#L42-L45 and the same file at `#L174-L178` (T4-07). Licence MIT.
- Plan today: `phases/P08-argus-app.md` P8-T04
- Hours delta: 0
- If accepted: ADR-026 says the agent step's environment has no `GITHUB_TOKEN`, and names whether the tenant workflow token or the App installation token is the principal that pushes.

### RISK-004
- Category: RISK
- Severity: High
- Claim: The same OpenHands workflow expands untrusted issue text inside a shell heredoc, a `git commit -m` string, and the PR title, so a title containing `$(...)` is command input. P7-T07 covers the model prompt and does not cover the workflow shell.
- Argus IDs: P8-T09, P8-T20, P7-T07, P7-T09
- Evidence: [CODE] https://github.com/OpenHands/software-agent-sdk/blob/46b1fa5cb91ada17e6ec938c7e8624a4fa19fa98/examples/03_github_workflows/03_todo_management/workflow.yml#L204-L210 (T4-09). Licence MIT.
- Plan today: `phases/P08-argus-app.md` P8-T09
- Hours delta: 0
- If accepted: P8-T09 and P8-T20 build the PR through the API with title and body as JSON fields, and a fixture title containing `$(...)` must not be executed.

### RISK-005
- Category: RISK
- Severity: High
- Claim: P1-T07 stops on "success," while the Playwright healer's success is a passing script, including `test.fixme()` or skip, and browser-use lets the model set `success` on the last step. P1-T08 depends on P1-T07, so a script that passes on the buggy tree can ship before the verifier exists.
- Argus IDs: P1-T07, P1-T08, P1-T13, P1-T14
- Evidence: [CODE] [DOCS] https://github.com/microsoft/playwright/blob/f9a841f968dd9a4e315df2ec2930da1952971667/packages/playwright/src/agents/playwright-test-healer.agent.md#L51-L55 and https://github.com/browser-use/browser-use/blob/2cc71890e65056b67fdb29d98bb407749c15bb08/browser_use/agent/service.py#L1571-L1574 (T2-01, T2-02, T2-09). Licences Apache-2.0 and MIT.
- Plan today: `phases/P01-repro-agent.md` P1-T07
- Hours delta: 0
- If accepted: Success is a script that fails on the buggy tree and passes on the golden tree; skip or `test.fixme()` is `error`; the cap reason is `retry-cap` recorded by the loop, and empty model output counts toward that cap.

### RISK-006
- Category: RISK
- Severity: Med
- Claim: Stuck detection is "the same tool call repeated," which does not fire on one hung `vim` or `python`, and P3-T06 names no per-command timeout. SWE-agent treats a blocklist of interactive commands and consecutive command timeouts as their own stop, so a single blocking call can hold the sandbox until an outer cap that is not checked during the call.
- Argus IDs: P3-T06, P3-T32, ADR-008
- Evidence: [CODE] https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/tools/tools.py#L139-L152 (T1-13). Related hang: https://github.com/Aider-AI/aider/issues/3005 (T1 issue list). Licence MIT for the SWE-agent path.
- Plan today: `phases/P03-fix-loop.md` P3-T32 and the stuck break-it
- Hours delta: 0
- If accepted: P3-T06 and P3-T32 name a per-command timeout, a consecutive-timeout stop distinct from `stuck`, and a rejection for interactive commands, with those integers written on the task.

### RISK-007
- Category: RISK
- Severity: Med
- Claim: Find-or-create is specified, but the implementations that miss it open a second PR via a random branch suffix, a `closes #N` commit heuristic, a prompt sentence, or a search that falls through to create on error. A run that looked successful and wrote no patch is also not a named reason to skip the PR.
- Argus IDs: P6-T21, P8-T09, P6-T02, P6-T07, ADR-023
- Evidence: [CODE] https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/run/hooks/open_pr.py#L39-L112 and https://github.com/OpenHands/software-agent-sdk/blob/46b1fa5cb91ada17e6ec938c7e8624a4fa19fa98/examples/03_github_workflows/05_posthog_debugging/posthog_debugging.py#L478-L528 (T4-02, T4-03, T4-08, T4-10). [ISSUE] https://github.com/SWE-agent/SWE-agent/issues/717 (T1 and T4 issue lists). Licence MIT.
- Plan today: `phases/P08-argus-app.md` P8-T09 and `phases/P06-argus-flow.md` P6-T21
- Hours delta: 0
- If accepted: P8-T09 uses one stable branch, one creator that is not the agent, draft-until-QA, no PR when the patch is empty, and a lookup error that leaves the existing PR untouched.

## DESIGN

### DESIGN-001
- Category: DESIGN
- Severity: High
- Claim: Variant E is a different experiment until ADR-011 says so: mini's ACI is one `bash` tool, the scored "patch" is stdout after `COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT`, and the default stops are a $3 `cost_limit`, unlimited steps, and three format errors. A litellm cost of 0 aborts unless `cost_tracking` is `ignore_errors`, and mini's default Docker has no `--network none`.
- Argus IDs: P3-T17, P3-T20, P3-T05, P3-T08, ADR-011, ADR-008
- Evidence: [CODE] https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/environments/local.py#L45-L55 and https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/models/litellm_model.py#L108-L126 and https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/environments/docker.py#L26-L33 (T1-01, T1-02, T1-03, T1-04, T1-07). [ISSUE] https://github.com/SWE-agent/mini-swe-agent/issues/303 and https://github.com/SWE-agent/mini-swe-agent/issues/382 and https://github.com/SWE-agent/mini-swe-agent/issues/773. Licence MIT. Do not add LiteLLM (https://github.com/SWE-agent/SWE-agent/issues/64).
- Plan today: `phases/P03-fix-loop.md` P3-T17 and `PLAN.md` Metrics contract
- Hours delta: 0
- If accepted: P3-T17 sets `cost_limit` 0, `cost_tracking=ignore_errors`, `--network none`, and the interpreter and env var mini actually reads, and ADR-011 states that the scored artifact and the stop reasons differ from Argus.

### DESIGN-002
- Category: DESIGN
- Severity: Med
- Claim: Three edit contracts disagree on a second match: SWE-agent's windowed docstring says first occurrence while `str.replace` replaces every one, OpenHands refuses a non-unique `old_str` and names the lines, and Aider's fuzzy fallback in `replace_most_similar_chunk` is unreachable. P3-T02's `edit` schema does not pick one.
- Argus IDs: P3-T02, P3-T07, ADR-008
- Evidence: [CODE] https://github.com/OpenHands/software-agent-sdk/blob/46b1fa5cb91ada17e6ec938c7e8624a4fa19fa98/openhands-tools/openhands/tools/file_editor/editor.py#L214-L241 and https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/tools/windowed/lib/windowed_file.py#L208-L216 (T1-12). Licences MIT, and Apache-2.0 for the Aider lesson (ideas; do not copy the fuzzy matcher).
- Plan today: `phases/P03-fix-loop.md` P3-T02
- Hours delta: 0
- If accepted: ADR-008 picks exact unique match with the line numbers in the error, and P3-T07 tests that, with no whitespace flex, no fuzzy matcher, and no second whole-file tool.

### DESIGN-003
- Category: DESIGN
- Severity: Med
- Claim: OpenHands nudges once at a threshold, then stops, and the thresholds cover identical pairs, error streaks, monologue, and alternating calls, while Argus's break-it allows either an immediate stop or one nudge and does not set N. Those two policies produce different stuck rates, and P3-T28's fake model only repeats `read_file`.
- Argus IDs: P3-T06, P3-T28, P3-T30, ADR-008
- Evidence: [CODE] https://github.com/OpenHands/software-agent-sdk/blob/46b1fa5cb91ada17e6ec938c7e8624a4fa19fa98/openhands-sdk/openhands/sdk/conversation/stuck_detector.py#L218-L248 (T1-14). Licence MIT.
- Plan today: `phases/P03-fix-loop.md` Break it, item 1
- Hours delta: 0
- If accepted: ADR-008 picks one policy and a numeric N now, and says whether alternating calls and a monologue count, because deciding that after P5's stuck rate is published makes the rate incomparable.

### DESIGN-004
- Category: DESIGN
- Severity: Med
- Claim: SWE-agent's format errors are a closed code set (`missing`, `multiple`, `invalid_json`, and the argument codes) that become `exit_format` after retries, separate from a stuck stop. OpenHands returns a tool error as a normal observation with `is_error`, and its `FailureKind` enum is not a bug-fix taxonomy.
- Argus IDs: P3-T02, P3-T07, P3-T21, P3-T30, ADR-008
- Evidence: [CODE] https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/exceptions.py#L10-L24 and https://github.com/OpenHands/software-agent-sdk/blob/46b1fa5cb91ada17e6ec938c7e8624a4fa19fa98/openhands-sdk/openhands/sdk/tool/schema.py#L365-L380 (T1-08, T1-16). Licence MIT.
- Plan today: `phases/P03-fix-loop.md` P3-T07 and P3-T30
- Hours delta: 0
- If accepted: P3-T07's bad inputs and P3-T21's labels use a closed error-code enum distinct from `stuck`, a tool error is a normal step with a flag, and `FailureKind` is not copied into the failure notes.

### DESIGN-005
- Category: DESIGN
- Severity: Med
- Claim: SWE-agent's failure rollup is exit statuses, and on most of those it still tries to save a worktree diff and may rewrite the status to `submitted`. Argus scores "the agent's final patch" and does not say whether a token-cap or stuck stop still scores that diff, and P3-T21's label list is not written.
- Argus IDs: P3-T18, P3-T21, ADR-008
- Evidence: [CODE] https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/agent/agents.py#L823-L826 (T1-09). Licence MIT.
- Plan today: `phases/P03-fix-loop.md` P3-T21 and `PLAN.md` Metrics contract
- Hours delta: 0
- If accepted: ADR-008 decides now whether a capped run scores the worktree diff, and P3-T21's list includes the P3-T06 stop reasons, because that choice moves the resolve rate.

### DESIGN-006
- Category: DESIGN
- Severity: Med
- Claim: Mini rewrites one JSON document every step and has no replay command, while SWE-agent replay re-executes stored actions in a fresh environment and can drift. Argus's acceptance is byte-for-byte replay from stored model responses, which stays [ME].
- Argus IDs: P3-T08, P3-T17, P3-T27, ADR-001
- Evidence: [CODE] [DOCS] https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/agents/default.py#L159-L190 and https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/run/run_replay.py#L1-L11 (T1-06, T1-11). Licence MIT.
- Plan today: `phases/P03-fix-loop.md` P3-T27
- Hours delta: 0
- If accepted: P3-T17 maps the mini JSON message list into JSONL, and P3-T27 keeps the stored model message and does not replay by shelling the actions again.

### DESIGN-007
- Category: DESIGN
- Severity: Med
- Claim: Mini truncates every long observation to a head plus a tail, SWE-agent's last-N deletion breaks the cached prefix, and OpenHands treats a summary that forgets too little as a failed condensation while keeping the head of the log. Argus's variant A ("no compaction") is not what mini runs, and P3-T12 does not stop a summary that fails to shrink the window.
- Argus IDs: P3-T09, P3-T10, P3-T11, P3-T12, P3-T16, P3-T17, ADR-009, ADR-011
- Evidence: [CODE] https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/config/mini.yaml#L112-L127 and https://github.com/OpenHands/software-agent-sdk/blob/46b1fa5cb91ada17e6ec938c7e8624a4fa19fa98/openhands-sdk/openhands/sdk/context/condenser/llm_summarizing_condenser.py#L54-L76 (T1-05, T1-10, T1-15). [ISSUE] https://github.com/OpenHands/software-agent-sdk/issues/1063. Licence MIT.
- Plan today: `phases/P03-fix-loop.md` P3-T12 and the ablation list
- Hours delta: 0
- If accepted: ADR-009 says the system prompt and the first user message survive, a summary that does not shrink is a stop, last-N elision is not added, and ADR-011 names which mini config is variant E.

### DESIGN-008
- Category: DESIGN
- Severity: Med
- Claim: After PLAN-009 corrects the masked-shift sentence, P4-T02 still has one unnamed threshold that mixes a pixel ratio, a color distance, and a layout change. Backstop hides a fixed-size region without reflow, Argos can ignore up to 20 pixels and then auto-ignore a repeated fingerprint, and reg-suit can log a mismatch and still exit 0.
- Argus IDs: P4-T02, P4-T07, ADR-012
- Evidence: [CODE] [DOCS] https://github.com/garris/BackstopJS/blob/a11d3657788bbffebd7a2b2eb5212006696afbff/core/util/runPlaywright.js#L269-L284 and https://github.com/argos-ci/argos/blob/500420acac590b5ec0d628236e5d8c456f048ec5/apps/backend/src/screenshot-diff/diff/image/index.ts#L17-L51 (T3-06, T3-08, T3-09, T3-11). [ISSUE] https://github.com/garris/BackstopJS/issues/761 is the reason not to retry a mismatch. Licence MIT. Do not take those tools as dependencies.
- Plan today: `phases/P04-verify.md` P4-T02
- Hours delta: 0
- If accepted: The mask keeps layout, the constant is a changed-pixel ratio written next to its unit, a size change fails without scaling, the 4 px shift exceeds the fringe cap, and a repeated fingerprint stays a hard failure.

### DESIGN-009
- Category: DESIGN
- Severity: Med
- Claim: SWE-bench now rejects an empty status map with no sign the suite ran, and still leaves an infra-flagged instance in the unresolved denominator. Argus says resolved-over-attempted with a Wilson interval, and does not say exit 2 or `bench/quarantine/` leave "attempted" or the ablation draw.
- Argus IDs: P0-T15, P0-T18, P0-T24, P0-T27, P0-T29, P5-T04, P5-T16, ADR-003, ADR-017
- Evidence: [CODE] https://github.com/SWE-bench/SWE-bench/blob/02e7a74ffd0b707aab73d203fe87bdc7c76afc8e/swebench/harness/grading.py#L155-L160 and https://github.com/SWE-bench/SWE-bench/blob/02e7a74ffd0b707aab73d203fe87bdc7c76afc8e/swebench/harness/infra_failure.py#L28-L37 (T3-01, T3-02, T3-03, T3-16). Licence MIT.
- Plan today: `PLAN.md` Metrics contract and `phases/P00-argus-bench.md` P0-T24
- Hours delta: 0
- If accepted: ADR-003 excludes exit 2 and quarantined tasks from "attempted," draws the ablation sample after quarantine, and keeps a mutant only on exit 1 then exit 0 with a non-empty check list.

### DESIGN-010
- Category: DESIGN
- Severity: Med
- Claim: FastChat swaps answer order, records a disagreement as `"inconsistent"`, and its published "over 80% agreement" is pairwise percent agreement with ties and `error` rows dropped, on a judge last touched in 2023. Argus can average the two orders into one label before α, which hides the flip the calibration is supposed to measure.
- Argus IDs: P4-T01, P4-T11, P4-T12, P4-T13, P4-T14, P4-T24, P4-T28, ADR-013
- Evidence: [CODE] [DOCS] https://github.com/lm-sys/FastChat/blob/587d5cfa1609a43d192cedb8441cac3c17db105d/fastchat/llm_judge/show_result.py#L64-L66 and https://github.com/lm-sys/FastChat/blob/587d5cfa1609a43d192cedb8441cac3c17db105d/fastchat/llm_judge/README.md#L153-L156 (T3-13, T3-14). Licence Apache-2.0. Ideas only; do not import the judge.
- Plan today: `phases/P04-verify.md` P4-T24 and the P4 done-when α line
- Hours delta: 0
- If accepted: The order-disagreement rate is reported beside α, a disagreeing pair is not averaged into one label, and an unparsed judge string stays in the α denominator as `error`.

### DESIGN-011
- Category: DESIGN
- Severity: Med
- Claim: promptfoo's red-team defaults generate attacks with a paid provider, and its `prompt-injection` strategy is a deprecated alias of static jailbreak templates whose own warning says it does not cover modern injection. Argus's ticket vector does not say the issue title is in the attack, and a write-capable actor is still untrusted after the label check.
- Argus IDs: P7-T07, P7-T08, P7-T09, P8-T08, P8-T24, ADR-024
- Evidence: [DOCS] [CODE] https://github.com/promptfoo/promptfoo/blob/e48ed85e08ff8a1ca74fa7d0e41daf47cf155efb/site/docs/red-team/strategies/jailbreak-templates.md#L7-L13 (T3-15). [CODE] https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/utils/github.py#L99-L107 (T4-05, T4-06). [ISSUE] https://github.com/promptfoo/promptfoo/pull/8964. Licence MIT.
- Plan today: `phases/P07-argus-guard.md` P7-T07
- Hours delta: 0
- If accepted: The committed config is three static cases, one each for ticket title-plus-body, a repo file, and a skill file, graded by deterministic assertions, with no generator and no LLM rubric.

### DESIGN-012
- Category: DESIGN
- Severity: Med
- Claim: DBOS starts one workflow per `SetWorkflowID`, `return-existing` keeps the first call's arguments, and a send without an idempotency key inserts a second message. The plan keys a workflow by ticket id and also stores a delivery id, which can start two workflows, and the poller cannot learn new GitHub state through `return-existing`.
- Argus IDs: P6-T02, P6-T06, P6-T07, P6-T08, P6-T10, P6-T22, ADR-021, ADR-023
- Evidence: [CODE] https://github.com/dbos-inc/dbos-transact-py/blob/718d06613d9b7dc4c935e098e4608b6745267760/dbos/_context.py#L648-L669 and https://github.com/dbos-inc/dbos-transact-py/blob/718d06613d9b7dc4c935e098e4608b6745267760/dbos/_sys_db.py#L3858-L3886 (T4-17). Demo behaviour was read with no quote: https://github.com/dbos-inc/dbos-demo-apps/blob/5568fc9fdb61a91e6f7cb300ef6f1cd254d219a6/python/widget-store/widget_store/main.py#L100-L130. dbos-transact-py is MIT. dbos-demo-apps has no licence file at that SHA; ideas only.
- Plan today: `phases/P06-argus-flow.md` P6-T06 and P6-T22
- Hours delta: 0
- If accepted: Webhook and poller share `SetWorkflowID(ticket_id)`, the handler returns 202 without waiting, the delivery id is only a hint-dedup record, and the QA signal carries an idempotency key.

### DESIGN-013
- Category: DESIGN
- Severity: Med
- Claim: DBOS recovers only pending rows for the same executor id and application version, a recorded exception is re-raised instead of re-run, and the default LISTEN connection plus a 30-second scheduler poll stay up for the life of the process. Risk 3 names Neon CU-hours and Render sleep, and does not name those knobs, so P6-T19 is invalid if the restarted process has a new version or a new executor id.
- Argus IDs: P6-T03, P6-T11, P6-T12, P6-T14, P6-T19, ADR-020, ADR-021, ADR-022. Risk 3 in `PLAN.md`
- Evidence: [CODE] https://github.com/dbos-inc/dbos-transact-py/blob/718d06613d9b7dc4c935e098e4608b6745267760/dbos/_dbos.py#L351-L376 and https://github.com/dbos-inc/dbos-transact-py/blob/718d06613d9b7dc4c935e098e4608b6745267760/dbos/_core.py#L2455-L2518 (T4-15, T4-16). [ISSUE] https://github.com/dbos-inc/dbos-transact-py/issues/147 and https://github.com/dbos-inc/dbos-demo-apps/issues/341. Licence MIT for dbos-transact-py.
- Plan today: `PLAN.md` risk 3 and `phases/P06-argus-flow.md` P6-T14
- Hours delta: 0
- If accepted: P6-T11 chooses `use_listen_notify` before the first migration, pins a stable app version and executor id, sets no conductor key on Render, and P6-T19 asserts a second GitHub call only for the kill that happens before the step result is stored.

### DESIGN-014
- Category: DESIGN
- Severity: Med
- Claim: code-inspector stores one path, prefers the call site with `prop || definition`, appends a tag suffix, and leaves an absolute path when git toplevel lookup fails, while a transform error is swallowed and the Vite plugin also injects a client and a local server. Argus asks `locate()` for two ranked candidates and a call-stack hint, which is the runtime stack ADR-006 says React 19 removed.
- Argus IDs: P2-T02, P2-T03, P2-T05, P2-T08, P2-T15, P2-T16, ADR-006
- Evidence: [CODE] [DOCS] https://github.com/zh-lx/code-inspector/blob/6235e8a97a484237b7308e13d7d700e5e7f3fea4/packages/core/src/server/transform/transform-jsx.ts#L1072-L1074 and https://github.com/zh-lx/code-inspector/blob/6235e8a97a484237b7308e13d7d700e5e7f3fea4/packages/vite/src/index.ts#L113-L115 (T2-12, T2-13, T2-14, T2-15, T2-16). [ISSUE] https://github.com/zh-lx/code-inspector/issues/250 and https://github.com/zh-lx/code-inspector/pull/590. Licence MIT.
- Plan today: `phases/P02-dom2src.md` Done when, and P2-T08
- Hours delta: 0
- If accepted: P2-T02 emits the definition and the JSX call site as repo-relative `file:line:col` with no tag suffix, the plugin is absent from production and registered before JSX, and `locate()` stays the Python tool with no client and no companion server.

### DESIGN-015
- Category: DESIGN
- Severity: Med
- Claim: The default MCP tool list has no `browser_verify_*` until `--caps=testing`, visibility is role plus accessible name, and a stale index can come back as a successful result with no error field. Snapshots are the action surface and have blown the context window, while a per-step screenshot is a second image path the ticket-image ablation does not mention.
- Argus IDs: P1-T01, P1-T04, P1-T06, P1-T07, P1-T10, P1-T14, P1-T15, ADR-004, ADR-005
- Evidence: [CODE] [DOCS] https://github.com/microsoft/playwright-mcp/blob/0c4107acbecb75472b23c05c0e42471a0011874f/README.md#L1604-L1625 and https://github.com/browser-use/browser-use/blob/2cc71890e65056b67fdb29d98bb407749c15bb08/browser_use/tools/service.py#L713-L718 (T2-04, T2-05, T2-06, T2-10, T2-11). [ISSUE] https://github.com/microsoft/playwright-mcp/issues/395. Navigate wait to avoid: https://github.com/browser-use/browser-use/pull/3549. Licences Apache-2.0 and MIT.
- Plan today: `phases/P01-repro-agent.md` P1-T04
- Hours delta: 0
- If accepted: `assert-visible` is role plus accessible name, `stale-target` and `not-unique` are typed errors, the snapshot takes a depth or byte cap, and variant B attaches the ticket image once rather than a new screenshot each revision.

### DESIGN-016
- Category: DESIGN
- Severity: Med
- Claim: The multimodal CLI alias resolves to `SWE-bench/SWE-bench_Multimodal`, the test split leaves `patch` and `image_assets` empty, and the quickstart still names the old Hub org. P5-T19 says at least 10 tasks load and does not pin the split, so a test-split row or a gold patch in the prompt would leak or empty the subset.
- Argus IDs: P5-T19, P5-T20
- Evidence: [CODE] [DOCS] https://github.com/SWE-bench/SWE-bench/blob/02e7a74ffd0b707aab73d203fe87bdc7c76afc8e/docs/guides/datasets.md#L72-L85 and https://github.com/SWE-bench/SWE-bench/blob/02e7a74ffd0b707aab73d203fe87bdc7c76afc8e/swebench/cli/_datasets.py#L5-L20 (T3-04). [ISSUE] https://github.com/SWE-bench/SWE-bench/issues/465. Licence MIT.
- Plan today: `phases/P05-argus-eval.md` P5-T19
- Hours delta: 0
- If accepted: The adapter pins split `dev`, records an exclusion for every test-split row and for a dev row with missing `image_assets` URLs, and keeps the gold patch out of the agent prompt.

## EDGE

### EDGE-001
- Category: EDGE
- Severity: Med
- Claim: A scorer or parser fix has to re-run Playwright unless the raw check log is kept, and a CI compare that logs a mismatch can still exit 0. P4-T23 says the verify workflow is green on stored screenshots and does not say a mismatched fixture fails the job.
- Argus IDs: P0-T15, P5-T04, P4-T23, P5-T16, P5-T17, ADR-017
- Evidence: [DOCS] [CODE] https://github.com/SWE-bench/SWE-bench/blob/02e7a74ffd0b707aab73d203fe87bdc7c76afc8e/docs/reference/cli.md#L53-L64 and https://github.com/reg-viz/reg-suit/blob/5c09c8eb1e356d7e8145e5850e6de17b2b25a5a0/packages/reg-suit-cli/src/cli.ts#L109-L114 (T3-05, T3-12). Licence MIT.
- Plan today: `phases/P00-argus-bench.md` P0-T15 and `phases/P04-verify.md` P4-T23
- Hours delta: 0
- If accepted: `bench score` keeps the unsliced log, and P4-T23 exits non-zero on a committed pair over the named ratio or on a missing or unparsable verdict file.

### EDGE-002
- Category: EDGE
- Severity: Med
- Claim: odiff marks a pixel as anti-aliased only when it has both a darker and a brighter neighbor, and a solid region of identical pixels is not anti-aliased, so ignoring fringe pixels does not cover a screenshot taken before the web font loads. P4-T26 already waits for fonts; it has no second fixture once the fonts are ready.
- Argus IDs: P4-T26, P4-T02, P0-T09
- Evidence: [CODE] [DOCS] https://github.com/dmtrKovalenko/odiff/blob/6dd1e9629810042c03a81fc787f37b245772970a/src/antialiasing.zig#L80-L96 (T3-10). Licence MIT. Do not take odiff as a dependency.
- Plan today: `phases/P04-verify.md` P4-T26
- Hours delta: 0
- If accepted: Keep the font wait, and add a fixture where a fringe under the named cap passes and a different font family still fails.

### EDGE-003
- Category: EDGE
- Severity: Med
- Claim: Playwright's generator runs each step, then writes the script from the log, and a click on snapshot ref `e2` is saved as a role locator. P1-T07 says generate, run, revise, and does not say the saved script uses the logged locator or that a symptom assertion is in the file before the loop can stop.
- Argus IDs: P1-T04, P1-T07, P1-T14
- Evidence: [CODE] [DOCS] https://github.com/microsoft/playwright/blob/f9a841f968dd9a4e315df2ec2930da1952971667/packages/playwright/src/agents/playwright-test-generator.agent.md#L33-L47 and https://github.com/microsoft/playwright-mcp/blob/0c4107acbecb75472b23c05c0e42471a0011874f/tests/click.spec.ts#L39-L48 (T2-03). Licence Apache-2.0.
- Plan today: `phases/P01-repro-agent.md` P1-T07
- Hours delta: 0
- If accepted: The saved script uses the logged role and name, not the ephemeral ref, and it contains a symptom assertion before the loop's stop.

### EDGE-004
- Category: EDGE
- Severity: Med
- Claim: A `browser_take_screenshot` payload labeled `image/jpeg` that did not match the bytes left the caller's next API request as a 400. P1-T06 checks that the ticket image is attached only in image mode, and does not check that the bytes match the media type.
- Argus IDs: P1-T06
- Evidence: [ISSUE] https://github.com/microsoft/playwright-mcp/issues/1211 (closed, 30 comments, 6 reactions; T2 issue list). Licence Apache-2.0.
- Plan today: `phases/P01-repro-agent.md` P1-T06
- Hours delta: 0
- If accepted: A bad image is a typed tool error, and the bytes must match the declared media type, so one bad shot does not burn the next model call.

### EDGE-005
- Category: EDGE
- Severity: Med
- Claim: A shared `mcp-chrome-profile` directory blocks a second browser, including after a crash. P1-T05 checks egress and does not give each run its own user-data directory, so a dead server can wedge the next task.
- Argus IDs: P1-T05, P1-T10
- Evidence: [ISSUE] https://github.com/microsoft/playwright-mcp/issues/769 (closed, 25 comments; T2 issue list). Licence Apache-2.0.
- Plan today: `phases/P01-repro-agent.md` P1-T05
- Hours delta: 0
- If accepted: Each repro run gets its own user-data-dir, and P1-T10's next task still starts after a crashed server.

### EDGE-006
- Category: EDGE
- Severity: Low
- Claim: An exception in client dispatch can exit the MCP server between calls. P1-T15 covers an induced kill during a tool call, and does not cover a page listener that kills the process while the loop is idle.
- Argus IDs: P1-T15
- Evidence: [ISSUE] https://github.com/microsoft/playwright-mcp/issues/1803 (open, 2 comments; T2 issue list). Licence Apache-2.0.
- Plan today: `phases/P01-repro-agent.md` P1-T15
- Hours delta: 0
- If accepted: A server exit between calls is the same `tool-unavailable` stop, inside the existing timeout.

### EDGE-007
- Category: EDGE
- Severity: Med
- Claim: A `FormatError` left the assistant message out of `traj.json`, so the step count was wrong and the model never saw the bad output. P3-T08 does not require a rejected tool call to remain a Trajectory record that contains the raw response.
- Argus IDs: P3-T08, P3-T27, P3-T30
- Evidence: [ISSUE] https://github.com/SWE-agent/mini-swe-agent/issues/737 (closed, 10 comments, 1 reaction; T1 issue list). At the reviewed SHA the model object does persist `extra.response` on `FormatError` (T1-04). Licence MIT.
- Plan today: `phases/P03-fix-loop.md` P3-T08
- Hours delta: 0
- If accepted: P3-T08's schema test requires the raw response on a rejected tool call, and replay can see that step.

### EDGE-008
- Category: EDGE
- Severity: Med
- Claim: Token-usage buckets can omit cache fields, and the quota ledger counts cached tokens apart from fresh tokens. P3-T08 does not say a missing cache field is zero rather than a crash.
- Argus IDs: P3-T08, ADR-002
- Evidence: [ISSUE] https://github.com/OpenHands/software-agent-sdk/pull/5169 (open, 7 comments, 3 reactions; T1 issue list). Licence MIT.
- Plan today: `PROJECT.md` Quota ledger, and `phases/P03-fix-loop.md` P3-T08
- Hours delta: 0
- If accepted: The Trajectory schema treats an omitted cache field as zero, and the ledger test covers that row.

### EDGE-009
- Category: EDGE
- Severity: Med
- Claim: Resuming a conversation wrote a second observation with the same `tool_call_id`, and the provider then rejected every later call. P3-T27 replays stored responses in one shot and does not require one observation per tool-call id.
- Argus IDs: P3-T27, ADR-008
- Evidence: [ISSUE] https://github.com/OpenHands/software-agent-sdk/issues/1782 (closed, 27 comments; T1 issue list). Licence MIT.
- Plan today: `phases/P03-fix-loop.md` P3-T27
- Hours delta: 0
- If accepted: If the tool-call format uses ids, ADR-008 and P3-T27 require one observation per id in a resumed log.

### EDGE-010
- Category: EDGE
- Severity: Med
- Claim: The str-replace editor started by walking the filesystem root. P7-T12 later probes a host-filesystem escape, and P3-T05 does not say `read_file` or `edit` reject a path outside the worktree.
- Argus IDs: P3-T02, P3-T05, P7-T12
- Evidence: [ISSUE] https://github.com/OpenHands/software-agent-sdk/issues/581 (closed, 6 comments, 3 reactions; T1 issue list). Licence MIT.
- Plan today: `phases/P03-fix-loop.md` P3-T05
- Hours delta: 0
- If accepted: P3-T02 returns a typed error for a path outside the worktree, and P7-T12 remains the later sandbox probe.

### EDGE-011
- Category: EDGE
- Severity: Med
- Claim: An OpenRouter response raised `OpenrouterException` about a missing `choices` payload. P3-T30 covers malformed tool arguments and does not cover a provider body with no `choices`.
- Argus IDs: P3-T30, ADR-008
- Evidence: [ISSUE] https://github.com/Aider-AI/aider/issues/3550 (closed, 52 comments, 12 reactions; T1 issue list). Licence Apache-2.0. Ideas only.
- Plan today: `phases/P03-fix-loop.md` P3-T30
- Hours delta: 0
- If accepted: A provider payload missing `choices` is a typed error returned to the loop, and the run does not crash.

### EDGE-012
- Category: EDGE
- Severity: Med
- Claim: Backport defaults that match the plan (comment and abort) sit next to modes that commit conflict markers, take `--strategy-option=theirs`, or `git push --force` the backport branch, and a failed push can continue into PR creation from a stale branch. A second label event posted error comments and tried to create the first PR again.
- Argus IDs: P8-T10, P8-T23, P8-T05, P6-T22, ADR-026
- Evidence: [CODE] https://github.com/korthout/backport-action/blob/08d2ffecdef82bdb06ea268ba07f50381440e4c4/src/backport.ts#L464-L487 and https://github.com/sorenlouv/backport/blob/f9d847e91713a58c6b8e76208241c7575569cd44/src/lib/git/push.ts#L21-L27 (T4-11, T4-12, T4-13, T4-14). [ISSUE] https://github.com/korthout/backport-action/issues/470. [DOCS] https://github.com/korthout/backport-action/blob/08d2ffecdef82bdb06ea268ba07f50381440e4c4/docs/adr/0003-scope-and-safety.md#L13-L16. Licences MIT and Apache-2.0 (sorenlouv: ideas, no snippet).
- Plan today: `phases/P08-argus-app.md` P8-T10 and P8-T23
- Hours delta: 0
- If accepted: P8-T23 fails the test on commit-markers, `theirs`, and force-push of the bot branch, refuses a tenant conflict command and a checkout of the PR head under the installation token, and a second run finds the existing PR or no-ops.

### EDGE-013
- Category: EDGE
- Severity: Med
- Claim: Backport PRs did not trigger CI, because of the `pull_request` token limitation. P8-T20 lints the reusable workflow and does not say the backport head is a branch the tenant workflow is allowed to test.
- Argus IDs: P8-T10, P8-T20, ADR-027
- Evidence: [ISSUE] https://github.com/korthout/backport-action/issues/379 (open, 1 comment; T4 issue list). Licence MIT.
- Plan today: `phases/P08-argus-app.md` P8-T20
- Hours delta: 0
- If accepted: ADR-027 says the backport head is a branch the tenant workflow is allowed to test.

### EDGE-014
- Category: EDGE
- Severity: Med
- Claim: The review pin of `@playwright/mcp` 0.0.83 does not contain `2026-07-28`, depends on a Playwright 1.64 alpha, and the Playwright clone at the review SHA is `1.65.0-next`, while the plan's version row is 1.63.0. P1-T01 writes a go/no-go with exact versions and does not require the `initialize` protocol version from the spike process.
- Argus IDs: P1-T00, P1-T01, P1-T03, P2-T00, ADR-004
- Evidence: [CODE] https://github.com/microsoft/playwright-mcp/blob/0c4107acbecb75472b23c05c0e42471a0011874f/package.json#L2-L44 and https://github.com/microsoft/playwright/blob/f9a841f968dd9a4e315df2ec2930da1952971667/package.json#L4 (T2-08). The official-page gap is FACT-009, not a second fact. Licence Apache-2.0. Protocol the server speaks: not verified in T2.
- Plan today: `phases/P01-repro-agent.md` P1-T01
- Hours delta: 0
- If accepted: P1-T01 records the `initialize` protocol version and the tool list from the spike process, and schemas are not copied from the 1.65-next or 1.64-alpha tree onto the pinned row.

## FACT

Changed rows below are T6 `changed? yes`. Unverified rows are FACT only where the plan states a figure the fetched page does not support. The current value stays the research file's words. `changed? no` rows are not findings.

### FACT-001
- Category: FACT
- Severity: Low
- Claim: The plan pins React 19.2.7. The npm latest page on 2026-10-28 reported 19.3.1.
- Argus IDs: P2 version pin, ADR-006
- Evidence: [DOCS] https://registry.npmjs.org/react/latest (T6 row React, changed? yes, checked 2026-10-28).
- Plan today: `PLAN.md` versions, quoted by T6
- Hours delta: 0
- If accepted: The version row becomes 19.3.1, and the React 19 source-mapping note is re-checked rather than assumed from 19.2.7.

### FACT-002
- Category: FACT
- Severity: Low
- Claim: The plan pins Vite 8.3. The npm latest page on 2026-10-28 reported 8.3.5.
- Argus IDs: P2 version pin
- Evidence: [DOCS] https://registry.npmjs.org/vite/latest (T6 row Vite, changed? yes, checked 2026-10-28).
- Plan today: `PLAN.md` versions, quoted by T6
- Hours delta: 0
- If accepted: The version row becomes 8.3.5.

### FACT-003
- Category: FACT
- Severity: Med
- Claim: The plan pins Playwright 1.63.0. The npm latest page on 2026-10-28 reported 1.64.1, which is the pin P1-T00 is supposed to re-check before schemas are copied.
- Argus IDs: P1-T00, P1-T01, ADR-004
- Evidence: [DOCS] https://registry.npmjs.org/playwright/latest (T6 row Playwright, changed? yes, checked 2026-10-28).
- Plan today: `PLAN.md` versions, quoted by T6
- Hours delta: 0
- If accepted: The version row becomes 1.64.1, and P1-T00 is the task that confirms it against the spike.

### FACT-004
- Category: FACT
- Severity: Low
- Claim: The plan pins the MCP Python SDK at v2.2.0. The PyPI JSON on 2026-10-28 reported 2.3.0, still MIT, summary "Model Context Protocol SDK."
- Argus IDs: P1-T01, P2 MCP client
- Evidence: [DOCS] https://pypi.org/pypi/mcp/json (T6 row MCP Python SDK, changed? yes, checked 2026-10-28).
- Plan today: `PLAN.md` versions, quoted by T6
- Hours delta: 0
- If accepted: The version row becomes 2.3.0.

### FACT-005
- Category: FACT
- Severity: High
- Claim: The plan calls Groq a free tier at 1,000 requests/day and 200k tokens/day per model for gpt-oss-20b and Qwen3.6-27B, with cached tokens excluded. The rate-limit page does not say "free tier"; it says Developer-plan base limits at organization level, lists `openai/gpt-oss-20b` and `qwen/qwen3.8-27b` at RPM 30, RPD 1K, TPM 8K, and TPD 200K, says cached tokens do not count, and does not state Qwen3.6-27B.
- Argus IDs: P0-T06, the cheap-tier row, ADR-002. `PROJECT.md` Models
- Evidence: [DOCS] https://console.groq.com/docs/rate-limits (T6 row Groq, changed? yes, checked 2026-10-28). Current wording above is copied from that row.
- Plan today: `PROJECT.md` Models
- Hours delta: 0
- If accepted: P0-T06's `docs/quotas.md` replaces the model id and the caps with the page's words, including TPM 8K and the absence of "free tier" and of Qwen3.6-27B, and no other number is filled in.

### FACT-006
- Category: FACT
- Severity: Med
- Claim: The plan says Neon free compute is 100 CU-hours per month. The pricing page says 100 CU-hours/project, and "per month" is not stated.
- Argus IDs: Risk 3, P6-T14, ADR-022
- Evidence: [DOCS] https://neon.com/pricing (T6 row Neon free compute, changed? yes, checked 2026-10-28).
- Plan today: `PROJECT.md` Infrastructure, quoted by T6 from `PLAN.md`
- Hours delta: 0
- If accepted: The risk-3 sentence uses "100 CU-hours/project" and does not say "per month" until a page states the period.

### FACT-007
- Category: FACT
- Severity: Low
- Claim: The plan says a Render cold start is 30 to 60 seconds. The free-tier page says the process takes about one minute, and "30 to 60" is not stated.
- Argus IDs: P6 webhook timing, risk 3
- Evidence: [DOCS] https://render.com/docs/free (T6 row Render cold start, changed? yes, checked 2026-10-28).
- Plan today: `PLAN.md` infrastructure notes, quoted by T6
- Hours delta: 0
- If accepted: The cold-start sentence says "about one minute," and does not keep "30 to 60."

### FACT-008
- Category: FACT
- Severity: Low
- Claim: The plan says Vite is Rolldown-based. The npm latest document does not state that. Its description is "Native-ESM powered web dev build tool."
- Argus IDs: P2 version pin
- Evidence: [DOCS] https://registry.npmjs.org/vite/latest (T6 row Vite, Rolldown-based, changed? unverified, checked 2026-10-28). Current value stays "not stated."
- Plan today: `PLAN.md` versions, quoted by T6
- Hours delta: 0
- If accepted: The version line does not say Rolldown-based until a fetched page states it.

### FACT-009
- Category: FACT
- Severity: Low
- Claim: The plan says Playwright 1.63.0 bundles MCP, and that Playwright MCP has no confirmed 2026-07-28 support. The npm latest document does not state "bundles MCP," and the spec changelog does not say whether `@playwright/mcp` or the MCP Python SDK implement the stateless core, MRTR, or the tasks extension. Current value stays "not stated."
- Argus IDs: P1-T00, P1-T01, P2-T00, ADR-004, risk 4
- Evidence: [DOCS] https://registry.npmjs.org/playwright/latest and https://modelcontextprotocol.io/specification/2026-07-28/changelog (T6 rows "Playwright bundles MCP" and "Playwright MCP and MCP Python SDK versus that spec," both changed? unverified, checked 2026-10-28). The pin gap is T2-08, and the spike check is EDGE-014, not a second fact. `@playwright/mcp` 0.0.83 itself is changed? no and is not a finding.
- Plan today: `PLAN.md` versions and risk 4
- Hours delta: 0
- If accepted: The version table keeps both claims as not stated, and does not treat the 2026-10-01 row as evidence the server speaks that spec.

### FACT-010
- Category: FACT
- Severity: Low
- Claim: The plan says the OTel GenAI semantic conventions are in development, have no stable release, and moved to a dedicated repo in June 2026. The README exists and says the repo extends the conventions, the schema URL is "TODO," and development status, a stable release, and June 2026 are not stated.
- Argus IDs: P5-T06, P5-T08, ADR-015
- Evidence: [DOCS] https://raw.githubusercontent.com/open-telemetry/semantic-conventions-genai/main/README.md (T6 row OTel GenAI semconv, changed? unverified, checked 2026-10-28). Current value for those three clauses stays "not stated."
- Plan today: `PLAN.md` versions, quoted by T6
- Hours delta: 0
- If accepted: The semconv sentence keeps development status, the stable-release claim, and the June 2026 date as not stated.

### FACT-011
- Category: FACT
- Severity: Low
- Claim: The plan says the fixer is Devstral 2 or Devstral Small 2, Apache-2.0 for Small, and that Mistral reports 68–72% on SWE-bench Verified. The pricing page does not state those names, that licence, or that score. Current value stays "not stated."
- Argus IDs: fixer row in `PROJECT.md` Models, ADR-011
- Evidence: [DOCS] https://mistral.ai/pricing (T6 row Devstral 2, changed? unverified, checked 2026-10-28). The separate "Mistral no longer publishes its free-tier numbers" row is changed? no and is not a finding.
- Plan today: `PROJECT.md` Models, quoted by T6 from `PLAN.md`
- Hours delta: 0
- If accepted: The fixer row does not cite the pricing page for the model name, the Apache-2.0 claim, or 68–72%, and no replacement number is written here.

### FACT-012
- Category: FACT
- Severity: Low
- Claim: The plan says Langfuse Cloud Hobby is an MIT-licensed product. The pricing page says Langfuse is open source and can be self-hosted for free, and it does not name MIT. Current value stays "not stated."
- Argus IDs: ADR-015, `PROJECT.md` Infrastructure
- Evidence: [DOCS] https://langfuse.com/pricing (T6 row Langfuse MIT licence, changed? unverified, checked 2026-10-28). The 50k-units and Hobby-free row is changed? no and is not a finding.
- Plan today: `PROJECT.md` Infrastructure, quoted by T6
- Hours delta: 0
- If accepted: ADR-015 does not cite MIT from the pricing page.

### FACT-013
- Category: FACT
- Severity: Low
- Claim: The plan says GitHub-hosted Linux runners have exposed `/dev/kvm` since October 2025. The Actions billing page does not state that. Current value stays "not stated."
- Argus IDs: P7-T11, ADR-025
- Evidence: [DOCS] https://docs.github.com/en/billing/managing-billing-for-github-actions/about-billing-for-github-actions (T6 row GitHub-hosted Linux `/dev/kvm`, changed? unverified, checked 2026-10-28).
- Plan today: `PLAN.md` versions, quoted by T6
- Hours delta: 0
- If accepted: The Firecracker-on-Actions sentence does not treat October 2025 or `/dev/kvm` as fetched from that page.

## PLAN

Every T5-01 through T5-26 is exactly one PLAN id. Severities are T5's.

### PLAN-001
- Category: PLAN
- Severity: Low
- Claim: The plan treats 28 weeks at 20 h/week as 556 h. T5 computes 28×20 = 560, and the non-buffer weeks through week 30 sum to 561 h because week 30 holds 5 h of P9 on top of the 556 core hours. No task is missing from the 556.
- Argus IDs: `PROJECT.md` Phases, `PLAN.md` Phase map, `analysis/CONSTRAINTS.md` item 2
- Evidence: [CODE] T5-01, from the phase tables and `TASKS.md` week sums in `analysis/research/T5-plan-critic.md`.
- Plan today: `PROJECT.md` section Phases
- Hours delta: 0
- If accepted: Correct the weeks sentence so it no longer equates 28×20 with 556.

### PLAN-002
- Category: PLAN
- Severity: Low
- Claim: Week headers match their checkbox sums, and twelve work weeks are not 20 h. Overs sit inside the +3 h allowance already written in `PLAN.md`; unders (19, 18, and week 32 at 16) are not explained by the "20 hour bins" sentence.
- Argus IDs: `PROJECT.md` Week by week, `PLAN.md` Week-by-week timeline, `TASKS.md` week headers
- Evidence: [CODE] T5-02.
- Plan today: `PROJECT.md` Week by week
- Hours delta: 0
- If accepted: The week intro says which weeks are under 20, and the 556 h and 596 h totals stay as they are.

### PLAN-003
- Category: PLAN
- Severity: Low
- Claim: ADR-004 is written in week 5 (P1-T02, depending only on P1-T01). P2-T00 in week 6 says to note a missing 2026-07-28 support for that ADR, and no later task revises `docs/adr`.
- Argus IDs: P1-T02, P2-T00, risk 4, ADR-004
- Evidence: [CODE] T5-03. The unverified spec claim itself is FACT-009.
- Plan today: `PLAN.md` Risk register row 4 and `phases/P02-dom2src.md` P2-T00
- Hours delta: 0
- If accepted: Name the task that amends ADR-004 after P2-T00, or move the spec note onto P1-T02.

### PLAN-004
- Category: PLAN
- Severity: Med
- Claim: P6's phase file says base weeks W20–23. The shift that fits the other "base plan" lines maps that onto calendar weeks 21–24, and week 21 is already full of P5.5. The 52 h actually sit in `TASKS.md` weeks 22–24.
- Argus IDs: `phases/P06-argus-flow.md` budget line, `PROJECT.md` P6 narrative, `PLAN.md` week table
- Evidence: [CODE] T5-04.
- Plan today: `phases/P06-argus-flow.md` budget line
- Hours delta: 0
- If accepted: The P6 weeks line says calendar weeks 22–24, matching `PROJECT.md` and `PLAN.md`.

### PLAN-005
- Category: PLAN
- Severity: Low
- Claim: P9's phase line says "+2 weeks after P8." Week 30 already contains P9-T00, P9-T01, and P9-T02 (5 h), before weeks 31 (19 h) and 32 (16 h).
- Argus IDs: `phases/P09-backend-lane.md` budget line, `PROJECT.md` week 30
- Evidence: [CODE] T5-05.
- Plan today: `phases/P09-backend-lane.md` budget line
- Hours delta: 0
- If accepted: The P9 weeks line names the week-30 tail. 5+19+16 stays 40 h.

### PLAN-006
- Category: PLAN
- Severity: High
- Claim: P7-T04 in week 24 requires a refused push to a protected branch and a refused call on an uninstalled repo, and its only dependency is P7-T02. The App manifest (P8-T02, week 27) and the token mint (P8-T03, week 28) are downstream of P7-T04, so the checklist forbids creating the App first.
- Argus IDs: P7-T04, P7 done-when, P8-T02, P8-T03
- Evidence: [CODE] T5-06.
- Plan today: `phases/P07-argus-guard.md` P7-T04 and `phases/P08-argus-app.md` P8-T02
- Hours delta: 0
- If accepted: Retarget the token tests so they run after a manifest exists, or narrow P7-T04 so week 24 does not require an App the checklist has not created.

### PLAN-007
- Category: PLAN
- Severity: Med
- Claim: The phase graph draws a dashed P6-to-P9 edge, and P9's goal says the lane reuses the P3-to-P6 parts. No P9 task's dependency or acceptance names `flow`, DBOS, the webhook, the poller, or the control plane.
- Argus IDs: `PLAN.md` Phase dependency graph, `phases/P09-backend-lane.md` Goal
- Evidence: [CODE] T5-07.
- Plan today: `PLAN.md` Phase dependency graph
- Hours delta: 0
- If accepted: Remove the dashed edge, or leave the lane as a local loop; adding a `flow` task is unestimated and needs a named cut before acceptance.

### PLAN-008
- Category: PLAN
- Severity: Med
- Claim: The graph draws solid arrows from P4 and P5 into P6 and no arrow from P5.5. The only predecessor id on a P6 task is P5.5-T17, on P6-T00, and no P6 task lists a P4 or P5 id.
- Argus IDs: `PLAN.md` Phase dependency graph, P6-T00, P6-T04, P6-T25
- Evidence: [CODE] T5-08. The cut that deletes P5.5-T17 is PLAN-014.
- Plan today: `PLAN.md` Phase dependency graph
- Hours delta: 0
- If accepted: Draw P5.5-to-P6, and drop the P4 and P5 arrows unless a P6 task actually lists those ids.

### PLAN-009
- Category: PLAN
- Severity: Med
- Claim: P4-T02 says the pixel check passes on a clean tree and fails on a 4 px shift in a masked-out-of-scope area. A mask that ignores that area passes, so the sentence requires both outcomes. T3-07 is this same defect.
- Argus IDs: P4-T02
- Evidence: [CODE] T5-09, the acceptance sentence in `phases/P04-verify.md`. [DOCS] https://github.com/garris/BackstopJS/blob/a11d3657788bbffebd7a2b2eb5212006696afbff/README.md#L462-L470 (T3-07). Licence MIT.
- Plan today: `phases/P04-verify.md` P4-T02
- Hours delta: 0
- If accepted: The check passes when the only difference is inside the mask, and fails when a 4 px shift is outside the mask.

### PLAN-010
- Category: PLAN
- Severity: Low
- Claim: P0-T12 requires every later seeded task to reference an archetype. Those tasks are created by P0-T13, whose own acceptance checks 10 per tier and does not mention an archetype.
- Argus IDs: P0-T12, P0-T13
- Evidence: [CODE] T5-10.
- Plan today: `phases/P00-argus-bench.md` P0-T12
- Hours delta: 0
- If accepted: Move the "references one archetype" check onto P0-T13, and leave P0-T12 as the document.

### PLAN-011
- Category: PLAN
- Severity: Med
- Claim: The intent judge and the embeddings run on one laptop CPU, a 13th-gen i7-13620H with 16 GB and no discrete GPU. The risk register's five rows do not list that machine, and the calibration that must not be cut has no second computer.
- Argus IDs: P4-T13, P4-T14, P2-T10, `PLAN.md` Risk register
- Evidence: [CODE] T5-11.
- Plan today: `PROJECT.md` Constraints and Models; `PLAN.md` Risk register
- Hours delta: 0
- If accepted: Add the single CPU as a risk-register row pointing at P4-T13 and P2-T10.

### PLAN-012
- Category: PLAN
- Severity: Med
- Claim: From P6 on, the agent job runs on GitHub Actions, and P8 keeps it there as the tenant's reusable workflow. Risk row 1's disappeared-tier example is GitHub Models, not Actions minutes or Pages, and no task names a second execution plane.
- Argus IDs: `PROJECT.md` Infrastructure, `PLAN.md` risk row 1, P8-T04
- Evidence: [CODE] T5-12.
- Plan today: `PLAN.md` Risk register row 1
- Hours delta: 0
- If accepted: The risk register names Actions minutes and public-repo policy as a single execution plane.

### PLAN-013
- Category: PLAN
- Severity: Low
- Claim: Langfuse Cloud Hobby at 50k units/month is the default trace viewer, and Phoenix is the scheduled swap (P5-T09, ADR-015). The 50k cap is in the free-tier collisions list and is not a risk-register row, so a full quota can still drop the traces the dashboard links.
- Argus IDs: P5-T09, P5-T23, P5-T25, ADR-015, `PLAN.md` Risk register
- Evidence: [CODE] T5-13.
- Plan today: `PROJECT.md` Infrastructure
- Hours delta: 0
- If accepted: Add a risk-register row for the 50k cap that points at the existing Phoenix swap.

### PLAN-014
- Category: PLAN
- Severity: High
- Claim: Cut 3 removes P5.5 (18 tasks, 28 h; core remainder 528 h and 249 tasks) and leaves P6-T00 depending on P5.5-T17 and P7-T07 depending on P5.5-T10. The graph does not draw P5.5-to-P6 either, so the checklist and the graph disagree on whether the kept core needs the phase the cut deletes.
- Argus IDs: `PLAN.md` Cut list item 3, P6-T00, P7-T07, P5.5-T10, P5.5-T17
- Evidence: [CODE] T5-14.
- Plan today: `PLAN.md` Cut list
- Hours delta: 0
- If accepted: Retarget P6-T00 and P7-T07 before the cut is taken; the −28 h stays unbooked here because the cut is not executable as published.

### PLAN-015
- Category: PLAN
- Severity: Med
- Claim: Cut 4 removes the Firecracker run, which T5 identifies as P7-T11 (3 h; core remainder 553 h), and tells ADR-025 to leave row C empty. P7-T13 still depends on P7-T11 and requires rows A, B, and C from real runs.
- Argus IDs: `PLAN.md` Cut list item 4, P7-T11, P7-T13, P7-T15, ADR-025
- Evidence: [CODE] T5-15.
- Plan today: `PLAN.md` Cut list and `phases/P07-argus-guard.md` P7-T13
- Hours delta: 0
- If accepted: P7-T13's acceptance allows an empty row C when the cut is taken; the −3 h stays unbooked here.

### PLAN-016
- Category: PLAN
- Severity: Med
- Claim: Cut 5 removes MRTR elicitation, which T5 identifies as P6-T09 (3 h; core remainder 553 h), and keeps the comment fallback P6-T10. P6-T18 (ADR-023) still depends on P6-T09.
- Argus IDs: `PLAN.md` Cut list item 5, P6-T09, P6-T10, P6-T18, ADR-023
- Evidence: [CODE] T5-16.
- Plan today: `PLAN.md` Cut list and `phases/P06-argus-flow.md` P6-T18
- Hours delta: 0
- If accepted: P6-T18 depends only on P6-T10 when the cut is taken; the −3 h stays unbooked here.

### PLAN-017
- Category: PLAN
- Severity: Med
- Claim: Cut 2 says "P8 multi-tenancy, down to a single-tenant App" and names no task id. The three titled second-tenant tasks are P8-T07 (3 h), P8-T14 (1 h), and P8-T21 (2 h), 6 h, and P8-T20 still depends on P8-T07 and still says its tests cover budgets.
- Argus IDs: `PLAN.md` Cut list item 2, P8-T07, P8-T14, P8-T20, P8-T21, ADR-028
- Evidence: [CODE] T5-17.
- Plan today: `PLAN.md` Cut list
- Hours delta: 0
- If accepted: Name those three ids on the cut, and drop P8-T07 from P8-T20's dependency and from its budget assertion; the −6 h stays unbooked here.

### PLAN-018
- Category: PLAN
- Severity: Med
- Claim: Risk 1's mitigation is at least two hosts per role, plus local Ollama for the judge and embeddings. The fixer has one host (Mistral) and the cheap tier has one host (Groq); no task adds a second host for either role.
- Argus IDs: `PLAN.md` risk row 1, P0-T05, P5-T12, P4-T15
- Evidence: [CODE] T5-18.
- Plan today: `PLAN.md` Risk register row 1 and `PROJECT.md` Models
- Hours delta: 0. unestimated; needs a named cut before acceptance
- If accepted: Narrow the risk sentence to the roles that have a second host, or name the second fixer and cheap-tier hosts on an existing task only after a named cut.

### PLAN-019
- Category: PLAN
- Severity: Med
- Claim: If the Playwright MCP spike is no-go, the done-when and risk 4 say direct Playwright is wired in as a tool. P1-T02 is a 1 h ADR, and no task implements that tool.
- Argus IDs: P1-T01, P1-T02, P1-T04, risk 4, ADR-004
- Evidence: [CODE] T5-19.
- Plan today: `phases/P01-repro-agent.md` Done when, and `PLAN.md` risk row 4
- Hours delta: 0. unestimated; needs a named cut before acceptance
- If accepted: Narrow risk 4 so the ADR is the mitigation, or add the direct-Playwright build to an existing task only after a named cut.

### PLAN-020
- Category: PLAN
- Severity: Med
- Claim: Every phase ablation table has a $-equivalent column, defined as tokens times list prices from `prices.json`. P5-T11 creates that file in week 19, and P0-T29 fills the P0 table in week 4. No task between them creates the file.
- Argus IDs: P0-T29, P5-T11, `PROJECT.md` Metrics contract
- Evidence: [CODE] T5-20.
- Plan today: `PROJECT.md` Metrics contract and `phases/P00-argus-bench.md` Done when
- Hours delta: 0
- If accepted: P0 through P4 leave the $-equivalent cell as "—" until P5-T11, and "filled in" does not cover that column.

### PLAN-021
- Category: PLAN
- Severity: Med
- Claim: `PROJECT.md` says every phase reports five numbers, and the fifth is quota share per bug. `PLAN.md`'s learning rules list four and omit it. P5-T04's results JSON does not name quota share; P5-T14 reports it for the routing ablation only.
- Argus IDs: P5-T04, P5-T14, P0-T07, `PROJECT.md` Metrics contract, `PLAN.md` Learning rules
- Evidence: [CODE] T5-21.
- Plan today: `PROJECT.md` Metrics contract
- Hours delta: 0
- If accepted: Either the contract drops quota share, or P5-T04's JSON includes it and earlier phases say the cell is empty until the ledger can divide by the cap.

### PLAN-022
- Category: PLAN
- Severity: Low
- Claim: P9's deploy checkpoint says the lane's results appear as a second series on the GitHub Pages dashboard, and no P9 task mentions the dashboard. The P0 package table says `argus-core` holds OTel helpers, and the OTel task is P5-T06.
- Argus IDs: `phases/P09-backend-lane.md` Deploy checkpoint, P5-T21, P5-T06, `PROJECT.md` Monorepo, `repo-structure.md`
- Evidence: [CODE] T5-22.
- Plan today: `phases/P09-backend-lane.md` Deploy checkpoint and `PROJECT.md` Monorepo
- Hours delta: 0
- If accepted: Remove the second-series sentence and the P0 "OTel helpers" placement, and leave both deliverables on the P5 tasks that already schedule them.

### PLAN-023
- Category: PLAN
- Severity: Med
- Claim: Both HTML files make `locate` its own state in the ticket machine. P6-T04 dispatches repro, fix, and verify, and no P6 acceptance names a locate state. `awaiting-qa` and `done` are in the P6 tasks and on the production rail, and they are absent from the architecture state card.
- Argus IDs: P6-T03, P6-T04, P6-T08, P3-T16, architecture card `o-sm`, production rail
- Evidence: [CODE] T5-23.
- Plan today: `architecture.html` card `o-sm` and `production.html` rail, against `phases/P06-argus-flow.md` P6-T04
- Hours delta: 0
- If accepted: Align both HTML files with the P6 state list; adding a locate workflow state beyond the existing P2 tool is unestimated and needs a named cut before acceptance.

### PLAN-024
- Category: PLAN
- Severity: Med
- Claim: The architecture card assigns opening the PR to P8. The production step assigns it to the P6 control plane, and also attaches `142-fix.html`, which no task's acceptance mentions. P6-T21 and P8-T09 both schedule PR work.
- Argus IDs: P6-T21, P8-T09, architecture card `a-pr`, production step "Open one pull request"
- Evidence: [CODE] T5-24.
- Plan today: `architecture.html` card `a-pr` and `production.html` "Open one pull request"
- Hours delta: 0
- If accepted: Name one opener in both HTML files, and remove the `142-fix.html` attachment until a task names that file.

### PLAN-025
- Category: PLAN
- Severity: Med
- Claim: Best-of-k sits before the checks in the mermaid and the architecture wires, inside the selector in P4-T19, and the production page calls it a cost knob in front of the gate. A hard-gate judge at α 0.80 can reject a patch the checks passed, which is a different rule from "the judge never overrides them."
- Argus IDs: P4-T06, P4-T19, P4-T20, ADR-012, ADR-013, architecture card `a-ver`, production verify step
- Evidence: [CODE] T5-25.
- Plan today: `PROJECT.md` P4, `PLAN.md` mermaid, `phases/P04-verify.md` P4-T19
- Hours delta: 0
- If accepted: ADR-012 and ADR-013 pick one order and say whether the judge can reject a clean check run, and P4-T19 and both HTML files use that order.

### PLAN-026
- Category: PLAN
- Severity: Low
- Claim: P4-T05 and the architecture console card include new errors and warnings, and P3-T14 and architecture card `g4` include bench checks. The production verify step says new console errors only, and the production fix step's gate list stops at unit tests.
- Argus IDs: P4-T05, P3-T14, architecture cards `v-con` and `g4`, production verify and fix steps
- Evidence: [CODE] T5-26.
- Plan today: `production.html` verify step and fix step
- Hours delta: 0
- If accepted: The production page lists warnings and bench checks with the phase tasks.

## CUT

None. Competitor evidence that says "do not add" (LiteLLM, a daily live agent run, an assignee skip, a plugin host, auto-ignore, a per-edit confirm inside P3) refers to work the plan does not schedule. T5's cut-list defects are PLAN-014 through PLAN-017, not cuts. A cut needs a negative or zero delta against hours the plan already assigned, and none of the researched trees names such a drop.

## FEAT

### FEAT-001
- Category: FEAT
- Severity: Low
- Claim: Aider's open request is that each atomic edit be shown and applied only after the user approves. Argus puts the human wait in `awaiting-qa` after the pull request, not on every edit, and a per-edit confirm in P3 would be new scope.
- Argus IDs: P6 `awaiting-qa` (P6-T08, P6-T09, P6-T10). Not specified in P3.
- Evidence: [ISSUE] https://github.com/Aider-AI/aider/issues/649 (open, 39 comments, 41 reactions; T1 issue list). Licence Apache-2.0. Ideas only.
- Plan today: not specified
- Hours delta: 0. unestimated; needs a named cut before acceptance
- If accepted: Leave the human wait on `awaiting-qa` unless a named cut pays for a per-edit confirm.

## Top 10 by impact

1. RISK-004, High, untrusted issue text is expanded in the workflow shell, so a title containing `$(...)` runs as a command. Hours delta 0.
2. RISK-001, High, a Playwright MCP go turns on `browser_run_code_unsafe`, which the README calls RCE-equivalent, and egress control does not allow-list tools. Hours delta 0.
3. RISK-003, High, the agent step still receives Actions-injected `GITHUB_TOKEN`, and the example tells the model to use it. Hours delta 0.
4. RISK-002, High, a git remote can contain the token, and the secret test only checks trajectories and traces. Hours delta 0.
5. RISK-005, High, P1-T07 can treat a passing script, including skip or `test.fixme()`, as success before the verifier exists. Hours delta 0.
6. DESIGN-001, High, variant E scores a magic-echo stdout under mini's $3 stop and default networked Docker, so the headline comparison is a different run. Hours delta 0.
7. PLAN-006, High, the App-token tests in week 24 require an App the checklist does not create until weeks 27–28. Hours delta 0.
8. PLAN-014, High, cutting P5.5 (28 h) leaves P6-T00 and P7-T07 depending on removed tasks. Hours delta 0.
9. FACT-005, High, the Groq row names Qwen3.6-27B and a "free tier," and the rate-limit page states `qwen/qwen3.8-27b`, Developer-plan org limits, and TPM 8K. Hours delta 0.
10. PLAN-025, Med, best-of-k and the judge are ordered three ways, including a hard gate that can reject a patch the checks passed. Hours delta 0.
