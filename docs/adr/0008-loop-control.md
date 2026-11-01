# ADR-008: Loop control, stop conditions and tool-call format

Status: accepted (P3-T22).

## Context

The fix loop has to say why a run ended, in a code the trajectory schema already allows. A later scorer has to be able to grade the worktree without changing that code. The baseline resolve rate is not in this decision. That run has not been made, because the fixer host has no key.

## Decision

The model reply this loop stores is a JSON object, `{"tool": "<name>", "arguments": { ... }}`. `arguments` is an object. When a provider message includes `tool_calls`, the loop reads the first call's name and JSON arguments, and replay keeps one observation per id. The stored content is not rewritten into the other shape.

`edit` replaces one exact match. Whitespace is part of the match. A second match is `not-unique` and the message names the file and the line numbers, as in `a.txt matches lines 1, 3`. There is no whitespace flex, no fuzzy match, and no whole-file write tool.

`run_fix` records one stop reason and does not change it afterward. `REPEAT` is 3. That count is a planning choice, not a measurement. A cap of zero is rejected. It does not mean "disabled".

| Code | When the loop records it |
|---|---|
| `submit` | The `submit` tool succeeds and no gate failed |
| `step-cap` | The step cap is reached |
| `token-cap` | Cumulative tokens in plus tokens out reach the token cap, before the tool runs |
| `QuotaExceeded` | The ledger refuses the call. The model is not called |
| `stuck` | The last 3 tool calls are the same name and the same arguments |
| `consecutive-timeout` | 3 command timeouts in a row. The same command still uses this code, not `stuck` |
| `retry-cap` | 3 malformed calls in a row. Checked before `stuck`, so three identical bad edits use this code |
| `summary` | The summary is not shorter than the turns it replaced |
| `verify-reject` | The verifier rejected the submitted patch, the loop returned that reason once, and the next submit was rejected too. Added in P4. `VERIFY_RETRIES` in `loop.py` is 1 |

`tool-unavailable` stays on the schema enum because the repro agent records it. This loop does not.

An alternating pair of calls is not `stuck`. A reply that is not a tool call counts toward `retry-cap`, not `stuck`.

A `token-cap` or `stuck` stop still scores the worktree diff. The verdict is a separate field. The stop reason is not rewritten to `submit` or to the verdict. This scoring rule is a planning choice, not a measured result. The same is true of the other stops: the diff is scored, and the recorded reason stays.

## Alternatives

- Treat three identical malformed edits as `stuck`. The model is then repeating a call the schema already rejected, and the count of bad arguments would disappear into the stuck count.
- Treat three identical timeouts as `stuck`. A timeout is the command, not the model choosing the same call again.
- Rewrite `token-cap` and `stuck` to `submit` once the diff is scored. The trajectory would no longer say why the run ended.
- Disable a cap by setting it to 0. A caller who forgets the cap would run without one.

## Consequences

`REPEAT` in `packages/fix-loop/src/fix_loop/loop.py` is the count for `stuck`, `consecutive-timeout`, and `retry-cap`. Changing it is a change to this decision. The scorer writes `verdict` and leaves `stop_reason` alone. The ablation table is not filled here.
