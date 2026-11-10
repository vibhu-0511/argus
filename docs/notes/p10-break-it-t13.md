# P10-T13 Break it: double approve

Test: `packages/workbench/tests/test_break_double_approve.py` (14 tests). Real routes through the real app (`create_app`), requests sent from a `ThreadPoolExecutor` released together by a barrier, one fresh `TestClient` per request. The PR goes to the in-memory mock GitHub. No model call, no network.

## Induced failure

| Case | What is sent | Repeated |
|---|---|---|
| same key twice | two `approve` requests with one `idempotency_key` at the same moment | 30 rounds, each on its own run and its own ticket (so its own branch) |
| different keys at once | two `approve` requests with keys `key-a` and `key-b` at the same moment | 30 rounds |
| four keys at once | four `approve` requests, four keys | 10 rounds |
| approve racing the PR route | one `approve` and three `POST /api/runs/{id}/pr` | 10 rounds |
| race window widened on purpose | the read of `decision.json` sleeps 50 ms after it read, so both requests see "no decision yet" unless something serialises them | 5 rounds with two keys, 3 rounds with one key |
| approve after a failed verifier | `POST /api/runs/fixture-verifier/decision` with `approve`, with and without a reason or note, 8 at once, and with an extra field claiming the verifier passed | direct API calls, no page |
| failing verdict behind a reviewable state | a run in `awaiting-qa` (the page would show Approve) whose `verdict.json` was replaced by the failing verdict | once |
| verdict turned bad after the approval | `POST /api/runs/{id}/pr` after the verdict file was replaced by a failing one | once |

## Expected signal

- Same key: both answers are 200, exactly one has `replayed: false` and one `replayed: true`, both carry the same stored decision, one `decision.json`, one PR on the mock (`POST /pulls` and `POST /git/refs` once per round), `pr.json` says `created` with `updates: 0`, the run is `done`.
- Different keys: exactly one 200 and one 409 whose body is `{"error": {"code": "already_decided", "field": "idempotency_key", ...}}`; the stored key is the winner's; one PR.
- Failed verifier: 409 `verifier_failed`, no `decision.json`, `state.json` byte for byte as before, no `pr.json`, not one request to the mock GitHub. An unknown extra field (`verdict_ok`, `force`) is a 422 `invalid_request`.

## Observed

Clean build: `14 passed`. The existing code from the review and PR groups already had what is needed, so no source file was changed: `decisions.decide` runs read-decision, rules, write-decision, state move and approve hooks under one `threading.Lock`, `store.write_file(..., overwrite=False)` creates `decision.json` with `open(..., "xb")` (atomic: one creator wins, the other gets `already_written`), and `pull_request.raise_pr` has its own lock around find-before-act. I looked for a race and found none in 30 + 30 + 10 + 10 + 8 rounds of the clean build.

Mutated builds (one change each, the original bytes written back after each run, `git status` clean afterwards):

| Mutation | File | Result | What the test saw |
|---|---|---|---|
| lock removed (`with _LOCK:` made `if True:`) | `decisions.py` | 4 failed, 10 passed | different keys: the loser got `already_written` (the atomic create caught it) instead of `already_decided`; same key: `(200, 409)` instead of `(200, 200)`, the second request was not a replay. Caught in the unwidened 30-round tests too, so the race is real on this machine, not only in the widened test |
| lock and atomic create removed (`with _LOCK:` made `if True:`, and `overwrite=False` dropped from the `decision.json` write) | `decisions.py` | 4 failed, 10 passed | both requests answered 200: `assert 2 == 1` winners in round 0 (`[200, 200]`); two decisions, two approve hooks |
| server verdict check removed (`if not verdict.ok:` in `approve_gate` made `if False:`) | `decisions.py` | 1 failed, 13 passed | the run in `awaiting-qa` with a failing verdict: `assert 200 == 409`, a decision was stored and the state moved to `done` |
| verdict check in the PR step removed (`if not verdict.ok:` in `raise_pr` made `if False:`) | `pull_request.py` | 1 failed, 13 passed | `POST /pr` for a run whose verdict is now a fail: `assert 200 == 409`, the PR was updated |

Said plainly:

- Removing only the lock does not make two PRs, because the exclusive create of `decision.json` still lets one request through. The test fails anyway because the loser's error and a same-key replay are wrong without the lock; the test asks for the right answer, not only for one PR.
- Removing the lock and the exclusive create makes two accepted decisions. Whether that mutated build also makes two PRs was not measured (the test stops at the second 200). By reading the code, `raise_pr` has its own lock and finds the first PR by branch, so the second approve would update it, not create one. That is a third layer, not a reason to drop the others.
- The `fixture-verifier` cases (state `failed`) are refused by two checks at once (the state and the verdict), so removing the verdict check alone does not fail them. The run with a reviewable state and a failing verdict file is the case that isolates the verdict check.

## Fix

None needed in the source. The defence is: idempotency key (same key returns the stored decision), a lock around decide-and-open-PR, an exclusive create of `decision.json`, and the server checking the verdict file, not the button.

## Not defended (said plainly)

The locks are process-wide (`ponytail:` comments in `decisions.py` and `pull_request.py`). Two server processes on one run store would need a file lock; the workbench starts one process on 127.0.0.1. The exclusive create of `decision.json` still protects the decision itself across processes, the PR step would not be protected.

Proof command: `uv run --all-packages python -m pytest packages/workbench/tests/test_break_double_approve.py -q`
