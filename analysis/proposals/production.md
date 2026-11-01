# Phase 4 proposal: production.html

Wording only. Rail and step text change where they disagree with P6 or P4.

### PLAN-023
- Severity: Med
- Section: RAIL
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:
```
  ['queued', 'Queued'],
  ['repro', 'Repro'],
  ['locate', 'Locate'],
  ['fix', 'Fix'],
  ['verify', 'Verify'],
  ['pr', 'PR open'],
  ['qa', 'Awaiting QA'],
  ['done', 'Done'],

<footer>Worked example of the production path in PLAN.md and architecture.html. States match the P6 machine: repro → locate → fix → verify → PR, then the QA wait. The planner variant is the P8 ablation, kept only if it wins on both success and tokens.</footer>

job: repro → locate → fix → verify`,

    checkpoint: 'The failing script and the verdict are the step result. State can move to locate.',

    rail: 'locate',
```
- Proposed text:
```
  ['queued', 'Queued'],
  ['repro', 'Repro'],
  ['fix', 'Fix'],
  ['verify', 'Verify'],
  ['pr', 'PR open'],
  ['qa', 'Awaiting QA'],
  ['done', 'Done'],

<footer>Worked example of the production path in PLAN.md and architecture.html. States match the P6 machine: repro → fix → verify → PR → awaiting-qa → done. The planner variant is the P8 ablation, kept only if it wins on both success and tokens.</footer>

job: repro → fix → verify`,

    checkpoint: 'The failing script and the verdict are the step result. State can move to fix.',

    rail: 'fix',
```

### PLAN-024
- Severity: Med
- Section: Open one pull request
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:
```
summary: 'The workflow opens the PR with find-or-create on you/shop-ui#142. The body links 142-fix.html, the per-check verdict, and the trajectory. The Actions artifact is the patch that gets committed.',

'The PR body links the before-and-after report, the checks, and the judge note.',

body:
  report: 142-fix.html
  pixel pass · overflow pass
  axe pass · console pass
  judge: intent met
  trajectory: 142.jsonl
```
- Proposed text:
```
summary: 'P6-T21 opens the PR; P8-T09 is the tenant-workflow path that calls that same opener. The workflow opens the PR with find-or-create on you/shop-ui#142. The body links the per-check verdict and the trajectory. The Actions artifact is the patch that gets committed.',

'The PR body links the checks and the judge note.',

body:
  pixel pass · overflow pass
  axe pass · console pass
  judge: intent met
  trajectory: 142.jsonl
```

### PLAN-025
- Severity: Med
- Section: Checks first, then the judge
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:
```
'The judge is Gemma, a different family from the fixer. If agreement with human labels is below the bar, its note is advisory and the checks still decide.',
'Best-of-k (1, 3, or 5) is a cost knob in front of this gate. The selector still has to pass the same checks.',

judge: intent met
       (cannot override a failed check)
```
- Proposed text:
```
'The judge is Gemma, a different family from the fixer. Checks run first; the judge does not override a passed check run; best-of-k stays inside the selector.',

judge: intent met
       (does not override a passed check run)
```

### PLAN-026
- Severity: Low
- Section: Checks first, then the judge; Patch inside the sandbox
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:
```
'Order: pixel diff (with region masks) → overflow → axe, new violations only → console, new errors only.',

  console:  pass   (no new errors)

'Gates, read-only: build, typecheck, lint, unit tests. A failed gate returns a typed error and the loop continues until a stop condition.',

run_gates: build pass · tsc pass ·
           lint pass · unit pass
```
- Proposed text:
```
'Order: pixel diff (with region masks) → overflow → axe, new violations only → console, new errors and warnings.',

  console:  pass   (no new errors or warnings)

'Gates, read-only: build, typecheck, lint, unit tests and bench checks. A failed gate returns a typed error and the loop continues until a stop condition.',

run_gates: build pass · tsc pass ·
           lint pass · unit pass · bench pass
```

Hours and tasks in this file: unchanged. No component added or removed.
