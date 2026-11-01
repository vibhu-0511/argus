# P6-T21 break it: kill the worker after the PR is opened, before the step result is stored

Test: `packages/flow/tests/test_pr_break_it.py`. It runs the T19 harness ([p6-t19.md](p6-t19.md), `packages/flow/scripts/p6_t19_crash_recovery.py`): a real child process runs the DBOS ticket workflow (`flow.workflow.ticket_workflow`, launched with `flow.dbos_runtime.launch`) against a throwaway local Postgres 16 (container `argus-p6-pg-w4a`, port 55437), with fake runners and a fake GitHub whose world is a ledger file (`flow.ledger_fakes`), so the PR outlives the process. The child stops at kill point `open-pr:pr-created` (the draft PR is in the ledger, `open_pr_step` has not returned) and the harness hard-kills its process tree from outside (TerminateProcess). A second process then recovers the workflow with the same executor id and pinned application version. No network, no model, no real GitHub.

**Induced failure.** The worker dies right after `create_draft_pr` and before DBOS stores the result of `open_pr_step`.

**Expected signal.** On restart the step runs again, finds the existing PR, and exactly one PR exists.

**Observed.** One kill, ledger in order (`n` = call counter for the op and key, `made` = the call made a new effect):

| seq | op | n | made | when |
|---|---|---|---|---|
| 1 to 3 | `dispatch-repro`, `dispatch-fix`, `dispatch-verify` | 1 | yes | first process; `repro_step`, `fix_step`, `verify_step` stored |
| 4 | `push-branch` | 1 | yes | first process, `open_pr_step` starts |
| 5 | `find-pr` | 1 | no | lookup found no PR |
| 6 | `create-pr` | 1 | yes, `draft: true` | **killed here** (6 rows exist, `open_pr_step` not stored) |
| 7 | `push-branch` | 2 | no | restart: the step runs again from its top; the push key is found |
| 8 | `find-pr` | 2 | no | restart: the lookup finds the PR, so no create |
| 9, 10 | `comment`, `label` (`awaiting-qa`) | 1 | yes | step finishes |
| 11 | `ready-pr` | 1 | yes | after the QA signal, in `finish_step` |
| 12, 13 | `comment`, `label` (`done`) | 1 | yes | `finish_step` finishes |

| Claim | What was seen |
|---|---|
| Restart opens no second PR | `create-pr` has one row in the whole run; the restart's `find_pr` found the PR and `create_draft_pr` was not called again. Run reached `done`. The same in the 10 kills at this point in the T19 run ([results-B.json](../../packages/flow/results/p6-t19/results-B.json)): 10 of 10 completed, 0 duplicate effects, repeated calls exactly `push-branch` and `find-pr` |
| One stable branch | every `push-branch` row carries `branch_name(ticket)` and so do the `create-pr`, `find-pr` and `ready-pr` keys; asserted in the test. The restart pushed to the same branch (key found), it did not make a new one |
| Draft until QA | the PR is created with `draft: true`; the only `ready-pr` row comes after the `awaiting-qa` label row, and `ready-pr` is called only from `finish_step` after an approve (asserted by ledger order) |
| No `closes #N` heuristic | `grep -rniE "closes\|fixes #\|resolves\|search/commits\|search/issues" packages/flow/src` finds only prose: `workflow.py` lines 15, 107, 156 (docstrings: "closes the PR", "no `closes #N`"), `states.py:154` (the `open-pr` row of `EFFECTS`: "No `closes #N` or commit-message search"), `qa_mcp.py:52` (a tool-field description, "reject closes it"). No code builds, parses or searches for such text. The PR lookup is by head branch: `github_read.py:81` `GET /pulls?head=<owner>:<branch>&state=all`. The test repeats this on the AST (string constants that are not docstrings; comments are not in the AST) and checks the `head` filter is still there |
| A lookup error leaves the existing PR untouched | with `flow.fakes.FakeGitHub` raising on lookup: `find_or_create_pr` raises, `create_draft_pr` stays at 1 call, `prs`, `bodies` and `closed` are unchanged, and the next lookup finds the same PR. In the whole workflow (PR already open on the stable branch, lookup raising): `open_pr_step` makes its 3 attempts (`find_pr` called 3 times, 0 creates), the workflow ends `failed`, the PR is the same object and still a draft, `ready_pr` and `close_pr` are never called |

- The second call after the kill is the expected at-least-once case. It is asserted only here and at the other points before a step result is stored; at the points between steps the T19 run saw no repeated call at all.
- `find_or_create_pr` is the whole mechanism: one branch name per ticket (`flow.states.branch_name`), a find before the create, a draft on creation. `flow/workflow.py` was not changed by this task.
- On `failed` the workflow still posts the `failed` comment and label to the issue (`finish_step`); that is the issue, not the PR.

**Not shown.**

- There is no real GitHub write client in the repo: `GitHubClient` is a Protocol with two fakes. The find-then-create race against the real API (two workers creating at the same instant; GitHub answers 422 to the second) is modelled by the fake raising on a second create, not exercised. A real `find_pr` should use the `head=<owner>:<branch>&state=all` read that `github_read.py` already does; that code has only been run against recorded JSON.
- A real GitHub could answer a lookup right after a create with an empty list (eventual consistency); the ledger cannot. Then the restart's create would get a 422 and the step would retry, find the PR on the next attempt. Not run.
- Whether GitHub reads "Argus fix for owner/repo#12" in the PR title or body as a closing keyword was not checked; the text has "for" between the verb and the reference, which GitHub's keyword syntax does not accept as far as the docs say, but this is from memory.
- A hard kill of a local process on Windows, database up; not a Render restart.

**Fix.** Already in `flow.workflow.find_or_create_pr` (T03) and the T02 keys; nothing new in T21. The rule: find the PR by its head branch in any state before creating, one branch per ticket, create as draft, mark ready only in `finish_step` after an approve, and let a lookup error propagate instead of treating it as "no PR".

Run (needs the container and `ARGUS_FLOW_DATABASE_URL`, commands in [p6-t19.md](p6-t19.md)): `uv run --all-packages python -m pytest packages/flow/tests/test_pr_break_it.py -q`. Without the variable the three tests that need Postgres are skipped; the fake-lookup test and the code check still run. About a minute.
