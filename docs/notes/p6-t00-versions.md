# P6-T00 version re-check

Checked on 2026-11-01. Every row has the page it came from. "not confirmed" means the page did not say, or the page could not be read. No number below is from memory. Format follows `docs/notes/p5-t00-versions.md`.

Dependency waived: P6-T00 lists `P5.5-T17` as its dependency. The owner started P6 before P5.5 (see `docs/notes/p6-waves.md`), so that dependency is waived and this check stands on its own date.

## DBOS (Python)

| Item | Value | Source | Notes |
|---|---|---|---|
| Package and version | PyPI `dbos` latest is 3.4.0, uploaded 2026-10-28 (UTC). Licence MIT. `Requires-Python >=3.10` | [PyPI JSON](https://pypi.org/pypi/dbos/json) | Same 3.4.0 as the 2026-10-30 check. Fits the repo's Python 3.12. Not yet a dependency in any `pyproject.toml` (T03 adds it) |
| Core dependencies | `psycopg[binary]>=3.1`, `sqlalchemy[asyncio]>=2.0.43`, `pyyaml`, `croniter`, `click`, `python-dateutil`. Extras: `otel`, `validation`, `aiosqlite`, `enterprise` (`dbos-enterprise==3.4.0`) | PyPI JSON | The Conductor client is in the `enterprise` extra, not in the base install |
| Postgres requirement | System database may be Postgres or SQLite; "Postgres is recommended for production". With Postgres DBOS always connects through the psycopg 3 driver and replaces any driver named in the URL. Default if no URL is given: a SQLite file. The docs describe "no separate orchestration server and no infrastructure required besides Postgres" | [configuration reference](https://docs.dbos.dev/python/reference/configuration), [architecture](https://docs.dbos.dev/architecture) | Minimum Postgres server version: not confirmed (neither page states one). Neon's Postgres major version is a T11 item |
| `use_listen_notify` | Defaults to `True` (Postgres LISTEN/NOTIFY to await notifications and events); `False` means polling. Ignored on SQLite. "On Postgres, this setting determines which notification triggers are created with the system database, so do not change it after the system database is first created." Related: `notification_listener_polling_interval_sec` default 1.0 s (used when polling) | configuration reference | Decide it before the first migration on Neon. Whether LISTEN/NOTIFY works through Neon's pooled connection endpoint: not confirmed (T11 tests it) |
| Executor id | Config key `executor_id`: "A unique process ID used to identify the application instance in distributed environments. If using DBOS Conductor or Cloud, this is set automatically." Each workflow is tagged with the id of the executor that started it. A restarting process with an executor id recovers only the PENDING workflows of that executor id and that application. Without Conductor, on a single server, every restart recovers all PENDING workflows | configuration reference, [workflow recovery](https://docs.dbos.dev/production/workflow-recovery) | Default value of `executor_id` when unset: not confirmed (the pages read do not give it). Render replaces the instance on each deploy, so T03/T12 must set a stable id explicitly |
| Application version | Config key `application_version`. "By default, application version is automatically computed from a hash of workflow source code." On recovery DBOS "only recovers workflows whose version matches the current application version". Setting a fixed string pins the version across deploys; the docs also describe an auto-upgrade mode with a per-deploy version | [upgrading workflow code](https://docs.dbos.dev/python/tutorials/upgrading-workflows) | With the default hash, any code change on redeploy gives a new version and old PENDING workflows are not recovered by the new code unless auto-upgrade is on. Pin the version (T03) |
| Conductor | Optional control plane. Enabled only if `conductor_key` is set; it needs `pip install "dbos[enterprise]"`. It detects dead executors over a websocket and has another executor recover their workflows; default executor timeout 60 s. Not required for single-server recovery | configuration reference, [distributed recovery](https://docs.dbos.dev/conductor/distributed-recovery), [architecture](https://docs.dbos.dev/architecture) | P6 runs one executor on Render with no `conductor_key` (PLAN risk 3). Pricing and free-tier limits of Conductor: not read, not confirmed |
| Step and workflow guarantees | Workflows run to completion; steps "are tried at least once but are never re-executed after they complete"; transactions commit exactly once; a workflow ID acts as an idempotency key | [workflows tutorial](https://docs.dbos.dev/python/tutorials/workflow-tutorial) | Used in `p6-t01-dbos-mrtr.md` |

## MCP spec and SDK

| Item | Value | Source | Notes |
|---|---|---|---|
| Latest spec | `2026-07-28`. GitHub release tag `2026-07-28`, not draft, not prerelease, published 2026-07-28T16:47:49Z. A separate `2026-07-28-RC` release is marked prerelease. Previous stable: `2025-11-25` | [releases API](https://api.github.com/repos/modelcontextprotocol/modelcontextprotocol/releases?per_page=3), [release post](https://blog.modelcontextprotocol.io/posts/2026-07-28/) | Unchanged since 2026-10-30. Docs site header: "Version 2026-07-28 (latest)" |
| MRTR | Post: the server returns `resultType: "input_required"` with the requests it needs answered, and the client retries the original call with the answers in `inputResponses` (SEP-2322). Spec page adds an opaque `requestState` the client must echo back. Allowed on `tools/call`, `prompts/get`, `resources/read` only | release post, [MRTR spec page](https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/mrtr) | Replaces server-initiated `elicitation/create`, `sampling/createMessage`, `roots/list`. Details in `p6-t01-dbos-mrtr.md` |
| Tasks | Moved out of the core into the extension `io.modelcontextprotocol/tasks` with poll-based `tasks/get` and a new `tasks/update` (SEP-2663) | release post, [Tasks overview](https://modelcontextprotocol.io/extensions/tasks/overview) | |
| Python SDK | PyPI `mcp` latest is 2.3.0, uploaded 2026-10-02 (UTC); `Requires-Python >=3.10`. GitHub release `v2.3.0` published 2026-10-02. The repo pins `mcp==2.3.0` in `packages/dom2src-mcp` and `packages/repro-agent`, and `uv.lock` has 2.3.0 | [PyPI JSON](https://pypi.org/pypi/mcp/json), [v2.3.0 release](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.3.0), `uv.lock` | Unchanged. The release post says all four Tier 1 SDKs, Python included, "speak 2026-07-28 as of today"; the v2.3.0 notes also refer to 2026-07-28 connections. Which MRTR server-side helper API the SDK exposes: not confirmed (T09 reads the SDK) |

## Render free web service

Source: [render.com/docs/free](https://render.com/docs/free), read 2026-11-01.

| Item | Value | Notes |
|---|---|---|
| Sleep after idle | Spins down after 15 minutes without inbound traffic (HTTP requests and WebSocket messages from existing connections) | Outbound traffic or a background poll does not keep it awake |
| Cold start | Spins back up on the next HTTP request or new WebSocket connection; "about one minute"; browsers see a loading page meanwhile | "30 to 60 seconds" is not stated on the page. This is longer than GitHub's 10 s webhook timeout |
| Instance hours | 750 free instance hours per workspace per calendar month, consumed only while running; when used up, Render suspends all Free web services until the next month | One service running 24 h for a 31-day month is 744 h (my arithmetic), so it fits only if nothing else in the workspace runs |
| Filesystem | Ephemeral: lost on redeploy, restart or spin-down | State must live in Neon, not on disk |
| Other limits | Can be restarted at any time; single instance only; no persistent disk, no SSH or one-off jobs; no private-network inbound; blocks outbound ports 25, 465, 587; may suspend a service that initiates an "uncommonly high volume" of public traffic (the page does not give a number). Bandwidth and build-minute allowances: the page states no figures | The restart-at-any-time rule is why DBOS recovery on startup matters |
| Free Postgres | Expires 30 days after creation | Not used; Neon instead |

## Neon free plan

Source: [neon.com/docs/introduction/plans](https://neon.com/docs/introduction/plans), read 2026-11-01. Scale to zero: [neon.com/docs/introduction/scale-to-zero](https://neon.com/docs/introduction/scale-to-zero).

| Item | Value | Notes |
|---|---|---|
| Compute allowance | The plan comparison table says "100 CU-hours/project". The Compute section of the same page says "Free: 100 CU-hours/project/month (enough to run a 0.25 CU compute in a project for 400 hours/month)" | **Changed.** Earlier notes (`PLAN.md`, `PROJECT.md`) said "per month is not stated". The Compute section now states it. The table row still omits it. Both are quoted here so the discrepancy is visible |
| CU-hour formula | compute size x hours running; 0.25 CU for 4 h is 1 CU-hour. One CU is about 4 GB RAM. All computes in a project count, including read replicas | Free autoscaling goes up to 2 CU |
| Scale to zero | Free: suspends after 5 minutes of inactivity and "cannot disable". Reactivation on the next query "within a few hundred milliseconds" | Cold-start latency of the first DBOS query is a T11/T14 measurement. A poll shorter than 5 min keeps the compute awake and spends CU-hours |
| Storage | 1 GB per project, 20 GB total across the account | |
| Egress | 5 GB per project per month | |
| Branches | 10 per project on Free | |
| PITR / history | 6 hour limit, capped at 1 GB of change history on Free | |

## GitHub webhook delivery timeout

Source: [Best practices for using webhooks](https://docs.github.com/en/webhooks/using-webhooks/best-practices-for-using-webhooks), read 2026-11-01.

| Item | Value | Notes |
|---|---|---|
| Timeout | "Your server should respond with a 2XX response within 10 seconds of receiving a webhook delivery." If it takes longer GitHub "terminates the connection and considers the delivery a failure" | Confirmed, 10 s. The page advises answering first and processing asynchronously |
| Redelivery | "If your server goes down, you should redeliver missed webhooks once your server is back up" (manual or via the redelivery API). `X-GitHub-Delivery` is the same on a redelivery as on the original | Not an automatic retry: the page tells you to redeliver. So the reconciliation poller is still needed |
| Dedup key | `X-GitHub-Delivery` is unique per event | Feeds T22 |

## Result

- Pins unchanged since 2026-10-30: DBOS 3.4.0 (3.x), MCP spec 2026-07-28, MCP Python SDK 2.3.0.
- Changed: Neon's Compute section now states "per month" for the 100 CU-hours; the table row does not.
- Not confirmed, carried into later tasks: minimum Postgres version for DBOS; default `executor_id`; LISTEN/NOTIFY over Neon's pooled endpoint (T11); the SDK's MRTR server API (T09); Conductor pricing (not needed while no `conductor_key` is set); Render and Neon behaviour under real traffic (T13, T14, owner steps).
