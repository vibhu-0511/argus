# P6-T02 Workflow state machine

Code: `packages/flow/src/flow/states.py`. Test: `packages/flow/tests/test_states.py`. The three tables below are generated from the code (`markdown_tables()`) and a test fails if this file and the code differ. Regenerate with:

```
uv run python -c "from flow.states import markdown_tables; print(markdown_tables())"
```

## How to read it

- A **state** is the pipeline step that is running, or waiting. The workflow stores its state after every step, and `next_state(state, event)` is the only place a state changes. An event that is not in the transition table raises `IllegalTransition`.
- A step does its **effects**, stores its result, then fires its event. A crash anywhere in that window re-runs the step. The effects are written so that the re-run finds what the first run already made (third table), which is the answer to "the worker dies after the PR is opened but before the state is saved".
- Terminal states also have effects (comment, label, ready or close the PR). They run in a final step after the terminal state is stored, and are keyed the same way, so a crash there re-runs them safely.
- **GitHub objects.** The ticket is an issue. The fix lives on one stable branch `argus/<slug>-<hash8>` with one draft PR. Each of repro, fix and verify is its own `workflow_dispatch` run of one Actions workflow with the inputs `step` and `run_key`; the run is named by the key. Labels `argus:awaiting-qa`, `argus:done`, `argus:rejected`, `argus:timed-out`, `argus:failed` mark the later states on the issue. The owner creates these five labels once in the repo; the workflow does not create labels.
- The "GitHub shows" column is what the reconciliation poller (T07) reads. A pre-PR state is read from run titles and conclusions, a later one from the PR and labels. Where two readings fit, the latest one wins.

## Decisions

- **One Actions run per step, not one run for all three.** The phase doc (T04) says a run executes repro, fix and verify. Dispatching them as three runs of the same workflow file, in order, still does that, and it makes each step a crash boundary (T19), gives each its own artifact, and lets the poller tell `fixing` from `verifying` by looking at the runs. The cost is up to three queue waits per ticket. T04 should confirm the choice or change the table.
- **No loop from `verifying` back to `fixing`.** The fix loop retries its own verify. `attempt` in a key is 1 until a deliberate re-run of a ticket exists; a retry of a step after a crash keeps the same attempt, so it finds the same effect.
- **QA reject closes the PR; timeout leaves it open as a draft.** Close is reopenable. A late signal after a timeout is an illegal transition and is dropped.
- **`done` means approved and ready for review.** The workflow never merges.
- **Not modelled:** a human closing the issue or the PR mid-run, and a second ticket for the same issue. Both would need new events. The poller (T07) is where they would first show up.
- **Known window:** `workflow_dispatch` returns 204 with no run id, and the run list can lag by a few seconds. A retry that lists runs too early could dispatch twice. A concurrency group on the key allows only one running and one pending run, which narrows the window but does not close it; T04 should poll for the run before it re-dispatches.

<!-- generated:begin -->
### States

| State | Kind | GitHub object | GitHub shows | Effects |
|---|---|---|---|---|
| `received` | start | issue | issue open; no `argus:*` run, no branch, no PR | `start-workflow` |
| `reproducing` | active | Actions run | a `dispatch-repro` run is queued or in progress, none concluded | `dispatch` |
| `fixing` | active | Actions run | `dispatch-repro` concluded success; no `dispatch-fix` run concluded | `dispatch` |
| `verifying` | active | Actions run | `dispatch-fix` concluded success; no `dispatch-verify` run concluded | `dispatch` |
| `opening-pr` | active | branch, PR | `dispatch-verify` concluded success; PR missing, or present without label `argus:awaiting-qa` | `push-branch`, `open-pr`, `post-comment`, `set-label` |
| `awaiting-qa` | active | PR | draft PR on the stable branch, open, issue labelled `argus:awaiting-qa` | `record-qa-signal` |
| `done` | terminal | PR | PR ready for review or merged; issue labelled `argus:done` | `ready-pr`, `post-comment`, `set-label` |
| `failed` | terminal | issue | any step run concluded failure or cancelled; issue labelled `argus:failed` | `post-comment`, `set-label` |
| `rejected` | terminal | PR | PR closed unmerged; issue labelled `argus:rejected` | `close-pr`, `post-comment`, `set-label` |
| `timed-out` | terminal | PR | PR still open and draft; issue labelled `argus:timed-out` | `post-comment`, `set-label` |

### Transitions

| From | Event | To | Fires when |
|---|---|---|---|
| `received` | `start` | `reproducing` | workflow body begins for a new ticket |
| `reproducing` | `repro_ok` | `fixing` | repro run concluded success and returned a script |
| `reproducing` | `repro_failed` | `failed` | repro run failed, was cancelled, or did not reproduce |
| `fixing` | `fix_ok` | `verifying` | fix run concluded success and returned a patch |
| `fixing` | `fix_failed` | `failed` | fix run failed, was cancelled, or hit its budget |
| `verifying` | `verify_ok` | `opening-pr` | verify run concluded success and the verdict is ok |
| `verifying` | `verify_failed` | `failed` | verify run failed or the verdict is not ok |
| `opening-pr` | `pr_opened` | `awaiting-qa` | draft PR exists on the stable branch |
| `opening-pr` | `pr_failed` | `failed` | GitHub refused the branch or PR after the step retries |
| `awaiting-qa` | `qa_approved` | `done` | first approve signal (review comment or MRTR answer) |
| `awaiting-qa` | `qa_rejected` | `rejected` | first reject signal |
| `awaiting-qa` | `qa_timeout` | `timed-out` | the durable QA deadline passed with no signal |

### Side effects

| Effect | GitHub object | Idempotency key | A retry finds it by |
|---|---|---|---|
| `start-workflow` | issue | workflow id = `<ticket_id>` | enqueue with the same workflow id; DBOS returns the existing workflow, so a second enqueue is a no-op |
| `dispatch` | Actions run | `argus:<ticket_id>:dispatch-<step>:<attempt>`, sent as input `run_key` and used as the run's `run-name` | list `workflow_dispatch` runs of the workflow and match the run title to the key; found: wait for it, do not dispatch. A concurrency group on the key allows one running and one pending run |
| `push-branch` | branch | branch `argus/<slug>-<hash8>` (no attempt in it) and commit trailer `Argus-Key: argus:<ticket_id>:push-branch:<attempt>` | GET the branch ref; its head commit carries the trailer: done. Ref missing: create it. Ref exists without the trailer: add the patch commit on top. Never force-push |
| `open-pr` | PR | the head branch (one stable branch per ticket); opened as draft | list PRs with `head=<owner>:<branch>` and `state=all`; found: reuse it, any state. None: create a draft. A lookup error raises and creates nothing. No `closes #N` or commit-message search |
| `post-comment` | issue comment | `argus:<ticket_id>:comment-<state>:<attempt>`, written into the body as `<!-- argus-key: <key> -->` | list the issue comments and look for the marker; found: skip, do not edit |
| `set-label` | issue label | label `argus:<state>`; adding a label that is present changes nothing | read the issue labels; add `argus:<state>`, then remove other `argus:*` labels, ignoring 404 |
| `ready-pr` | PR | the PR of the stable branch | read `isDraft`; already false: skip. Otherwise mark ready for review |
| `close-pr` | PR | the PR of the stable branch | read `state`; already closed: skip. Otherwise close it (reopenable) |
| `record-qa-signal` | none (workflow store) | `argus:<ticket_id>:qa:<source>:<source_id>`, source is `review-comment` or `mrtr` | the first signal moves the state; a repeat of the same key is dropped; a different key after the state left `awaiting-qa` hits IllegalTransition and is dropped |
<!-- generated:end -->

Key functions in `states.py`: `workflow_id(ticket_id)`, `branch_name(ticket_id)`, `effect_key(ticket_id, effect, attempt=1)`, `qa_signal_key(ticket_id, source, source_id)`, `comment_marker(key)`. They take strings and integers only, so they return the same value on every call and in every process.
