# Proposal for `phases/P08-argus-app.md`

Plan text only. No new tasks. No hour changes. P8-T02 does not move.

### RISK-003
- Severity: High
- Section: P8-T04
- Owner: [CLAUDE]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P8-T04 | Write the reusable workflow that runs the agent job in the tenant's repo | [CLAUDE] | build | 3 | P8-T02, P6-T04 | A tenant workflow of five lines calls it with `workflow_call` and runs repro, fix and verify; no secret is passed except through the tenant's own secrets |
```

- Proposed text:

```
| P8-T04 | Write the reusable workflow that runs the agent job in the tenant's repo | [CLAUDE] | build | 3 | P8-T02, P6-T04 | A tenant workflow of five lines calls it with `workflow_call` and runs repro, fix and verify; the agent step's environment has no `GITHUB_TOKEN`; ADR-026 names whether the tenant workflow token or the App installation token is the principal that pushes; no secret is passed except through the tenant's own secrets |
```

ADR-026 stays the [ME] decision.

### RISK-004
- Severity: High
- Section: P8-T09; P8-T20
- Owner: [PAIR] (P8-T09); [CLAUDE] (P8-T20)
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P8-T09 | Build PR creation with verdict, trajectory link and before and after screenshots | [PAIR] | build | 3 | P8-T08, P4-T22 | The PR body has the verifier verdict, the judge label, a trajectory link and two screenshots; re-running updates the same PR |
```

```
| P8-T20 | Add CI job for app tests and reusable-workflow lint, no LLM | [CLAUDE] | deploy | 2 | P8-T07, P8-T04 | Workflow green; lint passes on the reusable workflow; tests cover token minting, label permissions and budgets |
```

- Proposed text:

```
| P8-T09 | Build PR creation with verdict, trajectory link and before and after screenshots | [PAIR] | build | 3 | P8-T08, P4-T22 | The PR body has the verifier verdict, the judge label, a trajectory link and two screenshots; the PR is built through the API with title and body as JSON fields; a fixture title containing `$(...)` is not executed; one stable branch; one creator that is not the agent; draft until QA; no PR when the patch is empty; a lookup error leaves the existing PR untouched; re-running updates the same PR |
```

```
| P8-T20 | Add CI job for app tests and reusable-workflow lint, no LLM | [CLAUDE] | deploy | 2 | P8-T04 when the multi-tenancy cut is taken; otherwise P8-T07, P8-T04 | Workflow green; lint passes on the reusable workflow; tests cover token minting and label permissions; the budget assertion is included only when P8-T07 is kept; the PR is built through the API with title and body as JSON fields; a fixture title containing `$(...)` is not executed; ADR-027 says the backport head is a branch the tenant workflow is allowed to test |
```

Delta: P8-T09 and P8-T20 build the PR through the API with title and body as JSON fields, and a fixture title containing `$(...)` is not executed. The find-or-create clauses on P8-T09 are RISK-007. The dependency and budget words on P8-T20 are PLAN-017. The backport-head clause is EDGE-013. If those are accepted, use these rows.

### RISK-007
- Severity: Med
- Section: P8-T09
- Owner: [PAIR]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P8-T09 | Build PR creation with verdict, trajectory link and before and after screenshots | [PAIR] | build | 3 | P8-T08, P4-T22 | The PR body has the verifier verdict, the judge label, a trajectory link and two screenshots; re-running updates the same PR |
```

- Proposed text:

```
| P8-T09 | Build PR creation with verdict, trajectory link and before and after screenshots | [PAIR] | build | 3 | P8-T08, P4-T22 | The PR body has the verifier verdict, the judge label, a trajectory link and two screenshots; the PR is built through the API with title and body as JSON fields; a fixture title containing `$(...)` is not executed; one stable branch; one creator that is not the agent; draft until QA; no PR when the patch is empty; a lookup error leaves the existing PR untouched; re-running updates the same PR |
```

Delta: one stable branch, one creator that is not the agent, draft until QA, no PR when the patch is empty, and a lookup error leaves the existing PR untouched. The JSON fields and the `$(...)` fixture are RISK-004. If both are accepted, use this row.

### EDGE-012
- Severity: Med
- Section: P8-T23
- Owner: [ME]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P8-T23 | Break it: force a cherry-pick conflict in a backport | [ME] | test | 2 | P8-T10 | The bot comments the conflict and leaves branches untouched; written up |
```

```
3. **Backport conflict (P8-T23).** *Induced failure:* backport a fix onto a branch that has diverged. *Expected signal:* a comment describing the conflict; no force-push. *Fix:* abort the cherry-pick, leave the branch alone and hand over to a human.
```

- Proposed text:

```
| P8-T23 | Break it: force a cherry-pick conflict in a backport | [ME] | test | 2 | P8-T10 | The bot comments the conflict and leaves branches untouched; the test fails on commit-markers, `theirs`, and force-push of the bot branch; it refuses a tenant conflict command and a checkout of the PR head under the installation token; a second run finds the existing PR or no-ops; written up |
```

```
3. **Backport conflict (P8-T23).** *Induced failure:* backport a fix onto a branch that has diverged. *Expected signal:* a comment describing the conflict; the test fails on commit-markers, `theirs`, and force-push of the bot branch. *Fix:* abort the cherry-pick, leave the branch alone, refuse a tenant conflict command and a checkout of the PR head under the installation token, and on a second run find the existing PR or no-op.
```

### EDGE-013
- Severity: Med
- Section: P8-T13; P8-T20
- Owner: [ME] (P8-T13); [CLAUDE] (P8-T20)
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P8-T13 | Write ADR-027: Tenancy via a reusable workflow in the tenant's repo | [ME] | doc | 1 | P8-T06 | ADR compares running in the tenant repo vs on your servers on quota, trust boundary and cost |
```

```
| P8-T20 | Add CI job for app tests and reusable-workflow lint, no LLM | [CLAUDE] | deploy | 2 | P8-T07, P8-T04 | Workflow green; lint passes on the reusable workflow; tests cover token minting, label permissions and budgets |
```

- Proposed text:

```
| P8-T13 | Write ADR-027: Tenancy via a reusable workflow in the tenant's repo | [ME] | doc | 1 | P8-T06 | ADR compares running in the tenant repo vs on your servers on quota, trust boundary and cost, and says the backport head is a branch the tenant workflow is allowed to test |
```

```
| P8-T20 | Add CI job for app tests and reusable-workflow lint, no LLM | [CLAUDE] | deploy | 2 | P8-T04 when the multi-tenancy cut is taken; otherwise P8-T07, P8-T04 | Workflow green; lint passes on the reusable workflow; tests cover token minting and label permissions; the budget assertion is included only when P8-T07 is kept; the PR is built through the API with title and body as JSON fields; a fixture title containing `$(...)` is not executed; ADR-027 says the backport head is a branch the tenant workflow is allowed to test |
```

Delta: ADR-027 says the backport head is a branch the tenant workflow is allowed to test. The JSON fixture is RISK-004. The dependency and budget words are PLAN-017. If those are accepted, use this P8-T20 row.

### PLAN-017
- Severity: Med
- Section: P8-T20
- Owner: [CLAUDE]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P8-T20 | Add CI job for app tests and reusable-workflow lint, no LLM | [CLAUDE] | deploy | 2 | P8-T07, P8-T04 | Workflow green; lint passes on the reusable workflow; tests cover token minting, label permissions and budgets |
```

- Proposed text:

```
| P8-T20 | Add CI job for app tests and reusable-workflow lint, no LLM | [CLAUDE] | deploy | 2 | P8-T04 when the multi-tenancy cut is taken; otherwise P8-T07, P8-T04 | Workflow green; lint passes on the reusable workflow; tests cover token minting and label permissions; the budget assertion is included only when P8-T07 is kept; the PR is built through the API with title and body as JSON fields; a fixture title containing `$(...)` is not executed; ADR-027 says the backport head is a branch the tenant workflow is allowed to test |
```

Delta: drop P8-T07 from the dependency and from the budget assertion when the multi-tenancy cut is taken. The −6 h stays unbooked. P8-T07 stays in this file. The JSON fixture is RISK-004. The backport-head clause is EDGE-013. If those are accepted, use this row.

Hours and tasks in this file: unchanged.
