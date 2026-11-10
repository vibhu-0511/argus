**Draft PR text for P8. Not pushed, not created.** Base `stack/p7-guard`, head `stack/p8-app`.

## Problem

Argus ran only as the owner's own pipeline. There was no way for someone else to point it at their repo: no GitHub App definition, no per-repo token, no workflow that runs the agent in the tenant's repo, no per-repo config, no per-tenant quota (one user could use up the shared free-tier allowance), no intake from a labelled issue, no pull request with evidence, no backport, and no test of a planner and subagents variant of the fix loop.

## Solution

- Version re-check for the App, reusable-workflow and free-tier limits (`docs/notes/p8-t00-versions.md`), and notes on the two Anthropic posts on multi-agent systems and agent design (`p8-t01-multi-agent-notes.md`). The post claims about 4 times the tokens of a chat for one agent and about 15 times for a multi-agent system, and calls coding a poor fit.
- New package `packages/app` (`argus_app`, command `argus-app`) with the GitHub App manifest: five permissions that equal ADR-026, URLs from the environment.
- Installation flow in the flow service (`flow.installations`): record installation events and mint a one-hour token for one installed repo. A call on another repo is refused.
- Tenant config `.argus.yml` (start command, test command, routes, budget) with typed errors, and a one-page onboarding doc.
- Reusable workflow `.github/workflows/argus-reusable.yml`: a tenant calls it with `workflow_call` and it runs repro, fix and verify in the tenant's repo, with a read-only job token and the model key only in the fix step.
- Target-agnostic runner (`argus_app.runner`): start, test and routes come from `.argus.yml`; no repo command is in its source.
- Per-tenant quota: tenant id in the ledger keys, `TenantBudget`, `Ledger.for_tenant` and a fair-share rule. A tenant at its budget gets a typed refusal while a second tenant goes on.
- Ticket intake (`flow.intake`): a labelled issue starts exactly one workflow; a label from a user without write access is ignored and logged. A config check at intake comments a typed error.
- PR creation (`argus_app.pr`): verdict, judge label, trajectory link and screenshots in the body; built through the API with title and body as JSON fields.
- Backport bot (`argus_app.backport`): cherry-pick onto a configured branch; on a conflict it comments and moves no branch.
- Planner and subagents variant of the fix loop (`fix_loop.planner`): 1 to 5 typed sub-tasks, each with its own token cap, all tokens in one ledger; `params.variant` switch in the eval ablation harness. The ablation harness for 20 tasks is built.
- `app.yml`: CI for the App tests and a lint of the reusable workflow, no model.
- ADR-027 (tenancy), ADR-028 (tenant budgets), ADR-029 (single agent vs planner), all proposed.
- Four break-its: T21 tenant at its budget, T22 no test command, T23 backport conflict, T24 label from a read-only user (index in `docs/notes/p8-break-its.md`).
- Preparation for the owner: demo repo and demo script, landing README (`docs/landing/README.md`), release checklist (`docs/release-checklist.md`), owner steps for each task that needs the real App (`docs/notes/p8-t*-owner-steps.md`), package README and phase report.

## Architecture (HLD)

The diagram shows every phase up to and including this one. This phase's part has a thick border and is labelled `NEW IN THIS PR`; thick arrows are links added here. The same source is committed as `docs/architecture/overview.md`. Per-task detail is in `docs/architecture/p8.md`.

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
  end

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

  subgraph S7 ["P7 guard"]
    VERS["version re-check<br/>promptfoo, gVisor, Firecracker, App token, 2026-11-03"]:::p7
    OWASPN["OWASP ASI01 to ASI10 and Firecracker notes<br/>names from the launch post, PDF not read"]:::p7
    TM["threat model<br/>assets, trust boundaries, data flow, 10 ASI rows"]:::p7
    SECINV["secrets inventory<br/>name, place, who can read"]:::p7
    REDACT["redactor<br/>argus_core.redact, masks known env values and token shapes"]:::p7
    RSCAN["secret scan<br/>check_no_secrets.py, remote-URL check, secret-scan.yml green on GitHub"]:::p7
    AUDIT["audit log<br/>hash chain, guard verify-log, not wired into fix-loop"]:::p7
    EGRESS["egress probe<br/>tcp, https, dns; ran locally and on a GitHub runner"]:::p7
    ESCAPE["escape suite<br/>14 probes, docker 14 of 14, gvisor 14 of 14 alone, firecracker probes not ported"]:::p7
    APPTOK["App token<br/>flow.app_token, minimum permissions, one repo, mock transport, no App created"]:::p7
    REDTEAM["promptfoo red-team<br/>3 static cases: ticket, repo file, skill; deterministic checks"]:::p7
    RTRES["red-team results<br/>gemma4:e4b local, 15 runs each way, not the production model"]:::p7
    HARDEN["mitigations<br/>untrusted-data blocks, tool allowlist, output filter, off by default"]:::p7
    SBRUN["sandbox runtime setting<br/>guard sandbox-run; runsc ran on a GitHub runner"]:::p7
    GVWF["gvisor.yml<br/>ran on a GitHub runner"]:::p7
    GUARDCI["guard.yml<br/>escape suite, secret scan, verify-log, head hash in run summary; green on GitHub"]:::p7
    FCRUN["Firecracker tier<br/>firecracker-run and firecracker.yml; booted on a GitHub runner, 30 of 30, probes not ported"]:::p7
    ABLATION["tier ablation<br/>guard ablation; A, B and C run on GitHub runners, C has no probes"]:::p7
    BREAKS7["P7 break-its<br/>env dump, edited log, DNS lookup; App push refused 422 on a real throwaway repo"]:::p7
    ADRS7["ADR-024, 025, 026<br/>proposed: threat model, sandbox tier (only Docker measured), secrets and token scopes"]:::p7
    GREADME["guard README and phase report<br/>controls listed, state of each; report cells are dashes"]:::p7
  end

  subgraph S8 ["P8 app (NEW IN THIS PR)"]
    VERS8["version re-check<br/>App, reusable-workflow and free-tier limits, 2026-11-03"]:::p8
    MANOTES["multi-agent notes<br/>about 4x tokens per agent, about 15x multi-agent; coding is a bad fit"]:::p8
    MANIFEST["App manifest<br/>argus_app.manifest, five permissions equal ADR-026, URLs from env; App registered 2026-11-10 (id 5699242), installed on no repo"]:::p8
    PLANNER["planner and subagents<br/>fix_loop.planner, 1 to 5 typed sub-tasks, own token cap each; one smoke run"]:::p8
    VARIANT["variant switch<br/>params.variant in eval.ablation, single or planner"]:::p8
    INSTALL["installation flow<br/>flow.installations, token for one installed repo; mock GitHub only, real App not run"]:::p8
    TCONF["tenant config<br/>.argus.yml, argus_app.config, onboarding doc; typed errors"]:::p8
    RWF["reusable workflow<br/>argus-reusable.yml; never run on GitHub, actionlint not run"]:::p8
    TRUNNER["target-agnostic runner<br/>argus_app.runner; fixture repo ran for real, dcortex not run"]:::p8
    TQUOTA["tenant quota<br/>TenantBudget, Ledger.for_tenant, fair share; budgets not built into the service"]:::p8
    INTAKE["ticket intake<br/>flow.intake, label plus write access; mock GitHub only"]:::p8
    CFGINT["config check at intake<br/>argus_app.config_intake, typed comment, mock GitHub only"]:::p8
    PRBUILD["PR with evidence<br/>argus_app.pr; not called by the workflow yet"]:::p8
    BACKPORT["backport bot<br/>argus_app.backport; real git on local repos, mock GitHub, not on a webhook"]:::p8
    ABLRUN["ablation run<br/>harness built, nothing ran: no Ollama on the machine"]:::p8
    APPCI["app.yml<br/>App tests and lint, no model; not run on GitHub"]:::p8
    ADRS8["ADR-027, 028, 029<br/>proposed: tenancy, tenant budgets, planner vs single (no decision, no numbers)"]:::p8
    BREAKS8["P8 break-its<br/>T21 quota, T22 no test command, T23 conflict, T24 read-only label; mocks and local git"]:::p8
    PREP8["demo repo, script, README, checklist<br/>preparation only: no public repo, video or timed install"]:::p8
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

  %% P7 links
  VERS -. "versions" .-> TM
  OWASPN --> TM
  TM -. "injection paths" .-> TICKET
  TM -. "boundaries, tool abuse" .-> FIX
  TM -. "sandbox boundary" .-> WT
  TM -. "skill injection path" .-> SKLOAD
  TM -. "webhook and token" .-> WEBHOOK
  TM -. "workflow and Actions" .-> WF
  SECINV -. "lists" .-> REDACT
  REDACT -- "masks every trajectory file" --> TRAJ
  REDACT -- "masks span attributes" --> OTEL
  RSCAN -. "scans tracked files" .-> CORE
  AUDIT -. "will record tool calls" .-> TOOLS
  EGRESS -- "same probe as the sandbox" --> WT
  ESCAPE -- "14 probes" --> WT
  ESCAPE -. "extends" .-> EGRESS
  TM -. "ASI10 control" .-> AUDIT
  TM -. "ASI05 control" .-> ESCAPE
  APPTOK -. "mints the token for" .-> GHWRITE
  APPTOK -- "installation token, one repo" --> GITHUB
  REDACT -- "scrub now uses it" --> AGENTJOB
  REDTEAM -- "attack in the ticket and repo file" --> FIX
  REDTEAM -. "attack in a skill file" .-> SKLOAD
  REDTEAM --> RTRES
  HARDEN -- "wraps untrusted text" --> FIX
  HARDEN -- "filters output" --> REDACT
  RTRES -. "baseline against hardened" .-> HARDEN
  SBRUN -- "runtime flag" --> WT
  GVWF -. "ran on a runner" .-> SBRUN
  ESCAPE -. "gvisor tier" .-> SBRUN
  TM -. "ASI03 control" .-> APPTOK
  TM -. "ASI01 control" .-> HARDEN
  GUARDCI -- "runs" --> ESCAPE
  GUARDCI -. "runs" .-> RSCAN
  GUARDCI -- "verifies" --> AUDIT
  ESCAPE -- "each probe is a record" --> AUDIT
  FCRUN -. "tier C, booted on a runner" .-> SBRUN
  ABLATION -- "cold start and probes" --> ESCAPE
  ABLATION -. "all tiers ran on a runner" .-> SBRUN
  BREAKS7 -- "env dump" --> HARDEN
  BREAKS7 -- "edited line" --> AUDIT
  BREAKS7 -- "DNS lookup" --> EGRESS
  BREAKS7 -. "real run, 422" .-> APPTOK
  ADRS7 -. "decides" .-> TM
  ADRS7 -. "default tier" .-> SBRUN
  ADRS7 -. "token scopes" .-> APPTOK
  GREADME -. "lists the controls" .-> ESCAPE

  %% P8 links
  VERS8 -. "limits" .-> MANIFEST
  MANIFEST -. "permission list equals" .-> APPTOK
  MANIFEST -. "webhook URL is service/webhook" .-> WEBHOOK
  MANIFEST -. "registers on, not run" .-> GITHUB
  MANOTES -. "overhead and keep rule" .-> PLANNER
  PLANNER -- "each subagent runs the loop" --> FIX
  PLANNER -- "every agent's calls counted" --> LEDGER
  PLANNER -- "tier per call" --> ROUTER
  VARIANT -- "selects planner or single" --> PLANNER
  VARIANT -- "agent under test" --> RUNNER
  WEBHOOK -- "installation events" --> INSTALL
  INSTALL -- "mints, one repo" --> APPTOK
  MANIFEST -. "events it subscribes to" .-> INSTALL
  TCONF -- "commands and routes" --> TRUNNER
  RWF -- "runs" --> TRUNNER
  TRUNNER -- "wraps" --> AGENTJOB
  RWF -. "token profile write" .-> APPTOK
  INSTALL -- "tenant id" --> TQUOTA
  TQUOTA -- "extends" --> LEDGER
  WEBHOOK -- "label event" --> INTAKE
  INTAKE -- "one workflow per ticket" --> ENQ
  INTAKE -- "read token" --> INSTALL
  INTAKE -- "reads .argus.yml" --> CFGINT
  CFGINT -- "validates" --> TCONF
  PRBUILD -- "find before act" --> GHWRITE
  PRBUILD -. "reads verdict.json" .-> CHECKS
  BACKPORT -- "opens the PR" --> GHWRITE
  BACKPORT -. "write token" .-> APPTOK
  ABLRUN -. "would run" .-> VARIANT
  ABLRUN -. "would write results" .-> RUNNER
  APPCI -. "lints" .-> RWF
  APPCI -. "tests" .-> TRUNNER
  ADRS8 -. "decides" .-> RWF
  ADRS8 -. "decides" .-> TQUOTA
  ADRS8 -. "keeps single agent" .-> PLANNER
  BREAKS8 -. "tenant over budget" .-> TQUOTA
  BREAKS8 -. "no test command" .-> CFGINT
  BREAKS8 -. "cherry-pick conflict" .-> BACKPORT
  BREAKS8 -. "read-only label" .-> INTAKE
  PREP8 -. "first install target" .-> RWF

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
  classDef p55 fill:#e7e5e4,stroke:#57534e,stroke-width:1.5px,color:#111827
  style S55 fill:none,stroke:#57534e,stroke-width:1.5px
  classDef p6 fill:#ede9fe,stroke:#6d28d9,stroke-width:1.5px,color:#111827
  style S6 fill:none,stroke:#6d28d9,stroke-width:1.5px
  classDef p7 fill:#fee2e2,stroke:#b91c1c,stroke-width:1.5px,color:#111827
  style S7 fill:none,stroke:#b91c1c,stroke-width:1.5px
  classDef p8 fill:#ccfbf1,stroke:#0f766e,stroke-width:4px,color:#111827
  style S8 fill:none,stroke:#0f766e,stroke-width:4px
  classDef ext fill:#ffffff,stroke:#6b7280,color:#111827,stroke-dasharray: 4 3
  linkStyle 181,182,183,184,185,186,187,188,189,190,191,192,193,194,195,196,197,198,199,200,201,202,203,204,205,206,207,208,209,210,211,212,213,214,215,216,217,218,219,220 stroke-width:3px
```

## Stack

| Item | Value |
|---|---|
| Base | `stack/p7-guard` |
| Head | `stack/p8-app` |
| Previous PRs | [#15](https://github.com/vibhu-0511/argus/pull/15) P7 guard (open); [#12](https://github.com/vibhu-0511/argus/pull/12) P6 flow (draft, still open); [#14](https://github.com/vibhu-0511/argus/pull/14) P5.5 skills, [#13](https://github.com/vibhu-0511/argus/pull/13) and [#11](https://github.com/vibhu-0511/argus/pull/11) P5 (merged into `main`) |
| Size against `stack/p7-guard` (`215bee0`) | 109 files, +8,194 and -95 lines (without this PR text file) |

Notes on the stack:
- P8 is cut from `stack/p7-guard`. If P7 or P6 change before they merge, this branch needs a merge from them.
- P6 is not finished (PR 12 is a draft). The one P8 task that lists an open P6 task as a dependency, P8-T04 on P6-T04 (dispatch to Actions), was waived; see below.

## Tests

All run one package at a time on 2026-11-04 on Windows 11 (`uv run --all-packages python -m pytest packages/<name>/tests -q`), at head `c0bd9b6`. No test calls a model.

| Command | Result |
|---|---|
| `packages/app/tests` | 248 passed (38 min on a busy machine) |
| `packages/argus-core/tests` | 91 passed |
| `packages/eval/tests` | 96 passed |
| `packages/guard/tests` | 115 passed |
| `packages/skills/tests` | 65 passed, 1 skipped |
| `packages/verify/tests` | 47 passed |
| `packages/repro-agent/tests` | first run (other suites running at the same time): 43 passed, 1 skipped, 8 failed (`test_against_app.py`, browser navigation timeouts). Re-run alone: 51 passed, 1 skipped |
| `packages/fix-loop/tests` | first run: 124 passed, 2 failed: the known `test_ast_grep.py` failure, and `test_sandbox.py::test_sandbox_blocks_network_and_checks_writes` (a `docker run` timeout under load). Re-run of `test_sandbox.py` and `test_ast_grep.py` alone: sandbox test passed, `test_ast_grep.py` failed again (known) |
| `packages/flow/tests` with a throwaway Postgres 16 container `argus-p8-pr` on port 55461 (`ARGUS_FLOW_DATABASE_URL`), removed afterwards | 550 passed, 5 skipped |
| `packages/bench/tests` | 29 passed, 1 failed: `test_score.py::test_score_pass_fail_and_unsliced_reasons`, `Cannot find package '@playwright/test'` (no node modules in this worktree). The package is not changed by P8 |
| `packages/dom2src-mcp/tests` | 51 passed, 3 failed: `test_embed.py` and two in `test_repo_map.py`, `set ARGUS_PLATFORM_REPO to the dcortex-platform checkout` (no platform checkout set). The package is not changed by P8 |
| `uv lock --check` | clean (Resolved 104 packages) |
| Mermaid parse of the diagram | not re-run; the diagram is copied from the committed `docs/architecture/overview.md` |
| GitHub Actions on this PR | not run: the branch was not pushed. No P8 workflow (`argus-reusable.yml`, `app.yml`) has run on GitHub |
| `actionlint` | not run |
| `packages/dashboard`, `bugsmith`, `dom2src-plugin`, `target-app` | no tests folder |

## Out of scope

- Registering the App, installing it, and every call to the real GitHub API from P8 code. These are owner steps, written in `docs/notes/p8-t02-owner-steps.md`, `p8-t03-owner-steps.md` and `p8-t16-owner-steps.md`.
- A run of the reusable workflow in a tenant repo, a run of `app.yml`, and `actionlint` on either (needs a push).
- A real run on the dcortex repo, and any run of the fix agent against a model.
- The 20-task ablation (needs a local model, see below), the demo video, the licence file and the owner's `docs/` sweep.
- Turning the budgets into a service setting: the ledger supports tenants, the flow service does not build budgets from the tenant config yet.
- Calling PR creation, the config check and the backport bot from a running service. The functions exist and are tested; nothing calls them from a webhook yet.

## What this PR does not claim

17 of 26 P8 tasks are ticked and 9 are not. The App is registered (id 5699242, 2026-11-10) but installed on no repository, and the PR code paths and workflows never ran against it. No model was called. The limits are below.

**Unticked tasks (9), each with the reason:**
- **T03 installation flow and token minting:** "mints a token for that repo only, a call on another repo fails" was never seen on the real GitHub, because there is no registered App. It is tested against a mock GitHub, with a real Postgres for the store. Steps: `p8-t03-owner-steps.md`.
- **T04 reusable workflow:** needs a real Actions run (no push, no tenant repo, no real App). The file is parsed and checked locally. `actionlint` was not run. The dependency P6-T04 is waived.
- **T06 target-agnostic runner:** not run on the real dcortex repo (no checkout used), and the real fix agent never ran. It ran on a second small fixture repo with a fake fix agent.
- **T12 ablation, single agent vs planner, 20 tasks:** 0 of 20 tasks ran for either variant. There is no Ollama server, binary or `gemma4:e4b` on the build machine, and the rules allow no other model. The Ablation table and the phase report are dashes on purpose. The harness and configs are built and tested with stub models (`docs/notes/p8-t12.md`).
- **T16 install on a public repo and run one issue:** needs a registered App, an installation, a secret, a real Actions run and a model key. Nothing real ran. The demo repo and owner steps are prepared (`p8-t16-owner-steps.md`).
- **T17 landing README:** written (`docs/landing/README.md`), but "install and run in under 10 minutes" was never timed because nothing can be installed yet. Blanks left for the owner: App URL, run links, video link, licence.
- **T18 demo video:** nothing recorded. It needs the owner, and the success scene needs T16. A script and local rehearsal files for the rejection and the quota refusal exist.
- **T19 release checklist:** 2 of 4 done (secret scan, quota limits). No licence file (the owner's choice) and the `docs/` folder still names the private platform repo (68 matches in 22 files) and has a few home paths. See `docs/release-checklist.md`.
- **T20 CI job:** `app.yml` is checked by tests and run step by step locally, but "workflow green" needs a push. The `actionlint` step has not been seen to run.

**Waived or open dependencies:**
- P6 is still open (PR 12 is a draft; 7 P6 tasks are unticked). P8-T04 depends on P6-T04 (dispatch to Actions). It is waived: the reusable workflow does not use the P6 dispatch code, and `agent-job.yml` is untouched.
- T25 (README and phase report) is ticked while its dependency T19 is open.
- Nothing from P6 or P7 was re-run on GitHub for this PR.

**Phase report and ablation:**
- Every cell in the phase report against P7 is a dash. P7 has no resolve-rate, token or latency numbers, and P8 ran no task against a model. No number was made up.
- The planner variant (T11) is tested with stub models only. Its gain or cost is not measured. ADR-029 states the keep rule (must win on resolve rate and on tokens per bug) and, with no rows, draws no decision: the single agent stays the default.

**Limits behind the ticks:**
- **Mocks:** T08 intake, T09 PR creation, T10 backport and the four break-its (T21 to T24) were tested against a mock GitHub (a stateful fake), scripted models and local git repositories. No real label event, issue, PR or installation was used. Each break-it note lists the mutations used to show the test can fail (`docs/notes/p8-break-it-t21.md` to `t24.md`).
- **Not wired:** PR creation, the config check and the backport bot are functions; no running service calls them from a webhook yet. The reusable workflow does not call the PR code yet.
- **Quota:** T07 budgets live in the ledger. The service does not build them from the tenant config yet. The quota numbers in `docs/quotas.md` were checked on 2026-10-29 for the owner's own key; tenant plans are not confirmed.
- **Backport:** the real `git` ran on local bare repositories. The T23 break-it found that the git argument check let through some options; it was tightened (`SAFE_FLAGS`). Other git versions and a real remote were not tried.
- **ADRs 027, 028, 029** were written by Claude and have the status proposed. The owner decides. ADR-027 compares the tenant repo with our servers on quota, trust boundary and cost, but no cost figure was measured.
- **T01 notes** are a first pass written by Claude from the two posts; the owner should read the posts. The numbers (about 4 times and about 15 times the tokens of a chat) are Anthropic's, for its own research feature, not measured on Argus.
- **T00 versions:** re-checked on 2026-11-03 from registry JSON and docs pages. Three pins moved in the table (Tailwind 4.3.4, `@playwright/mcp` 0.0.84, gVisor release-20261102.0). This PR does not claim any of the code was re-tested on the new versions.
- **Sandbox and security:** inherited from P7. Docker `--network none` is the default tier and the only one measured (ADR-025). The App token plan and ADR-026 were checked on a throwaway repo in P7, not on a production App. The open risks in ADR-024 and ADR-027 are still open.

**Other limits:**
- **Small local model:** the model results this PR builds on (the P7 red-team) came from a small local model (`gemma4:e4b`), not the production model. P8 adds no new model result: the planner and the 20-task ablation never ran against a model.
- **Known test failure:** `packages/fix-loop/tests/test_ast_grep.py` fails, as it did before P5.
- **Test failures in this run:** `test_ast_grep.py` (known, before P5). `bench` (one test) and `dom2src-mcp` (three tests) fail on this machine for environment reasons given in the test table: the node package `@playwright/test` is missing (bench) and no platform checkout is set (dom2src-mcp). Those two packages are not touched by P8, and no P7 run of them is in the P7 PR text, so whether they passed before is not shown. Two other failures (`repro-agent` browser tests, one `fix-loop` Docker sandbox test) happened only while other suites ran in parallel and passed when run alone.
- **Test times are not benchmarks.** The suites ran in parallel on one laptop with Docker.
Owner steps that remain, in order: register the App (T02), install it and mint a token (T03), push and run the reusable workflow and `app.yml` (T04, T20), run on a real repo (T16), run the 20-task ablation on a local model (T12), record the video (T18), choose a licence and sweep `docs/` (T19), fill the README blanks (T17). To decide: accept ADR-027, 028 and 029.
