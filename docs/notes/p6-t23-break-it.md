# P6-T23 break it: let Render sleep and drop a webhook

**Update 2026-11-03: the real run happened; see the section "Real run" at the end.** The text below is the local stand-in that came first.

**This is a local stand-in. The real Render sleep was NOT run** (no Render service exists yet: T12 and T13 are owner-only). Nothing here measured a cold start, a GitHub delivery timeout or a real Render poll. Owner steps for the real version are at the end.

Test: `packages/flow/tests/test_render_sleep_break_it.py`; the story and the script are in `packages/flow/tests/render_sleep_demo.py`. It drives the real FastAPI app (`flow.webhook.create_app`) with a signed `issues` webhook for a new ticket, the real `Reconciler.poll_once` over the recorded GitHub JSON (`fixtures/reconcile/new_ticket.json` through an `httpx.MockTransport`, plus the open-issue listing), and the enqueuer. Two runs of the same story:

- With `FakeEnqueuer`, which keeps one "workflow" per ticket id (the rule `SetWorkflowID(ticket_id)` gives). Needs nothing.
- With the real `DbosEnqueuer` and the real DBOS ticket workflow on a local Postgres (needs `ARGUS_FLOW_DATABASE_URL`, skipped with a reason otherwise). Runners and GitHub client are the fakes from `flow.fakes`, so "one PR" is an assertion on their call counts.

No network, no model, no secret (the webhook secret is a test value).

**Induced failure.** The service is "asleep": an `Asleep` enqueuer wraps the real one and refuses every hand-over (`ConnectionError`). A signed webhook for a new ticket (`acme/shop#12`, delivery id `render-sleep-delivery-1`) arrives. The enqueue fails in the background task, so the delivery is lost: no workflow starts and nothing reacts.

**Expected signal.** No immediate reaction. Then `poll_once` finds the new ticket from GitHub alone and starts exactly one workflow. A late redelivery of the same webhook afterwards still ends in one workflow.

**Observed** (`uv run --all-packages python packages/flow/tests/render_sleep_demo.py`, fake enqueuer):

| Step | What happened | Workflows for the ticket |
|---|---|---|
| 1. Webhook while asleep | HTTP 202 (the handler answers, the enqueue runs after it); enqueue refused once; the app logged `enqueue failed for acme/shop#12` with the `ConnectionError` | 0 |
| 2. `poll_once` | derived state `received`, action `started`, `errors` empty | 1 |
| 3. Late redelivery, same delivery id, service awake | 202 with status `accepted` (not `duplicate`) | 1 |
| 4. `poll_once` again | action `exists`; the engine was asked for the ticket twice in total (poller, redelivery), both with the same id | 1 |

The same assertions hold on the real DBOS workflow (`2 passed` for the test file with the database set). There, after a review-comment approve, the one workflow reached `done`, `create_draft_pr` was called once, one PR existed and each runner ran once.

- The delivery id of the lost webhook is **not** left in the dedup record: the failed enqueue forgets it (T06). That is why the late redelivery is `accepted` and not dropped as `duplicate`; had it been remembered, the redelivery would have been lost too, and only the poller would have started the workflow. Either way one workflow exists, because the workflow key is the ticket id.
- The poller reads only GitHub (five GETs per ticket). Its first answer for a ticket nobody has seen is `received`, and the workflow then replays its keyed steps.
- A redelivery is not automatic: GitHub's own page says to redeliver missed webhooks yourself (`p6-t00-versions.md`, GitHub webhook section). Without a redelivery the poller is the only way back, which is the point of the break.

**Not shown, and why this is only a stand-in.**

- A real sleeping service does not answer at all. GitHub waits 10 s, gives up and marks the delivery failed. Here the app answers 202 and its enqueue fails; the end state (a hint lost, no workflow) is the same, the path to it is not. The GitHub delivery log, the timeout and the cold start were not exercised.
- **The poller sits on the awake side of the story here.** In the design (T07) `poll_forever` runs inside the service. A Render free service that is asleep runs no code: "Outbound traffic or a background poll does not keep it awake" (Render page, in `p6-t00-versions.md`), and it wakes only on an inbound request. So with the in-process poller alone, the real sequence "service sleeps, webhook is lost, one poll interval later the workflow starts" would **not** happen: the poller would stay asleep with the service, and the lost webhook would be recovered only when something else wakes the service (any later request, a redelivery from the owner, an external ping). The local test cannot show this because it calls `poll_once` itself. What wakes the service on a schedule (an external pinger, a scheduled GitHub Actions job that calls the service or runs the poll) is open and belongs to ADR-021/022 and T13. This is the reason I left the task unticked.
- Neon suspend at the same time (T24), the QA wait, a crash (T19, T21), many tickets, the GitHub rate limit, the poll interval (300 s is a default, not a measurement).
- The recorded GitHub JSON is hand-written to the documented response shape, not captured from a live repository.

**Fix** (already in the code; nothing new in T23): the webhook is only a hint and does no GitHub read inline (T06); the workflow key is the ticket id, so a hint, a poll and a redelivery meet on one workflow (T03, T06, T07); a failed enqueue forgets the delivery id (T06); the poller reads GitHub on a schedule instead of trusting delivery (T07). Open, not fixed: the schedule must run somewhere that is awake (see above).

**Owner steps: the real version** (needs the Render service from T12 and a poller that is actually running; wording of the Render and GitHub pages is from memory, not seen in this session):

1. Deploy the service (T12) with the webhook configured on a test repository (payload URL, content type `application/json`, secret = `GITHUB_WEBHOOK_SECRET`, event: Issues), and the poller running as designed.
2. Leave the service with no inbound request for more than 15 minutes (Render's documented sleep time, `p6-t00-versions.md`). Check in the Render dashboard that it shows as spun down.
3. Open a new issue in the test repository. In the repository's webhook settings, open Recent Deliveries and note the delivery: expected a timeout or a failure after about 10 s, with no 2xx. Note the time.
4. Do **not** redeliver. Wait one poll interval (default 300 s) and then a little more. Check the Render logs and the DBOS workflow table for a workflow whose id is the ticket id (`owner/repo#number`), and the issue for the first Argus comment or label.
5. Write down: did the workflow start at all, how long after the issue was opened, and whether the service had woken up by then. If nothing started, that confirms the finding above (a sleeping service runs no poller) and the fix is a scheduled wake-up (for example a scheduled GitHub Actions job); record it for ADR-021/022.
6. Then use Redeliver on the failed delivery and check that the ticket still has exactly one workflow.

Run: `uv run --all-packages python -m pytest packages/flow/tests/test_render_sleep_break_it.py -q` (the DBOS case needs `ARGUS_FLOW_DATABASE_URL`; commands for a throwaway Postgres are in [p6-t07.md](p6-t07.md)). Script: `uv run --all-packages python packages/flow/tests/render_sleep_demo.py`.

## Real run (2026-11-03)

**Setup.** Render free service `argus-flow` (Oregon), commit `c63e2a6` (the first with INFO logging), `ARGUS_FLOW_POLL_ENABLED=true`, `ARGUS_FLOW_TICKET_LABEL=argus-t23`, poll interval 300 s. A webhook on `vibhu-0511/argus` for the **Issues** event only, content type JSON, the same secret as the service. A label `argus-t23` on the repository. The agent workflow is not on `main` and its secrets are not set, so the pipeline is expected to fail at the agent dispatch.

**The service slept.** The instance `l7zdh` started at 09:05:57 IST and logged `poll: 0 tickets listed` at 09:05:59, 09:10:59 and 09:16:00. There is no line after that: nothing polled for 30 minutes. (The spin-down itself is inferred from the missing lines; the Render Events page was not consulted.)

**Induced failure.** Issue #16 `T23 Test` created with the label `argus-t23` at 09:46:19 IST (04:16:19Z). GitHub sent `issues opened` and `issues labeled`; both ended as `500` with `context deadline exceeded (Client.Timeout exceeded while awaiting headers)` after 10 s (recorded 04:16:31Z).

**Observed** (Render application log in IST, the GitHub delivery list, and the issue; the Render logs were read from screenshots the owner sent):

| Time | What |
|---|---|
| 09:46:19 | issue created |
| 09:46:21 to 09:46:31 | both deliveries sent and abandoned by GitHub at 10 s |
| 09:46:50 | `DBOS launched` on a new instance `6ztwx` (about 30 s after the request) |
| 09:46:52 | `workflow engine started; poll loop on` |
| 09:46:52 and 09:46:53 | `POST /webhook` answered `202 Accepted` twice: the two requests GitHub had given up on |
| 09:46:54 | `poll: 1 tickets listed, started 1, exists 0, settled 0, errors 0` |
| 09:47:00 | comment on the issue: `Argus: failed. reproducing: repro_step failed after 3 attempts`, with the hidden key `argus-key: argus:vibhu-0511/argus#16:comment-failed:1` |
| 09:47:01 | label `argus:failed` set |
| 09:47:02 | `POST /webhook` 202 in 0.28 s: the `labeled` event of the service's own label |
| 09:51:56, 09:56:58 | `poll: 1 tickets listed, started 0, exists 1` |
| 09:55:14 | the owner redelivered the `opened` event: 202 in 0.12 s, marked as a redelivery; the issue still had one comment and the same two label events |

The comment and the label are the first real writes by `flow.github_write` to GitHub. The pipeline failed where expected (no agent job could run); the point of the run is the path around it.

**Reading.**

- The webhook failed at GitHub exactly as T13 predicted: a cold start of about 30 s against a 10 s window.
- Render did not drop the abandoned requests: the woken instance answered both 202 about 31 s after the issue was created. One observation.
- The poller's first poll, two seconds after the engine started, found the ticket and reported `started 1`. The webhook handler's own enqueue is not visible in the logs; the workflow id (the ticket id) absorbs a second enqueue, and there was one workflow outcome, one comment and one label.
- A redelivery after the workflow had finished changed nothing.
- The expected signal "no immediate reaction, then the poller starts the workflow" was seen in this form: no reaction for 30 s, then the workflow started 2 s after the service came up.

**Not shown.**

- The poller recovering a hint that **never** reached the service. Here the webhook itself woke the instance and its requests were served, so both paths were alive. A lost hint with the service down or crashed was not tried.
- Who started the workflow, strictly: the poller reported `started 1`, so it enqueued it; whether the webhook's enqueue ran first, second or not at all is not in the logs.
- A sleeping service polling: it does not, and nothing wakes it on a schedule. If no request arrives, a ticket waits. That is the open item of ADR-022.
- One run, one evening, one idle length (about 30 minutes). The idle gap was not timed against the 15 minute rule; the missing poll lines suggest the instance was gone by 09:21.
- A real agent run: the dispatch failed three times, so repro, fix and verify did not run (T04).

The owner closed issue #16 afterwards, so it is no longer polled.

