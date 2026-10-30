# Proposal for `phases/P07-argus-guard.md`

Plan text only. No new tasks. No hour changes.

### RISK-002
- Severity: High
- Section: P7-T03; P7-T04
- Owner: [PAIR]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P7-T03 | Inventory secrets, keep them out of prompts, logs and trajectories, and scan CI for leaks | [PAIR] | build | 2 | P7-T02 | A table lists each secret, where it lives and who can read it; a test plants a fake secret and shows it is redacted from a trajectory and a trace; CI secret scan is green |
```

```
| P7-T04 | Make the GitHub App token least-privilege and short-lived | [PAIR] | build | 2 | P7-T02 | Permission list is the minimum that the workflow needs; negative tests show a push to a protected branch and a call on an uninstalled repo are refused |
```

- Proposed text:

```
| P7-T03 | Inventory secrets, keep them out of prompts, logs and trajectories, and scan CI for leaks | [PAIR] | build | 2 | P7-T02 | A table lists each secret, where it lives and who can read it; a test plants a fake secret and shows it is redacted from a trajectory and a trace; a token in a remote URL is forbidden; CI secret scan is green |
```

```
| P7-T04 | Make the GitHub App token least-privilege and short-lived | [PAIR] | build | 2 | P7-T02 | Permission list is the minimum that the workflow needs, and the scopes are stated before the first push; week 24 does not require an App the checklist creates in week 27 |
```

Delta: P7-T03 forbids a token in a remote URL, and P7-T04 states the scopes before the first push. The week-24 narrowing is PLAN-006. If both are accepted, use this P7-T04 row.

### DESIGN-011
- Severity: Med
- Section: P7-T07
- Owner: [PAIR]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P7-T07 | Set up promptfoo red-team config for injection via ticket, repo file and skill | [PAIR] | build | 2 | P7-T02, P5.5-T10 | Config runs against the fix-loop with stub tools and no real model calls for a dry run; test cases are listed per attack vector |
```

- Proposed text:

```
| P7-T07 | Set up promptfoo red-team config for injection via ticket, repo file and skill | [PAIR] | build | 2 | P7-T02 when the P5.5 cut is taken; otherwise P7-T02, P5.5-T10 | The committed config is three static cases, one each for ticket title-plus-body, a repo file, and a skill file, graded by deterministic assertions, with no generator and no LLM rubric; dry run uses stub tools and no real model calls |
```

Delta: the committed config is three static cases, one each for ticket title-plus-body, a repo file, and a skill file, graded by deterministic assertions, with no generator and no LLM rubric. The dependency words are PLAN-014. If both are accepted, use this row.

### PLAN-006
- Severity: High
- Section: P7-T04
- Owner: [PAIR]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P7-T04 | Make the GitHub App token least-privilege and short-lived | [PAIR] | build | 2 | P7-T02 | Permission list is the minimum that the workflow needs; negative tests show a push to a protected branch and a call on an uninstalled repo are refused |
```

- Proposed text:

```
| P7-T04 | Make the GitHub App token least-privilege and short-lived | [PAIR] | build | 2 | P7-T02 | Permission list is the minimum that the workflow needs, and the scopes are stated before the first push; week 24 does not require an App the checklist creates in week 27 |
```

Delta: narrow P7-T04 so week 24 does not require an App the checklist creates in week 27. The task stays in week 24. The scopes clause is RISK-002. If both are accepted, use this row. Done when and P7-T20 stay as written. P8-T02 is not mentioned, and it does not move.

### PLAN-014
- Severity: High
- Section: P7-T07
- Owner: [PAIR]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P7-T07 | Set up promptfoo red-team config for injection via ticket, repo file and skill | [PAIR] | build | 2 | P7-T02, P5.5-T10 | Config runs against the fix-loop with stub tools and no real model calls for a dry run; test cases are listed per attack vector |
```

- Proposed text:

```
| P7-T07 | Set up promptfoo red-team config for injection via ticket, repo file and skill | [PAIR] | build | 2 | P7-T02 when the P5.5 cut is taken; otherwise P7-T02, P5.5-T10 | The committed config is three static cases, one each for ticket title-plus-body, a repo file, and a skill file, graded by deterministic assertions, with no generator and no LLM rubric; dry run uses stub tools and no real model calls |
```

Delta: retarget the P5.5-T10 dependency in this row. The −28 h stays unbooked. The static-case acceptance is DESIGN-011. If both are accepted, use this row.

### PLAN-015
- Severity: Med
- Section: P7-T13
- Owner: [ME]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P7-T13 | Run ablation: Docker vs gVisor vs Firecracker on cold start and escape tests | [ME] | eval | 3 | P7-T11, P7-T12 | Rows A, B and C filled from real runs (cold start p50 and p95 over repeated starts, escape probes passed) |
```

- Proposed text:

```
| P7-T13 | Run ablation: Docker vs gVisor vs Firecracker on cold start and escape tests | [ME] | eval | 3 | P7-T11, P7-T12 | Rows A and B filled from real runs (cold start p50 and p95 over repeated starts, escape probes passed); row C is filled from a real run, or left empty when the Firecracker cut is taken |
```

P7-T11 stays in this file. The −3 h stays unbooked.

Hours and tasks in this file: unchanged.
