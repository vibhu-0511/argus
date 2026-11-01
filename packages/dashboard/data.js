window.ARGUS_RUNS = [
 {
  "run_id": "p3-a-claude-baseline",
  "created_at": "2026-11-01T12:00:00Z",
  "agent": {
   "name": "p3-variant-a-claude-session",
   "model": "claude-session",
   "host": "claude-session",
   "params": {
    "source": "packages/fix-loop/runs/p3-a-claude-results.json",
    "token_source": "chars/4 estimate",
    "latency": "not recorded"
   }
  },
  "counts": {
   "resolved": 20,
   "unresolved": 9,
   "excluded": 1,
   "error": 0
  },
  "resolve_rate": {
   "successes": 20,
   "total": 29,
   "rate": 0.689655,
   "ci_low": 0.507695,
   "ci_high": 0.827246,
   "interval": "wilson95"
  },
  "tokens": {
   "total": {
    "tokens_in": 5884209,
    "tokens_out": 5946,
    "tokens_cached": 0
   },
   "per_task": {
    "tokens_in": 202903.759,
    "tokens_out": 205.034,
    "tokens_cached": 0.0
   }
  },
  "latency_s": {
   "p50": null,
   "p95": null,
   "n": 0
  },
  "trajectory_metrics": null,
  "$_equivalent": null,
  "source": "packages/eval/fixtures/gate/baseline.json",
  "made_up": false
 },
 {
  "run_id": "worse-made-up",
  "created_at": "2026-11-01T12:00:00Z",
  "agent": {
   "name": "p3-variant-a-claude-session-worse",
   "model": "claude-session",
   "host": "claude-session",
   "params": {
    "source": "MADE UP: baseline with 8 resolved tasks flipped to unresolved and tokens_in x1.6",
    "token_source": "made up"
   }
  },
  "counts": {
   "resolved": 12,
   "unresolved": 17,
   "excluded": 1,
   "error": 0
  },
  "resolve_rate": {
   "successes": 12,
   "total": 29,
   "rate": 0.413793,
   "ci_low": 0.255129,
   "ci_high": 0.592625,
   "interval": "wilson95"
  },
  "tokens": {
   "total": {
    "tokens_in": 9414733,
    "tokens_out": 5946,
    "tokens_cached": 0
   },
   "per_task": {
    "tokens_in": 324645.966,
    "tokens_out": 205.034,
    "tokens_cached": 0.0
   }
  },
  "latency_s": {
   "p50": null,
   "p95": null,
   "n": 0
  },
  "trajectory_metrics": null,
  "$_equivalent": null,
  "source": "packages/eval/fixtures/gate/worse.json",
  "made_up": true
 }
];
