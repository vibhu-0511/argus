# Argus repo structure

This folder becomes the root of the monorepo. Python packages share one **uv workspace**; TypeScript packages share one **pnpm workspace**.

## Root files
| Path | Purpose |
|---|---|
| `PLAN.md` | Master plan: stack, architecture, timeline, metrics contract, risks, cut list |
| `TASKS.md` | Flat task checklist in execution order |
| `repo-structure.md` | This file |
| `phases/` | One file per phase (P00 to P09, plus P05.5) |
| `config/profiles.md` | Active profile. `personal` is $0. `company` may name a paid model API and a paid host. Secrets stay in the env var named there |
| `config/platform.md` | System under test: dcortex Canvas and the copa-local Postgres. Both profiles use it |
| `docs/adr/` | ADRs 001 to 030, one file each (`NNNN-title.md`) |
| `.github/workflows/` | CI: golden-fix run, tests on recorded fixtures, regression gate, dashboard deploy, skill lint, escape tests |
| `pyproject.toml` | uv workspace root (lists the Python packages) |
| `pnpm-workspace.yaml` | pnpm workspace root (lists the TypeScript packages) |

## Packages (under `packages/`)
| Package | Language | Phase | Contents |
|---|---|---|---|
| `argus-core` | py | P0 | Ticket/Task/Trajectory types, OpenAI-compatible model client (host from `config/profiles.md`), quota ledger |
| `target-app` | ts | P0 | Binding to dcortex Canvas and copa-local Postgres (`config/platform.md`). Not a second UI |
| `bench` | py + ts | P0 | Scorer CLI plus Playwright checks |
| `bugsmith` | ts | P0 | JSX/CSS mutation generator |
| `repro-agent` | py | P1 | Repro agent, repro verifier |
| `dom2src-plugin` | ts | P2 | Vite plugin adding `data-src` |
| `dom2src-mcp` | py | P2 | `locate()` MCP server (MCP Python SDK v2) |
| `fix-loop` | py | P3 | Agent loop, tools, context manager, sandbox runner, gates |
| `verify` | py + ts | P4 | Deterministic checks, judge, best-of-k |
| `eval` | py | P5 | Eval runner, trajectory metrics, regression gate |
| `dashboard` | static | P5 | GitHub Pages site built from results JSON |
| `skills/` | markdown | P5.5 | Reviewed skill files (agentskills.io format) |
| `flow` | py | P6 | FastAPI + DBOS control plane, reconciliation poller |
| `guard` | docs + config | P7 | Threat model, promptfoo configs, escape-test suite, audit-log verifier |
| `app` | py | P8 | GitHub App plus the reusable workflow |

P9 (optional) adds a small FastAPI target backend and lane-specific tools that reuse `argus-core`, `fix-loop`, `verify`, `eval` and `flow`.

## Layout
```
argus/
├── PLAN.md  TASKS.md  repo-structure.md
├── pyproject.toml            # uv workspace
├── pnpm-workspace.yaml       # pnpm workspace
├── config/profiles.md
├── config/platform.md
├── phases/
├── docs/
│   ├── adr/
│   ├── notes/
│   └── quotas.md             # measured free-tier limits (P0-T06)
├── .github/workflows/
└── packages/
    ├── argus-core/  target-app/  bench/  bugsmith/
    ├── repro-agent/  dom2src-plugin/  dom2src-mcp/
    ├── fix-loop/  verify/  eval/  dashboard/
    ├── skills/  flow/  guard/  app/
```
