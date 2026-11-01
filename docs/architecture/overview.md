# Architecture overview (P0)

As-built view of Argus after phase P0. Later phases are not drawn. This file grows by one phase in each stacked pull request; the diagram source is the same text the PR description shows.

```mermaid
flowchart LR
  CANVAS["dcortex Canvas<br/>system under test"]:::ext
  PG[("copa-local Postgres")]:::ext
  HOSTS["Model hosts<br/>Groq, Mistral, Ollama"]:::ext

  subgraph S0 ["P0 bench and quota ledger (NEW IN THIS PR)"]
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

  classDef p0 fill:#dbeafe,stroke:#1d4ed8,stroke-width:4px,color:#111827
  style S0 fill:none,stroke:#1d4ed8,stroke-width:4px
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

Colours: P0 blue, P1 cyan, P2 green, P3 yellow, P4 orange.

## What P0 adds

- `packages/bench`: 30 seeded and 300 generated bug tasks, and the scorer that runs a task's Playwright checks against a copy of Canvas with no model call.
- `packages/bugsmith`: breaks the UI on purpose (JSX and CSS rules); a generated bug is kept only if the checks fail on it and pass on the original.
- A flake detector (repeat runs, quarantine on disagreement) and the golden-fix runner.
- `packages/argus-core`: the Ticket, Task and Trajectory schemas, the OpenAI-compatible model client and the quota ledger that refuses a call before any request is sent.
- `packages/target-app`: the binding to Canvas and Postgres. `golden.yml` is a manual workflow because the Canvas repo is private.

## Sources

Built from `PLAN.md` (Architecture) and, where they exist, the `docs/architecture/pN.md` "As built" sections.
