# flow

Control plane of Argus (phase P6): a durable ticket-to-fix workflow on DBOS and Postgres, a GitHub webhook endpoint that treats events as hints, a reconciliation poller that rebuilds state from GitHub, GitHub Actions as the execution plane, and a human QA signal wait. It is meant to run free on Render (web service) and Neon (Postgres).

Architecture, one section per task: [docs/architecture/p6.md](../../docs/architecture/p6.md). Phase file, ablation and phase report: [phases/P06-argus-flow.md](../../phases/P06-argus-flow.md). Notes per task: `docs/notes/p6-*.md`. Rules of the build: [docs/notes/p6-waves.md](../../docs/notes/p6-waves.md).

## Status (read this first)

**Deployed in part (2026-11-03).** The service runs on Render free at `https://argus-flow.onrender.com` against a Neon project, and `/health` and `/health/db` answered on the public URL. No webhook is registered, no ticket has run, and nothing below the service has been seen on real GitHub or Actions. Everything else below was built and tested with a throwaway Postgres and fakes (on a local machine, and the flow tests also on GitHub Actions, see T20). No model was called.

What is not finished, and why (state of `TASKS.md` when this README was written):

| Task | Unticked because |
|---|---|
| T04 GitHub Actions dispatch | The runner (`flow.actions`), `.github/workflows/agent-job.yml` and the entry point `python -m flow.agent_job` (`src/flow/agent_job.py`) exist and are tested against a fake Actions API with fake steps. The default steps (the real repro, fix and verify) have never run. The workflow now checks out the platform repository (secret `ARGUS_PLATFORM_TOKEN`) and builds the images and the repro rig it needs on the runner, but none of that has run on Linux, and `agent-job.yml` has never run on GitHub. The acceptance run (a real dispatch returning patch and trajectory) was not seen. [p6-t04.md](../../docs/notes/p6-t04.md) |
| T12 Render deploy | **Done, ticked 2026-11-03.** The service runs on Render free (commit `91f6f11`) and `/health` and `/health/db` answered on the public URL. No webhook or ticket run yet. [p6-t12.md](../../docs/notes/p6-t12.md) |
| T13 Render cold start | The T12 deploy now exists; not measured yet. Note: `docs/notes/p6-t13.md` (another session's task) |
| T14 Neon CU-hours over 48 hours | Needs the deploy and a 48-hour wait; not measured. Note: `docs/notes/p6-t14.md` |
| T23 Render sleeps, webhook lost | Only a local stand-in ran. It found a design gap: a sleeping Render service runs no poller, so the in-process poller alone does not recover a lost webhook. Open. [p6-t23-break-it.md](../../docs/notes/p6-t23-break-it.md) |
| T16, T17 ADR-021, ADR-022 | Written by another session in `docs/adr/` (`0021-*`, `0022-*`); they need the T13 and T14 measurements as evidence. |
| T25 this README and the phase report | The P5 row is filled; the P6 row and the delta are dashes because P6 ran no model. See the end of this file and [p6-t25.md](../../docs/notes/p6-t25.md). |

Other limits that matter:

- **The workflow's GitHub write client (`github_write.HttpGitHubClient`) is built and wired into the service, but has never talked to the real GitHub.** It covers the seven `GitHubClient` methods (push by git data API, find-or-create draft PR, ready, close, comment with a hidden marker, label) and is tested only against a fake GitHub over `httpx.MockTransport`, including one whole `ticket_workflow` run on a local Postgres. Not seen: the real API's answers, the 422 race, the token's permissions. It needs its own token `GITHUB_WRITE_TOKEN`. The dispatched job's default steps have never run and the workflow cannot yet check out the platform repository or start the Docker rig, so a real ticket would still fail at the repro dispatch. `render.yaml` therefore keeps `ARGUS_FLOW_POLL_ENABLED=false`, and the webhook should not be registered on a real repository yet.
- T20 (the flow CI job) is done: `.github/workflows/flow.yml` ran green on GitHub on 2026-11-02, on the push and on the pull request: 364 passed, 5 skipped against a `postgres:16` service container, no model call, no repository secret. [p6-t20.md](../../docs/notes/p6-t20.md).
- T11 (Neon config, TLS, reconnect) and T24 (suspend break-it) were checked **on a local Postgres only**, with `pg_terminate_backend` and a stopped container standing in for a Neon suspend. A real Neon suspend, its wake-up time and its certificate chain were not seen. [p6-t11.md](../../docs/notes/p6-t11.md) section 6, [p6-t24-break-it.md](../../docs/notes/p6-t24-break-it.md).
- The MCP QA tool (`flow.qa_mcp`) is not mounted in the service; QA approval in the service works through the review-comment path.
- The crash-recovery experiment (T19) ran on fakes with a hard process kill, not on Render. Details: [p6-t19.md](../../docs/notes/p6-t19.md).

## Module map

All under `src/flow/`.

| Module | What it does | Task |
|---|---|---|
| `states` | Pure state machine for one ticket: states, legal transitions, idempotency keys. No DBOS, no network. | T02 |
| `webhook` | FastAPI endpoint: verifies the HMAC-SHA256 signature (401 if bad), treats the event as a hint, answers 202 without waiting or reading GitHub. | T05, T06 |
| `enqueue` | The seam between the webhook and the workflow: the `Enqueuer` interface; a hint becomes one workflow keyed by the ticket id. | T06 |
| `workflow` | The ticket-to-fix workflow as a DBOS workflow with durable, idempotent steps (repro, fix, verify, open PR, QA wait, finish). | T03, T08 |
| `dbos_runtime` | Launches DBOS and provides the real `DbosEnqueuer`. | T03 |
| `config` | DBOS settings fixed before the first migration (`use_listen_notify` off, application version `argus-flow-1`, executor id `argus-flow-0`, no conductor key); reads the database URL and refuses a remote URL without TLS. | T03, T11 |
| `db_wake` | `wait_for_database`: bounded retry with backoff to wake a suspended Neon database; never logs the URL. | T11 |
| `actions` | `ActionsRunner`: runs a step by dispatching `agent-job.yml`, finding the run by its key, waiting, downloading the `argus-result` artifact. | T04 |
| `reconcile` | The poller: rebuilds a ticket's state from GitHub alone and starts or finds its workflow. `poll_once`, `poll_forever`. | T07 |
| `github_read` | Read-only GitHub REST reader for the poller (GET only). | T07 |
| `github_write` | The workflow's GitHub write client over REST: keyed branch push, find-or-create draft PR, ready, close, marker comment, label. Every call finds before it acts. | P6 write client |
| `diff_apply` | Applies a unified diff to file texts in memory, so `github_write` can push a patch through the git data API. Text files only. | P6 write client |
| `qa` | The QA signal: one message to the ticket's workflow, deduplicated by an idempotency key. | T08 |
| `review_comment` | QA approval by a review comment (`/argus approve`, `/argus reject`) from an allowed reviewer; no MCP needed. | T10 |
| `qa_mcp` | QA approval as an MCP tool that asks through MRTR elicitation (`input_required` / `inputResponses`). Not mounted in the service. | T09 |
| `service` | The ASGI app Render runs: webhook, `/health`, `/health/db`, DBOS start in the background, the poll loop. | T12 |
| `ledger_fakes` | Fake runners and GitHub client whose world is an append-only file, so effects survive a killed process. Test and experiment support. | T19 |

Also: `fakes` (in-memory fakes for the workflow tests), `scripts/p6_t19_crash_recovery.py` (the crash-recovery harness), `results/p6-t19/` (its raw JSON).

## Run the tests

From the repository root:

```bash
uv run --all-packages python -m pytest packages/flow/tests -q
```

Run this package on its own, not in one pytest run with other packages (test file names collide).

Without a database, the tests that need Postgres are skipped with a reason. To run them, point `ARGUS_FLOW_DATABASE_URL` at a **throwaway** Postgres. The password is generated, never written in a file:

```bash
PW=$(python -c "import secrets;print(secrets.token_urlsafe(18))"); docker run -d --name argus-flow-test-pg -e POSTGRES_PASSWORD="$PW" -e POSTGRES_DB=argus_flow_test -p 127.0.0.1:55440:5432 postgres:16-alpine && export ARGUS_FLOW_DATABASE_URL="postgresql://postgres:$PW@127.0.0.1:55440/argus_flow_test"
```

Wait until `docker exec argus-flow-test-pg pg_isready -U postgres` says it accepts connections, run the pytest line above in the same shell, then remove the container with `docker rm -f -v argus-flow-test-pg`. (Git Bash on Windows: `export MSYS_NO_PATHCONV=1` first.)

The stop/start and TLS tests need more: `ARGUS_FLOW_TEST_CONTAINER` (a container whose name starts with `argus-p6-pg-`) and, for TLS, a server with `ssl=on` and `?sslmode=require` in the URL. Without them they skip. Commands: [p6-t11.md](../../docs/notes/p6-t11.md) "Run it". The crash-recovery experiment and its fast subset: [p6-t19.md](../../docs/notes/p6-t19.md) "Run it".

Recorded counts (from the task notes, not re-run for this README): 298 passed and 37 skipped without a database (T12, 2026-11-01); 315 passed and 5 skipped with a local Postgres (T20, 2026-11-01); 364 passed and 5 skipped on GitHub Actions with a `postgres:16` service container (T20, 2026-11-02).

## Environment variables the service needs

Names only. Never put a value in a file, a log or a commit. `render.yaml` marks each secret `sync: false`, so Render asks for it when the Blueprint is applied.

| Variable | Needed | What it is |
|---|---|---|
| `ARGUS_FLOW_DATABASE_URL` | yes | Neon **direct** (not pooled) URL with `sslmode=require` (or `verify-ca`, `verify-full`). A remote URL without TLS is refused. |
| `GITHUB_WEBHOOK_SECRET` | yes | The secret shared with the GitHub webhook; the HMAC key. |
| `GITHUB_DISPATCH_TOKEN` | yes | Fine-grained token, Actions read and write on the one repository. |
| `GITHUB_WRITE_TOKEN` | yes | Fine-grained token, Contents, Pull requests and Issues read and write on the one repository. Used by the workflow's write client. |
| `ARGUS_FLOW_REPO` | yes | `owner/name` of the repository whose issues are tickets. |
| `GITHUB_TOKEN` | when polling is on | Fine-grained token, read-only (issues, pull requests, contents, actions) on that repository. |
| `ARGUS_FLOW_QA_REVIEWERS` | for QA | Comma-separated GitHub logins allowed to approve; empty allows nobody. |
| `ARGUS_FLOW_QA_TIMEOUT_SECONDS` | recommended | How long a reviewer may take. If empty, the code uses 60 s, which is a test value. |
| `ARGUS_FLOW_POLL_ENABLED` | optional | `false`, `0`, `no` or `off` turns the poll loop off. Unset means on. `render.yaml` sets `false`. |
| `ARGUS_FLOW_TICKET_LABEL` | optional | Only issues with this label are polled. Set it before turning polling on. |
| `ARGUS_FLOW_POLL_INTERVAL_S`, `ARGUS_FLOW_POLL_PAGE_SIZE`, `ARGUS_FLOW_POLL_MAX_PAGES` | optional | Poller cadence and paging (defaults in `flow/reconcile.py`). |
| `PORT` | set by Render | The port uvicorn binds (Render's default 10000). |

Do **not** set `DBOS_CONDUCTOR_KEY`, `DBOS__CONDUCTOR_KEY`, `DBOS__CLOUD`, `DBOS__VMID` or `DBOS__APPVERSION` on Render. The model key for the dispatched job is a GitHub Actions secret (`ARGUS_MODEL_API_KEY`), not a service variable.

## Deploy: Neon, then Render

Copied from [p6-t11.md](../../docs/notes/p6-t11.md) section 4, [p6-t12.md](../../docs/notes/p6-t12.md) "Owner steps" and [p6-t04.md](../../docs/notes/p6-t04.md) "Owner steps". Those notes were written without access to either console; the console wording is from memory, and none of these steps has been run. Free-plan limits (750 instance hours, sleep after 15 minutes idle, cold start "about one minute", Neon 100 CU-hours and 5-minute suspend): [p6-t00-versions.md](../../docs/notes/p6-t00-versions.md).

### 1. Neon

1. Create a Neon project on the Free plan, in a region near the Render region. Keep the default database and role. Do not enable anything that disables scale to zero.
2. On the project dashboard open **Connect** and turn **Connection pooling off** so the host has no `-pooler`. Copy the connection string (`postgresql://<role>:<password>@ep-....neon.tech/<db>?sslmode=require`). This is `ARGUS_FLOW_DATABASE_URL`. Use the direct endpoint: DBOS takes session-level advisory locks and was not tried behind PgBouncer.

### 2. GitHub tokens

1. Dispatch token: GitHub, Settings, Developer settings, Fine-grained tokens. Resource owner is the repository owner; **only select repositories**, the one repository; permission **Actions: Read and write**; nothing else; expiry 30 days, then rotate. This is `GITHUB_DISPATCH_TOKEN`.
2. Write token: same page, same repository only; permissions **Contents, Pull requests and Issues: Read and write**; expiry 30 days. This is `GITHUB_WRITE_TOKEN` (the workflow pushes the branch, opens and updates the PR, comments and labels with it).
3. Poller token (only when polling is on): read-only on issues, pull requests, contents and actions of that repository. This is `GITHUB_TOKEN`.
4. Model key for the job: repository Settings, Secrets and variables, Actions, secret `ARGUS_MODEL_API_KEY` (or `gh secret set ARGUS_MODEL_API_KEY`, which prompts).
5. `agent-job.yml` must be on the repository's default branch for GitHub to list a `workflow_dispatch` workflow. This needs a push and merge. The job's entry point `flow.agent_job` exists, but its default steps are unrun. The workflow now checks out the platform repository and starts the rig (needs the secrets `ARGUS_PLATFORM_TOKEN` and `ARGUS_MODEL_API_KEY`; owner steps in [p6-t04.md](../../docs/notes/p6-t04.md)), so a dispatched `seed-*` task is expected to get further, but this has not been seen; a live issue id still ends in a failure `result.json`.

### 3. Render

1. Sign up at render.com. The free web service needs no paid plan (a card may be asked for).
2. Dashboard, New, **Blueprint**; connect the GitHub repository; choose the branch that contains `render.yaml` and `packages/flow`. The Blueprint has no `repo` or `branch` key.
3. Render lists the service `argus-flow` and asks for each `sync: false` variable. Fill in the table above. `autoDeployTrigger` is `"off"`: redeploy with Manual Deploy. Build: `uv sync --frozen --package flow --no-dev`. Start: `uv run --frozen --no-sync --package flow uvicorn --factory flow.service:create_service_app --host 0.0.0.0 --port $PORT`.
4. Wait for the deploy and open Logs. Expect in order: `Initializing DBOS system database with URL: postgresql://...:***@...`, `Application version: argus-flow-1`, `Executor ID: argus-flow-0`, `DBOS launched!`, `workflow engine started; poll loop off`. `database not ready, attempt N of 6` means the Neon wake-up probe is working. `workflow engine did not start (...)` means `/health` is 503.
5. Check the public URL (shown at the top of the service page):

   ```bash
   curl -s -m 70 -w ' HTTP %{http_code} in %{time_total}s\n' https://<your-service>.onrender.com/health
   ```

   Expected once the engine is up: `{"status":"ok","engine":"ready"} HTTP 200`. Only then may T12 be ticked. `/health/db` runs `select 1` and wakes Neon, so do not use it as the Render health check.
6. Webhook, **after** a dispatched run can succeed (see Status): repository Settings, Webhooks, Add webhook. Payload URL `https://<your-service>.onrender.com/webhook`; content type `application/json` (the HMAC is over the raw JSON body); secret the same string as `GITHUB_WEBHOOK_SECRET`; events Issues, Pull requests, Pull request reviews, Pull request review comments. A first `ping` is answered 202 `ignored`; a wrong secret gets 401.
7. Poll loop, later: set `ARGUS_FLOW_POLL_ENABLED` to `true` and `ARGUS_FLOW_TICKET_LABEL` to a label. It runs only while the instance is awake, and a poll more often than every 5 minutes keeps the Neon compute awake (T14 is meant to measure that).

### Check the dispatch by hand (once `agent-job.yml` is on the default branch)

```bash
gh workflow run agent-job.yml -f ticket_id='OWNER/REPO#1' -f step=repro -f run_key='argus:OWNER/REPO#1:dispatch-repro:1' -f upstream=''
gh run list --workflow agent-job.yml --limit 3
```

The run's TITLE must equal the `run_key`. Until the workflow checks out the platform repository and starts the Docker rig, expect the run to fail at that step and upload a failure `result.json`.

## Phase report

The ablation and the phase report against the previous phase are in [phases/P06-argus-flow.md](../../phases/P06-argus-flow.md). The previous-phase (P5) row holds P5's final numbers: resolve rate 71.4% (20/28), 34,940 tokens/bug, $0.0694, p50 1617.0 s, p95 5097.5 s, from `packages/eval/results/ablation-B.json`. The P6 row and the delta are dashes: P6 ran no model (its crash-recovery experiment used fakes), so there is nothing honest to put next to P5's numbers on a real model. What would fill the row and why T25 is still open: [p6-t25.md](../../docs/notes/p6-t25.md).
