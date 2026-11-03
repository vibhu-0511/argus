# P6-T13 Render cold start

Run: 2026-11-02 20:18 to 22:01 UTC (2026-11-03 01:48 to 03:31 IST). Service: `argus-flow`, Render **Free** web service, region **Oregon (US West)**, `https://argus-flow.onrender.com`. Commit deployed: `91f6f11` (branch `stack/p6-flow`). The database is a Neon project in `us-east-1`.

Tool: `packages/flow/scripts/p6_t13_cold_start.py`, run from the owner's PC. Each try waits an idle gap with nothing else sent to the service, sends one correctly signed `ping` webhook to `/webhook`, and records the seconds until the HTTP answer; a second ping right after gives a warm baseline. A ping names no ticket, so the handler answers `202 ignored` at once (`flow.webhook`): the time is the wake-up of the web service, not of Neon or DBOS. Raw numbers: [`packages/flow/results/p6-t13/results.json`](../../packages/flow/results/p6-t13/results.json).

| Try | Idle gap (s) | Cold: HTTP | Cold: seconds | Cold: verdict | Warm: seconds |
|---|---|---|---|---|---|
| 1 | 1200 | 202 | 21.803 | slow | 1.057 |
| 2 | 1200 | 202 | 51.815 | slow | 1.05 |
| 3 | 1200 | 202 | 31.724 | slow | 1.117 |
| 4 | 1200 | 202 | 43.552 | slow | 1.112 |
| 5 | 1200 | 202 | 33.693 | slow | 1.07 |

Verdict `slow` = answered 202 in 10 s or more (GitHub gives up on a delivery after 10 s). Cold: min 21.8 s, median 33.7 s, max 51.8 s, 5 of 5 over 10 s, none failed. Warm: 1.05 to 1.12 s (this includes the round trip from the owner's PC to Oregon).

**Gaps over 10 s: the 1200 s gap (20 minutes), all 5 tries.**

## What this shows

- A free Render service that has been idle for 20 minutes answers a webhook ping after 22 to 52 s, never inside GitHub's 10 s window. A delivery that arrives to a sleeping service will be marked failed by GitHub, and GitHub does not retry it on its own (ADR-021).
- Render's own health check, which asked `/health` every 5 seconds in the service log, did **not** keep the service awake: five of five tries were slow. (I infer that it was asleep from the delay; Render's dashboard was not consulted for each try.)
- The range matches Render's banner ("can delay requests by 50 seconds or more") and its page ("about one minute"); the measured times are shorter than a minute in 5 of 5 tries and one reached 51.8 s.
- Every cold request still got its 202 from the client's point of view: the connection was held until the instance was up. Whether GitHub's own request, which closes after 10 s, still reaches the handler after the wake-up was tested later with a real delivery (P6-T23, `p6-t23-break-it.md`): it did, twice.

## What this does not show

- Only one idle gap length was used, 20 minutes. Shorter gaps (the 15 minute boundary of Render's page) and longer ones (hours) were not tried, so how the time depends on the gap is not known.
- Five tries on one service, from one place, on one evening. No spread claim beyond the table.
- The client timeout was 90 s; none came near it.
- The first request after the deploy was not a sleep test and is not in the table. A check run just before it (gap 0, written to a temp file, not to the results) answered 202 in 0.838 s on an awake service.
- The time to the first `202` does not include Neon waking or the DBOS engine being ready: the handler answers before the engine is ready (late-bound enqueuer). The enqueue behind it waits up to 120 s for the engine (`flow.service`).

Notes: no row looks warm (the fastest cold try was 21.8 s); no non-202 status; the owner's PC stayed awake for the whole run.
