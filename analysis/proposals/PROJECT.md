# PROJECT.md text proposals

Phase 4 planning review. Each block replaces only the quoted span in `PROJECT.md`. No task, risk that needs new build work, or hour is added. Source files are not edited by this proposal.

PLAN-011 and PLAN-013 each add one row to the Risks table. Row 6 is the laptop CPU. Row 7 is the Langfuse cap. Both rows stay.

### FACT-005
- Severity: High
- Section: Models
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:

```text
| Cheap tier (repro, localize, summaries) | gpt-oss-20b, Qwen3.6-27B | Groq free tier: 1,000 requests/day and 200k tokens/day per model. Cached tokens do not count against the cap | Prompt caching becomes a quota lever, not only a cost lever |
```

- Proposed text:

```text
| Cheap tier (repro, localize, summaries) | openai/gpt-oss-20b, qwen/qwen3.8-27b | Developer-plan base limits, organization level: RPM 30, RPD 1K, TPM 8K, TPD 200K. Cached tokens do not count. "free tier" is not stated. Qwen3.6-27B is not stated | Prompt caching becomes a quota lever, not only a cost lever |
```

- Current text (Phases):

```text
free-tier caps (for example Groq's 200k tokens/day per model)
```

- Proposed text:

```text
Developer-plan organization limits (for example Groq openai/gpt-oss-20b and qwen/qwen3.8-27b at RPM 30, RPD 1K, TPM 8K, TPD 200K; cached tokens do not count)
```

- Current text (Known free-tier collisions):

```text
Groq's published cap in the plan is 1,000 requests/day and 200k tokens/day per model, with cached tokens excluded.
```

- Proposed text:

```text
Groq's Developer-plan organization limits for openai/gpt-oss-20b and qwen/qwen3.8-27b are RPM 30, RPD 1K, TPM 8K, and TPD 200K. Cached tokens do not count. "free tier" is not stated. Qwen3.6-27B is not stated.
```

### FACT-006
- Severity: Med
- Section: P6 — flow (weeks 22–24)
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:

```text
compared with the 100 CU-hour monthly free limit.
```

- Proposed text:

```text
compared with 100 CU-hours/project. "per month" is not stated.
```

- Current text (Known free-tier collisions):

```text
which likely exceeds Neon's 100 CU-hours per month.
```

- Proposed text:

```text
which likely exceeds Neon's 100 CU-hours/project. "per month" is not stated.
```

- Current text (Known free-tier collisions):

```text
Neon free compute is 100 CU-hours per month.
```

- Proposed text:

```text
Neon free compute is 100 CU-hours/project. "per month" is not stated.
```

### FACT-011
- Severity: Low
- Section: Models
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:

```text
| Fixer (strong) | Devstral 2 / Devstral Small 2 (Mistral family; Apache-2.0 for Small) | Mistral free tier | A coding-agent model. Mistral reports 68–72% on SWE-bench Verified. That figure is their claim, not a number this project has measured |
```

- Proposed text:

```text
| Fixer (strong) | Devstral 2 / Devstral Small 2 | Mistral free tier | A coding-agent model. The Mistral pricing page does not state these names, Apache-2.0 for Small, or 68–72% on SWE-bench Verified. No replacement number is written here |
```

### FACT-012
- Severity: Low
- Section: Infrastructure
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:

```text
OTLP to Langfuse Cloud Hobby (free, MIT-licensed product, 50k units/month).
```

- Proposed text:

```text
OTLP to Langfuse Cloud Hobby (free, 50k units/month). MIT is not stated on the pricing page. The pricing page says Langfuse is open source and can be self-hosted for free.
```

### PLAN-001
- Severity: Low
- Section: Phases
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:

```text
Hours are at 20 h/week. Core work is P0 through P8: **556 hours, 255 tasks, 28 weeks of work plus 2 buffer weeks, so 30 weeks.**
```

- Proposed text:

```text
Hours are at 20 h/week. Core work is P0 through P8: **556 hours, 255 tasks**, the sum of the phase table, in 28 weeks of work plus 2 buffer weeks, so 30 weeks.
```

556 stays 556. 255 stays 255.

### PLAN-002
- Severity: Low
- Section: Week by week
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:

```text
Weeks are 20 hour bins in task order. A phase may start in the tail of the previous phase's last week. Buffer weeks have no scheduled tasks. The exact checklist is [`TASKS.md`](TASKS.md).
```

- Proposed text:

```text
Weeks are 20 hour bins in task order, and a week can run up to 3 h over 20 because a task is placed in the week it starts. Weeks under 20 h are week 9 (19 h), week 10 (19 h), week 15 (19 h), week 19 (18 h), week 20 (19 h), week 27 (19 h), week 31 (19 h), and week 32 (16 h). A phase may start in the tail of the previous phase's last week. Buffer weeks have no scheduled tasks. The exact checklist is [`TASKS.md`](TASKS.md).
```

The 556 h and 596 h totals stay as they are. Week headers in `TASKS.md` already match their checkbox sums.

### PLAN-011
- Severity: Med
- Section: Risks
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:

```text
| 5 | Scope and fatigue at 20 h/week for about seven months | Hard cut after P6. Buffer weeks after P4 and after P6. The cut list below |
```

- Proposed text:

```text
| 5 | Scope and fatigue at 20 h/week for about seven months | Hard cut after P6. Buffer weeks after P4 and after P6. The cut list below |
| 6 | One laptop CPU. The machine is a 13th-gen Intel i7-13620H with 16 GB RAM and no discrete GPU. Judge calibration and embeddings run on that CPU | P4-T13 and P2-T10 stay on this machine |
```

The Constraints sentence already names that machine. This row points at P4-T13 and P2-T10. No second computer is added.

### PLAN-012
- Severity: Med
- Section: Risks
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:

```text
Free-tier quotas change or disappear. GitHub Models was reportedly retired in July 2026
```

- Proposed text:

```text
Free-tier quotas change or disappear. GitHub Models was reportedly retired in July 2026. GitHub Actions minutes and public-repo policy are the single execution plane
```

### PLAN-013
- Severity: Low
- Section: Risks
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:

```text
| 5 | Scope and fatigue at 20 h/week for about seven months | Hard cut after P6. Buffer weeks after P4 and after P6. The cut list below |
```

- Proposed text:

```text
| 5 | Scope and fatigue at 20 h/week for about seven months | Hard cut after P6. Buffer weeks after P4 and after P6. The cut list below |
| 7 | Langfuse Cloud Hobby at 50k units/month is the default trace viewer. A full quota can drop the traces the dashboard links | Phoenix is the scheduled swap. P5-T09, ADR-015 |
```

Keep row 6 from PLAN-011 and row 7 here. The 50k figure stays.

### PLAN-018
- Severity: Med
- Section: Risks
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:

```text
at least two hosts per role, local Ollama for the judge and embeddings
```

- Proposed text:

```text
a local Ollama host for the judge and for embeddings, the roles that already have a second host
```

No fixer host and no cheap-tier host are added.

### PLAN-020
- Severity: Med
- Section: Metrics contract
- Owner: [ME]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```text
| $-equivalent | Tokens times published list prices from `prices.json` (source URL and date per model). A comparison unit, not money spent. Cached tokens use the published cached rate when one exists, otherwise the input rate, and the choice is stated |
```

- Proposed text:

```text
| $-equivalent | Tokens times published list prices from `prices.json` (source URL and date per model). A comparison unit, not money spent. Cached tokens use the published cached rate when one exists, otherwise the input rate, and the choice is stated. P0 through P4 leave this cell as "—" until P5-T11, and "filled in" does not cover this column |
```

### PLAN-021
- Severity: Med
- Section: Constraints that shape the design; Metrics contract
- Owner: [ME]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```text
- **Every phase ends with an ablation** and reports the same five metrics against the previous phase.
```

- Proposed text:

```text
- **Every phase ends with an ablation** and reports resolve rate, tokens/bug, $-equivalent, and p50/p95 latency against the previous phase.
```

- Current text:

```text
Every phase reports the same five numbers, on the same evaluation set, against the previous phase.
```

- Proposed text:

```text
Every phase reports the same four numbers (resolve rate, tokens/bug, $-equivalent, and p50/p95 latency), on the same evaluation set, against the previous phase.
```

- Current text:

```text
| Quota share/bug | The bug's requests and tokens divided by that provider's measured daily cap. The binding (largest) share is reported |
| Latency p50 and p95 | Wall-clock from task start to final patch. Time waiting for a quota reset is excluded and reported separately |
```

- Proposed text:

```text
| Latency p50 and p95 | Wall-clock from task start to final patch. Time waiting for a quota reset is excluded and reported separately |
```

Quota share is dropped as a required fifth number. No JSON field is added.

### PLAN-022
- Severity: Low
- Section: Monorepo
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:

```text
| `argus-core` | Python | P0 | Ticket, Task, and Trajectory types; OpenAI-compatible model client; quota ledger; OTel helpers |
```

- Proposed text:

```text
| `argus-core` | Python | P0 | Ticket, Task, and Trajectory types; OpenAI-compatible model client; quota ledger |
```

OTel stays on P5-T06, the task that already schedules it.

### PLAN-025
- Severity: Med
- Section: What a finished run looks like; P4 — verify (weeks 12–16)
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:

```text
4. **Verify.** Cheap deterministic checks run first: pixel diff, overflow, axe-core (new violations only), and new console errors. A cross-family vision judge (Gemma, not the Mistral fixer) then asks whether the fix matches the ticket without collateral change. The judge ships as a hard gate only if Krippendorff's alpha against hand labels reaches 0.80. Otherwise it stays advisory, and that decision is written down. Best-of-k (k = 1, 3, 5) picks among candidate patches.
```

- Proposed text:

```text
4. **Verify.** Cheap deterministic checks run first: pixel diff, overflow, axe-core (new violations only), and new console errors. A cross-family vision judge (Gemma, not the Mistral fixer) asks whether the fix matches the ticket without collateral change. The judge does not override a passed check run. Best-of-k (k = 1, 3, 5) sits inside the selector and picks among candidate patches.
```

- Current text:

```text
Decide whether a patch fixed the bug and broke nothing else. Deterministic checks first, then a calibrated judge, then a measurement of what extra samples buy.
```

- Proposed text:

```text
Decide whether a patch fixed the bug and broke nothing else. Deterministic checks run first. The judge does not override a passed check run. Best-of-k sits inside the selector.
```

- Current text:

```text
If the budget runs out below 0.80, ADR-013 records the shortfall and the judge is advisory only. A same-family Mistral vision judge is the self-preference control. Best-of-k runs at k = 1, 3, and 5.
```

- Proposed text:

```text
The judge does not override a passed check run. ADR-013 records the measured alpha. A same-family Mistral vision judge is the self-preference control. Best-of-k sits inside the selector and runs at k = 1, 3, and 5.
```

No hard reject-on-clean-checks gate is added. The alpha target sentence above this quote stays.

Hours and tasks in this file: unchanged.
