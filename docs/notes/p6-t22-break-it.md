# P6-T22 break it: deliver the same webhook twice

Test: `packages/flow/tests/test_duplicate_delivery.py`. It posts signed deliveries to the real FastAPI app (`flow.webhook.create_app`) through the test client, with `FakeEnqueuer` standing in for the DBOS workflow start. `FakeEnqueuer` records every `enqueue_reconcile` call and keeps one "workflow" per ticket id, the rule `SetWorkflowID(ticket_id)` will give in P6-T03. No network, no model.

**Induced failure.** The same webhook body arrives twice with the same `X-GitHub-Delivery` id (a GitHub redelivery, or a retry after a lost response).

**Expected signal.** The second delivery is dropped as already seen. Enqueue is called once, one workflow exists.

**Observed.**

| Case | Responses | `enqueue_reconcile` calls | Workflows (ticket ids) |
|---|---|---|---|
| Same delivery id twice | 202 `accepted`, 202 `duplicate` | 1 | 1 |
| Two different delivery ids, same ticket | 202, 202 (both `accepted`) | 2 | 1 |
| Dedup record off (size 0), same id twice, plus a restarted app with an empty record | all 202 `accepted` | 3 | 1 |
| Record of size 2, ids d-1, d-2, d-3, then d-3, then d-1 | d-3 `duplicate`, d-1 `accepted` again (evicted) | 4 for d-1..d-3 plus the repeated d-1 | 1 |
| Forged signature with the same id, then the real one | 401, then 202 `accepted` | 1 | 1 |

- The duplicate answers 202, not an error, so GitHub does not mark the delivery as failed.
- Dropping the repeat is an optimisation. When the record is switched off, lost on restart, or has evicted the id, the repeat is enqueued again, and still only one workflow exists, because the workflow is keyed by the ticket id and not by the delivery id. The fake enqueuer models that rule; the real guarantee comes from DBOS in P6-T03.
- The id is recorded only after the signature has passed, so a forged request cannot use up a real delivery id.
- If the enqueue itself raises, the delivery id is forgotten, so GitHub's redelivery is not dropped (covered in `test_webhook.py`).

**Not shown.** The "one workflow" is the fake's set of ticket ids. No DBOS workflow, database or real redelivery from GitHub was involved. Re-check this against DBOS once P6-T03 lands: starting a workflow under an id that already exists must return the existing one.

**Fix.** The delivery id is a hint-dedup record only (`HintDedup`: bounded, in memory, per process). The workflow key is the ticket id (`owner/repo#number`). Do not key anything by the delivery id.

Run: `uv run pytest packages/flow/tests/test_duplicate_delivery.py -q`
