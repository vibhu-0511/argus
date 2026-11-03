# P6-T24 break it: suspend Neon mid-run

**This simulates the suspend locally. The real Neon suspend and resume was NOT run** (no Neon account in this session; owner step at the end).

Test: `packages/flow/tests/test_suspend_break_it.py`, with the stand-ins in `packages/flow/tests/suspend_support.py`. It runs the real DBOS ticket workflow (`flow.workflow.ticket_workflow`, launched with `flow.dbos_runtime.launch`) against a throwaway local Postgres 16 with TLS (container `argus-p6-pg-w3d`, port 55436), with fake runners and a fake GitHub (`flow.fakes`). The fakes count every call, so "no duplicated side effect" is an assertion on those counts. No network, no model. Config and the retry design: [p6-t11.md](p6-t11.md).

Two stand-ins for "Neon suspended the compute": `pg_terminate_backend` on every other session of the database, and `docker stop` followed by `docker start` of the container. Both are the closest local thing, not the same thing (see "Not shown").

**Induced failure.** The database goes away while a workflow is in the middle of its `fix_step`: after the fix runner has made its effect and before DBOS can store the step's result. This is the worst moment, a side effect with no stored result.

**Expected signal.** The first database call after the loss fails; the service reconnects; the workflow reaches `done`; every runner and every GitHub effect happened once; each step's result is stored once.

**Observed.**

| Case | What was done | Result | Counts asserted |
|---|---|---|---|
| 1. Every session killed inside `fix_step` | `pg_terminate_backend` on all other sessions (4, 5 and 6 sessions in three runs) | `done`; DBOS logged `Database connection failed: ... terminating connection due to administrator command` from its own threads, then carried on | repro, fix, verify runner: 1 call each; 1 branch push key; 1 PR (`create_draft_pr` called once); 2 comments; label `done`; the five steps stored once each, in order; one workflow row |
| 2. Server stopped inside `fix_step`, started again 3 s later | `docker stop` after the fix effect, `docker start` from a timer thread | `done`. DBOS blocked in its retry on the step-result write: 3, 4 and 11 `Database connection failed ... Retrying in X s (attempt N)` warnings in three runs (waits seen: 0.89 s, 1.11 s, 5.73 s). Server down about 5 s by the test's clock in the last run (`docker stop` returned to `docker start` returned). Run time in the three runs: **15.8 s, 18.9 s and 109.8 s** | the same counts as case 1: the fix runner was called once, not again after the reconnect |
| 3. Webhook arrives while the server is stopped | signed `issues` webhook through the real app with the real `DbosEnqueuer`; `ATTEMPTS` patched to 2 for this step | first delivery: 202 `accepted`, its background enqueue gave up with `DatabaseUnavailable` after the bounded wait, nothing ran. After the server was back, redelivery of the **same** delivery id: 202 `accepted` (not `duplicate`, the failed enqueue had forgotten the id), the workflow ran to `done` | same counts as case 1; one workflow row. Test took 24 s |

- The reconnect after a killed connection needs no code of ours: DBOS's engine has `pool_pre_ping`, and every system-database call runs under `db_retry` (1 s doubling to 60 s, jittered, no deadline). `flow.db_wake` adds only the bounded wait at launch and before an enqueue.
- The step is not run again after the reconnect, because the database error happens when DBOS stores the result, not inside the step body; `db_retry` repeats that one write. What protects against a *crash* in the same window is the keyed effects (T03, T21), not this test.
- In case 2 one run took 109.8 s for a server that was down for seconds. The retry waits double up to 60 s and each failed connect can wait its connect timeout (10 s in DBOS); I did not break the 109.8 s down, and the other two runs were close to the outage length. So a resume can be late by up to a minute after the database is back. With Neon's few hundred milliseconds to wake the delay would be the first retry, not a long outage, but that is not measured here.
- While the server was down, DBOS's other threads (queue dispatch for `argus-flow` and `_dbos_internal_queue`, the queue reload, the background-jobs lock) logged warnings with stack traces and recovered on their own. Those warnings name host and port (`127.0.0.1`, `55436`), not the password: 0 matches of the generated password in the whole pytest output of the last run. On Render the Neon host name will appear in those lines.
- **Finding for T14, not concluded here:** those same warnings, seen within a second of the stop, show that DBOS threads query the system database on a timer even when no workflow is running. If that is a fixed 1 s poll, a Neon compute will never see 5 minutes of idle while the service is up, so it would never suspend (and burn CU-hours: 0.25 CU for 400 h is the 100 CU-hours allowance). T14 measures it with the real dashboard; the interval was not measured here.

**Not shown.**

- A real Neon suspend. Local stand-ins differ from a suspended compute: `pg_terminate_backend` ends sessions but the server still answers; a stopped Docker container refuses or times out connections (here: connect timeouts) and then restarts, while Neon accepts the connection and answers after a short wake-up, per its docs "within a few hundred milliseconds" (not measured). How the first query actually fails on Neon (a dropped TLS session, a refused connect, a slow answer) is not known from here.
- A crash of the process during the outage (T19, T21), a Render restart, or the outage lasting longer than the retry window. DBOS's retry has no deadline: a database that never returns blocks workflow threads for ever. The webhook and poller path is bounded by the probe in `DbosEnqueuer.enqueue`; the workflow itself is not.
- The QA wait across a suspend (the workflow in `awaiting-qa` while the compute suspends). Not run; it is also the case where polling may prevent the suspend (finding above).
- GitHub and the runners are fakes.

**Fix** (already in T11, nothing new in T24): DBOS's own `pool_pre_ping` and `db_retry` for the step path; a bounded, logged retry with backoff and a short connect timeout (`flow.db_wake`) at launch and before every enqueue; the webhook forgets a delivery id when the enqueue fails so the redelivery is accepted; the poller repairs a hint that was never redelivered.

**Owner step: the real Neon suspend** (needs T12's deploy or a local run of the service pointed at the Neon direct URL; Neon console wording is from memory, not seen):

1. With the service running against Neon (steps in [p6-t11.md](p6-t11.md) section 4), start a ticket whose workflow reaches `awaiting-qa`, or any workflow that is mid-run.
2. In the Neon console, suspend the compute if the console offers it (Branch or Compute settings; not checked). If it does not, stop the Render service, wait more than 5 minutes, and check in Neon **Monitoring** that the compute shows idle or suspended, then start the service.
3. Send the QA approve (`/argus approve` review comment) or a webhook, and note: the time of the first answer, the Render log lines `database not ready, attempt N of 6` or `Database connection failed ... Retrying`, and whether the ticket reaches `done` with one PR and two comments.
4. Report: whether Neon suspended at all while the service was up and idle (T14), the wake-up time the first query saw, and the errors in the log. Paste only log lines without secrets; the password is masked in DBOS's own start-up line.
5. Leave P6-T24's real-Neon part open until this is done; the tick in `TASKS.md` rests on the local simulation.

Run (needs the container and the two environment variables; commands in [p6-t11.md](p6-t11.md)): `uv run --all-packages python -m pytest packages/flow/tests/test_suspend_break_it.py -q -s`. Without the variables the three tests are skipped with a reason. The file takes about a minute on this machine; Docker start and stop times vary a lot (the ablation also runs Docker jobs here).
