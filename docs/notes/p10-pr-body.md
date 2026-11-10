**Draft PR text for P10. Not pushed, not created.** Base `stack/p8-app`, head `stack/p10-workbench`.

## Problem

Argus had no screen. Every run was a command line and a folder of files, so the owner could not type an issue, watch a run, read the before/after report, decide, and see the PR in one place. There was also no way to look at the run history without opening result files by hand.

P10 builds that UI as far as it can be real on one machine, and no further. It is local, it calls no model, and it opens no real PR.

## Solution

- New package `packages/workbench` (`argus_workbench`, command `argus-workbench serve`): a FastAPI app on `127.0.0.1` plus a static page (plain HTML, CSS and JS, no build step). No login. It is not a hosted service.
- Run store (T01): one folder per run under `.local/workbench/runs/<run_id>/` (git-ignored) with `ticket.json`, `state.json` and the other files of the run folder contract. State names and moves come from `flow.states`. A run id outside `[a-z0-9-]{1,64}` is refused.
- Server and request guards (T02): per-start token on every POST, Host and Origin checks (DNS rebinding), a CSP with no inline script, no CORS header, typed errors. The command has no `--host` option.
- Five screens, each labelled BUILT / PARTLY BUILT / PLANNED from the spec:
  - Screen 1, New issue (T03): text cap, optional PNG or JPEG screenshot checked by magic bytes (5 MB cap), repo and route from the spec list, free-tier acknowledgement, typed errors by field.
  - Screen 2, Live run (T06): stage bar and step timeline that poll while a run plays, tokens per step, quota meter, Stop and Retry. Quota-wait and stuck look different and say why.
  - Screen 3, Review and decision (T07): four checks in order, an advisory judge label, the report in a sandboxed frame, Approve / Request changes / Reject, one decision per idempotency key. The server refuses Approve after a failed verifier.
  - Screen 4, PR raised (T08): on Approve a draft PR is built through `argus_app.pr` and `flow.github_write` on an in-memory mock GitHub. One stable branch, update on a second approve, no PR for an empty patch.
  - Screen 5, History (T09): run list with SIMULATED and REPLAY badges, and four metrics read from stored result files only (a dash where none exists). Simulated and replay runs are in no aggregate (tested).
- Runners (T04, T05): `ScriptedRunner` (5 scenarios: normal, quota, stuck, verifier failed, judge disagrees), `ReplayRunner` (plays a stored trajectory) and `FixLoopRunner` (wraps `fix_loop.run_fix`, scripted model only, not reachable over HTTP). Every file they write is tagged SIMULATED or REPLAY. The quota scenario hard-stops through `argus_core.ledger`.
- Four break-its (T10 to T13, index in `docs/notes/p10-break-its.md`): inert rendering of script and markup, hostile uploads, forged requests, double approve. Each has a note listing the mutated builds that made it fail.
- End-to-end run (T14): a Chromium walk of all five screens and the five scenarios, 23 screenshots in `packages/workbench/docs/shots/`, plus a 6-test HTTP-level walk (`test_e2e_http.py`).
- ADR-031 (T15): the workbench is local, file-backed and unauthenticated; what that does not defend. Status proposed.
- Package README with a table of every control and its state, `docs/architecture/p10.md` with a section per task, and the phase report (`phases/P10-argus-workbench.md`, all cells dashes on purpose).
- `docs/architecture/overview.md` now draws P10 (the diagram below).

## Architecture (HLD)

The diagram shows every phase up to and including this one (P9 is not drawn). This phase's part has a thick border and is labelled `NEW IN THIS PR`; thick arrows are links added here. The same source is committed as `docs/architecture/overview.md`. Per-task detail is in `docs/architecture/p10.md`.

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

  subgraph S8 ["P8 app"]
    VERS8["version re-check<br/>App, reusable-workflow and free-tier limits, 2026-11-03"]:::p8
    MANOTES["multi-agent notes<br/>about 4x tokens per agent, about 15x multi-agent; coding is a bad fit"]:::p8
    MANIFEST["App manifest<br/>argus_app.manifest, five permissions equal ADR-026, URLs from env; App not registered"]:::p8
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

  subgraph S10 ["P10 workbench (NEW IN THIS PR)"]
    WSTORE["run store<br/>argus_workbench.store, one folder per run, typed state.json; local files, no database"]:::p10
    WSERVER["API server<br/>FastAPI on 127.0.0.1 only, no login, calls no model"]:::p10
    WSEC["request guards<br/>per-start token, Host and Origin check, CSP, typed errors"]:::p10
    WSCR1["screen 1 New issue<br/>typed intake, screenshot by signature, 5 MiB cap"]:::p10
    WSCR2["screen 2 Live run<br/>polls the run; quota-wait and stuck views; meter is ILLUSTRATIVE"]:::p10
    WSCR3["screen 3 Review<br/>checks, judge note, sandboxed report; Request changes and Reject not clicked in a browser, T07 not ticked"]:::p10
    WSCR4["screen 4 PR raised<br/>mock GitHub only; tab label still reads PLANNED P8"]:::p10
    WSCR5["screen 5 History<br/>run list with SIMULATED and REPLAY badges; metrics from stored P5 results only"]:::p10
    WSCRIPT["ScriptedRunner<br/>five scenarios, every file tagged SIMULATED; no model"]:::p10
    WREPLAY["ReplayRunner<br/>plays a stored trajectory as REPLAY; no patch, no verdict"]:::p10
    WFIXRUN["FixLoopRunner<br/>run_fix with a scripted model; tests only, not reachable over HTTP, never run on a real model"]:::p10
    WDECIDE["review and decision<br/>Approve, Request changes, Reject; idempotency key; failed verifier refuses Approve"]:::p10
    WMOCKPR["PR step<br/>pull_request.py on an in-memory mock GitHub; no real PR was opened"]:::p10
    WHISTM["history metrics<br/>history_metrics.py; simulated and replay runs are never counted"]:::p10
    WBREAKS10["P10 break-its<br/>T10 markup inert, T11 hostile uploads, T12 forged requests, T13 double approve; T10 not ticked"]:::p10
    WE2E["end-to-end run<br/>HTTP walk test; browser walk with screenshots, some buttons not clicked"]:::p10
    WADR["ADR-031<br/>proposed: local, file-backed, unauthenticated; owner to decide"]:::p10
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

  %% P10 links
  WSERVER -- "guards every request" --> WSEC
  WSERVER -- "routes read and write runs" --> WSTORE
  WSTORE -- "Ticket, Trajectory, StopReason" --> CORE
  WSTORE -- "only the allowed transitions" --> STATES
  WSTORE -- "check order" --> CHECKS
  WSCR1 -- "creates the run folder" --> WSTORE
  WSCR2 -- "quota meter reads" --> LEDGER
  WSCRIPT -- "quota scenario is charged through" --> LEDGER
  WSCRIPT -- "state changes" --> WSTORE
  WREPLAY -- "plays a stored" --> TRAJ
  WFIXRUN -- "runs the loop" --> FIX
  WFIXRUN -- "calls counted" --> LEDGER
  WSCR3 -- "decides with" --> WDECIDE
  WDECIDE -- "Approve and Reject events" --> STATES
  WDECIDE -- "reads verdict.json" --> CHECKS
  WDECIDE -. "judge note, advisory" .-> JUDGE
  WDECIDE -- "approve hook" --> WMOCKPR
  WSCR4 -- "raises" --> WMOCKPR
  WMOCKPR -- "find before act, draft PR" --> PRBUILD
  WMOCKPR -- "client over a mock transport" --> GHWRITE
  WMOCKPR -- "one branch per ticket" --> STATES
  WSCR5 -- "lists runs" --> WSTORE
  WSCR5 -- "numbers from" --> WHISTM
  WHISTM -- "result file list" --> DASH
  WHISTM -- "Results and Wilson interval" --> RUNNER
  WHISTM -- "tenant share of tokens" --> LEDGER
  WBREAKS10 -. "markup, uploads, forged requests" .-> WSEC
  WBREAKS10 -. "double approve" .-> WDECIDE
  WE2E -. "walks the five screens" .-> WSERVER
  WADR -. "decides the trust model" .-> WSEC
  WADR -. "builds on" .-> ADRS7

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
  classDef p8 fill:#ccfbf1,stroke:#0f766e,stroke-width:1.5px,color:#111827
  style S8 fill:none,stroke:#0f766e,stroke-width:1.5px
  classDef p10 fill:#fae8ff,stroke:#a21caf,stroke-width:4px,color:#111827
  style S10 fill:none,stroke:#a21caf,stroke-width:4px
  classDef ext fill:#ffffff,stroke:#6b7280,color:#111827,stroke-dasharray: 4 3
  linkStyle 221,222,223,224,225,226,227,228,229,230,231,232,233,234,235,236,237,238,239,240,241,242,243,244,245,246,247,248,249,250,251 stroke-width:3px
```

## Architecture (LLD)

How one request moves through the workbench (all on `127.0.0.1`, no model, no network):

1. **Guards first.** Every request passes `security.py`: Host must be `127.0.0.1` or `localhost`; a POST needs the per-start token and, if it has an Origin, a local one. The CSP is on every response. A refusal is a typed error `{"error": {"code", "field", "message"}}` and changes nothing.
2. **Intake.** `routes/issues.py` validates the form (text cap, magic bytes, allowed lists, acknowledgement), picks the file name itself, and creates the run folder in state `received` through `store.py`. The store only accepts moves that `flow.states` allows.
3. **Run.** `manager.py` starts a runner on a tick (default 700 ms). `ScriptedRunner` (`runner.py`) writes `trajectory.jsonl` step by step from the spec's illustrative `sim` block, plus `verdict.json`, `report.html` and `patch.diff` for the scenarios that get that far. The quota scenario calls `argus_core.ledger` and stops on `QuotaExceeded`. Stop ends a run; Retry makes a new run id and never changes the old one. Every file is tagged SIMULATED or REPLAY.
4. **Live view.** `routes/runs_view.py` and `meter.py` are read-only. The page polls (it does not use SSE).
5. **Review and decision.** `routes/review.py` shows the four checks in the order of `verify.pipeline`. The report is served with its own sandbox CSP and shown in a frame with no allow tokens. `decisions.py` creates `decision.json` exclusively, under a lock, once per idempotency key. The server checks the verdict, not the button.
6. **PR.** On Approve, `pull_request.py` builds the PR through `argus_app.pr.open_or_update_pr` over `mock_github.py` (an in-memory transport; the URL ends in `.invalid`). A second approve updates the same PR. `pr.json` records it.
7. **History.** `routes/history.py` and `history_metrics.py` list the run folders and read metrics only from stored result files (through the dashboard file list and `eval.results`). A SIMULATED or REPLAY run is listed with a badge and counted in nothing.

Links to existing code: `flow.states` (state names), `argus_core` (ticket schema, ledger), `verify` (check order), `argus_app.pr` and `flow.github_write` (PR), `fix_loop.run_fix` (adapter), `eval.results` and `packages/dashboard` (history). No file of an existing package is changed; outside `packages/workbench` the diff touches docs, `TASKS.md`, the phase file, `pyproject.toml` and `uv.lock` (workspace member).

Decisions made before the phase (in `phases/P10-argus-workbench.md`; the owner can change any of them, and a change must be stated here; none was changed):
1. Local only: FastAPI on 127.0.0.1 plus a static page, no login, not a hosted service.
2. New package `packages/workbench`; the run store is files under `.local/workbench/runs/<run_id>/`; schemas come from other packages, nothing is copied.
3. Runs are SCRIPTED or REPLAYED (three runners); everything they produce is tagged and in no aggregate.
4. No real PR: the PR screen uses the mock GitHub transport. A real PR needs the registered App (owner step).
5. State names come from `flow.states`, not the explainer's proposed list; `quota-wait` and `stuck` are display states derived from the stop reason.
6. The ADR number is ADR-031 (ADR-030 is reserved for P9).

## Stack

| Item | Value |
|---|---|
| Base | `stack/p8-app` (`5561a09`) |
| Head | `stack/p10-workbench` (`c66e3bb`) |
| Previous PRs | P8 is `stack/p8-app`, not pushed, no PR yet. [#12](https://github.com/vibhu-0511/argus/pull/12) P6 flow (draft, still open). [#15](https://github.com/vibhu-0511/argus/pull/15) P7 guard was open when the P8 text was written; its state now was not re-checked. P5.5 and P5 were merged into `main` per the P8 text |
| Size against `stack/p8-app` | 107 files, +11,832 and -9 lines (`git diff --shortstat stack/p8-app...stack/p10-workbench`, without this PR text file) |

Notes on the stack:
- P10 is cut from `stack/p8-app` (it is the merge base). If P8, P7 or P6 change before they merge, this branch needs a merge from them.
- P8 is not pushed and 10 of its 26 tasks are unticked (see the P8 PR text). P10-T00 depends on P8-T25, which is ticked there while its own dependency T19 is open.
- P9 is skipped; ADR-030 is reserved for it.

## Tests

All run one package at a time on 2026-11-10 on Windows 11 (`uv run --all-packages python -m pytest packages/<name>/tests -q`), one after the other (not in parallel), at head `096e1a4` (the commit before this text file was added). No test calls a model.

| Command | Result |
|---|---|
| `packages/workbench/tests` | 607 passed, 0 skipped (131 s on this run; the README says about 65 s on a quieter machine) |
| `packages/app/tests` | 248 passed |
| `packages/argus-core/tests` | 91 passed |
| `packages/eval/tests` | 96 passed |
| `packages/guard/tests` | 115 passed |
| `packages/skills/tests` | 65 passed, 1 skipped |
| `packages/verify/tests` | 47 passed |
| `packages/repro-agent/tests` | 51 passed, 1 skipped |
| `packages/fix-loop/tests` | 125 passed, 1 failed: the known `test_ast_grep.py::test_pattern_returns_file_and_line_and_a_bad_pattern_is_typed` (`src/main.tsx is not in the worktree`) |
| `packages/flow/tests` with a throwaway Postgres 16 container `argus-p10-pr` on port 55561 (`ARGUS_FLOW_DATABASE_URL`, random password), removed afterwards | 550 passed, 5 skipped |
| `packages/bench/tests` | 29 passed, 1 failed: `test_score.py::test_score_pass_fail_and_unsliced_reasons`, `Cannot find package '@playwright/test'` (no node modules in this worktree). Not changed by P10 |
| `packages/dom2src-mcp/tests` | 51 passed, 3 failed: `test_embed.py::test_query_returns_ranked_canvas_files` and two in `test_repo_map.py`, `set ARGUS_PLATFORM_REPO to the dcortex-platform checkout` (no platform checkout set). Not changed by P10 |
| `uv lock --check` | clean (Resolved 105 packages; P8 had 104, the new member is `workbench`) |
| Mermaid parse of the diagram | `mermaid parse OK, 465 lines`; 252 links, thick range 221 to 251 (31 P10 links), re-checked on 2026-11-10 at head `c66e3bb` |
| GitHub Actions on this PR | **not run.** The branch was not pushed, and no workflow exists for the workbench. Nothing of P10 ran on GitHub |
| `actionlint` | not run (no P10 workflow) |
| `packages/dashboard`, `bugsmith`, `dom2src-plugin`, `target-app` | no tests folder |

Re-run at `c66e3bb` on 2026-11-10 by the owner's session: workbench 607 passed, argus-core 91, app 248, eval 96, verify 47, guard 115, flow 550 passed and 5 skipped (throwaway Postgres, removed), fix-loop 125 passed and 1 failed (the known `test_ast_grep.py`), `uv lock --check` clean. The two small changes in `c66e3bb` (a label and a link colour) touch no test.

Not re-run here: the Chromium walk of T14 (23 screenshots from 2026-11-10 are committed; the browser was not started again for this text) and the mutated builds of the four break-its (their counts are in the phase report and the break-it notes).

## Out of scope

- Registering the GitHub App and a real PR from an approved run (owner steps: `docs/notes/p8-t02-owner-steps.md`, `p8-t03-owner-steps.md`).
- Any model call. P10 makes none, in code or in tests.
- Hosting the workbench, a login, TLS, tenant isolation, a rate limit (ADR-031 says these are not defended).
- Calibrating the judge (100 labels by a person; alpha of at least 0.80 first).
- Real runs for History. Only a real model run can give History a number of its own.
- A GitHub Actions workflow for the workbench. None was written.
- The GitHub-label trigger on Screen 1 (only the typed trigger works; `github` is refused with `trigger_not_typed`).
- Mark ready for review, merged and conflict states on Screen 4, and the timed-out and check-error states on Screen 3.
- Fixing the spec tab label for Screen 4, which still reads `PLANNED P8` (the label is the spec's text, copied verbatim by rule).

## What this PR does not claim

16 of 17 P10 tasks are ticked and 1 is not. Nothing in this PR ran on GitHub (the branch was not pushed), no model was called, and no real PR was opened. The limits are below.

**Unticked task (1), with the reason:**
- **T03 Screen 1, New issue:** the criterion "the stored ticket directory passes `bench validate`" holds only in part. `bench validate` wants `ticket.json`, `checks.json`, `meta.json`, `bug.patch` and `golden.patch`; a bug report from the form has no patches or checks, so the bare run folder fails (a test pins that, exit 1). Copied next to the four task-only files of the seeded BUG-17 task, the stored `ticket.json` and screenshot pass (`valid <dir>`). Whether that meets the criterion is the owner's call. Note: `docs/notes/p10-t03.md`.

**Ticked after a second look (T07, T10):** the task authors left both unticked. On the merged build, Request changes was clicked in the browser pane: it stored the note and started a follow-up run, and the stored note rendered as text. Approve was refused by the running server after a failed verifier (`verifier_failed`, 409) and needed a written reason when the judge said fail (`reason_required`, 400). Reject was not clicked in a browser; its listed-reason rule is covered by `test_review.py`. T10's PR-body case now runs with the merged build (607 passed, none skipped) and the break-it fails on mutated builds. The browser check of T10 on every screen was not repeated.

**Waived or open dependencies:**
- T14 (end-to-end browser run) is ticked while its dependency T03 is not. T16 depends on T14.
- Base branches: P8 (`stack/p8-app`) is not pushed and has 10 unticked tasks; P6 (PR 12) is a draft and still open; P7 was open when the P8 text was written. Nothing from P6, P7 or P8 was re-run on GitHub for this PR.

**Decisions made before the phase that the owner can change** (from `phases/P10-argus-workbench.md`; none was changed, and a change must be stated in this text):
1. Local only: FastAPI on 127.0.0.1, a static page, no login, not a hosted service.
2. New package `packages/workbench`; the run store is git-ignored files under `.local/workbench/runs/<run_id>/`.
3. Runs are SCRIPTED or REPLAYED (`ScriptedRunner` with 5 scenarios, `ReplayRunner`, and `FixLoopRunner` with a scripted model only), tagged and in no aggregate.
4. No real PR: the PR screen uses the mock GitHub transport.
5. State names come from `flow.states`, not the explainer's list; `quota-wait` and `stuck` are display states.
6. The ADR number is ADR-031 (ADR-030 is reserved for P9).

**No model, nothing measured:**
- No model was called anywhere in P10, in code or in tests (`tests/test_no_model.py` checks that no key, token or model name is read at import and no model client is named in the source).
- Every run the workbench makes is SIMULATED or REPLAY. The steps and token counts of a scripted run are the illustrative `sim` block of the spec, not a measurement. These runs are in no aggregate (tested in `test_history.py`).
- The phase report against P8 is all dashes on purpose. P8 has no resolve rate, tokens or latency (its 20-task ablation ran 0 of 20), and P10 produces none. No number was made up.
- The History screen showed numbers (resolve rate 71.4%, 20 of 28 tasks, Wilson 95% 52.9% to 84.7%; tokens per bug 34,471 in; p50 latency 1617.0 s) read from `packages/eval/results/ablation-B.json`. That is the P5 routing ablation from a Claude session (tokens are a chars/4 estimate, latency is wall clock with several tasks at once). It is not a P10 result and not a P8 result. Quota share showed a dash because no ledger file with a tenant dimension exists on this machine.
- The judge label on the Review screen is scripted. No judge ran in P10 and alpha was never computed (the 100 calibration labels are null), so the label is advisory.
- The quota meter rows are marked ILLUSTRATIVE. The quota scenario stops through the real `argus_core.ledger`, but the throwaway ledger stands in for a real provider quota.

**The PR screen is a mock:**
- The PR is built through `argus_app.pr` and `flow.github_write` over an in-memory mock GitHub. The URL ends in `.invalid`. No network call, no issue, no branch and no PR was created on GitHub, and the App is not registered. CI state on the PR reads "not run".
- Mark ready, merged and conflict states are not built. The tab label for Screen 4 still reads `PLANNED P8` although the screen is built (the spec's text is copied verbatim by rule).

**Limits behind the ticks:**
- **Not built:** the GitHub-label trigger on Screen 1 (spec text only; `github` is refused with `trigger_not_typed`), the "service waking" state, duplicate-submit dedupe (two submits make two runs), and a CI workflow for the workbench.
- **Not reachable or not clicked:** `FixLoopRunner` is not reachable over HTTP and was never run against a real model. `ReplayRunner` was not clicked in a browser (the page has no replay control; API only). Retry after the quota reset (00:00 UTC) was not seen in a browser.
- **Browser evidence:** Chromium only (Playwright), on 2026-11-10. The Playwright browser was shared with other sessions during the run, so later walks used isolated contexts. The `argus-workbench.exe` launcher is blocked on the owner's machine (Windows Application Control, error 4551); the module form `python -m argus_workbench.cli serve` was used.
- **Uploads:** only the signature is checked, so a PNG header followed by junk is stored (nothing serves it back). The size cap reads the Content-Length header (411 when absent).
- **Double approve:** the locks are per process. Two server processes on one run folder are not covered. The mutation test removed both locks; the exclusive create of `decision.json` stayed, so it shows the lock matters, not that the create alone is unsafe.
- **Break-its:** one mutated build per break-it was re-run for the phase report; the full mutation sets are in the notes `docs/notes/p10-break-it-t10.md` to `t13.md` and were run on the task branches. The counts in the index are from each task branch, not from the merged package. The T12 test covers the issue-create and start routes by discovering every unsafe route, which it could do only after the merge.
- **Security:** ADR-031 is written by Claude and has the status proposed; the owner decides. Local is not the same as safe: the workbench has no login, no TLS, no rate limit and no tenant isolation, and it is not defended as a hosted service.
- **Cosmetic, left as is:** the backport text on the PR screen ends "(P8-T10).)."; `GET /favicon.ico` is a 404.
- **Inherited:** sandbox and security limits from P7 and the unfinished P8 apply. P10 adds no sandbox run.

**Other limits:**
- **Known test failure:** `packages/fix-loop/tests/test_ast_grep.py` fails, as it did before P5.
- **Test failures in this run:** `test_ast_grep.py` (known). `bench` (one test) and `dom2src-mcp` (three tests) fail on this machine for environment reasons given in the test table: the node package `@playwright/test` is missing (bench) and no platform checkout is set (dom2src-mcp). P10 does not touch those two packages, and no earlier run of them is in this text, so whether they passed before is not shown here.
- **Flaky tests:** in the P8 run, two `repro-agent` browser tests and one `fix-loop` Docker sandbox test failed only while other suites ran in parallel and passed alone. This run did not run in parallel and none of them failed, so that is not shown to be fixed.
- **Test times are not benchmarks.** The workbench suite took 131 s here against about 65 s on an earlier run on the same machine.

Owner steps that remain, in order: decide the open box (T03); click Reject in a browser (T07); push the branch and see the first CI run; register the App and install it (P8-T02, P8-T03) before any real PR; calibrate the judge; fix the Screen 4 tab label in the spec. To decide: accept ADR-031.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
