# P01-repro-agent

### RISK-001
- Severity: High
- Section: P1-T01, P1-T04, P1-T05
- Owner: [ME] (P1-T01, P1-T04); [CLAUDE] (P1-T05)
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P1-T01 | Spike: call Playwright MCP from an MCP Python SDK v2 client | [ME] | learn | 3 | P1-T00 | A script launches the server, lists tools and runs one navigate plus snapshot; the result is a written go/no-go in `docs/notes/p1-mcp-spike.md` with exact versions |

| P1-T04 | Define repro tool schemas (navigate, snapshot, click, type, assert-visible, screenshot) | [ME] | build | 2 | P1-T02, P0-T03 | Each tool has a typed schema, a description and a typed error result; schema files validate; one test per tool against the target app |

| P1-T05 | Build Docker image to run Playwright repro scripts with no network egress beyond the app | [CLAUDE] | build | 2 | P1-T04 | `docker run` executes a sample script and returns its exit code; the container cannot reach the internet |
```

- Proposed text:

```
| P1-T01 | Spike: call Playwright MCP from an MCP Python SDK v2 client | [ME] | learn | 3 | P1-T00 | A script launches the server, lists tools and runs one navigate plus snapshot; the result is a written go/no-go in `docs/notes/p1-mcp-spike.md` with exact versions; a go allow-lists the six repro tools, leaves `browser_run_code_unsafe` off, and does not add `page.evaluate` |

| P1-T04 | Define repro tool schemas (navigate, snapshot, click, type, assert-visible, screenshot) | [ME] | build | 2 | P1-T02, P0-T03 | Each tool has a typed schema, a description and a typed error result; those six tools are the allow-list, `browser_run_code_unsafe` is off, and `page.evaluate` is not added; schema files validate; one test per tool against the target app |

| P1-T05 | Build Docker image to run Playwright repro scripts with no network egress beyond the app | [CLAUDE] | build | 2 | P1-T04 | `docker run` executes a sample script and returns its exit code; the container cannot reach the internet; `browser_run_code_unsafe` stays off and `page.evaluate` is not added |
```

### RISK-005
- Severity: High
- Section: P1-T07, P1-T08
- Owner: [ME]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P1-T07 | Build repro agent loop: generate script, run it, revise on error, hard retry cap | [ME] | build | 4 | P1-T04, P1-T05, P1-T06, P0-T05 | Loop stops on success, on cap or on `QuotaExceeded`, and records a stop reason; one trajectory file per run validates against the Trajectory schema |

| P1-T08 | Build repro verifier: script must fail on buggy tree and pass on golden tree | [ME] | build | 2 | P1-T07, P0-T15 | Verifier returns one of `valid`, `passes-on-bug`, `fails-on-golden`, `error`; four hand-made scripts exercise each verdict |
```

- Proposed text:

```
| P1-T07 | Build repro agent loop: generate script, run it, revise on error, hard retry cap | [ME] | build | 4 | P1-T04, P1-T05, P1-T06, P0-T05 | Loop stops on a script that fails on the buggy tree and passes on the golden tree, on cap or on `QuotaExceeded`, and records a stop reason; the cap reason is `retry-cap` recorded by the loop, and empty model output counts toward that cap; one trajectory file per run validates against the Trajectory schema |

| P1-T08 | Build repro verifier: script must fail on buggy tree and pass on golden tree | [ME] | build | 2 | P1-T07, P0-T15 | Verifier returns one of `valid`, `passes-on-bug`, `fails-on-golden`, `error`; skip or `test.fixme()` is `error`; four hand-made scripts exercise each verdict |
```

### DESIGN-015
- Severity: Med
- Section: P1-T04, Ablation
- Owner: [ME] (P1-T04); [CLAUDE] (Ablation variants, nearest task P1-T16)
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P1-T04 | Define repro tool schemas (navigate, snapshot, click, type, assert-visible, screenshot) | [ME] | build | 2 | P1-T02, P0-T03 | Each tool has a typed schema, a description and a typed error result; schema files validate; one test per tool against the target app |

**Variants:** A = ticket text only; B = ticket text plus screenshot.
```

- Proposed text:

```
| P1-T04 | Define repro tool schemas (navigate, snapshot, click, type, assert-visible, screenshot) | [ME] | build | 2 | P1-T02, P0-T03 | Each tool has a typed schema, a description and a typed error result; `assert-visible` is role plus accessible name; `stale-target` and `not-unique` are typed errors; the snapshot takes a depth or byte cap; schema files validate; one test per tool against the target app |

**Variants:** A = ticket text only; B = ticket text plus the ticket image, attached once rather than a new screenshot each revision.
```

### EDGE-003
- Severity: Med
- Section: P1-T07
- Owner: [ME]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P1-T07 | Build repro agent loop: generate script, run it, revise on error, hard retry cap | [ME] | build | 4 | P1-T04, P1-T05, P1-T06, P0-T05 | Loop stops on success, on cap or on `QuotaExceeded`, and records a stop reason; one trajectory file per run validates against the Trajectory schema |
```

- Proposed text:

```
| P1-T07 | Build repro agent loop: generate script, run it, revise on error, hard retry cap | [ME] | build | 4 | P1-T04, P1-T05, P1-T06, P0-T05 | Loop stops on success, on cap or on `QuotaExceeded`, and records a stop reason; the saved script uses the logged role and name, not the ephemeral ref, and it contains a symptom assertion before the loop's stop; one trajectory file per run validates against the Trajectory schema |
```

### EDGE-004
- Severity: Med
- Section: P1-T06
- Owner: [PAIR]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P1-T06 | Assemble ticket and screenshot prompt (text-only and text-plus-image modes) | [PAIR] | build | 2 | P1-T04 | One function builds both modes from a Ticket; a snapshot test shows the image is attached only in image mode |
```

- Proposed text:

```
| P1-T06 | Assemble ticket and screenshot prompt (text-only and text-plus-image modes) | [PAIR] | build | 2 | P1-T04 | One function builds both modes from a Ticket; a snapshot test shows the image is attached only in image mode; a bad image is a typed tool error, and the bytes must match the declared media type, so one bad shot does not burn the next model call |
```

### EDGE-005
- Severity: Med
- Section: P1-T05, P1-T10
- Owner: [CLAUDE] (P1-T05); [ME] (P1-T10)
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P1-T05 | Build Docker image to run Playwright repro scripts with no network egress beyond the app | [CLAUDE] | build | 2 | P1-T04 | `docker run` executes a sample script and returns its exit code; the container cannot reach the internet |

| P1-T10 | Run repro-agent on 30 seeded tasks, text only | [ME] | eval | 2 | P1-T08 | 30 verdicts and 30 trajectories saved; ledger shows the run stayed inside the quota |
```

- Proposed text:

```
| P1-T05 | Build Docker image to run Playwright repro scripts with no network egress beyond the app | [CLAUDE] | build | 2 | P1-T04 | `docker run` executes a sample script and returns its exit code; the container cannot reach the internet; each repro run gets its own user-data-dir |

| P1-T10 | Run repro-agent on 30 seeded tasks, text only | [ME] | eval | 2 | P1-T08 | 30 verdicts and 30 trajectories saved; ledger shows the run stayed inside the quota; the next task still starts after a crashed server |
```

### EDGE-006
- Severity: Low
- Section: P1-T15
- Owner: [ME]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P1-T15 | Break it: kill the MCP server mid-run | [ME] | test | 2 | P1-T07 | Loop reports a tool-unavailable stop reason, does not hang past a timeout, and falls back as the fix says |
```

- Proposed text:

```
| P1-T15 | Break it: kill the MCP server mid-run | [ME] | test | 2 | P1-T07 | Loop reports a tool-unavailable stop reason, does not hang past a timeout, and falls back as the fix says; a server exit between calls is the same `tool-unavailable` stop, inside the existing timeout |
```

### EDGE-014
- Severity: Med
- Section: P1-T01
- Owner: [ME]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P1-T01 | Spike: call Playwright MCP from an MCP Python SDK v2 client | [ME] | learn | 3 | P1-T00 | A script launches the server, lists tools and runs one navigate plus snapshot; the result is a written go/no-go in `docs/notes/p1-mcp-spike.md` with exact versions |
```

- Proposed text:

```
| P1-T01 | Spike: call Playwright MCP from an MCP Python SDK v2 client | [ME] | learn | 3 | P1-T00 | A script launches the server, lists tools and runs one navigate plus snapshot; the result is a written go/no-go in `docs/notes/p1-mcp-spike.md` with exact versions; it records the `initialize` protocol version and the tool list from the spike process, and schemas are not copied from the 1.65-next or 1.64-alpha tree onto the pinned row |
```

### PLAN-003
- Severity: Low
- Section: P1-T02
- Owner: [ME]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P1-T02 | Write ADR-004: Playwright MCP vs direct Playwright as tool | [ME] | doc | 1 | P1-T01 | ADR states the choice, the spike evidence and the fallback; marked as the Risk 4 mitigation |
```

- Proposed text:

```
| P1-T02 | Write ADR-004: Playwright MCP vs direct Playwright as tool | [ME] | doc | 1 | P1-T01 | ADR states the choice, the spike evidence and the fallback, and notes whether Playwright MCP supports the 2026-07-28 spec; marked as the Risk 4 mitigation |
```

### PLAN-019
- Severity: Med
- Section: Done when
- Owner: [ME]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
- The interop spike between Playwright MCP and an MCP Python SDK v2 client has a written go/no-go. If it is no-go, direct Playwright is wired in as a tool instead (ADR-004).
```

- Proposed text:

```
- The interop spike between Playwright MCP and an MCP Python SDK v2 client has a written go/no-go. If it is no-go, the mitigation is ADR-004, not an unscheduled direct-Playwright build.
```

Hours and tasks in this file: unchanged.
