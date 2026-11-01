# Phase 4 proposal: architecture.html

Wording only. Card text changes where it disagrees with P6 or P4.

### PLAN-023
- Severity: Med
- Section: card `o-sm`
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:
```
    ['o-sm','list','Ticket state machine','repro → locate → fix → verify → PR','p6'],
```
- Proposed text:
```
    ['o-sm','list','Ticket state machine','repro → fix → verify → PR → awaiting-qa → done','p6'],
```

### PLAN-024
- Severity: Med
- Section: card `a-pr`
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:
```
    ['a-pr','pr','Open PR','patch + verdict + trajectory','p8'],
```
- Proposed text:
```
    ['a-pr','pr','Open PR','P6-T21 opens the PR; P8-T09 is the tenant-workflow path that calls that same opener.','p6'],
```

### PLAN-025
- Severity: Med
- Section: card `a-ver`
- Owner: not specified
- Hours delta: 0
- Replacement or cut: none
- Current text:
```
    ['a-ver','check','Verifier','checks first · judge second · fail closed','p4'],
```
- Proposed text:
```
    ['a-ver','check','Verifier','checks run first; the judge does not override a passed check run; best-of-k stays inside the selector','p4'],
```

Hours and tasks in this file: unchanged. No component added or removed.
