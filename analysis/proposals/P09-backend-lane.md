# Proposal for `phases/P09-backend-lane.md`

Plan text only. No new tasks. No hour changes. No flow task is added.

### PLAN-005
- Severity: Low
- Section: budget line
- Owner: [CLAUDE]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
**Budget:** about 40 h · **Weeks:** +2 weeks after P8 (first on the cut list) · **Packages:** reuses `argus-core`, `fix-loop`, `verify`, `eval`, `flow`; adds a small backend target and lane-specific tools
```

- Proposed text:

```
**Budget:** about 40 h · **Weeks:** the week-30 tail, then weeks 31–32 (first on the cut list) · **Packages:** reuses `argus-core`, `fix-loop`, `verify`, `eval`, `flow`; adds a small backend target and lane-specific tools
```

The weeks line names the week-30 tail. About 40 h stays.

### PLAN-007
- Severity: Med
- Section: Goal
- Owner: [CLAUDE]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
Run a second lane, from a Sentry-style error event to a failing pytest to a verified fix, by reusing the P3 to P6 parts instead of rebuilding them, and measure how much was reused.
```

- Proposed text:

```
Run a second lane, from a Sentry-style error event to a failing pytest to a verified fix, as a local loop, and measure how much was reused.
```

The lane stays a local loop. No flow task is added.

### PLAN-022
- Severity: Low
- Section: Deploy checkpoint
- Owner: [CLAUDE]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
The golden-fix run for the backend tasks joins the existing GitHub Actions jobs, and the lane's results appear as a second series on the GitHub Pages dashboard. No new hosting.
```

- Proposed text:

```
The golden-fix run for the backend tasks joins the existing GitHub Actions jobs. No new hosting.
```

The dashboard second-series sentence is deleted. No P9 task is added for the dashboard.

Hours and tasks in this file: unchanged.
