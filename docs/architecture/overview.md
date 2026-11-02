# Architecture overview (P0 to P6)

As-built view of Argus after phases P5.5 and P6 (so far). Later phases are not drawn. This file grows by one phase in each stacked pull request; the diagram source is the same text the PR description shows.

```mermaid
flowchart LR
  TICKET["Ticket<br/>text and optional screenshot"]:::ext
  CANVAS["dcortex Canvas<br/>system under test"]:::ext
  PG[("copa-local Postgres")]:::ext
  FPG[("DBOS system database<br/>local Postgres now, Neon later")]:::ext
  HOSTS["Model hosts<br/>Groq, Mistral, Ollama"]:::ext
  TRACES["Trace backends<br/>Langfuse Cloud, Phoenix local"]:::ext
  GITHUB["GitHub<br/>issues, PRs, Actions, webhooks"]:::ext

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

  subgraph S5 ["P5 eval"]
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
    PAGES["dashboard.yml<br/>builds the page as a CI download"]:::p5
    ABLH["ablation harness<br/>strong-only vs routed policy"]:::p5
    DRIVER["Claude-session driver<br/>one subagent per step, tier per stage"]:::p5
    TREES["repro tree runner<br/>buggy and golden tree, internal network"]:::p5
    MMRUN["multimodal run<br/>local SWE-bench grading, none dropped"]:::p5
  end

  subgraph S55 ["P5.5 skills"]
    SPLIT["train and held-out split<br/>check: no shared task or file-operator pair"]:::p55
    SKLOAD["skill loader<br/>catalog in prompt, load_skill returns a body"]:::p55
    TRUST["trust checks<br/>review flag, hash pin, tool allowlist, cap of 3"]:::p55
    LOCK["skills.lock.json<br/>owner's sign-off, pin command"]:::p55
    SKILLS["5 reviewed skills<br/>SKILL.md only, hash-pinned"]:::p55
    COLLECT["trajectory collection<br/>20 resolved train runs"]:::p55
    DRAFTER["draft script<br/>unreviewed drafts, frontmatter written by script"]:::p55
    SLINT["skills lint<br/>skills-lint.yml, no model"]:::p55
    SELECT["selection test<br/>catalog only, 7 of 10 right"]:::p55
    SABL["with vs without skills<br/>29 held-out tasks, no gain seen"]:::p55
    BREAKS["break-it tests<br/>poisoned, always-matching, stale"]:::p55
  subgraph S6 ["P6 flow"]
    STATES["workflow state machine<br/>10 states, 12 transitions, idempotency keys"]:::p6
    WEBHOOK["webhook endpoint<br/>HMAC-SHA256, fail closed"]:::p6
    HINT["hint handler<br/>202, no GitHub read, delivery-id dedup"]:::p6
    ENQ["enqueue interface<br/>DbosEnqueuer, one workflow per ticket id"]:::p6
    WF["DBOS ticket workflow<br/>five idempotent steps, stored results"]:::p6
    CFG["flow config<br/>listen_notify off, pinned version and executor"]:::p6
    ACTIONS["Actions runner<br/>dispatch, find before start, artifact"]:::p6
    AJOB["agent-job.yml<br/>workflow_dispatch, never run on GitHub"]:::p6
    GREAD["GitHub reader<br/>read-only: issue, branch, PR, run"]:::p6
    RECON["reconciliation poller<br/>derive_state, poll_once"]:::p6
    QA["QA signal wait<br/>approve, reject, timeout, idempotency key"]:::p6
    RCOM["review-comment parser<br/>the QA path that ships"]:::p6
    QMCP["MRTR elicitation tool<br/>input_required, inputResponses"]:::p6
    DBWAKE["database wake-up<br/>bounded retry with backoff, TLS required"]:::p6
    SERVICE["Render service<br/>flow.service, /health, live on Render free"]:::p6
    GHWRITE["GitHub write client<br/>find before act, draft PR, mock transport only"]:::p6
    AGENTJOB["flow.agent_job<br/>runs one step, writes result.json, never run on GitHub"]:::p6
    CRASH["crash-recovery harness<br/>real process kills, ledger fakes"]:::p6
    FLOWCI["flow.yml<br/>Postgres service container, green on GitHub"]:::p6
    COLD["cold-start timer<br/>signed ping, 10 s verdict, not run"]:::p6
    NEONUSE["Neon usage probe<br/>CU-hours against polling, not run"]:::p6
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
  SEEDED -- "held-out set" --> SPLIT
  MUTANTS -- "train pool" --> SPLIT
  SKLOAD -- "catalog and load_skill tool" --> FIX
  SKLOAD -.-> TRAJ
  SPLIT -- "train order" --> COLLECT
  DRIVER -- "variant T, train mutants" --> COLLECT
  COLLECT --> DRAFTER
  DRAFTER -- "unreviewed drafts, then review" --> SKILLS
  LOCK --> TRUST
  TRUST --> SKLOAD
  SKLOAD -- "reads, loads on demand" --> SKILLS
  SLINT --> SKILLS
  SLINT -. "the loader's own checks" .-> TRUST
  SELECT --> SKLOAD
  DRIVER -- "variant S, skills on" --> SKLOAD
  SABL --> RUNNER
  SABL -. "stored P5 variant A" .-> ABLH
  BREAKS --> TRUST
  BREAKS --> WT
  GITHUB --> WEBHOOK
  WEBHOOK --> HINT
  HINT --> ENQ
  STATES -. "workflow id key" .-> ENQ
  STATES -. "step names, not imported" .-> REPRO
  STATES -. "step names, not imported" .-> FIX
  STATES -. "step names, not imported" .-> CHECKS
  ENQ --> WF
  WF -- "moves only via next_state" --> STATES
  WF --> FPG
  CFG --> WF
  WF --> ACTIONS
  ACTIONS -- "workflow_dispatch" --> AJOB
  AJOB --> AGENTJOB
  AGENTJOB --> REPRO
  AGENTJOB --> FIX
  AGENTJOB -. "scores the patch" .-> SCORER
  ACTIONS --> GITHUB
  GREAD --> GITHUB
  RECON --> GREAD
  RECON --> ENQ
  RECON -. "derive_state" .-> STATES
  WF --> QA
  RCOM --> QA
  WEBHOOK --> RCOM
  QMCP --> QA
  CFG --> DBWAKE
  DBWAKE --> FPG
  SERVICE --> WEBHOOK
  SERVICE --> DBWAKE
  SERVICE --> RECON
  SERVICE --> GHWRITE
  GHWRITE --> GITHUB
  CRASH -. "hard-kills the worker" .-> WF
  FLOWCI -. "flow test suite" .-> WF
  COLD -. "times the 202" .-> WEBHOOK
  NEONUSE -. "reads usage of" .-> FPG

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
  classDef p5 fill:#fce7f3,stroke:#be185d,stroke-width:1.5px,color:#111827
  style S5 fill:none,stroke:#be185d,stroke-width:1.5px
  classDef p55 fill:#ede9fe,stroke:#6d28d9,stroke-width:1.5px,color:#111827
  style S55 fill:none,stroke:#6d28d9,stroke-width:1.5px
  classDef ext fill:#ffffff,stroke:#6b7280,color:#111827,stroke-dasharray: 4 3
  classDef p6 fill:#ccfbf1,stroke:#0f766e,stroke-width:1.5px,color:#111827
  style S6 fill:none,stroke:#0f766e,stroke-width:1.5px
  classDef ext fill:#ffffff,stroke:#6b7280,color:#111827,stroke-dasharray: 4 3
```

## How to read it

| Mark | Meaning |
|---|---|
| Thick border, box labelled `NEW IN THIS PR` | the part this phase adds |
| Thin border | an earlier phase |
| Dashed white box | a system outside this repo (Canvas, Postgres, model hosts, the ticket) |
| Dotted arrow | a stored input (`fixture`), a test-only link or an advisory link, not a live call |
| Thick arrow | a link added in this phase |

Colours: P0 blue, P1 cyan, P2 green, P3 yellow, P4 orange, P5 pink, P5.5 purple, P6 teal.

## What P5.5 adds

- `packages/skills`: five reviewed skills (`SKILL.md` only, one per bug archetype) and the tools around them. `skills.split` builds and checks the train and held-out split (held-out is the 30 seeded tasks, 29 run; train is 40 mutants; the check fails on a shared task id or a shared (file, operator) pair). `skills.collect` and `skills.draft` turn resolved train runs into unreviewed drafts. `skills.pin` is the owner's sign-off. `skills.lint` is the CI check. `skills.selection` is the catalog-only selection test.
- `fix_loop.skills`: reads `packages/skills/skills/<name>/SKILL.md` and gives `run_fix` a `skills` argument. The system message lists names and descriptions only; the `load_skill` tool returns one body, and at most 3 load per run. Twenty skills add 880 estimated tokens against 23,280 for their bodies in the test. Loads are read back from the trajectory (no schema change).
- Trust controls: a skill is refused unless `skills.lock.json` holds a reviewed entry with the SHA-256 of the file, and the agent may call only the tools the loaded skills allow (a skill narrows the tools, never widens them). The review flag is read from the lock, never from the file. ADR-019 says what this trusts, checks and cannot check.
- Measured: a catalog-only selection test (7 of 10 right, 3 misses that no wording can fix because the ticket text does not tell three CSS skills apart) and a with-vs-without run on the 29 held-out tasks (variant S of `eval.t14_turn`, `eval.skills_ablation`): 21 of 29 against 19 of 27, the same outcome on all 27 paired tasks, tokens in about 8% higher, a skill loaded in 14 of 29 runs and 2 of the 5 skills ever loaded. Skills did not help. They are off by default.
- Break-its: a skill that edits the bench checks (refused, or the read-only mount rejects the write), one that sends data out (no route, logged), one whose description matches every ticket (lint and a cap of 3), one that names a moved file (a path lint).
- ADR-018 (format and distillation criteria: what a run must show to feed a skill, at least 3 runs per skill, a selection check before a pin, who reviews, what must be shown before skills are on by default) and ADR-019 (trust model).
- The phase report against P5 is in `phases/P05.5-argus-skills.md`, made with `python -m eval report`; the two T08 rows are results files in `packages/eval/results/t08/`.
- Per-task detail: `docs/architecture/p5.5.md`.

## What P6 adds

- `packages/flow`: the ticket workflow state machine (`flow.states`): ten states, 12 legal transitions, any other pair raises, and stable idempotency keys for each side effect. Pure Python, no DBOS yet.
- A FastAPI webhook endpoint that checks GitHub's HMAC-SHA256 signature (secret from `GITHUB_WEBHOOK_SECRET`, fail closed) and a handler that treats the webhook as a hint: it enqueues a reconcile and returns 202 with no GitHub read. A repeated delivery id is a no-op. The enqueue is an interface; `DbosEnqueuer` starts the workflow under the ticket id.
- `flow.workflow` (T03): the ticket workflow as a DBOS workflow with five idempotent steps (repro, fix, verify, open PR, hand-off), step results stored in Postgres, find-or-create PR on one stable draft branch. `flow.config` fixes `use_listen_notify` off, a pinned application version and executor id, and no conductor key. The repro, fix and verify runners and the GitHub client are injected fakes; nothing dispatches to Actions yet (T04) and the QA wait is a stub (T08).
- `flow.actions` (T04): an Actions runner that dispatches a step as a `workflow_dispatch` run, finds an existing run by its run key before starting one, and reads the patch and trajectory artifact. `agent-job.yml` is written but has never run on GitHub, and its entry point `flow.agent_job` (wave 6) runs one step and writes `result.json`, but its default steps have not run and the workflow does not yet check out the platform repository or start the Docker rig, so T04 is unticked.
- `flow.reconcile` and `flow.github_read` (T07): a read-only GitHub reader and a poller that maps issue, branch, PR and run onto the workflow states and enqueues under the same workflow id as the webhook. Tested on 11 recorded GitHub JSON fixtures.
- QA wait (T08, T10, T09, T18): the workflow waits in `awaiting-qa` for an approve or reject signal with a timeout. A review comment (`/argus approve` or `/argus reject`) from an allowed reviewer ships as the QA path (ADR-023); the MRTR elicitation tool is built and tested in memory, with no real MCP client run.
- `flow.db_wake` (T11, T24): a bounded wake-up with backoff before DBOS launches, and a rule that a non-local database URL must use TLS (`sslmode=require` or stronger). Tested against a local Postgres with TLS, by killing connections and by stopping and starting it; nothing ran against Neon. ADR-020 records DBOS over Temporal (decision only, nothing built for Temporal).
- `flow.service` and `render.yaml` (T12): the one app Render would run, with `/health` that answers before the database is awake and a late-bound enqueuer so the webhook still answers 202. Live on Render free since 2026-11-03 (`/health` answered on the public URL; no webhook or ticket run yet). The workflow's GitHub write client (`flow.github_write`, wave 6) finds before it acts and keeps the PR a draft; it has only run against a mock transport, never real GitHub. The Blueprint keeps polling off until the first real run.
- Crash-recovery experiment (T19, T21): 150 real process kills per variant (plain function against DBOS) at 15 points, fake runners with a durable ledger. Both variants finished every run; DBOS repeated fewer calls (0.93 against 4.47 per kill) and made no duplicate effect, the plain function set one label twice. Killing after the PR is created left one draft PR (10 of 10).
- `flow.yml` (T20) runs the flow tests on a Postgres service container and was green on GitHub on 2026-11-02 (364 passed, 5 skipped). A Render sleep that drops a webhook is shown locally (T23); a sleeping service runs no poller, an open finding.
- Measurement tooling (T13, T14): a script that times the Render cold start with a signed ping against the 10 s webhook timeout, and a probe that compares Neon usage with what DBOS polling asks of the database. Neither has run against a real deploy; no cold-start time and no CU-hour figure exist. Owner steps are in `docs/notes/p6-t13.md` and `p6-t14.md`.
- ADR-021 (webhooks as hints with reconciliation) and ADR-022 (free-tier topology) are written and marked proposed. `packages/flow/README.md` and the phase report hold the status; the P5 cells stay as dashes.
- Version re-check and DBOS and MRTR notes (`docs/notes/p6-t00-versions.md`, `p6-t01-dbos-mrtr.md`). Per-task detail: `docs/architecture/p6.md`.
- P6 was started before P5.5 and before P5 finished, by the owner's choice (`docs/notes/p6-waves.md`).

## What P5 added

- `packages/eval`: the five trajectory metrics (steps, tool-error rate, redundant-call rate, stuck rate, recover-after-gate-failure rate) over stored trajectory files, and a runner that writes one results JSON with a Wilson 95% interval. The results JSON is the file the report, gate and dashboard read.
- `packages/argus-core/prices.json`: dated list prices per model and the dollar-equivalent function. The runner and the spans use it.
- `eval report` and `eval gate`: the phase report table, and a gate that fails when a run is below the baseline's Wilson lower bound. All thresholds are in `gate.toml`.
- `argus_core.telemetry`: OTel spans for each model call, tool call and agent run. With no provider started they do nothing.
- `argus_core.router` and `routing.yaml`: repro and localize go to the cheap tier, fix to the strong tier, with a fallback to the other host. The loop does not use it yet (T14).
- The fix prompt has a byte-stable prefix, and the ledger keeps cached and fresh tokens apart.
- Spans go through an attribute normalizer (profiles for Langfuse and Phoenix; unknown names pass through and are counted), then an OTLP exporter chosen from environment variables with a bounded queue. The swap to a second backend was shown with a local Phoenix and two local receivers. The Langfuse export is built but no trace has been seen there.
- The fix loop and the repro agent can take a router and record the tier, host and model on each step. The ablation harness holds the two policies (all strong, or routed) and the table script. A Claude-session driver ran the 29 seeded tasks under both policies (and a third, fix on the cheap model) through a repro tree runner; the results are in `packages/eval/results/`.
- `dashboard.yml` builds the page and attaches it to the run as a download (Pages is not available on this private repo). The normalizer has a strict switch that raises on a renamed attribute, and a dead trace backend costs one bounded timeout.
- `eval-gate.yml` runs the gate on a stored results pair, and `packages/dashboard` builds a static page from the results files. ADR-015 and ADR-017 record the choices.
- `eval multimodal` also grades agent patches locally with the SWE-bench harness (15 tasks, 7 solved, 5 unsolved, 3 excluded or not scored, none dropped).
- `eval multimodal`: the SWE-bench Multimodal `dev` subset, with the dropped rows and reasons listed.
- Per-task detail: `docs/architecture/p5.md`.

## What P4 added

- `packages/verify`: four fixed checks in a fixed order (pixel, overflow, axe, console); a hard failure returns one verdict and stops.
- A vision judge that is advisory only and never overrides a passing check run.
- Best-of-k selection (default k = 1, cap 5), the Krippendorff-alpha code and a CI gate on a stored before/after pair (`verify.yml`).
- 100 calibration pairs of real Canvas screenshots with labels that are Claude's drafts adopted by the owner (not independent human labels), and the best-of-k runs `packages/fix-loop/runs/p4-t20-*`.

## Earlier phases

- **P0 bench and quota ledger:** `packages/bench`: 30 seeded and 300 generated bug tasks, and the scorer that runs a task's Playwright checks against a copy of Canvas with no model call.
- **P1 repro agent:** `packages/repro-agent`: a loop that asks a model for a Playwright script, runs it, revises on error and stops at a cap with a named stop reason.
- **P2 dom2src:** `packages/dom2src-plugin`: a Vite plugin that stamps `data-src="file:line:col"` on elements in dev and test builds.
- **P3 fix loop:** `packages/fix-loop`: six typed tools (no write-file; an edit must match exactly once) and a loop with named stop reasons.

## Sources

Built from `PLAN.md` (Architecture) and, where they exist, the `docs/architecture/pN.md` "As built" sections. Edges not stated word for word there: `RVERIFY --> SCORER` (the verifier runs a script on a task's buggy and golden trees); `SEEDED -.-> ABL` (retrievers are scored by the golden patch's file); `GATES --> SCORER` (the `bench` gate); `BOK --> FIX` (best-of-k picks among fix-loop candidates, `phases/P04-verify.md` T19).
