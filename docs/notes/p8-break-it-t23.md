# P8-T23 Break it: force a cherry-pick conflict in a backport

Test: `packages/app/tests/test_break_it_t23.py` (37 cases). Real `git` on local bare repositories (helpers of `test_backport.py`), the stateful fake GitHub (`packages/flow/tests/github_api_fake.py`), a spy runner that records every git argument list. No network, no model, no real App or installation token. Run time is about 3 and a half minutes, because every case clones and picks with real git on Windows.

## The induced failure

`release` gets a commit that changes line two of `a.txt`; `main` gets the fix that changes the same line. The fix PR is merged and the bot is asked to backport it to `release`. The same is done for a modify/delete conflict and an add/add conflict on two files.

## Every clause of the T23 row is a test

| Clause | Test | Signal that must hold |
|---|---|---|
| The bot comments the conflict | `test_a_conflict_is_commented_and_not_one_ref_moves` (edit/edit, modify/delete, add/add) | outcome `conflict`; exactly one comment naming the target, the commit and every conflicted file |
| and leaves branches untouched | same | every ref of the origin equal before and after; no `argus/backport-...` ref; no push; no PR; `cherry-pick --abort` was the last pick call; the temporary clone is gone; every process started was `git` |
| A fix already on the target is not a conflict | `test_a_fix_that_is_already_on_the_target_changes_nothing` | outcome `failed` ("without a conflict"), refs equal, no comment, no push |
| Fails on a force-push of the bot branch | `test_a_bot_branch_that_differs_is_never_overwritten_and_no_pr_is_made_from_it` (a person pushed to the branch; the target moved after a half-done run) | outcome `stale-branch`, twice; no push call; the ref of the bot branch is the same commit before and after; no PR |
| Fails on a failed push that still retries PR creation | `test_a_push_the_remote_rejects_creates_no_pr_and_is_not_retried`, `test_after_rejected_pushes_the_next_run_starts_clean_...` | a `pre-receive` hook on the origin makes the push really fail; outcome `push-failed`, one push call, no PR request at all, no comment; two more failing runs do the same; after the hook is removed one PR is opened from the new branch with one push |
| Fails on PR creation from a stale branch | the stale-branch test above | `api.pulls == []` and no `POST /pulls` after the stale branch was found |
| Refuses a tenant conflict command | `test_a_tenant_conflict_command_is_refused_and_no_process_starts` (7 field names, 3 value shapes each), `test_a_command_written_into_the_tenants_repo_is_never_run_on_a_conflict` | `ConflictCommandRefused` with no process started; an `on_conflict` command in the tenant's own `.argus.yml` and a `merge=` driver in `.gitattributes` on the target branch: the marker file is never created, only `git` ran |
| Refuses a checkout of the PR head under the installation token | `test_a_pr_head_is_never_checked_out_or_picked_even_with_a_token` (the event names the head as merge commit; the event head is stale), `test_git_options_in_any_spelling_...` | `Refused`; no checkout, cherry-pick, push or fetch call carries the head sha or the head ref; refs equal (including `refs/pull/12/head`); the other side: a merged commit is picked and the only checkout is `-b <backport branch>` |
| A second run finds the existing PR or no-ops | `test_a_second_run_after_each_outcome_...`, `test_a_conflict_run_three_times_...`, `test_a_pr_that_failed_after_the_push_...`, `test_two_runs_at_the_same_time_...` | opened: `exists`, no git call, one lookup request and no write; a declined (closed) backport is not opened again; conflict three times: one comment, no push; PR failed after the push: next run opens it with no second push; two threads at once: one PR, `release` untouched |

## Observed output

```
$ uv run --all-packages python -m pytest packages/app/tests/test_break_it_t23.py -q
37 passed in 196.59s (0:03:16)
$ uv run --all-packages python -m pytest packages/app/tests/test_backport.py packages/app/tests/test_cli.py packages/app/tests/test_config.py -q
89 passed in 177.90s (0:02:57)
```

## Mutation outputs: the tests fail on a bad bot

Each mutant is a copy of `backport.py` edited in the way the clause forbids, run against the tests of that clause (`-k`), then reverted (`git diff` of the file shows only the fix described below). The output lines are the first assertion that failed.

| Mutant | Edit | Result (tests of the clause) | Why it fails |
|---|---|---|---|
| M1 force-push of the bot branch | guard removed, stale check removed, `git push --force origin <branch>` | 2 failed, 35 deselected | `AssertionError` in the spy: `--force` is in the argument list |
| M1c force-push with a spelling the spy does not know | same, but `-fu` | 2 failed, 35 deselected | `assert 'opened' == 'stale-branch'`: the branch of a person was overwritten and a PR opened |
| M1b the same `-fu`, guard kept | stale check removed, `push -fu` | 2 failed, 35 deselected | `Refused: git argument '-fu' is refused` (the guard in `check_args`, see the finding below) |
| M2 PR creation goes on after a failed push | the `push-failed` return replaced by `pass` | 2 failed, 35 deselected | `assert 'opened' == 'push-failed'` |
| M3 PR creation from a stale branch | the `stale-branch` return replaced by `pass` | 2 failed, 35 deselected | `assert 'opened' == 'stale-branch'` |
| M4 the push is retried once | second `git push` after a failure | 1 failed, 36 deselected | `assert 2 == 1` (push calls) |
| M5 PR head allowed | ancestor check removed, keep-away list emptied | 2 failed, 35 deselected | `DID NOT RAISE Refused` |
| M6 tenant conflict command accepted | `commands` check and the exact-keys check removed | 7 failed, 30 deselected | `DID NOT RAISE ConflictCommandRefused` (one per field name) |
| M7 the bot runs the tenant's `on_conflict` | after the abort: read `.argus.yml`, `subprocess.run(cmd, shell=True)` | 1 failed, 36 deselected | the marker file exists |
| M8 second run does not look for the existing PR | `if existing is not None` replaced by `if False` | 1 failed, 36 deselected | `assert 'opened' == 'exists'` |
| M9 conflict comment written on every run | random suffix in the comment key | 1 failed, 36 deselected | `assert 3 == 1` (comments) |
| M10 a conflict falls through to push and PR | the `conflict` return replaced by `pass` | 3 failed, 34 deselected | `assert 'opened' == 'conflict'` |

All mutants were reverted (`restored` printed by the runner; `git status` shows `backport.py` changed only by the fix below). The mutation script is not kept in the repo: it is a loop that replaces one line of `backport.py`, runs the `-k` selection and puts the file back.

## What the break-it found, and the fix

The T10 guard `check_args` refused a fixed list of spellings (`--force`, `-f`, `--delete`, ...). Git also accepts `-fu` (short flags together), an unambiguous prefix such as `--del`, `--mirro`, `--force-with-lease=x:y`, a push refspec `refs/heads/x:refs/heads/release` that writes another branch, and options that run a command (`--upload-pack=...`, `--config core.sshCommand=...`). 13 of 14 such argument lists passed `check_args` (the one refused was `checkout -f`). The bot itself never builds them; the guard exists for the day someone edits the bot.

Fix in `argus_app/backport.py` (`SAFE_FLAGS`, one condition in `check_args`): an option that is not one the bot passes today is refused whatever it is called, and a push argument with a `:` is refused. Before the fix: `13 failed, 1 passed`; after: `14 passed` (`-k git_options_in_any`). The 54 tests of `test_backport.py` still pass.

## Not done, not verified

- Everything ran on local bare repositories and a fake GitHub. A real HTTPS clone and push with an installation token, GitHub's own refusal of a force push (branch protection), and the real `refs/pull/<n>/head` of a fork were not tried. The `refs/pull/12/head` here is a ref made by hand in the bare origin.
- The concurrency test accepts any of `opened`, `exists`, `push-failed`, `stale-branch` for a loser; it checks only the invariants (one PR, `release` untouched, the winner opened). It is not a proof against every interleaving.
- `check_args` does not know which branch a push may write; a push of `release` itself would pass it. Only the code path in `backport_merged_pr` pushes the bot branch (ceiling: pass the allowed branch into `check_args` if the bot gets a second push).
- A hook the tenant's repo ships is not cloned and `core.hooksPath` points at an empty folder; a merge driver named in `.gitattributes` has no definition in the bot's empty config. Both are shown not to run in the marker test, not proven for every git version.
