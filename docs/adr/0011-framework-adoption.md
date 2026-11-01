# ADR-011: Framework adoption rule after the baseline

Status: accepted (P3-T25).

## Context

The fix loop is written in this repo. No agent framework is a dependency before the baseline. A later ADR may adopt one only by clearing the bar in this decision. The mini-swe-agent comparison that would supply that evidence has not been run. This decision does not cite a resolve rate, and it does not fill the ablation table.

## Decision

Variant E is mini-swe-agent at `04d809ceab9df28f9adaed044884180159172930`, config `src/minisweagent/config/mini.yaml`, with the P3-T17 overrides and no others:

- `cost_limit` 0. In that config, 0 disables the dollar check. The stock value is 3.0.
- `cost_tracking` `ignore_errors`.
- `--network none`, plus the Argus CPU cap, memory cap, worktree mount, and read-only checks mount.
- interpreter `["bash", "-lc"]`.

The observation template in that yaml stays in force. An output of 10000 characters or more keeps a 5000-character head and a 5000-character tail. That cut is part of variant E. It is not variant A.

Mini's own scored artifact is the stdout after the first line `COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT`, when that command returns 0. The rest of that stdout is `submission`. It is not a git diff. Argus scores the worktree diff, and a passing score whose checks were touched is not resolved. Those two artifacts are not the same number.

The stop reasons differ. Mini records `Submitted`, `LimitsExceeded` (the dollar cap, or the step cap when it is above 0), `TimeExceeded`, and `RepeatedFormatError` after three format errors. A step limit of 0 means unlimited steps. Argus records the codes in ADR-008: `submit`, `step-cap`, `token-cap`, `QuotaExceeded`, `stuck`, `consecutive-timeout`, `retry-cap`, and `summary`. `RepeatedFormatError` is not `stuck`. Mini has no stuck check and no token cap.

The interface differs. Mini has one `bash` tool. Argus has the typed tools. A resolve-rate gap is a gap between those two interfaces. It is not evidence that a framework is better at the same tools.

The evidence that would justify adopting a framework is the variant E row against the variant A row, both filled from real runs on the same 30 seeded tasks and the same model. The metric is the resolve rate with a Wilson 95% interval, the same interval the bench already uses. A framework is justified only when E's interval lies entirely above A's. Overlapping intervals are not a gap. Tokens per bug, latency, and quota share are reported beside that rate and do not by themselves justify a framework.

A gap measured on mini's `submission` string, on mini's default Docker (`run_args` of `--rm` and a network), or on the stock `cost_limit` of 3.0, is not this comparison. This decision does not adopt a framework.

## Alternatives

- Treat any higher point estimate as enough. The interval exists so a small sample cannot adopt a dependency.
- Treat mini's `submission` as the bench patch. An empty echo would then score as a patch, and the worktree diff would never be graded.
- Call stock `mini.yaml` variant E, including the $3 stop and the networked container. That run can die for a reason Argus does not have, in a sandbox Argus does not use.
- Adopt a framework now, before either row exists. The bar would then be a story about a comparison that was not run.

## Consequences

Variant E, when it is run, uses the config named above. The ablation cell stays `—` until that run. `packages/fix-loop` does not gain a framework dependency from this decision. A later ADR that adopts one has to show the two Wilson intervals and this config.
