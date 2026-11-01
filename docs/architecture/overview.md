# Architecture overview (P0 to P2)

As-built view of Argus after phase P2. Later phases are not drawn. This file grows by one phase in each stacked pull request; the diagram source is the same text the PR description shows.

```mermaid
flowchart LR
  TICKET["Ticket<br/>text and optional screenshot"]:::ext
  CANVAS["dcortex Canvas<br/>system under test"]:::ext
  PG[("copa-local Postgres")]:::ext
  HOSTS["Model hosts<br/>Groq, Mistral, Ollama"]:::ext

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

  subgraph S2 ["P2 dom2src (NEW IN THIS PR)"]
    PLUGIN["Vite plugin<br/>stamps data-src"]:::p2
    LOCATE["locate MCP server<br/>spec 2026-07-28"]:::p2
    RMAP["repo-map index"]:::p2
    PGV["pgvector file search"]:::p2
    ABL["retrieval harness<br/>and ablation"]:::p2
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

  classDef p0 fill:#dbeafe,stroke:#1d4ed8,stroke-width:1.5px,color:#111827
  style S0 fill:none,stroke:#1d4ed8,stroke-width:1.5px
  classDef p1 fill:#cffafe,stroke:#0e7490,stroke-width:1.5px,color:#111827
  style S1 fill:none,stroke:#0e7490,stroke-width:1.5px
  classDef p2 fill:#dcfce7,stroke:#15803d,stroke-width:4px,color:#111827
  style S2 fill:none,stroke:#15803d,stroke-width:4px
  classDef ext fill:#ffffff,stroke:#6b7280,color:#111827,stroke-dasharray: 4 3
  linkStyle 23,24,25,26,27,28 stroke-width:3px
```

## How to read it

| Mark | Meaning |
|---|---|
| Thick border, box labelled `NEW IN THIS PR` | the part this phase adds |
| Thin border | an earlier phase |
| Dashed white box | a system outside this repo (Canvas, Postgres, model hosts, the ticket) |
| Dotted arrow | a stored input (`fixture`), a test-only link or an advisory link, not a live call |
| Thick arrow | a link added in this phase |

Colours: P0 blue, P1 cyan, P2 green, P3 yellow, P4 orange.

## What P2 adds

- `packages/dom2src-plugin`: a Vite plugin that stamps `data-src="file:line:col"` on elements in dev and test builds.
- `packages/dom2src-mcp`: `locate(selector, html)` as an MCP server, a symbol repo-map and local pgvector search over Canvas files.
- A harness that scores each retriever by the file in the golden patch, and an ablation over the 30 seeded tasks.

## Earlier phases

- **P0 bench and quota ledger:** `packages/bench`: 30 seeded and 300 generated bug tasks, and the scorer that runs a task's Playwright checks against a copy of Canvas with no model call.
- **P1 repro agent:** `packages/repro-agent`: a loop that asks a model for a Playwright script, runs it, revises on error and stops at a cap with a named stop reason.

## Sources

Built from `PLAN.md` (Architecture) and, where they exist, the `docs/architecture/pN.md` "As built" sections. Edges not stated word for word there: `RVERIFY --> SCORER` (the verifier runs a script on a task's buggy and golden trees); `SEEDED -.-> ABL` (retrievers are scored by the golden patch's file).
