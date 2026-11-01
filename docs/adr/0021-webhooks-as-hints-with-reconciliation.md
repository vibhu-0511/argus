# ADR-021: Webhooks as hints with reconciliation

Status: proposed (P6-T16), drafted by Claude at the owner's request, for the owner to review. It is accepted when the owner approves it. **It is incomplete on purpose:** the phase asks it to use the Render cold-start measurement (P6-T13) as evidence, and that measurement does not exist, because no Render service exists. The design below rests on what is built and tested locally, on vendor pages read on 2026-11-01 (`docs/notes/p6-t00-versions.md`), and on local stand-ins for the sleep and the lost webhook (T22, T23, T24). Where the cold start would be evidence, the text says so and gives no number.

## Context

A ticket is a GitHub issue. The workflow that fixes it (`flow.workflow.ticket_workflow`, DBOS on Postgres) has to start when the issue appears and has to find its way back to the right state after any gap. GitHub offers a push: a webhook. The facts about that push, from GitHub's own page (read 2026-11-01, `p6-t00-versions.md`):

- The receiver must answer 2xx within 10 seconds, or GitHub ends the connection and counts the delivery as failed.
- A failed delivery is **not retried by GitHub**; the page says to redeliver missed webhooks yourself, by hand or through the redelivery API. A redelivery carries the same `X-GitHub-Delivery` id as the original.
- The page advises answering first and processing afterwards.

The deployment is one free Render web service that sleeps after 15 minutes without inbound traffic and takes "about one minute" to come back, per Render's page (same notes). That is longer than 10 seconds. So a webhook that arrives while the service sleeps can be lost, and with a free service that is expected to happen, not an edge case (ADR-022 covers the topology).

The question is what the webhook is allowed to be: the event that drives the workflow, or something weaker.

## Decision

**A webhook is a hint. GitHub is the source of truth. A poller reads GitHub and repairs what a hint missed.**

1. **The handler does no work that depends on GitHub.** After the HMAC check (`flow.webhook.verified_body`, fails closed when no secret is set) it reads the event name and delivery id from the headers, derives the ticket id from the payload, schedules `enqueue_reconcile(ticket_id)` to run after the response, and returns 202. It makes no GitHub call and waits for nothing (`flow/webhook.py`, `flow/enqueue.py`). Handler time, measured in-process with an enqueue that sleeps 2 s: the response was fully sent after 0.8 to 1.8 ms (`docs/architecture/p6.md`, P6-T06). That is the handler on a laptop, **not** a Render cold start. Whether a woken Render instance answers inside 10 s is exactly what T13 would show, and it has not run.
2. **The workflow id is the ticket id.** The key is `owner/repo#number`. The webhook and the poller both call the same `Enqueuer`, which starts the workflow under `SetWorkflowID(ticket_id)`. DBOS does not start a second workflow under an id it already has; a second enqueue after the first run finished returned the first run (checked on 3.4.0, `docs/adr/0020-dbos-vs-temporal.md`). A hint, a poll and a redelivery therefore land on one workflow. Inside the workflow, every side effect is find-then-create on a key derived from the ticket (`flow.states.EFFECTS`), so a workflow that starts late or twice opens one PR (T21).
3. **The delivery id is a hint-dedup record and nothing else.** `HintDedup` is a bounded (1024), in-memory, per-process set. It drops a repeat of the same delivery early and answers it 202 `duplicate`, so GitHub does not mark it failed. It is lost on restart, evicted when full, and not shared between instances. T22 shows that with the record switched off, lost or evicted, the repeat is enqueued again and still ends in one workflow. Dropping a repeat is an optimisation; the ticket id is what keeps the run single. Nothing is ever keyed by the delivery id. The id is recorded only after the signature passes, so a forged request cannot use up a real id. If the enqueue fails, the id is forgotten, so GitHub's redelivery is accepted instead of dropped (T23, and T24 case 3).
4. **The poller rebuilds state from GitHub alone.** `Reconciler.poll_once` lists open issues and, per ticket, makes five GET requests (issue, PRs on the stable branch, the branch ref, `workflow_dispatch` runs, issue comments). `derive_state` is a pure function from that to a `State` (the "GitHub shows" column of `flow.states.STATES`). The poller cannot write to GitHub (no other HTTP verb in `flow/github_read.py`). It does not write a state into DBOS either: if no workflow exists and the derived state is not an end state it starts one through the shared `Enqueuer`, and the workflow replays its keyed steps and finds the runs, branch and PR GitHub already shows. If a workflow exists it only reports (`exists`, with `diverged` when a finished workflow ended in a state GitHub no longer shows). If the state is an end state it starts nothing (`settled`). A GitHub or database error raises before anything is enqueued (`docs/notes/p6-t07.md`).
5. **Defaults, as built:** interval 300 s (floor 60 s, so a typo cannot hammer the API), page size 30, 3 pages, so at most 90 open tickets are polled and the least recently updated beyond that are not. These are picked, not measured. In the Blueprint the poll loop is **off** (`ARGUS_FLOW_POLL_ENABLED=false`, `render.yaml`) until a real GitHub write client exists.

### Poll cost: what is known, what is not

| | Value | Status |
|---|---|---|
| GitHub requests per poll | `5 x tickets + 1 listing request per page`; with one open ticket, 6; at the 90-ticket ceiling (30 x 3 pages), 90 x 5 + 3 = 453 | arithmetic from the code |
| Per hour at 300 s (12 polls) | 72 for one ticket; 5,436 at the ceiling | arithmetic |
| Against GitHub's API rate limit for the token | **not compared.** The limit for the account type was not read for this ADR | open |
| Database reads per poll | one `get_workflow_status` per ticket (`DbosLookup`) | read from the code |
| Whether that keeps the Neon compute awake (5 min idle timer against a 300 s interval) and what it costs in CU-hours | **not measured** (T14) | open |
| Whether the poll can run while the service sleeps | **no**, see below | finding |

A cost in CU-hours or Render hours is not claimed. The phase asks this ADR to state the poll interval and its cost; the interval is 300 s and the cost is only known in GitHub requests, not in the free-tier quantities that matter.

### What the poller cannot do: wake the service

`poll_forever` runs inside the Render process, so it runs only while the service is awake. Render's page says outbound traffic and background work do not keep a free service awake; only inbound requests do. A sleeping service runs no poller, so **the sequence "webhook lost, one poll interval later the workflow starts" does not hold on its own**. In the T23 stand-in the test calls `poll_once` itself, which hides this. The webhook sends the first request that wakes the service, GitHub gives up after 10 seconds, and the poller then has to be running when the instance is up again. If nothing else calls the service, the lost hint is recovered only after some later request arrives (an unrelated webhook, a manual redelivery, a person opening `/health`). What wakes the service on a schedule is undecided and unmeasured; ADR-022 lists the candidates. Until one is chosen and run, reconciliation is a repair that happens when the service is next awake, not on a schedule.

## The one exception: a review comment is acted on directly

`/argus approve` and `/argus reject` in a PR review or inline review comment are **not** treated as a hint. `flow.webhook` parses them from the payload alone (`flow.review_comment.parse_review_event`) and hands the decision to the QA signal (`flow.qa.send_qa_signal`) after answering 202; nothing is enqueued and GitHub is not read. This is the single case where the payload is trusted for content, and it is chosen deliberately (ADR-023 is the full decision):

- **The payload is the only place the decision lives.** A hint says "something may have changed; go and look". For a QA decision there is nothing to look at: the human's answer is the comment, and the state GitHub shows (PR still draft, label `awaiting-qa`) does not change until the workflow itself acts on that answer. The poller reads the issue, the PRs, the branch, runs and issue comments; it does **not** read PR reviews or review comments, so it could not recover this decision from GitHub even if it tried.
- **The workflow already exists and is waiting.** This is a signal to a running `DBOS.recv`, not a start. Duplicates are absorbed by the signal's own idempotency key (`qa_signal_key`, built from the comment id), not by the delivery id: the same comment delivered twice, or edited back and forth, changes nothing, and the workflow records the first signal and drops the rest.
- **It is guarded where a hint is not.** The commenter's login must be in `ARGUS_FLOW_QA_REVIEWERS` (unset allows nobody), the PR title and head branch must match the Argus PR for the ticket, and exactly one command must appear at the start of a line. A failure is a quiet no-op.

Cost of the exception, stated plainly: **a lost review-comment delivery is not repaired.** The review path returns before the delivery-id record, so a GitHub redelivery is accepted and sent again; but if nobody redelivers, the workflow stays in `awaiting-qa` until its timeout and ends in `timed-out`, and a command posted after that is dropped (a finished workflow id is not reused; a re-run is not built). A second weakness is that `send_qa` logs and swallows a failure (for example the engine not running within 120 s), so a signal delivered while the service is waking can be lost without any retry of ours. Neither was exercised against a real GitHub delivery; the payloads are hand-written fixtures.

## Alternatives

- **The webhook as the event: parse the payload and act on it for every event type.** Rejected. A delivery can be lost (10 s timeout, a sleeping host, a database that is down) and GitHub does not retry; the payload is a snapshot that can already be stale; and acting on it in the handler would put GitHub calls and a database wake-up inside the 10 s window. The T23 and T24 stand-ins show the failure and the repair.
- **Poll only, no webhook.** Not chosen: it would remove the 10 s problem, but every ticket would wait for the next poll, and on Render free the poll runs only while the service is awake, so it needs the same unsolved wake-up. The webhook is the cheap fast path when it works.
- **Key the workflow by delivery id and dedup in the engine.** Rejected: two different deliveries about one ticket would then start two workflows; the ticket id is the thing that must be unique (T22, row 2: two delivery ids for one ticket gave two enqueues and one workflow).
- **Persist delivery ids in Postgres.** Not done: it would add a database write to the handler and wake the Neon compute on every delivery, to protect an optimisation. Revisit only if repeats become costly (`ponytail:` note in `flow/enqueue.py`).
- **Have the poller write the derived state into the workflow.** Not built: DBOS has no resume-at argument here, and the replay of keyed steps already lands at the right state (T07).

## Consequences and open items

- **T13 is the missing evidence.** Until a Render deploy is timed over several idle gaps, this ADR cannot say whether the first webhook after a sleep fits 10 s, and the claim "a woken service can still lose the hint" is a reading of the vendor pages, not a measurement. `TASKS.md` stays unticked for P6-T16; its criterion ("uses the cold-start measurement as evidence and states the poll interval and its cost") is only half met: the interval is stated, the cost is stated only in GitHub requests, and the cold-start measurement is absent.
- **Defect, not fixed here: PR events name the wrong ticket.** `ticket_id_of` takes `payload["pull_request"]["number"]`, which is the PR number, not the issue number. With the real `DbosEnqueuer`, a `pull_request` delivery would start a workflow keyed `owner/repo#<PR number>`. The runbook subscribes the webhook to Pull requests (`docs/notes/p6-t12.md`). The poller never maps a PR to a ticket (it raises `NotATicket` and skips PRs). The fix belongs in the handler: ignore `pull_request` events for enqueueing, or map the PR to its issue. Found by T07, documented in `p6-t07.md`, still present in `flow/webhook.py`.
- **Lost review comments** are not repaired (above). Making the poller read PR reviews and review comments, or the `/argus` command in issue comments, would close it; not checked, not built.
- **`issue_comment` is not parsed,** so a command in the conversation tab is ignored silently (ADR-023).
- **The poller is off in the Blueprint** and its GitHub write counterpart is `UnwiredGitHub`, so on the deployed service nothing real is reconciled yet (ADR-022).
- Facts about GitHub's and Render's behaviour are dated 2026-11-01. The 300 s default is a choice for the owner to confirm or change after T13 and T14; the code takes it from `ARGUS_FLOW_POLL_INTERVAL_S`.

## Sources

Read on 2026-11-01 unless stated; repository facts are from the files named.

| Fact | Source |
|---|---|
| 10 s to answer 2xx; failure not retried automatically, redeliver by hand or API; same `X-GitHub-Delivery` on redelivery; answer first, process later | https://docs.github.com/en/webhooks/using-webhooks/best-practices-for-using-webhooks (`docs/notes/p6-t00-versions.md`) |
| Render free: sleeps after 15 min without inbound traffic, outbound traffic or background polls do not keep it awake, cold start "about one minute" | https://render.com/docs/free (same notes) |
| Neon free: suspends after 5 minutes idle | https://neon.com/docs/introduction/plans (same notes; re-read 2026-11-02 for ADR-022) |
| Handler flow, review-comment exception, `HintDedup`, enqueue contract | `packages/flow/src/flow/webhook.py`, `enqueue.py`, `review_comment.py`, `qa.py` |
| Poller reads and `derive_state`, defaults, `settled`/`exists`/`started` | `packages/flow/src/flow/reconcile.py`, `github_read.py`; `docs/notes/p6-t07.md` |
| Handler time 0.8 to 1.8 ms in-process | `docs/architecture/p6.md` section P6-T06 |
| Duplicate delivery cases | `docs/notes/p6-t22-break-it.md`, `packages/flow/tests/test_duplicate_delivery.py` |
| Dropped webhook while asleep (stand-in), and why the poller cannot run asleep | `docs/notes/p6-t23-break-it.md`, `packages/flow/tests/test_render_sleep_break_it.py` |
| Webhook during a database outage, forgetting the id, redelivery accepted | `docs/notes/p6-t24-break-it.md`, `packages/flow/src/flow/db_wake.py` |
| Restart opens no second PR | `docs/notes/p6-t21-break-it.md`, `docs/notes/p6-t19.md` |
| Poller off in the Blueprint; `UnwiredGitHub`; webhook events and `qa_send` wiring | `render.yaml`, `packages/flow/src/flow/service.py`, `docs/notes/p6-t12.md` |
