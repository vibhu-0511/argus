# ADR-022: Free-tier deployment topology

Status: proposed (P6-T17), drafted by Claude at the owner's request, for the owner to review. It is accepted when the owner approves it. Updated 2026-11-03: the Render service and a Neon project now exist (the service answered `/health` and `/health/db` on `https://argus-flow.onrender.com`, DBOS launched on Neon, commit `91f6f11`), and the Render cold start was measured (P6-T13, `docs/notes/p6-render.md`). **Still not measured:** Neon CU-hours and whether polling keeps the compute awake (T14, not started), any real webhook delivery, any ticket run, any agent job on Actions. **No poll cadence has been chosen.** The phase asks the ADR to state how Render sleep and Neon compute interact and the poll cadence that was chosen; the interaction below is reasoning from vendor pages plus local stand-ins plus the one cold-start measurement, and that is why `TASKS.md` leaves P6-T17 unticked until T14. The open problems are listed in their own section and are not hidden in the text.

## Context

The ticket-to-fix pipeline has to run for free (`docs/notes/p6-waves.md`): a durable DBOS workflow, a GitHub webhook endpoint, a reconciliation poller, and an execution plane for the heavy agent work. ADR-020 chose DBOS (a library, so the engine lives in our own process and needs only Postgres). ADR-021 chose webhooks as hints with a poller that reads GitHub. This ADR places those parts on three free services and says where they collide.

## Topology

| Part | Where | What runs there | Built | Deployed |
|---|---|---|---|---|
| Service | Render free web service `argus-flow` (`render.yaml`, native Python, health check `/health`), region Oregon (US West) | One process: FastAPI webhook (`POST /webhook`), `/health`, `/health/db`, DBOS engine, the poll loop (`flow.service.create_service_app`) | Yes | **Yes, 2026-11-03** (health answered; polling off; no webhook registered) |
| State | Neon free Postgres in `us-east-1`, direct (not pooled) URL, `sslmode=require` | DBOS system database: step results, queue, QA signal rows | Config, TLS guard, wake-up probe: yes. Tested on a local Postgres 16, including TLS and forced disconnects | **Yes, 2026-11-03** (DBOS applied its migrations and launched on Postgres 18.6; no suspend seen) |
| Execution plane | GitHub Actions `workflow_dispatch` (`.github/workflows/agent-job.yml`) | Repro, fix, verify in the sandbox; returns `result.json`, `patch.diff`, `trajectory.jsonl` as an artifact | Dispatch, find, wait, download code and tests exist (`flow/actions.py`, T04); it has never run on GitHub (`p6-t04.md`) | **No** |
| Source of truth | GitHub (issues, PRs, branch, runs, comments) | Read by the poller, written by the workflow, sends webhooks | Reader: yes (recorded JSON only) | Webhook not registered |

Data flow: GitHub -> webhook -> service -> Neon (the workflow); service -> GitHub Actions (dispatch); GitHub Actions -> artifact -> service; service <-> GitHub (the poller reads; the workflow's write client would write). Secrets are Render environment variables, marked `sync: false` in the Blueprint; none is in the repository. There is no DBOS conductor key and no `DBOS_*` or `DBOS__*` variable on Render (`p6-t11.md`).

Limits the choice leans on (vendor pages read 2026-11-01, `docs/notes/p6-t00-versions.md`; Neon plans page re-read 2026-11-02, see below):

- Render free: sleeps after 15 minutes without inbound traffic; outbound traffic and background work do not keep it awake; "about one minute" to start again on the next request; 750 instance hours per workspace per month; ephemeral disk; one instance; may be restarted at any time.
- Neon free: scale to zero after 5 minutes of inactivity, cannot be disabled; reactivation "within a few hundred milliseconds" per the docs; 100 CU-hours per project (wording below); 1 GB storage per project.
- GitHub: 10 seconds to answer a webhook; failed deliveries are not retried by GitHub.

## How Render sleep and Neon compute interact

Reasoned from the pages above and from what the code does; **not measured**.

| Service state | Process | Database traffic | Neon compute |
|---|---|---|---|
| Render awake, busy | webhook, workflow, poll loop (when enabled) | queries from DBOS threads and the poller | awake, spending CU-hours |
| Render awake, idle | DBOS threads still run on timers. In the T24 stand-in, warnings from DBOS's queue and background threads appeared within a second of the database stopping with no workflow running, so they query it on a timer; **the interval was not measured** (`p6-t24-break-it.md`) | probably a continuous trickle | **likely never reaches 5 minutes of idle, so it does not suspend** (to be shown by T14) |
| Render asleep | no process, no poller | none | suspends after 5 minutes idle |
| Render waking | about one minute (Render's figure, unmeasured), then `wait_for_database` for up to about 60 s (6 attempts, 1, 2, 4, 8, 15 s waits, 5 s connect timeout) before DBOS starts (`flow/db_wake.py`) | first connection wakes the compute | wakes |

Consequences that follow, each an open question rather than a result:

1. **The two idle timers do not match.** Render sleeps at 15 minutes with no inbound request; Neon suspends at 5 minutes with no query. While the service is up, DBOS's own polling (and the poller, every 300 s by default, which is only just inside Neon's 5-minute window) can keep Neon awake without any inbound request; once Render sleeps, Neon follows 5 minutes later. So Neon's CU-hours are spent while Render is awake, and a Render that is kept awake all the time keeps Neon on all the time.
2. **A compute that never suspends uses the allowance in days.** Arithmetic from the plans page example (0.25 CU for 400 hours is 100 CU-hours): a 0.25 CU compute running 24 hours a day uses 6 CU-hours a day and reaches 100 CU-hours in about 16.7 days. This assumes 0.25 CU all the time; the size the free compute actually runs at was not observed, and autoscaling goes up to 2 CU. If it is so, the allowance is gone well inside a month and the Neon part of the topology fails the "free" constraint. This is the question T14 exists to answer.
3. **Keeping Render awake costs the other allowance.** One service awake all month is 744 hours in a 31-day month, against 750 free hours per workspace (my arithmetic from the Render page); it fits only if nothing else in the workspace runs. So "ping often enough that it never sleeps" trades the sleep problem for the hour limit and for point 2.
4. **A cold webhook pays both delays in series.** A delivery that wakes a sleeping service meets Render's start (about a minute) and then the Neon wake and DBOS launch before the engine is ready. The handler itself answers 202 at once even before the engine is ready (late-bound enqueuer, `flow/service.py`), and its background enqueue waits up to 120 s for the engine; but GitHub's 10 s window closes long before, and the page says a failed delivery is not retried. In one real test (T23, 2026-11-03) the request GitHub abandoned was still served by the woken instance: two `POST /webhook` answered 202 about 31 s after the issue was created, and the workflow wrote its comment at 41 s. One observation; ADR-021 keeps the poller for the cases where the request is not served. What this does not show is a hint that never reaches the service at all.
5. **`/health` is safe for the timer, `/health/db` is not.** `/health` answers without touching the database; `/health/db` wakes a suspended compute and counts toward CU-hours, so it must not be Render's health check or a ping target (`p6-t12.md`).

## Open problems (stated, not decided)

1. **A sleeping service runs no poller, so something has to wake it on a schedule.** `poll_forever` lives inside the Render process; Render says outbound traffic and background polls do not keep a free service awake. Without a wake-up, a webhook lost during sleep is repaired only when some later request happens to arrive (T23 finding; the local test hid it by calling `poll_once` itself). When the service starts, the poll loop's first action is a poll, so any request that wakes it is followed by a poll as soon as the engine is ready (code, `flow/reconcile.py`). Candidates: **(a)** a scheduled GitHub Actions workflow that calls `/health`; **(b)** an external cron/ping service. A third, **(c)** running the poll from a scheduled Actions job instead of inside the service, was not designed (it would need the database URL in Actions and would wake Neon from there). **Undecided and unmeasured.** None is built, there is no scheduled workflow in `.github/workflows`, and the properties of GitHub's scheduled workflows (minimum interval, delays, behaviour on inactive repositories) and of any external service's free tier were **not checked** for this ADR. Whichever is chosen sets the real recovery latency, which is the ping interval plus a cold start, not the 300 s poll interval.
2. **Cold start against GitHub's 10-second webhook timeout: measured.** After 20 idle minutes, five signed pings to the deployed service were answered in 21.8, 31.7, 33.7, 43.6 and 51.8 s (`docs/notes/p6-render.md`, `packages/flow/results/p6-t13/results.json`): all five over 10 s. The first webhook after a sleep misses GitHub's window; Render's own 5-second health check did not keep the instance awake. Only the 20-minute gap was tried, and no real GitHub delivery was sent, so whether the delivery GitHub abandoned is still handled after the wake-up is not known (T23). The Render service is in Oregon and the Neon database in `us-east-1`, so each database round trip crosses the US; the effect was not measured.
3. **Neon scale to zero after 5 minutes, and the CU-hour allowance.** Whether DBOS and the poller keep the compute awake, and how many CU-hours 48 hours of polling cost, is T14 and is not measured. The allowance wording also conflicts, see next section.
4. **The write client and the agent job exist but have never run for real.** `flow.github_write.HttpGitHubClient` (find before act, draft PR, mock-transport tests only) replaces the stub that raised, and `flow.agent_job` with its `agent-job.yml` (platform checkout and Docker rig) exist, but nothing has been dispatched on GitHub: the repository secrets `ARGUS_PLATFORM_TOKEN` and `ARGUS_MODEL_API_KEY` are not set and the Linux rig path is untested (`p6-t04.md`). So the deployed service has not done any real work. The Blueprint keeps `ARGUS_FLOW_POLL_ENABLED=false`, and the runbook says to hold webhook registration until a dispatched run can succeed, since with polling on and no ticket label the poller would enqueue a workflow for every open issue. The MCP QA tool (`flow.qa_mcp`) is not mounted either; QA runs through the review-comment path only.

## The Neon CU-hour wording conflict (T14)

Recorded, not resolved.

- **The phase file** (`phases/P06-argus-flow.md`, task P6-T14) says the measured CU-hours are to be compared with "100 CU-hours/project" and adds that "'per month' is not stated".
- **The Neon plans page**, https://neon.com/docs/introduction/plans, fetched on **2026-11-02** (HTTP 200) by a fetch helper that returned the page text; the page shows no "last updated" date. As returned: the plan overview table's compute row says "100 CU-hours/project" with no period; the Compute section says "100 CU-hours/project/month (enough to run a 0.25 CU compute in a project for 400 hours/month)"; two FAQ answers say "100 CU-hours/month included" and "100 CU-hours of compute per project per month". Free scale to zero: "5 min inactivity; cannot disable". Free autoscaling: "Up to 2 CU (8 GB RAM)".
- **The earlier check** (`p6-t00-versions.md`, 2026-11-01) had already found the same split: the table row omits "per month", the Compute section states it.

So the page now says "per month" (or "/month") in three places and omits it in two (the table row and the "who it's for" line); the phase file's statement that it is not stated was true of an earlier reading and is no longer true of the Compute section. This ADR decides nothing about it. What it cannot check: which wording Neon bills against, and whether the allowance resets monthly in practice, because that needs an account and its billing view. T14 should record the number it measures and compare it with both readings (100 in total over the measured period, and 100 per month), and the owner should correct the T14 wording in the phase file. The arithmetic in the previous section uses the per-month reading because the example on the page does.

## Decision

Place the parts as in the topology table: **one Render free web service holding the webhook, the DBOS engine and the poll loop; Neon free Postgres on its direct endpoint for DBOS state; GitHub Actions as the execution plane.** The reasons are those in ADR-020 and ADR-021: no paid component, one process, state in a database we control, GitHub as the source of truth.

**What this ADR does not decide, and what remains to settle it:**

- The poll cadence. The code default is 300 s (minimum 60 s), picked and not measured, and the Blueprint has polling off. A cadence is chosen after T14 (does polling keep Neon awake, what does 48 hours cost) and after the wake-up mechanism is chosen, because the wake-up interval, not the poll interval, bounds recovery.
- The wake-up mechanism (candidates a to c above), after a measured cold start (T13).
- Whether the free Neon allowance suffices. If T14 shows that the service keeps the compute awake and exhausts the allowance, the decision must change: for example stop polling while no ticket is open, turn off the DBOS timers that cannot be turned off (not examined), or leave the free tier. The ADR lists these as options, none tried.

## Alternatives

- **Render paid instance (always on).** Would remove sleep, the cold start and the need for a wake-up, and fits the in-process poller. Not priced here and not free; outside the phase's constraint. Not examined further.
- **Render free Postgres instead of Neon.** Rejected: Render's page says it expires 30 days after creation (`p6-t00-versions.md`).
- **Neon pooled endpoint.** Not used: DBOS takes session-level advisory locks and session-level `SET` on its connections; pooled transaction mode may well work, but it was not tried (`p6-t11.md` section 3).
- **Poll from GitHub Actions on a schedule, no in-process poller** (open problem 1, option c). Not designed; the likeliest way to make the schedule independent of Render's sleep, at the price of database credentials in Actions and an Actions-side wake of Neon.
- **A different host or engine.** DBOS versus Temporal is ADR-020. Other free hosts were not compared.

## Consequences

- The topology is a design and a set of tested pieces, not a running system. Every claim about Render or Neon behaviour above is a vendor statement or reasoning, and each is dated 2026-11-01 or 2026-11-02.
- Owner steps (accounts, services, tokens, webhook registration, the cold-start and 48-hour measurements) are in `docs/notes/p6-t12.md`, `p6-t11.md`, `p6-t23-break-it.md`, `p6-t24-break-it.md`. Registering the webhook should wait for the GitHub write client and for the PR-event ticket id fix described in ADR-021.
- When T13 and T14 produce numbers, this ADR should be revised with them: the cold-start table, the CU-hours measured, whether Neon suspended while the service was up, and the cadence then chosen. `TASKS.md` stays unticked for P6-T17 until then.
- Free-tier terms change; the page dates are given so a later reader can tell how old each figure is.

## Sources

| Fact | Source | Date read |
|---|---|---|
| Neon free: compute allowance in the table row, the Compute section and two FAQ answers; scale to zero "5 min inactivity; cannot disable"; autoscaling up to 2 CU; no "last updated" date shown | https://neon.com/docs/introduction/plans, fetched by a fetch helper that returned verbatim phrases | 2026-11-02 |
| Neon free: 100 CU-hours/project and the same split between table and Compute section; reactivation "within a few hundred milliseconds"; storage 1 GB per project | https://neon.com/docs/introduction/plans, https://neon.com/docs/introduction/scale-to-zero (`docs/notes/p6-t00-versions.md`) | 2026-11-01 |
| Render free: 15 minutes idle, outbound and background work do not keep awake, "about one minute", 750 hours, ephemeral disk, one instance, free Postgres expires after 30 days | https://render.com/docs/free (same notes) | 2026-11-01 |
| GitHub: 10 s to answer, no automatic retry, redeliver by hand or API | https://docs.github.com/en/webhooks/using-webhooks/best-practices-for-using-webhooks (same notes) | 2026-11-01 |
| Service, Blueprint, `/health` versus `/health/db`, `UnwiredGitHub`, poll off, QA tool not mounted | `packages/flow/src/flow/service.py`, `render.yaml`, `docs/notes/p6-t12.md` | repository |
| Wake-up probe (6 attempts, about 60 s), TLS guard, direct endpoint, pooled endpoint not tried | `packages/flow/src/flow/db_wake.py`, `docs/notes/p6-t11.md` | repository |
| DBOS threads query the database on a timer (observed in a stand-in, interval not measured) | `docs/notes/p6-t24-break-it.md` | repository |
| A sleeping service runs no poller; the local test cannot show it | `docs/notes/p6-t23-break-it.md` | repository |
| `flow.agent_job` does not exist; a dispatched run fails at that step | `docs/notes/p6-t04.md`, `.github/workflows/agent-job.yml` | repository |
| Poll defaults (300 s, 30 per page, 3 pages) and request counts | `packages/flow/src/flow/reconcile.py`, `docs/notes/p6-t07.md` | repository |
| T14 wording ("per month" is not stated) | `phases/P06-argus-flow.md`, task P6-T14 | repository |
