# target-app

This package is the binding to dcortex. It is not a second UI, and it does not vendor Canvas or start a Vite app. Argus writes a git patch in a worktree of the platform repo. It does not insert into platform tables.

The source of these facts is [`config/platform.md`](../../config/platform.md).

## Cell

Synthetic cell only. Live Copa is out of scope.

| | |
|---|---|
| Repo | `dcortex-ai/dcortex-platform` on GitHub. The local checkout path is the env var `ARGUS_PLATFORM_REPO` |
| Compose | `docker compose --profile copa-local up --build` |
| Tenant | `copa-local` (`BFF_TENANT_ID`, `MIGRATE_TENANT_ID`) |
| Console | `http://localhost:19080` |
| Postgres service | `db-copa-local` |
| Host port | 5433 |
| Database name | `copa_local` |
| Env names | `DATABASE_URL`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` |

No password is stored in this repo. A full-posture read needs the GUC `app.current_tenant`. Schema is TypeScript DDL applied by `apps/migrate`. Registry: `apps/migrate/src/baseline.ts`.

Dev sign-in published in the platform README is `admin` / `dev-admin`.

## Flows

The first checks use these five flows. They do not need a flight seed and they are not legality screens.

1. Sign in at `/login` or `/ops/login`.
2. Ops menu: `/ops/radar`, `/ops/operations`, `/ops/launchpad`, `/ops/rules`.
3. Desk tabs at `/desk` (`?sel=console|timeline|crew|brief`).
4. User admin at `/admin/users`.
5. Audit table at `/admin/audit`.

## What a check uses

P0-T11's clean tree and broken tree are two worktrees of the platform repo above. The model call stays outside the sandbox. On the personal profile the model host is Groq, Mistral, or local Ollama.
