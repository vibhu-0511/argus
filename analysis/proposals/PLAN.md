# PLAN.md text proposals

Phase 4 planning review. Each block replaces only the quoted span in `PLAN.md`. No task, risk that needs new build work, or hour is added. Source files are not edited by this proposal.

Skipped, because `PLAN.md` does not contain the claim:

- DESIGN-001. No metrics sentence names variant E. The phase-map ablation says "a baseline against mini-swe-agent", and the resolve-rate row scores "the agent's final patch".
- DESIGN-005. The metrics contract does not state what a capped run scores.
- PLAN-004. The week table already places P6 in weeks 22, 23, and 24.

### DESIGN-009
- Severity: Med
- Section: Metrics contract
- Owner: [ME]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```text
A task is resolved when the bench scorer passes on the agent's final patch, no bench check file was touched, and (from P4) the verifier accepts. Reported as resolved over attempted, with a Wilson 95% interval
```

- Proposed text:

```text
A task is resolved when the bench scorer passes on the agent's final patch, no bench check file was touched, and (from P4) the verifier accepts. Reported as resolved over attempted, with a Wilson 95% interval. ADR-003 excludes exit 2 and tasks in `bench/quarantine/` from attempted, draws the ablation sample after quarantine, and keeps a mutant only on exit 1 then exit 0 with a non-empty check list
```

### DESIGN-013
- Severity: Med
- Section: Risk register (top 5)
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:

```text
| 3 | **Neon CU-hours and Render sleep collide with DBOS polling** | Measure in P6; reconciliation design; ADR alternatives | P6-T13, P6-T14, ADR-021, ADR-022 |
```

- Proposed text:

```text
| 3 | **Neon CU-hours and Render sleep collide with DBOS polling.** Recovery also depends on `use_listen_notify` before the first migration, a stable app version, a stable executor id, and no conductor key on Render | Measure in P6; reconciliation design; ADR alternatives. The crash-recovery run asserts a second GitHub call only for the kill that happens before the step result is stored | P6-T13, P6-T14, ADR-021, ADR-022 |
```

### FACT-001
- Severity: Low
- Section: Versions checked on 2026-10-01
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:

```text
| React | 19.2.7 |
```

- Proposed text:

```text
| React | 19.3.1 |
```

- Current text:

```text
- **React 19 dropped `_debugSource`.** React 19.2 removed `source`/`self` from `jsxDEV`, so a build-time `data-src` attribute is the only robust route (P2, ADR-006).
```

- Proposed text:

```text
- **React 19 source mapping.** Re-check the React 19.2 removal of `source`/`self` from `jsxDEV` against React 19.3.1. The build-time `data-src` attribute remains the P2 route (ADR-006).
```

### FACT-002
- Severity: Low
- Section: Versions checked on 2026-10-01
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:

```text
| Vite | 8.3 (Rolldown-based) |
```

- Proposed text:

```text
| Vite | 8.3.5 (Rolldown-based is not stated. Description: "Native-ESM powered web dev build tool") |
```

### FACT-003
- Severity: Med
- Section: Versions checked on 2026-10-01
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:

```text
| Playwright | 1.63.0 (bundles MCP) |
```

- Proposed text:

```text
| Playwright | 1.64.1 (whether this package bundles MCP is not stated) |
```

### FACT-004
- Severity: Low
- Section: Versions checked on 2026-10-01
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:

```text
| MCP Python SDK | v2.2.0 |
```

- Proposed text:

```text
| MCP Python SDK | 2.3.0 |
```

### FACT-006
- Severity: Med
- Section: Free-quota budget
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:

```text
Neon free compute: 100 CU-hours per month.
```

- Proposed text:

```text
Neon free compute: 100 CU-hours/project. "per month" is not stated.
```

- Current text (Deploy track):

```text
which likely exceeds Neon's 100 CU-hours per month.
```

- Proposed text:

```text
which likely exceeds Neon's 100 CU-hours/project. "per month" is not stated.
```

### FACT-007
- Severity: Low
- Section: Free-quota budget
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:

```text
Render cold start 30 to 60 s
```

- Proposed text:

```text
Render cold start is about one minute. "30 to 60" seconds is not stated
```

- Current text (Deploy track):

```text
They take 30 to 60 s, which is longer than GitHub's 10 s webhook timeout.
```

- Proposed text:

```text
They take about one minute, which is longer than GitHub's 10 s webhook timeout. "30 to 60" seconds is not stated.
```

### FACT-008
- Severity: Low
- Section: Versions checked on 2026-10-01
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:

```text
(Rolldown-based)
```

- Proposed text:

```text
(Rolldown-based is not stated. Description: "Native-ESM powered web dev build tool")
```

Same Vite cell as FACT-002. One replacement: `| Vite | 8.3.5 (Rolldown-based is not stated. Description: "Native-ESM powered web dev build tool") |`.

### FACT-009
- Severity: Low
- Section: Versions checked on 2026-10-01; Phase map; Risk register (top 5)
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:

```text
(bundles MCP)
```

- Proposed text:

```text
(whether this package bundles MCP is not stated)
```

Same Playwright cell as FACT-003. One replacement: `| Playwright | 1.64.1 (whether this package bundles MCP is not stated) |`.

- Current text (Phase map):

```text
`locate()` MCP server on 2026-07-28
```

- Proposed text:

```text
`locate()` MCP server. Whether the pinned server implements spec 2026-07-28 is not stated
```

- Current text (Risk register (top 5)):

```text
Playwright MCP, with no confirmed 2026-07-28 support, may not work with an SDK-v2 client
```

- Proposed text:

```text
Playwright MCP may not work with an SDK-v2 client. Whether the pinned `@playwright/mcp` server or the MCP Python SDK implements spec 2026-07-28 is not stated
```

The MCP spec row stays. It states the changelog, which the fetched page states. It does not say the pinned server implements that spec.

### FACT-010
- Severity: Low
- Section: Versions checked on 2026-10-01
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:

```text
| OTel GenAI semconv | Development status, no stable release; moved to a dedicated repo in June 2026 |
```

- Proposed text:

```text
| OTel GenAI semconv | Development status: not stated. A stable release: not stated. June 2026: not stated. The dedicated-repo README says: "This repository extends the OpenTelemetry Semantic Conventions with GenAI-specific conventions." |
```

### FACT-013
- Severity: Low
- Section: Infrastructure
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:

```text
Linux runners have exposed `/dev/kvm` since Oct 2025, which allows Firecracker and gVisor tier measurements at no cost
```

- Proposed text:

```text
Linux runners exposing `/dev/kvm` since Oct 2025 is not stated on the Actions billing page
```

### PLAN-001
- Severity: Low
- Section: Phase map
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:

```text
**Total: about 556 h, 28 weeks of work, plus 2 buffer weeks: 30 weeks.** P9 adds 2 more.
```

- Proposed text:

```text
**Total: 556 h, the sum of the phase table, in 28 weeks of work plus 2 buffer weeks: 30 weeks.** P9 adds 2 more.
```

556 stays 556. 255 stays 255.

### PLAN-003
- Severity: Low
- Section: Risk register (top 5)
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:

```text
A spike task in P1 and a P2 T00 check.
```

- Proposed text:

```text
The spike is P1-T01. P1-T02 writes ADR-004 and holds the spec note.
```

### PLAN-007
- Severity: Med
- Section: Phase dependency graph
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:

```text
  P8 --> P9
  P3 -.-> P9
  P6 -.-> P9
```

- Proposed text:

```text
  P8 --> P9
  P3 -.-> P9
```

The dashed edge removed is `P6 -.-> P9`. No flow task is added. `P3 -.-> P9` stays.

### PLAN-008
- Severity: Med
- Section: Phase dependency graph
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:

```text
  P4 --> P6
  P5 --> P6
```

- Proposed text:

```text
  P55 --> P6
```

P6-T00 lists `P5.5-T17`. No P6 task lists a P4 id or a P5 id, so `P4 --> P6` and `P5 --> P6` go. `P55 --> P7` stays.

### PLAN-011
- Severity: Med
- Section: Risk register (top 5)
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:

```text
## Risk register (top 5)
```

- Proposed text:

```text
## Risk register
```

- Current text:

```text
| 5 | **Scope and fatigue at 20 h/wk for about 7 months** | A hard cut line after P6 (the deployed core); buffer weeks after P4 and P6 | The two buffer weeks, the cut list below |
```

- Proposed text:

```text
| 5 | **Scope and fatigue at 20 h/wk for about 7 months** | A hard cut line after P6 (the deployed core); buffer weeks after P4 and P6 | The two buffer weeks, the cut list below |
| 6 | **One laptop CPU.** The machine is a 13th-gen i7-13620H with 16 GB and no discrete GPU. Judge calibration and embeddings run on that CPU | P4-T13 and P2-T10 stay on this machine | P4-T13, P2-T10 |
```

Row 6 names the existing machine. No second computer is added. PLAN-013 adds row 7 on this same table.

### PLAN-012
- Severity: Med
- Section: Risk register (top 5)
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:

```text
**Free-tier quotas change or disappear.** GitHub Models was reportedly retired in July 2026
```

- Proposed text:

```text
**Free-tier quotas change or disappear.** GitHub Models was reportedly retired in July 2026. GitHub Actions minutes and public-repo policy are the single execution plane
```

### PLAN-013
- Severity: Low
- Section: Risk register (top 5)
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:

```text
| 5 | **Scope and fatigue at 20 h/wk for about 7 months** | A hard cut line after P6 (the deployed core); buffer weeks after P4 and P6 | The two buffer weeks, the cut list below |
```

- Proposed text:

```text
| 5 | **Scope and fatigue at 20 h/wk for about 7 months** | A hard cut line after P6 (the deployed core); buffer weeks after P4 and P6 | The two buffer weeks, the cut list below |
| 7 | **Langfuse Cloud Hobby is 50k units/month**, the default trace viewer. A full quota can drop traces the dashboard links | Phoenix is the scheduled swap | P5-T09, ADR-015 |
```

Keep row 6 from PLAN-011 and row 7 here. The 50k figure stays. The row points at the existing Phoenix swap.

### PLAN-014
- Severity: High
- Section: Cut list
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:

```text
3. **P5.5** (argus-skills)
```

- Proposed text:

```text
3. **P5.5** (argus-skills). Before this cut is taken, P6-T00's dependency moves off P5.5-T17 and P7-T07's dependency moves off P5.5-T10
```

The 28 h stays inside the 556 h core total.

### PLAN-015
- Severity: Med
- Section: Cut list
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:

```text
4. **The Firecracker tier**, reduced to an ADR plus a gVisor measurement only
```

- Proposed text:

```text
4. **The Firecracker tier**, reduced to an ADR plus a gVisor measurement only. Before this cut is taken, P7-T13's acceptance allows an empty row C
```

The 3 h stays inside the 556 h core total.

### PLAN-016
- Severity: Med
- Section: Cut list
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:

```text
5. **MRTR elicitation**, replaced by plain GitHub review comments (P6-T10 is already the fallback)
```

- Proposed text:

```text
5. **MRTR elicitation**, replaced by plain GitHub review comments (P6-T10 is already the fallback). Before this cut is taken, P6-T18 depends only on P6-T10
```

The 3 h stays inside the 556 h core total.

### PLAN-017
- Severity: Med
- Section: Cut list
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:

```text
2. **P8 multi-tenancy**, down to a single-tenant App
```

- Proposed text:

```text
2. **P8 multi-tenancy**, down to a single-tenant App. The cut is P8-T07, P8-T14, and P8-T21. Before this cut is taken, P8-T20 drops P8-T07 from its dependency list and drops budgets from its test assertion
```

The 6 h stays inside the 556 h core total.

### PLAN-018
- Severity: Med
- Section: Risk register (top 5)
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:

```text
at least two hosts per role; a local Ollama fallback for the judge and embeddings
```

- Proposed text:

```text
a local Ollama host for the judge and for embeddings, the roles that already have a second host
```

No fixer host and no cheap-tier host are added.

### PLAN-019
- Severity: Med
- Section: Risk register (top 5)
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:

```text
If it fails, use Playwright directly as a tool
```

- Proposed text:

```text
If it is no-go, the mitigation is writing ADR-004. A direct-Playwright implementation is unscheduled
```

### PLAN-021
- Severity: Med
- Section: Metrics contract
- Owner: [ME]
- Hours delta: 0
- Replacement or cut: none

Learning rules already list four numbers: resolve rate, tokens/bug, $-equivalent, and p50/p95 latency. That sentence stays. The contract below is what changes. No JSON field is added.

- Current text:

```text
Every phase reports the same five numbers, on the same evaluation set, against the previous phase.
```

- Proposed text:

```text
Every phase reports the same four numbers listed in the learning rules (resolve rate, tokens/bug, $-equivalent, and p50/p95 latency), on the same evaluation set, against the previous phase.
```

- Current text:

```text
| Quota share/bug | For each provider and model used, the bug's requests and tokens divided by that provider's measured daily cap (from `docs/quotas.md`); the binding (largest) share is reported |
| Latency p50 and p95 | Wall-clock time from task start to final patch. Time spent waiting for quota to reset is excluded and reported separately |
```

- Proposed text:

```text
| Latency p50 and p95 | Wall-clock time from task start to final patch. Time spent waiting for quota to reset is excluded and reported separately |
```

Quota share is dropped as a required fifth number.

### PLAN-025
- Severity: Med
- Section: Architecture
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:

```text
  FIX --> BOK
  BOK --> VERIFY
  VERIFY --> JUDGE
```

- Proposed text:

```text
  FIX --> VERIFY
  VERIFY --> BOK
  JUDGE -- "does not override a passed check run" --> BOK
```

Checks run first. Best-of-k stays the selector node. The judge edge feeds that selector and does not add a hard reject-on-clean-checks gate. `JUDGE --> LEDGER` and `VERIFY --> GH` stay.

Hours and tasks in this file: unchanged.
