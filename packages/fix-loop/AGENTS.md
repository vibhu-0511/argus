# dcortex-platform worktree

This file is the map for a fix run. The checkout is the repo named in `config/platform.md`. Argus writes a git patch in a worktree of that repo. It does not insert into platform tables.

## Layout

| Path | What it is |
|---|---|
| `apps/` | Deployables. `apps/canvas` is the ops console (Vite + React), served by `apps/bff`. `apps/migrate` applies schema. `apps/cortex-runtime` consumes the outbox. |
| `platform/` | Shared layers: `contracts`, `stratum`, `cortex`, `forge`, `bff`, `canvas-format`, `canvas-ui`. |
| `domains/` | Airline content, including `domains/airline/crew`. |
| `tenants/` | Per-airline config. Argus uses the `copa-local` tenant. |
| `rules/` | Shared domain rules. |
| `tests/` | Cross-package gates, including `tests/e2e-ui`. |
| `deploy/` | Dockerfiles and cell config. |
| `knowledge-base/` | Wiki. Local run details are in `knowledge-base/concepts/running-locally.md`. |

Other apps in `apps/`: `data-plane`, `metric-snapshots`, `passenger-ops`, `api`, `engineering-ops`, `work-os`, `commitment-audit`.

## Run

From the repo root, in Git Bash, with LF line endings:

```bash
corepack enable
pnpm install --frozen-lockfile
docker compose --profile copa-local up --build
```

Node is 24. pnpm is 10.12.1, from corepack, not a global npm install.

`copa-local` console: `http://localhost:19080`. Postgres host port `5433`, database name `copa_local`. Dev sign-in published in the platform README is `admin` / `dev-admin`. Signed-in `/` opens `/ops/radar`.

Canvas scripts in `apps/canvas/package.json`:

```bash
npm run typecheck
npm run build
npm run lint
npm run test
```

## Gotchas

- Use the synthetic `copa-local` cell. Live Copa (VPN, database `copa_local_aims`) is out of scope. Plain `docker compose up` is a different console, `http://localhost:18080`, and a relaxed posture.
- Do not write `stratum.entities`, `cortex.verdicts`, or `forge.solve_records`. Do not copy a database password into a prompt or a patch.
- Schema is TypeScript DDL in `apps/migrate/src/baseline.ts`. There is no SQL migrations folder.
- The model call stays outside the sandbox. Bench checks are read-only.
