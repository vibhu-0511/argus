## Problem

Nothing measured the whole pipeline end to end, nothing recorded how a run got to its result, and nothing stopped a change from quietly making the fixer worse. It was also unknown whether sending the cheap steps to a cheaper model saves anything without losing fixes.

## Solution

- Five trajectory metrics (steps, tool-error rate, redundant-call rate, stuck rate, recover-after-gate-failure rate) with exact formulas, and an eval runner that writes one results file with a Wilson 95% interval, tokens, a list-price dollar equivalent and latency.
- A phase report generator, a regression gate that compares a results file with a stored baseline using intervals (all thresholds in one file, ADR-017), and a workflow that runs it on stored results with no model call.
- OpenTelemetry spans for each model call, tool call and agent run, an attribute normalizer for Langfuse and Phoenix (unknown names pass through and are counted), and OTLP export from environment variables with a bounded queue (ADR-015). The same stubbed run reached a local Phoenix and two local receivers by changing only the endpoint and the profile.
- A router with the policy as data (repro and localize on the cheap tier, fix on the strong tier, fallback on a quota refusal only; ADR-016), a dated price table, a byte-stable prompt prefix, and cached tokens counted apart from fresh ones.
- The routing ablation, run for real with Claude sessions as the model on 29 seeded tasks in two variants (58 runs), with a live repro tree runner and a turn-by-turn driver. The runs and their evidence are in their own commit.
- Break-it tests: a renamed span attribute (strict mode raises), a dead trace backend (one bounded timeout), a timestamp at the top of the prompt (cached tokens drop to zero, with a stub provider), and the fix stage on the cheap model (the gate fails). The 29 runs of the last one are in their own commit.
- A SWE-bench Multimodal dev-subset adapter (15 tasks, exclusions listed) and a local grading run: 15 of 15 reference patches resolve, and the agent run is graded (7 solved, 5 unsolved, 3 excluded or not scored).
- A static dashboard that opens from disk, and a Pages workflow for it.

## Results

| Run (same 29 seeded tasks, Claude sessions as the model) | Resolved (95% interval) | Tokens/bug | List-price $/bug |
|---|---|---|---|
| A, every stage on the strong model | 19 of 27 (51.5% to 84.1%) | 38,757 | $0.0819 |
| B, repro on the cheap model, fix on the strong one | 20 of 28 (52.9% to 84.7%) | 34,939 | $0.0694 |
| C (break-it), fix stage on the cheap model | 13 of 29 (28.4% to 62.5%) | 56,687 | $0.0059 |

- A and B are not distinguishable (paired on 27 tasks: 18 both, 7 neither, 1 each way). The cheap tier carried about 2% of B's tokens, because the repro stage found a repro in 1 of 58 runs and localize makes no model call.
- The gate exits 1 on C against the stored baseline (20 of 29) and exits 0 on A and B. C lost 7 tasks that B resolved and gained none.

## Architecture (HLD)

The diagram shows every phase up to and including this one. This phase's part has a thick border and is labelled `NEW IN THIS PR`; thick arrows are links added here. The same source is committed as `docs/architecture/overview.md`; the design grew task by task in `docs/architecture/p5.md`.

```mermaid
flowchart LR
  TICKET["Ticket<br/>text and optional screenshot"]:::ext
  CANVAS["dcortex Canvas<br/>system under test"]:::ext
  PG[("copa-local Postgres")]:::ext
  HOSTS["Model hosts<br/>Groq, Mistral, Ollama"]:::ext
  TRACES["Trace backends<br/>Langfuse Cloud, Phoenix local"]:::ext

  subgraph S0 ["P0 bench and quota ledger"]
    CORE["argus-core<br/>Ticket, Task, Trajectory schemas"]:::p0
    CLIENT["OpenAI-compatible<br/>model client"]:::p0
    LEDGER["Quota ledger<br/>hard stop before the request"]:::p0
    TARGET["target-app<br/>binding to Canvas and Postgres"]:::p0
    SEEDED["30 seeded tasks"]:::p0
    BUGSMITH["bugsmith<br/>JSX and CSS mutation operators"]:::p0
    FILTER["Validity filter<br/>fails on bug, passes on fix"]:::p0
    MUTANTS["300 mutated tasks<br/>seed 1"]:::p0
    SCORER["bench scorer<br/>Playwright checks, no model"]:::p0
    GOLDEN["golden-fix runner<br/>and flake detector"]:::p0
    BASELINE["one-shot baseline"]:::p0
    CI["golden.yml<br/>manual dispatch"]:::p0
  end

  subgraph S1 ["P1 repro agent"]
    REPRO["repro loop<br/>retry cap, stop reasons"]:::p1
    PWMCP["Playwright MCP<br/>six tools"]:::p1
    RSANDBOX["repro Docker image<br/>no egress beyond the app"]:::p1
    RVERIFY["repro verifier<br/>fails on bug, passes on fix"]:::p1
    REPLAY["fixture replay<br/>CI, no model"]:::p1
  end

  subgraph S2 ["P2 dom2src"]
    PLUGIN["Vite plugin<br/>stamps data-src"]:::p2
    LOCATE["locate MCP server<br/>spec 2026-07-28"]:::p2
    RMAP["repo-map index"]:::p2
    PGV["pgvector file search"]:::p2
    ABL["retrieval harness<br/>and ablation"]:::p2
  end

  subgraph S3 ["P3 fix loop"]
    FIX["fix-loop run_fix<br/>named stop reasons"]:::p3
    TOOLS["six typed tools<br/>exact-match edit"]:::p3
    WT["worktree and Docker sandbox<br/>network none"]:::p3
    CTX["context budget<br/>four strategies"]:::p3
    GATES["build, typecheck,<br/>lint, unit, bench gates"]:::p3
    TRAJ["trajectory JSONL<br/>and replay"]:::p3
  end

  subgraph S4 ["P4 verify"]
    CHECKS["checks in order<br/>pixel, overflow, axe, console"]:::p4
    JUDGE["vision judge<br/>advisory only"]:::p4
    BOK["best-of-k<br/>default k 1, cap 5"]:::p4
    CAL["100 calibration pairs<br/>and alpha code"]:::p4
    VCI["verify.yml<br/>stored-pair gate"]:::p4
  end

  subgraph S5 ["P5 eval (NEW IN THIS PR)"]
    METRICS["trajectory metrics<br/>five formulas, docs/metrics.md"]:::p5
    RUNNER["eval runner<br/>Wilson 95% interval, results JSON"]:::p5
    PRICES["price table<br/>dated list prices, dollar equivalent"]:::p5
    REPORT["phase report<br/>previous, this, delta"]:::p5
    GATE["regression gate<br/>baseline lower bound, gate.toml"]:::p5
    OTEL["OTel spans<br/>invoke_agent, chat, execute_tool"]:::p5
    ROUTER["router<br/>routing.yaml, cheap and strong tier"]:::p5
    PCACHE["prompt cache accounting<br/>stable prefix, cached vs fresh"]:::p5
    MM["SWE-bench Multimodal adapter<br/>dev split, exclusions listed"]:::p5
    EXPORT["OTLP export<br/>env config, bounded queue"]:::p5
    NORM["attribute normalizer<br/>langfuse and phoenix profiles"]:::p5
    EGATE["eval-gate.yml<br/>stored results, no model"]:::p5
    DASH["static dashboard<br/>opens from disk"]:::p5
    PAGES["dashboard.yml<br/>GitHub Pages deploy"]:::p5
    ABLH["ablation harness<br/>strong-only vs routed policy"]:::p5
    DRIVER["Claude-session driver<br/>one subagent per step, tier per stage"]:::p5
    TREES["repro tree runner<br/>buggy and golden tree, internal network"]:::p5
    MMRUN["multimodal run<br/>local SWE-bench grading, none dropped"]:::p5
  end

  BUGSMITH --> FILTER
  FILTER --> SCORER
  FILTER --> MUTANTS
  SEEDED --> SCORER
  MUTANTS --> SCORER
  GOLDEN --> SCORER
  CI --> GOLDEN
  SCORER --> TARGET
  TARGET --> CANVAS
  TARGET --> PG
  BASELINE --> SCORER
  BASELINE --> CLIENT
  CLIENT --> LEDGER
  LEDGER --> HOSTS
  CORE -.-> CLIENT
  CORE -.-> SCORER
  TICKET --> REPRO
  REPRO --> PWMCP
  REPRO --> RSANDBOX
  REPRO --> RVERIFY
  RVERIFY --> SCORER
  REPRO --> CLIENT
  REPLAY -.-> REPRO
  PLUGIN --> CANVAS
  PLUGIN --> LOCATE
  LOCATE --> ABL
  RMAP --> ABL
  PGV --> ABL
  SEEDED -. "golden patch file" .-> ABL
  RVERIFY -. "fixture" .-> FIX
  LOCATE -. "fixture" .-> FIX
  PGV -. "fixture" .-> FIX
  FIX --> TOOLS
  FIX --> WT
  FIX --> CTX
  FIX --> GATES
  FIX --> TRAJ
  FIX --> CLIENT
  GATES -- "bench gate" --> SCORER
  FIX -- "verify callback" --> CHECKS
  CHECKS --> BOK
  JUDGE -. "never overrides a passed check" .-> BOK
  JUDGE --> CLIENT
  BOK --> FIX
  CAL --> JUDGE
  VCI --> CHECKS
  TRAJ --> METRICS
  SEEDED --> RUNNER
  RUNNER --> METRICS
  RUNNER -. "agent under test" .-> FIX
  PRICES --> RUNNER
  RUNNER --> REPORT
  RUNNER --> GATE
  MM --> RUNNER
  FIX --> OTEL
  REPRO --> OTEL
  CLIENT --> OTEL
  PRICES --> OTEL
  ROUTER --> CLIENT
  ROUTER --> LEDGER
  ROUTER -. "tier on each step" .-> TRAJ
  PCACHE --> LEDGER
  PCACHE -. "stable prefix" .-> FIX
  OTEL --> NORM
  NORM --> EXPORT
  EXPORT --> TRACES
  EGATE --> GATE
  RUNNER -. "results files" .-> DASH
  PAGES --> DASH
  ABLH --> ROUTER
  ABLH --> RUNNER
  ROUTER -- "stage per call" --> FIX
  ROUTER -- "stage per call" --> REPRO
  DRIVER --> ABLH
  DRIVER --> TREES
  TREES --> RVERIFY
  MM --> MMRUN
  MMRUN --> RUNNER

  classDef p0 fill:#dbeafe,stroke:#1d4ed8,stroke-width:1.5px,color:#111827
  style S0 fill:none,stroke:#1d4ed8,stroke-width:1.5px
  classDef p1 fill:#cffafe,stroke:#0e7490,stroke-width:1.5px,color:#111827
  style S1 fill:none,stroke:#0e7490,stroke-width:1.5px
  classDef p2 fill:#dcfce7,stroke:#15803d,stroke-width:1.5px,color:#111827
  style S2 fill:none,stroke:#15803d,stroke-width:1.5px
  classDef p3 fill:#fef9c3,stroke:#a16207,stroke-width:1.5px,color:#111827
  style S3 fill:none,stroke:#a16207,stroke-width:1.5px
  classDef p4 fill:#ffedd5,stroke:#c2410c,stroke-width:1.5px,color:#111827
  style S4 fill:none,stroke:#c2410c,stroke-width:1.5px
  classDef p5 fill:#fce7f3,stroke:#be185d,stroke-width:4px,color:#111827
  style S5 fill:none,stroke:#be185d,stroke-width:4px
  classDef ext fill:#ffffff,stroke:#6b7280,color:#111827,stroke-dasharray: 4 3
  linkStyle 46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,67,68,69,70,71,72,73,74,75,76,77 stroke-width:3px
```

## Stack

- Base branch: `main` (it already holds P0 to P4: PRs #4 and #5 were merged, and #6 to #8 were merged into `stack/base` and `main` by the merge commit d4e514b). Head branch: `stack/p5-eval`, cut from the P4 tip. Previous PRs: #8, #7, #6.
- Next PR: none yet (P5.5 onward not started). PR #10 (extras) is separate and untouched.
- Size: 643 files, about 18780 added lines, about 15 MB. The run evidence (`packages/eval/results/t14/`, 522 files, 13.2 MB) is in two commits of its own so reviewers can skip it.
- Commits are one per task, in plain language, with bullet points. Each wave of tasks ran as parallel sessions and was merged with a merge commit.

## Tests

| Command | Result |
|---|---|
| `uv lock --check`, `uv sync --all-packages --locked` | passed |
| `uv run pytest packages/eval/tests -q` | **70 passed** |
| `uv run pytest packages/argus-core/tests -q` | **78 passed** |
| `uv run pytest packages/fix-loop/tests -q` | **64 passed, 1 failed**: `test_ast_grep` fails the same way on `stack/p4-verify`, before any P5 change |
| `repro-agent`, `dom2src-mcp`, `verify`, `dashboard` tests | **38**, **51**, **47**, **3 passed** (docker and live tests deselected) |
| `python -m eval gate` on the baseline, A and B | exit 0; on the break-it run C and on `fixtures/gate/worse.json`: exit 1 |
| `.github/workflows/check_no_secrets.py` | only `golden.yml` is flagged, as before P5 |
| GitHub Actions on push | `eval-gate`, `verify`, `repro`, `dom2src` pass; `fix-loop` fails on `ModuleNotFoundError: jsonschema` in `test_trajectory.py` and `test_verify_gate.py`, the same import error as on the P3 and P4 PRs (an undeclared test dependency, not changed here) |

## Out of scope

- P5.5 (skills), P6 (flow), P7 (guard), P8 (app) and the backend lane.
- A routing ablation on Groq or Mistral: the free tiers are too small (about 13 days for both variants) and Mistral has no key.
- Making the harness replay deterministic under load (below).

## What this PR does not claim

- **Only a smoke trace has been seen in Langfuse** (P5-T07 is ticked on that; P5-T23 is not). The owner ran `python -m argus_core.telemetry` against a Langfuse Hobby project (US region) on 2026-11-02 and saw one trace: `invoke_agent argus-smoke` with a `chat` (generation) and a tool child. No trace of a real fix-loop run has been sent yet, so there is no real-run trace screenshot or project link. A real Phoenix 21.0.0 received the same stubbed run earlier. Details: `docs/notes/p5-t07.md`.
- **The Pages deploy has not run** (P5-T22): Pages is switched on, but GitHub only runs a workflow from the default branch, and the `github-pages` environment accepts deploys from `main` only, so `dashboard.yml` first runs when this PR is merged. The repo is private, so whether the page URL is public depends on the plan. Steps: `docs/notes/p5-t22.md`. The `eval-gate` workflow was seen on GitHub (P5-T17): green on this branch, and red on a temporary branch that carried the deliberately worse results file (run 41395983193, since deleted).
- **P5-T14 is unticked**: quota share is a dash (Claude sessions have only a self-imposed cap) and latency is not comparable between variants. Whether a Claude-session run meets the task is the owner's call.
- **P5-T20 is unticked**: the multimodal agent was one plain Claude subagent per task, one draw each, not the argus pipeline, and the agents did not run the repo tests. Two Chart.js tasks timed out in the grader on both tries (patch produced, not scored).
- **P5-T28 is unticked**: it needs the dashboard and Langfuse links from T23. The phase report against P4 is filled, but its two rows are not the same method (stateful P3 baseline against stateless Claude-session turns), so the +2.5 point resolve-rate delta means no change and the token delta is shown as not comparable.
- One run per cell, one model family, tiers set by a subagent parameter. Tokens are chars/4 estimates that leave out harness overhead. Not comparable with the Groq rows of earlier phases.
- Two B runs (`seed-h06`, `seed-h09`) hit a replay mismatch under load (the harness caches successful repro runs but not `tool-unavailable` ones) and were run again once; their first attempts are not included. `seed-h09` is excluded in every variant (scorer exit 2), and `seed-h06` in variant A.
- `test_ast_grep` was failing before this PR and is not touched.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
