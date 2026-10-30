# System under test

Argus does not grow its own UI or its own airline database. The bench, the repro checks, and the fix loop run against dcortex-platform as it already exists. This file is that binding. The personal and company profiles both point here. Hours stay 556 h / 255 tasks. P0-T09 is still 4 h. The work is the binding, not a second React app.

Argus's own workflow store at P6 stays the personal profile's Render and Neon. That database is not this one.

## Cell

Use the synthetic cell only. Live Copa (Option E, VPN, database `copa_local_aims`) is out of scope.

| | |
|---|---|
| Repo | `C:\Users\vibha\Downloads\data\dcortex\dcortex_claude\dcortex-platform` |
| Compose | `docker compose --profile copa-local up --build` |
| Tenant | `copa-local` (`BFF_TENANT_ID`, `MIGRATE_TENANT_ID`) |
| Console | `http://localhost:19080` |
| Postgres service | `db-copa-local` |
| Host port | 5433 |
| Database name | `copa_local` |
| Env names | `DATABASE_URL`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` |

Do not copy a password into this file or into Argus. Full-posture reads need the GUC `app.current_tenant`. No GUC means zero rows.

Schema is TypeScript DDL applied by `apps/migrate`, not a SQL migrations folder. Registry: `apps/migrate/src/baseline.ts`.

## What Argus may exercise

Canvas is served by the BFF. Signed-in `/` opens `/ops/radar`. Playwright already in `tests/e2e-ui` covers sign-in, `/review`, and the five `/desk` tabs. The first Argus checks use these five flows, which do not need a flight seed and are not legality screens:

1. Sign in at `/login` or `/ops/login`.
2. Ops menu: `/ops/radar`, `/ops/operations`, `/ops/launchpad`, `/ops/rules`.
3. Desk tabs at `/desk` (`?sel=console|timeline|crew|brief`).
4. User admin at `/admin/users`.
5. Audit table at `/admin/audit`.

Dev sign-in published in the platform README is `admin` / `dev-admin`.

## What Argus does not write

Argus writes a git patch in a worktree of the platform repo. It does not insert into platform tables. In particular it does not write `stratum.entities`, `cortex.verdicts`, or `forge.solve_records`. A console click is not how a task is created. Tasks arrive through the outbox and `apps/cortex-runtime`. A human verdict is `POST /api/tasks/:taskId/verdict`. Argus does not take that path, and it does not sit on the legality or solve path.

The model call stays outside the sandbox. On the personal profile the model host is still Groq, Mistral, and local Ollama. `platform/model-client` (Anthropic and Bedrock) is the company profile's client, and only after that profile is filled.

## Package

`packages/target-app` is this binding: a README that names the repo, the cell, the five flows, and the env var names. It does not vendor Canvas and it does not run a second Vite app. P0-T11's clean tree and broken tree are two worktrees of the platform repo.
