# ADR-020: DBOS vs Temporal

Status: proposed (P6-T15), drafted by Claude at the owner's request, for the owner to review. It is accepted when the owner approves it. It is a decision on paper: the workflow was built with DBOS (P6-T03) and **no Temporal variant was built or run**. Every Temporal statement below comes from Temporal's own documentation as read on 2026-11-01, not from running anything.

## Context

The ticket-to-fix workflow needs durable execution: a crash in the middle of a run must resume at the last finished step, a QA approval can take days, and one ticket must never run twice. Two engines fit that job. The phase fixes the constraints: a free deployment (Render free web service plus Neon free Postgres, GitHub Actions as the execution plane), one process, no paid control plane (`docs/notes/p6-waves.md`, `phases/P06-argus-flow.md`).

- **DBOS Transact** is a library. The workflow runs inside our own FastAPI process and checkpoints each step into a Postgres we already need. That is what `flow.workflow.ticket_workflow` is (`docs/architecture/p6.md`, P6-T03; `docs/notes/p6-t03.md`).
- **Temporal** is a service. A Temporal Service holds the workflow histories and hands tasks to separate worker processes that run our workflow and activity code. It is offered as a paid cloud or as software you host.

The question is which one fits a free, in-process deployment, and what would change the answer.

## What was checked, and what was not

| | DBOS (as built) | Temporal |
|---|---|---|
| Written in this repo | Yes: `flow/workflow.py`, `dbos_runtime.py`, `qa.py`, `reconcile.py` | **No.** Not built, not installed, not run |
| Run against a real engine | Yes, on a local Postgres 16 in a throwaway container: workflow, duplicate enqueue, QA signal, review-comment path (`docs/notes/p6-t03.md`, `p6-t09.md`) | No |
| Run on the free hosts | **No.** Render and Neon are not deployed (T11, T12 open); Neon cold start, CU-hours and LISTEN/NOTIFY behaviour are T13, T14, T11 | No |
| Crash recovery measured | **No.** The kill experiment is T19 | No |
| Basis for the comparison | Docs and our own tests | Documentation only |

So the comparison below is documentation against documentation, plus one engine that works on a laptop. Nothing here says Temporal would fail on our load; it says the pages read do not show it fitting the free hosts, and that we did not try.

## Comparison

**Operating cost.**

| | DBOS | Temporal |
|---|---|---|
| Engine | The library is free and MIT licensed. Paid: Conductor and the Enterprise extension (separate licence), plans from $99 per month; no free Conductor tier is shown. We set no `conductor_key`, and a test asserts that | Cloud: pay as you go with no base fee, from $50 per million Actions, plus $0.042 per GB-hour of active and $0.00105 per GB-hour of retained storage. A Business plan is $500 per month or 10% of usage, whichever is greater. Self-hosted server: MIT licensed, so no licence cost, but you run it |
| Free credit | Not needed | $150 in credits for 90 days on the pay-as-you-go plan. The docs also mention credits from a startup programme; its terms and whether we qualify: not checked. Credits carry an expiry. When they are used up the account is invoiced; the pricing-page FAQ answer was not read |
| What a run costs | Rows in our own Postgres: one write per step and two per workflow (`p6-t01-dbos-mrtr.md`). The Neon cost of that (CU-hours with polling) is **not measured yet** (T14) | **Not computed.** How Temporal counts Actions for a workflow like ours was not read, so no monthly figure is given. The prices above are the only numbers |

**Free hosting.**

- **DBOS.** Needs only Postgres, no separate server, per its own pages. Render free runs the one process (sleeps after 15 minutes without inbound traffic, ephemeral disk, may restart at any time, `p6-t00-versions.md`), Neon free holds the state. On restart DBOS recovers pending workflows with a pinned `application_version` and `executor_id` (`flow/config.py`). Whether this holds on the real hosts is T11 to T14; today it is shown only locally.
- **Temporal Cloud.** Our code still has to run somewhere as a long-lived worker: the Python docs describe workers as persistent processes that you host and that poll a task queue. A Render free service can host that, but it sleeps when idle, and the Render page says outbound traffic does not keep it awake. **My reading, not tested:** a sleeping worker is woken by the next webhook, so it may work, but Cloud bills usage once the credit is gone (a $0 base fee, then $50 per million Actions; no ongoing free allowance is shown), so this fails the "free" constraint for a deployment that is meant to last.
- **Temporal self-hosted.** The docs describe two Go binaries (server and UI), a persistence database (Cassandra, MySQL or PostgreSQL; tested PostgreSQL versions are listed, the minimum is not stated) and a visibility store, with Elasticsearch recommended for production and SQL stores possible from server 1.20. The docs also say Temporal hosts should not be exposed to the open internet. Memory and CPU needs: **not stated on the pages read**, and Render's free memory limit was not read either, so whether the server fits on a free instance is **not confirmed**. Render's free tier is one instance with no inbound private network (`p6-t00-versions.md`), so a server and a worker would not be two free services that talk privately. Neon could hold the Temporal database in principle; its Postgres version and Temporal's schema fit were not checked.

**In-process fit.**

- DBOS is imported into the FastAPI process. The webhook handler's enqueue and the poller's enqueue are one call (`SetWorkflowID(ticket_id)`, verified on 3.4.0, including a second enqueue after the first run finished returning the first run). The queue is polled by the same process. No network hop sits between the webhook and the workflow engine except Postgres.
- Temporal splits the engine from the code: the web process would be a client, the workflow code runs in a worker. The SDK may allow the client and worker in one Python process (the worker's `run()` blocks until shutdown, so it would run beside the web server); the pages read neither confirm nor rule this out. Even then, the engine itself is a separate service.
- Both require deterministic workflow code, with network calls moved out (DBOS steps, Temporal activities). Temporal's Python SDK adds a sandbox that fails the workflow task on a banned call, and its own page says the sandbox does not remove the risk. DBOS raises `DBOSStepNondeterminismError` when a recorded step result differs. Our workflow already keeps every GitHub and Actions call in a step, so the rule costs the same either way.
- Temporal limits one workflow history to 51,200 events or 50 MB. A ticket run has five steps and one wait, far below that.

**Lock-in.**

- **DBOS.** Library and state are ours: MIT code, state in tables in our Postgres. The commercial part is not used. Code coupling is real but small: only `config.py`, `dbos_runtime.py`, `qa.py`, `qa_mcp.py`, `reconcile.py` and `workflow.py` import `dbos`. The state machine (`states.py`), the Actions runner, the GitHub reader, the webhook and the review-comment parser do not, and the runners and GitHub client are injected through `Protocol`s. Leaving means rewriting those six modules; moving in-flight workflows between engines is not possible and was not looked at.
- **Temporal.** SDK and server are MIT licensed. Cloud is a vendor service whose bill grows with Actions. Whether code written for Cloud runs unchanged against a self-hosted server: not confirmed on the pages read. Workflow code is tied to Temporal's API and its history-replay rules, as ours is to DBOS's.
- Neither is free of lock-in at the workflow-function level. The mitigation is the same for both and already in place: keep the logic in plain modules and the engine in a thin layer.

## Decision

**DBOS, as built.** On the four criteria the documentation points one way for this project: no paid or separate component (the engine is a library plus the Postgres we need anyway), the workflow runs inside the one free process, the state is in a database we control, and the part of DBOS that costs money is not used. Temporal Cloud would work but has no ongoing free tier on the pages read; self-hosted Temporal adds at least a server and a worker to a free tier that gives one instance, with a resource need that nothing read states.

The decision rests on the free-tier constraint and on what was already built, not on a measured advantage. Temporal's own strengths were not tested here: its history and replay model, its UI, its language coverage and the scale it targets. A single-process workflow handling one ticket at a time does not call on them, which is why they do not decide this.

## What would change the answer

Switch to Temporal (or add a second engine) if one of these turns out true:

1. **DBOS on the free hosts fails its checks.** Neon CU-hours with DBOS polling exceed the 100 CU-hours per project (T14), Neon suspension cannot be recovered from (T24), or the crash-recovery experiment (T19) shows duplicate side effects that find-or-create cannot cure.
2. **The deployment is no longer free or single-process.** With a paid budget, Temporal Cloud removes the database load from our Postgres and brings its UI; the price per Action would then need a real count of Actions per ticket, which has not been done.
3. **A language DBOS does not support, or several executors.** DBOS lists Python, TypeScript, Go, Rust and Java, and its README names a missing language as a reason to prefer Temporal; which languages Temporal covers was not read. Having another executor take over a dead one's workflows goes through Conductor, a paid component.
4. **Throughput or run length beyond one Postgres.** DBOS lists sharded Postgres as an Enterprise feature; Temporal's limits above are the other bound.
5. **DBOS licensing or pricing changes** so that what we use (the MIT library) is no longer enough.

Also revisit if the Render free tier changes (sleep time, instance count), since the in-process choice leans on one instance staying cheap.

## Alternatives

- **Build the Temporal variant and compare by measurement.** Not done: the phase asks for a decision only, the task is a document, and a variant would need a hosted server or paid Cloud to run at all. It is the way to settle point 1 above with numbers if the owner wants them.
- **Temporal Cloud only for the first 90 days of credits.** Not chosen: it ends in a migration or a bill, and the project's goal is a deployment that stays free.
- **A plain function with a database table for state.** This is variant A in the P6 crash-recovery experiment (T19), the baseline that shows what durability adds. Not a candidate for the shipped workflow.

## Consequences

- The workflow keeps the DBOS dependency pinned (`dbos==3.4.0`) and keeps engine calls in the six modules named above, so a switch stays a bounded rewrite.
- The ADR makes no claim about Temporal's cost for our load or about its fit on Render free; both are open because nothing was run.
- T11 to T14, T19 and T24 produce the evidence that can overturn this decision for DBOS. Their results should be read against the numbered list above.
- Facts here are dated 2026-11-01. Prices, credits and plan names on vendor pages change; the sources table gives each page.

## Sources

All read on 2026-11-01. Short phrases are quoted; the rest is summarised. "Not on page" in the text above means the page did not say it. Most pages were read through a fetch helper that returned its notes; the PyPI row and the pricing-page credit and minimums lines were checked again by downloading the page directly.

| Fact | Source | Date read |
|---|---|---|
| Cloud pay-as-you-go from $50 per million Actions, $0.042 and $0.00105 per GB-hour, "$150 credits for 90 days", "No minimums"; Business and Enterprise tiers | https://temporal.io/pricing | 2026-11-01 |
| Per-Action volume tiers (down to $25 only above 100M), Developer $0 base fee, Business $500 or 10% of usage, how promotional credits are invoiced | https://docs.temporal.io/cloud/pricing.md | 2026-11-01 |
| Self-hosted: two Go binaries (server, UI); not for the open internet; dev server is for development | https://docs.temporal.io/self-hosted-guide/deployment | 2026-11-01 |
| Persistence: Cassandra, MySQL, PostgreSQL (tested 13.18 to 16.6), SQLite dev only; Vitess and CockroachDB not tested | https://docs.temporal.io/temporal-service/persistence | 2026-11-01 |
| Visibility store required; Elasticsearch recommended; PostgreSQL 12+ on server 1.20+ | https://docs.temporal.io/self-hosted-guide/visibility | 2026-11-01 |
| Server licence MIT (sidebar and README; LICENSE text not fetched) | https://github.com/temporalio/temporal | 2026-11-01 |
| Determinism: same Workflow API calls in the same order; network and LLM calls belong in activities | https://docs.temporal.io/workflow-definition#deterministic-constraints, https://docs.temporal.io/workflows | 2026-11-01 |
| Python sandbox is "not completely isolated"; can be bypassed; failure fails the workflow task | https://docs.temporal.io/develop/python/python-sdk-sandbox | 2026-11-01 |
| Workers are persistent processes you host; connection direction and ports not on the pages read | https://docs.temporal.io/develop/python/workers/run-worker-process | 2026-11-01 |
| History limit 51,200 events or 50 MB | https://docs.temporal.io/workflow-execution/limits | 2026-11-01 |
| `temporalio` 1.35.0, uploaded 2026-10-28 (UTC), `Requires-Python >=3.10`, classifier MIT | https://pypi.org/pypi/temporalio/json | 2026-11-01 |
| DBOS Transact is MIT; Enterprise is a separate licence and "should connect to Conductor" in production | https://docs.dbos.dev/explanations/transact-enterprise | 2026-11-01 |
| DBOS Pro $99 per month, Teams $499 per month, Enterprise custom, Cloud "contact sales"; no free Conductor tier shown; libraries listed for Python, TypeScript, Go, Rust, Java | https://www.dbos.dev/pricing | 2026-11-01 |
| DBOS needs only Postgres, no extra infrastructure; Temporal described as an external server | https://github.com/dbos-inc/dbos-transact-py | 2026-11-01 |
| DBOS determinism and `DBOSStepNondeterminismError` | https://docs.dbos.dev/python/tutorials/workflow-tutorial | 2026-11-01 |
| DBOS 3.4.0, Postgres or SQLite, Conductor optional, executor id and version; Render free and Neon free limits | `docs/notes/p6-t00-versions.md` (pages listed there) | 2026-11-01 |
| What the DBOS workflow does here and the `SetWorkflowID` check | `docs/notes/p6-t03.md`, `packages/flow/src/flow/workflow.py` | 2026-11-01 |
