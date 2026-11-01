# P03-fix-loop

### RISK-006
- Severity: Med
- Section: P3-T06, P3-T32
- Owner: [ME] (P3-T06); [ME] (P3-T32)
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P3-T06 | Build core agent loop: message history, model call, stop conditions | [ME] | build | 4 | P3-T02, P0-T05 | Loop stops on `submit`, step cap, token cap, `QuotaExceeded` and stuck detection; each stop reason appears in the trajectory |

| P3-T32 | Break it: make the model run a destructive shell command | [ME] | test | 2 | P3-T05 | The command only affects the disposable worktree and container; the host tree is unchanged (hash check); written up |
```

- Proposed text:

```
| P3-T06 | Build core agent loop: message history, model call, stop conditions | [ME] | build | 4 | P3-T02, P0-T05 | Loop stops on `submit`, step cap, token cap, `QuotaExceeded`, stuck detection, and a consecutive-timeout stop distinct from `stuck`; each command has a timeout; an interactive command is rejected; each stop reason appears in the trajectory |

| P3-T32 | Break it: make the model run a destructive shell command | [ME] | test | 2 | P3-T05 | The command only affects the disposable worktree and container; the host tree is unchanged (hash check); each command has a timeout; consecutive timeouts are a stop distinct from `stuck`; an interactive command is rejected; written up |
```

### DESIGN-001
- Severity: High
- Section: P3-T17, P3-T25
- Owner: [PAIR] (P3-T17); [ME] (P3-T25)
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P3-T17 | Set up mini-swe-agent against the OpenAI-compatible endpoint | [PAIR] | build | 4 | P3-T05, P0-T05 | mini-swe-agent solves or fails one fixture task through the same ledger and sandbox; its trajectory is converted to the Trajectory format |

| P3-T25 | Write ADR-011: Framework adoption rule after the baseline | [ME] | doc | 1 | P3-T20 | ADR says what evidence would justify adopting a framework, using the mini-swe-agent comparison |
```

- Proposed text:

```
| P3-T17 | Set up mini-swe-agent against the OpenAI-compatible endpoint | [PAIR] | build | 4 | P3-T05, P0-T05 | mini-swe-agent solves or fails one fixture task through the same ledger and sandbox; it sets `cost_limit` 0, `cost_tracking=ignore_errors`, `--network none`, interpreter `["bash", "-lc"]`, and names the environment variable that pinned mini reads for the OpenAI-compatible endpoint; its trajectory is converted to the Trajectory format |

| P3-T25 | Write ADR-011: Framework adoption rule after the baseline | [ME] | doc | 1 | P3-T20 | ADR says what evidence would justify adopting a framework, using the mini-swe-agent comparison, and states that the scored artifact is stdout after `COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT` and that the stop reasons differ from Argus |
```

### DESIGN-002
- Severity: Med
- Section: P3-T02, P3-T07, P3-T22
- Owner: [ME]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P3-T02 | Define agent tool schemas: read_file, list_dir, search, edit, run_cmd, submit | [ME] | build | 4 | P3-T01, P0-T03 | Each tool has a typed schema, description and typed error results; schema files validate; one unit test per tool |

| P3-T07 | Build tool dispatch with argument validation and error handling | [ME] | build | 3 | P3-T06 | Malformed arguments return a typed error to the model rather than raising; dispatch is tested with 5 bad inputs |

| P3-T22 | Write ADR-008: Loop control, stop conditions and tool-call format | [ME] | doc | 1 | P3-T18 | ADR lists each stop condition and its reason code |
```

- Proposed text:

```
| P3-T02 | Define agent tool schemas: read_file, list_dir, search, edit, run_cmd, submit | [ME] | build | 4 | P3-T01, P0-T03 | Each tool has a typed schema, description and typed error results; `edit` is an exact unique match, the error names the line numbers, with no whitespace flex, no fuzzy matcher, and no second whole-file tool; schema files validate; one unit test per tool |

| P3-T07 | Build tool dispatch with argument validation and error handling | [ME] | build | 3 | P3-T06 | Malformed arguments return a typed error to the model rather than raising; dispatch is tested with 5 bad inputs, and one of them is a non-unique `edit` whose error names the line numbers; there is no whitespace flex, no fuzzy matcher, and no second whole-file tool |

| P3-T22 | Write ADR-008: Loop control, stop conditions and tool-call format | [ME] | doc | 1 | P3-T18 | ADR lists each stop condition and its reason code, and picks exact unique match for `edit`, with the line numbers in the error |
```

### DESIGN-003
- Severity: Med
- Section: Break it, item 1; P3-T06; P3-T22; P3-T28
- Owner: [ME]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
*Fix:* detect N identical consecutive calls and end the run or inject a "you are repeating yourself" message once.

| P3-T06 | Build core agent loop: message history, model call, stop conditions | [ME] | build | 4 | P3-T02, P0-T05 | Loop stops on `submit`, step cap, token cap, `QuotaExceeded` and stuck detection; each stop reason appears in the trajectory |

| P3-T22 | Write ADR-008: Loop control, stop conditions and tool-call format | [ME] | doc | 1 | P3-T18 | ADR lists each stop condition and its reason code |

| P3-T28 | Break it: make the model repeat the same tool call | [ME] | test | 2 | P3-T06 | Stuck detection fires and the run ends with reason `stuck`; written up in the Break it section |
```

- Proposed text:

```
*Fix:* detect 3 identical consecutive tool calls and end the run. Alternating calls and a monologue do not count. This N is a planning choice, not a measured result.

| P3-T06 | Build core agent loop: message history, model call, stop conditions | [ME] | build | 4 | P3-T02, P0-T05 | Loop stops on `submit`, step cap, token cap, `QuotaExceeded` and stuck detection; stuck detection is 3 consecutive identical tool calls, alternating calls and a monologue do not count, and this N is a planning choice, not a measured result; each stop reason appears in the trajectory |

| P3-T22 | Write ADR-008: Loop control, stop conditions and tool-call format | [ME] | doc | 1 | P3-T18 | ADR lists each stop condition and its reason code, and picks stuck as 3 consecutive identical tool calls; alternating calls and a monologue do not count; this N is a planning choice, not a measured result |

| P3-T28 | Break it: make the model repeat the same tool call | [ME] | test | 2 | P3-T06 | Stuck detection fires on 3 consecutive identical tool calls and the run ends with reason `stuck`; alternating calls and a monologue do not count; this N is a planning choice, not a measured result; written up in the Break it section |
```

### DESIGN-004
- Severity: Med
- Section: P3-T07, P3-T21
- Owner: [ME]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P3-T07 | Build tool dispatch with argument validation and error handling | [ME] | build | 3 | P3-T06 | Malformed arguments return a typed error to the model rather than raising; dispatch is tested with 5 bad inputs |

| P3-T21 | Label failed runs with a failure taxonomy | [ME] | eval | 3 | P3-T19 | Every failed trajectory has one label from a written list; counts per label are in `docs/notes/p3-failures.md` |
```

- Proposed text:

```
| P3-T07 | Build tool dispatch with argument validation and error handling | [ME] | build | 3 | P3-T06 | Malformed arguments return a typed error to the model rather than raising; a tool error is a normal step with a flag; the error codes are a closed enum distinct from `stuck`; dispatch is tested with 5 bad inputs |

| P3-T21 | Label failed runs with a failure taxonomy | [ME] | eval | 3 | P3-T19 | Every failed trajectory has one label from a written list; the labels are a closed error-code enum distinct from `stuck`, and `FailureKind` is not copied into the failure notes; counts per label are in `docs/notes/p3-failures.md` |
```

### DESIGN-005
- Severity: Med
- Section: P3-T21, P3-T22
- Owner: [ME]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P3-T21 | Label failed runs with a failure taxonomy | [ME] | eval | 3 | P3-T19 | Every failed trajectory has one label from a written list; counts per label are in `docs/notes/p3-failures.md` |

| P3-T22 | Write ADR-008: Loop control, stop conditions and tool-call format | [ME] | doc | 1 | P3-T18 | ADR lists each stop condition and its reason code |
```

- Proposed text:

```
| P3-T21 | Label failed runs with a failure taxonomy | [ME] | eval | 3 | P3-T19 | Every failed trajectory has one label from a written list, and that list includes the P3-T06 stop reasons; counts per label are in `docs/notes/p3-failures.md` |

| P3-T22 | Write ADR-008: Loop control, stop conditions and tool-call format | [ME] | doc | 1 | P3-T18 | ADR lists each stop condition and its reason code, and decides that a token-cap or stuck stop still scores the worktree diff and does not rewrite that stop reason; this is a planning choice, not a measured result |
```

### DESIGN-006
- Severity: Med
- Section: P3-T17, P3-T27
- Owner: [PAIR]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P3-T17 | Set up mini-swe-agent against the OpenAI-compatible endpoint | [PAIR] | build | 4 | P3-T05, P0-T05 | mini-swe-agent solves or fails one fixture task through the same ledger and sandbox; its trajectory is converted to the Trajectory format |

| P3-T27 | Build deterministic replay of a recorded trajectory with no LLM call | [PAIR] | build | 2 | P3-T08 | `fix-loop replay <file>` reproduces the final patch byte for byte from the stored model responses |
```

- Proposed text:

```
| P3-T17 | Set up mini-swe-agent against the OpenAI-compatible endpoint | [PAIR] | build | 4 | P3-T05, P0-T05 | mini-swe-agent solves or fails one fixture task through the same ledger and sandbox; its trajectory is converted to the Trajectory format by mapping the mini JSON message list into JSONL |

| P3-T27 | Build deterministic replay of a recorded trajectory with no LLM call | [PAIR] | build | 2 | P3-T08 | `fix-loop replay <file>` reproduces the final patch byte for byte from the stored model responses; it keeps the stored model message and does not replay by shelling the actions again |
```

### DESIGN-007
- Severity: Med
- Section: P3-T12, P3-T23, P3-T25, Ablation
- Owner: [ME] (P3-T12, P3-T23, P3-T25); [CLAUDE] (Ablation variants, nearest task P3-T33)
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P3-T12 | Implement context strategy: rolling summary | [ME] | build | 3 | P3-T09 | Older turns are replaced by a summary produced by the cheap-tier model; summary tokens are counted in the ledger |

| P3-T23 | Write ADR-009: Context management policy | [ME] | doc | 1 | P3-T19 | ADR cites the ablation table and states the default strategy and when to switch |

| P3-T25 | Write ADR-011: Framework adoption rule after the baseline | [ME] | doc | 1 | P3-T20 | ADR says what evidence would justify adopting a framework, using the mini-swe-agent comparison |

**Variants:** A = no compaction; B = output caps; C = offload-to-files; D = summarize; E = mini-swe-agent baseline.
```

- Proposed text:

```
| P3-T12 | Implement context strategy: rolling summary | [ME] | build | 3 | P3-T09 | Older turns are replaced by a summary produced by the cheap-tier model; the system prompt and the first user message survive; a summary that does not shrink the window is a stop; last-N elision is not added; summary tokens are counted in the ledger |

| P3-T23 | Write ADR-009: Context management policy | [ME] | doc | 1 | P3-T19 | ADR cites the ablation table and states the default strategy and when to switch, and says the system prompt and the first user message survive, a summary that does not shrink is a stop, and last-N elision is not added |

| P3-T25 | Write ADR-011: Framework adoption rule after the baseline | [ME] | doc | 1 | P3-T20 | ADR says what evidence would justify adopting a framework, using the mini-swe-agent comparison, and names which mini config is variant E |

**Variants:** A = no compaction; B = output caps; C = offload-to-files; D = summarize; E = mini-swe-agent baseline, the mini config ADR-011 names.
```

### EDGE-007
- Severity: Med
- Section: P3-T08
- Owner: [PAIR]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P3-T08 | Build trajectory recorder (every step as a Trajectory record) | [PAIR] | build | 3 | P3-T06, P0-T03 | A run writes one JSONL file that validates against the Trajectory schema; it includes tokens in, out and cached per step |
```

- Proposed text:

```
| P3-T08 | Build trajectory recorder (every step as a Trajectory record) | [PAIR] | build | 3 | P3-T06, P0-T03 | A run writes one JSONL file that validates against the Trajectory schema; it includes tokens in, out and cached per step; a rejected tool call remains a Trajectory record that contains the raw response, and replay can see that step |
```

### EDGE-008
- Severity: Med
- Section: P3-T08
- Owner: [PAIR]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P3-T08 | Build trajectory recorder (every step as a Trajectory record) | [PAIR] | build | 3 | P3-T06, P0-T03 | A run writes one JSONL file that validates against the Trajectory schema; it includes tokens in, out and cached per step |
```

- Proposed text:

```
| P3-T08 | Build trajectory recorder (every step as a Trajectory record) | [PAIR] | build | 3 | P3-T06, P0-T03 | A run writes one JSONL file that validates against the Trajectory schema; it includes tokens in, out and cached per step; an omitted cache field is zero |
```

### EDGE-009
- Severity: Med
- Section: P3-T27
- Owner: [PAIR]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P3-T27 | Build deterministic replay of a recorded trajectory with no LLM call | [PAIR] | build | 2 | P3-T08 | `fix-loop replay <file>` reproduces the final patch byte for byte from the stored model responses |
```

- Proposed text:

```
| P3-T27 | Build deterministic replay of a recorded trajectory with no LLM call | [PAIR] | build | 2 | P3-T08 | `fix-loop replay <file>` reproduces the final patch byte for byte from the stored model responses; if the tool-call format uses ids, a resumed log has one observation per id |
```

### EDGE-010
- Severity: Med
- Section: P3-T02
- Owner: [ME]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P3-T02 | Define agent tool schemas: read_file, list_dir, search, edit, run_cmd, submit | [ME] | build | 4 | P3-T01, P0-T03 | Each tool has a typed schema, description and typed error results; schema files validate; one unit test per tool |
```

- Proposed text:

```
| P3-T02 | Define agent tool schemas: read_file, list_dir, search, edit, run_cmd, submit | [ME] | build | 4 | P3-T01, P0-T03 | Each tool has a typed schema, description and typed error results; `read_file` and `edit` return a typed error for a path outside the worktree, and the host-filesystem probe stays P7-T12; schema files validate; one unit test per tool |
```

### EDGE-011
- Severity: Med
- Section: P3-T30
- Owner: [ME]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P3-T30 | Break it: make the model send malformed tool arguments | [ME] | test | 2 | P3-T07 | A typed error goes back to the model, the run does not crash, and repeated errors end the run; written up |
```

- Proposed text:

```
| P3-T30 | Break it: make the model send malformed tool arguments | [ME] | test | 2 | P3-T07 | A typed error goes back to the model, the run does not crash, and repeated errors end the run; a provider payload missing `choices` is a typed error returned to the loop, and the run does not crash; written up |
```

Hours and tasks in this file: unchanged.
