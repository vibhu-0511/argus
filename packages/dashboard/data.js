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
  "source": "packages/eval/results/baseline.json",
  "made_up": false
 },
 {
  "run_id": "t20-multimodal-claude-session",
  "created_at": "2026-11-01T19:57:11Z",
  "agent": {
   "name": "claude-session",
   "model": "claude-session",
   "host": "local",
   "params": {}
  },
  "counts": {
   "resolved": 7,
   "unresolved": 5,
   "excluded": 3,
   "error": 0
  },
  "resolve_rate": {
   "successes": 7,
   "total": 12,
   "rate": 0.583333,
   "ci_low": 0.319507,
   "ci_high": 0.806743,
   "interval": "wilson95"
  },
  "tokens": {
   "total": {
    "tokens_in": 0,
    "tokens_out": 0,
    "tokens_cached": 0
   },
   "per_task": {
    "tokens_in": 0.0,
    "tokens_out": 0.0,
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
  "source": "packages/eval/results/p5-t20-multimodal.json",
  "made_up": false
 },
 {
  "run_id": "t20-multimodal-argus",
  "created_at": "2026-11-02T13:45:03Z",
  "agent": {
   "name": "argus-fix-loop-claude-session",
   "model": "claude-sonnet-5-5",
   "host": "claude-session",
   "params": {
    "claude_session": true,
    "worker_model": "sonnet",
    "tools": [
     "read_file",
     "list_dir",
     "search",
     "ast_grep",
     "edit",
     "run_cmd",
     "submit"
    ],
    "run_cmd": "read-only git and node --check only, no Docker",
    "fix_context": {
     "strategy": "cap",
     "budget": 32000
    },
    "step_cap": 20,
    "token_cap": 400000,
    "token_source": "chars/4 estimate of the messages; excludes subagent harness overhead"
   }
  },
  "counts": {
   "resolved": 7,
   "unresolved": 7,
   "excluded": 1,
   "error": 0
  },
  "resolve_rate": {
   "successes": 7,
   "total": 14,
   "rate": 0.5,
   "ci_low": 0.267989,
   "ci_high": 0.732011,
   "interval": "wilson95"
  },
  "tokens": {
   "total": {
    "tokens_in": 328981,
    "tokens_out": 3130,
    "tokens_cached": 0
   },
   "per_task": {
    "tokens_in": 23498.643,
    "tokens_out": 223.571,
    "tokens_cached": 0.0
   }
  },
  "latency_s": {
   "p50": 945.25,
   "p95": 1604.86,
   "n": 14
  },
  "trajectory_metrics": {
   "trajectories": 14,
   "steps": {
    "total": 96,
    "mean": 6.857143,
    "median": 6.5
   },
   "tool_error_rate": {
    "value": 0.083333,
    "num": 8,
    "den": 96
   },
   "redundant_call_rate": {
    "value": 0.0,
    "num": 0,
    "den": 83
   },
   "stuck_rate": {
    "value": 0.071429,
    "num": 1,
    "den": 14
   },
   "recover_after_gate_failure_rate": {
    "value": null,
    "num": 0,
    "den": 0
   }
  },
  "$_equivalent": 0.689262,
  "source": "packages/eval/results/p5-t20-multimodal-argus.json",
  "made_up": false
 },
 {
  "run_id": "breakit-C-claude-cheap-fix",
  "created_at": "2026-11-01T21:09:16Z",
  "agent": {
   "name": "breakit-C-claude-cheap-fix",
   "model": "claude-sonnet-5-5",
   "host": "claude-session",
   "params": {
    "out_dir": "C:\\Users\\vibha\\Downloads\\data\\personal\\argus\\.claude\\worktrees\\p5-tasks-waves-45bbcf\\packages\\eval\\runs\\t14\\C",
    "claude_session": true,
    "token_source": "chars/4 estimate of the messages; excludes subagent harness overhead",
    "worker_models": {
     "cheap": "haiku",
     "strong": "sonnet"
    },
    "stages": {
     "repro": "cheap",
     "localize": "cheap",
     "fix": "cheap"
    },
    "fix_context": {
     "strategy": "cap",
     "budget": 32000
    },
    "repro_cap": 3,
    "latency": "wall clock of the whole task including coordinator waits; several tasks ran at once"
   }
  },
  "counts": {
   "resolved": 13,
   "unresolved": 16,
   "excluded": 0,
   "error": 0
  },
  "resolve_rate": {
   "successes": 13,
   "total": 29,
   "rate": 0.448276,
   "ci_low": 0.284129,
   "ci_high": 0.624523,
   "interval": "wilson95"
  },
  "tokens": {
   "total": {
    "tokens_in": 1630434,
    "tokens_out": 13478,
    "tokens_cached": 0
   },
   "per_task": {
    "tokens_in": 56221.862,
    "tokens_out": 464.759,
    "tokens_cached": 0.0
   }
  },
  "latency_s": {
   "p50": 1026.7,
   "p95": 1779.68,
   "n": 29
  },
  "trajectory_metrics": {
   "trajectories": 29,
   "steps": {
    "total": 226,
    "mean": 7.793103,
    "median": 6.0
   },
   "tool_error_rate": {
    "value": 0.079646,
    "num": 18,
    "den": 226
   },
   "redundant_call_rate": {
    "value": 0.020202,
    "num": 4,
    "den": 198
   },
   "stuck_rate": {
    "value": 0.0,
    "num": 0,
    "den": 29
   },
   "recover_after_gate_failure_rate": {
    "value": null,
    "num": 0,
    "den": 0
   }
  },
  "$_equivalent": 0.169782,
  "source": "packages/eval/results/breakit-C.json",
  "made_up": false
 },
 {
  "run_id": "ablation-A-claude-strong-only",
  "created_at": "2026-11-01T18:02:32Z",
  "agent": {
   "name": "ablation-A-claude-strong-only",
   "model": "claude-sonnet-5-5",
   "host": "claude-session",
   "params": {
    "out_dir": "C:\\Users\\vibha\\Downloads\\data\\personal\\argus\\.claude\\worktrees\\p5-tasks-waves-45bbcf\\packages\\eval\\runs\\t14\\A",
    "claude_session": true,
    "token_source": "chars/4 estimate of the messages; excludes subagent harness overhead",
    "worker_models": {
     "strong": "sonnet"
    },
    "stages": {
     "repro": "strong",
     "localize": "strong",
     "fix": "strong"
    },
    "fix_context": {
     "strategy": "cap",
     "budget": 32000
    },
    "repro_cap": 3,
    "latency": "wall clock of the whole task including coordinator waits; several tasks ran at once"
   }
  },
  "counts": {
   "resolved": 19,
   "unresolved": 8,
   "excluded": 2,
   "error": 0
  },
  "resolve_rate": {
   "successes": 19,
   "total": 27,
   "rate": 0.703704,
   "ci_low": 0.51519,
   "ci_high": 0.841471,
   "interval": "wilson95"
  },
  "tokens": {
   "total": {
    "tokens_in": 1031530,
    "tokens_out": 14903,
    "tokens_cached": 0
   },
   "per_task": {
    "tokens_in": 38204.815,
    "tokens_out": 551.963,
    "tokens_cached": 0.0
   }
  },
  "latency_s": {
   "p50": 819.0,
   "p95": 1800.66,
   "n": 27
  },
  "trajectory_metrics": {
   "trajectories": 29,
   "steps": {
    "total": 222,
    "mean": 7.655172,
    "median": 7.0
   },
   "tool_error_rate": {
    "value": 0.130631,
    "num": 29,
    "den": 222
   },
   "redundant_call_rate": {
    "value": 0.0,
    "num": 0,
    "den": 195
   },
   "stuck_rate": {
    "value": 0.0,
    "num": 0,
    "den": 29
   },
   "recover_after_gate_failure_rate": {
    "value": null,
    "num": 0,
    "den": 0
   }
  },
  "$_equivalent": 2.21209,
  "source": "packages/eval/results/ablation-A.json",
  "made_up": false
 },
 {
  "run_id": "ablation-B-claude-routed",
  "created_at": "2026-11-01T18:02:33Z",
  "agent": {
   "name": "ablation-B-claude-routed",
   "model": "claude-sonnet-5-5",
   "host": "claude-session",
   "params": {
    "out_dir": "C:\\Users\\vibha\\Downloads\\data\\personal\\argus\\.claude\\worktrees\\p5-tasks-waves-45bbcf\\packages\\eval\\runs\\t14\\B",
    "claude_session": true,
    "token_source": "chars/4 estimate of the messages; excludes subagent harness overhead",
    "worker_models": {
     "cheap": "haiku",
     "strong": "sonnet"
    },
    "stages": {
     "repro": "cheap",
     "localize": "cheap",
     "fix": "strong"
    },
    "fix_context": {
     "strategy": "cap",
     "budget": 32000
    },
    "repro_cap": 3,
    "latency": "wall clock of the whole task including coordinator waits; several tasks ran at once"
   }
  },
  "counts": {
   "resolved": 20,
   "unresolved": 8,
   "excluded": 1,
   "error": 0
  },
  "resolve_rate": {
   "successes": 20,
   "total": 28,
   "rate": 0.714286,
   "ci_low": 0.529404,
   "ci_high": 0.847462,
   "interval": "wilson95"
  },
  "tokens": {
   "total": {
    "tokens_in": 965190,
    "tokens_out": 13116,
    "tokens_cached": 0
   },
   "per_task": {
    "tokens_in": 34471.071,
    "tokens_out": 468.429,
    "tokens_cached": 0.0
   }
  },
  "latency_s": {
   "p50": 1617.05,
   "p95": 5097.535,
   "n": 28
  },
  "trajectory_metrics": {
   "trajectories": 29,
   "steps": {
    "total": 204,
    "mean": 7.034483,
    "median": 6.0
   },
   "tool_error_rate": {
    "value": 0.083333,
    "num": 17,
    "den": 204
   },
   "redundant_call_rate": {
    "value": 0.011429,
    "num": 2,
    "den": 175
   },
   "stuck_rate": {
    "value": 0.0,
    "num": 0,
    "den": 29
   },
   "recover_after_gate_failure_rate": {
    "value": null,
    "num": 0,
    "den": 0
   }
  },
  "$_equivalent": 1.944574,
  "source": "packages/eval/results/ablation-B.json",
  "made_up": false
 }
];
