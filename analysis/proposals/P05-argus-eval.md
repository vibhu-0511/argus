# Proposal for `phases/P05-argus-eval.md`

Plan text only. No new tasks. No hour changes. No quota-share field is added.

### DESIGN-016
- Severity: Med
- Section: P5-T19
- Owner: [PAIR]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P5-T19 | Build the SWE-bench Multimodal subset adapter (10 to 20 tasks) into the Task format | [PAIR] | build | 3 | P5-T04 | Subset list is committed; adapter converts each task or records an exclusion reason; at least 10 tasks load |
```

- Proposed text:

```
| P5-T19 | Build the SWE-bench Multimodal subset adapter (10 to 20 tasks) into the Task format | [PAIR] | build | 3 | P5-T04 | Subset list is committed; the adapter pins split `dev`; it records an exclusion for every test-split row and for a dev row with missing `image_assets` URLs; the gold patch stays out of the agent prompt; at least 10 tasks load |
```

### FACT-010
- Severity: Low
- Section: Agentic concepts learned; Interview questions; P5-T01
- Owner: [CLAUDE] for the concept and interview lines (nearest task P5-T00); [ME] for P5-T01
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
2. **OTel GenAI semantic conventions** — still in development status; how to keep traces portable with a normalizer.
```

```
2. The GenAI semantic conventions are still in development. How do you keep traces and dashboards from breaking when an attribute is renamed or the backend changes?
```

```
| P5-T01 | Read the OTel GenAI conventions and the reliable-agents paper, write notes | [ME] | learn | 1 | P5-T00 | Notes list the span and attribute names this project will use and which are still marked development |
```

- Proposed text:

```
2. **OTel GenAI semantic conventions** — development status is not stated; how to keep traces portable with a normalizer.
```

```
2. Development status for the GenAI semantic conventions is not stated. How do you keep traces and dashboards from breaking when an attribute is renamed or the backend changes?
```

```
| P5-T01 | Read the OTel GenAI conventions and the reliable-agents paper, write notes | [ME] | learn | 1 | P5-T00 | Notes list the span and attribute names this project will use and record development status as not stated |
```

This file states the development-status claim and does not state a stable release or a June 2026 move. Those two stay absent. The development-status wording becomes not stated.

Hours and tasks in this file: unchanged.
