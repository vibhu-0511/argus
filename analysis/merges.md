# Merged replacements

The 19 NEEDS-NUANCE findings, one replacement per task. Hours delta 0. No new task. The 54 approved rows are not in this file. Stuck detection stays unnumbered. No per-edit confirm.

EDGE-012's test names a force-push of the bot branch and a failed push that still retries pull-request creation from a stale branch. It does not name `theirs` or committing conflict markers.

DESIGN-001 keeps interpreter `["bash", "-lc"]` from `docker.py` L38–L39 at SHA `04d809ceab9df28f9adaed044884180159172930`, read on 2026-10-28. That line sits outside the original L26–L33 permalink. The OpenAI-compatible environment variable is not named here: issue 382 was not fetched. `$3`, `step_limit` 0, and three format errors stay off these rows.

## P0-T24 — DESIGN-009

```text
| P0-T24 | Build mutation validity filter: keep only fail-before, pass-after mutants | [ME] | build | 4 | P0-T15, P0-T22, P0-T23 | Filter rejects a mutant with no visual change and a mutant that breaks the build; a mutant is kept only on exit 1 on the mutant then exit 0 on the original, with a non-empty check list |
```

## P0-T27 — DESIGN-009

```text
| P0-T27 | Write ADR-003: Mutation validity and flake policy | [ME] | doc | 1 | P0-T26 | ADR states the validity rule, the flake threshold, and that exit 2 and quarantined tasks are excluded from "attempted" |
```

## P0-T29 — DESIGN-009, PLAN-020

```text
| P0-T29 | Run ablation: seeded vs mutated bugs under the one-shot baseline | [ME] | eval | 2 | P0-T26, P0-T28 | Both rows of the Ablation table are filled from a real run, with Wilson 95% intervals; the mutated sample is drawn after quarantine; the $-equivalent cell stays "—" until P5-T11; this task does not create `prices.json`; runs used the ledger and stayed under quota |
```

Done when, same phase: "Filled in" does not cover the $-equivalent cell, which stays "—" until P5-T11. This phase does not create `prices.json`.

## P1-T01 — RISK-001, EDGE-014

```text
| P1-T01 | Spike: call Playwright MCP from an MCP Python SDK v2 client | [ME] | learn | 3 | P1-T00 | A script launches the server, lists tools and runs one navigate plus snapshot; the result is a written go/no-go in `docs/notes/p1-mcp-spike.md` with exact versions; a go allow-lists the six repro tools, leaves `browser_run_code_unsafe` off, and does not add `page.evaluate`; it records the `initialize` protocol version and the tool list from the spike process, and schemas are not copied from the 1.65-next or 1.64-alpha tree onto the pinned row |
```

## P1-T04 — RISK-001, DESIGN-015

```text
| P1-T04 | Define repro tool schemas (navigate, snapshot, click, type, assert-visible, screenshot) | [ME] | build | 2 | P1-T02, P0-T03 | Each tool has a typed schema, a description and a typed error result; those six tools are the allow-list, `browser_run_code_unsafe` is off, and `page.evaluate` is not added; `assert-visible` is role plus accessible name; `stale-target` and `not-unique` are typed errors; the snapshot takes a depth or byte cap; schema files validate; one test per tool against the target app |
```

Ablation variants, same phase: B = ticket text plus the ticket image, attached once rather than a new screenshot each revision.

## P1-T05 — RISK-001, EDGE-005

```text
| P1-T05 | Build Docker image to run Playwright repro scripts with no network egress beyond the app | [CLAUDE] | build | 2 | P1-T04 | `docker run` executes a sample script and returns its exit code; the container cannot reach the internet; `browser_run_code_unsafe` stays off and `page.evaluate` is not added; each repro run gets its own user-data-dir |
```

## P1-T07 — RISK-005, EDGE-003

```text
| P1-T07 | Build repro agent loop: generate script, run it, revise on error, hard retry cap | [ME] | build | 4 | P1-T04, P1-T05, P1-T06, P0-T05 | Loop stops on a script that fails on the buggy tree and passes on the golden tree, on cap or on `QuotaExceeded`, and records a stop reason; the cap reason is `retry-cap` recorded by the loop, and empty model output counts toward that cap; the saved script uses the logged role and name, not the ephemeral ref, and it contains a symptom assertion before the loop's stop; one trajectory file per run validates against the Trajectory schema |
```

## P1-T08 — RISK-005

```text
| P1-T08 | Build repro verifier: script must fail on buggy tree and pass on golden tree | [ME] | build | 2 | P1-T07, P0-T15 | Verifier returns one of `valid`, `passes-on-bug`, `fails-on-golden`, `error`; skip or `test.fixme()` is `error`; four hand-made scripts exercise each verdict |
```

## P1-T10 — EDGE-005

```text
| P1-T10 | Run repro-agent on 30 seeded tasks, text only | [ME] | eval | 2 | P1-T08 | 30 verdicts and 30 trajectories saved; ledger shows the run stayed inside the quota; the next task still starts after a crashed server |
```

## P3-T02 — DESIGN-002, EDGE-010

```text
| P3-T02 | Define agent tool schemas: read_file, list_dir, search, edit, run_cmd, submit | [ME] | build | 4 | P3-T01, P0-T03 | Each tool has a typed schema, description and typed error results; `edit` is an exact unique match, the error names the line numbers, with no whitespace flex, no fuzzy matcher, and no second whole-file tool; `read_file` and `edit` return a typed error for a path outside the worktree, and the host-filesystem probe stays P7-T12; schema files validate; one unit test per tool |
```

## P3-T07 — DESIGN-002, DESIGN-004

```text
| P3-T07 | Build tool dispatch with argument validation and error handling | [ME] | build | 3 | P3-T06 | Malformed arguments return a typed error to the model rather than raising; a tool error is a normal step with a flag; the error codes are a closed enum distinct from `stuck`; dispatch is tested with 5 bad inputs, and one of them is a non-unique `edit` whose error names the line numbers; there is no whitespace flex, no fuzzy matcher, and no second whole-file tool |
```

## P3-T08 — EDGE-007, EDGE-008

```text
| P3-T08 | Build trajectory recorder (every step as a Trajectory record) | [PAIR] | build | 3 | P3-T06, P0-T03 | A run writes one JSONL file that validates against the Trajectory schema; it includes tokens in, out and cached per step; a rejected tool call remains a Trajectory record that contains the raw response, and replay can see that step; an omitted cache field is zero |
```

## P3-T12 — DESIGN-007

```text
| P3-T12 | Implement context strategy: rolling summary | [ME] | build | 3 | P3-T09 | Older turns are replaced by a summary produced by the cheap-tier model; the system prompt and the first user message survive; a summary that does not shrink the window is a stop; last-N elision is not added; summary tokens are counted in the ledger |
```

## P3-T17 — DESIGN-001, DESIGN-006

```text
| P3-T17 | Set up mini-swe-agent against the OpenAI-compatible endpoint | [PAIR] | build | 4 | P3-T05, P0-T05 | mini-swe-agent solves or fails one fixture task through the same ledger and sandbox; it sets `cost_limit` 0, `cost_tracking=ignore_errors`, `--network none`, interpreter `["bash", "-lc"]`, and names the environment variable that pinned mini reads for the OpenAI-compatible endpoint; its trajectory is converted to the Trajectory format by mapping the mini JSON message list into JSONL |
```

## P3-T21 — DESIGN-004, DESIGN-005

```text
| P3-T21 | Label failed runs with a failure taxonomy | [ME] | eval | 3 | P3-T19 | Every failed trajectory has one label from a written list, and that list includes the P3-T06 stop reasons; the labels are a closed error-code enum distinct from `stuck`, and `FailureKind` is not copied into the failure notes; counts per label are in `docs/notes/p3-failures.md` |
```

## P3-T22 — DESIGN-002, DESIGN-005

```text
| P3-T22 | Write ADR-008: Loop control, stop conditions and tool-call format | [ME] | doc | 1 | P3-T18 | ADR lists each stop condition and its reason code, picks exact unique match for `edit` with the line numbers in the error, and decides that a token-cap or stuck stop still scores the worktree diff and does not rewrite that stop reason; this scoring rule is a planning choice, not a measured result |
```

No stuck count on this row.

## P3-T23 — DESIGN-007

```text
| P3-T23 | Write ADR-009: Context management policy | [ME] | doc | 1 | P3-T19 | ADR cites the ablation table and states the default strategy and when to switch, and says the system prompt and the first user message survive, a summary that does not shrink is a stop, and last-N elision is not added |
```

## P3-T25 — DESIGN-001, DESIGN-007

```text
| P3-T25 | Write ADR-011: Framework adoption rule after the baseline | [ME] | doc | 1 | P3-T20 | ADR says what evidence would justify adopting a framework, using the mini-swe-agent comparison, states that the scored artifact is stdout after `COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT` and that the stop reasons differ from Argus, and names which mini config is variant E |
```

## P3-T27 — DESIGN-006, EDGE-009

```text
| P3-T27 | Build deterministic replay of a recorded trajectory with no LLM call | [PAIR] | build | 2 | P3-T08 | `fix-loop replay <file>` reproduces the final patch byte for byte from the stored model responses; it keeps the stored model message and does not replay by shelling the actions again; if the tool-call format uses ids, a resumed log has one observation per id |
```

Ablation variants, same phase: E = mini-swe-agent baseline, the mini config ADR-011 names.

## P8-T23 — EDGE-012

```text
| P8-T23 | Break it: force a cherry-pick conflict in a backport | [ME] | test | 2 | P8-T10 | The bot comments the conflict and leaves branches untouched; the test fails on a force-push of the bot branch and on a failed push that still retries pull-request creation from a stale branch; it refuses a tenant conflict command and a checkout of the PR head under the installation token; a second run finds the existing PR or no-ops; written up |
```

Break-it item 3 uses the same two failure names and the same fix. It does not name `theirs` or conflict markers.

## Contracts

PLAN.md and PROJECT.md resolve-rate cells gain: ADR-003 excludes exit 2 and tasks in `bench/quarantine/` from attempted, draws the ablation sample after quarantine, and keeps a mutant only on exit 1 then exit 0 with a non-empty check list.

PLAN.md and PROJECT.md $-equivalent cells gain: P0 through P4 leave this cell as "—" until P5-T11, and "filled in" does not cover this column.

## Totals

Core 556 h / 255 tasks. P9 40 h / 17 tasks. Grand total 596 h / 272 tasks.
