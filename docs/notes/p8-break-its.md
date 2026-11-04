# P8 break-it index

Four failures were induced on purpose. Each was run against mocks or local bare repos, never against the real GitHub App or a real model.

| Task | What was induced | Observed result | Note |
|---|---|---|---|
| P8-T21 | One tenant (`acme`) used up its own budget, and then its provider share, while a second tenant (`globex`) ran at the same time. | `acme` stopped with a typed `TenantQuotaExceeded` before the model was called, and the refused call was not counted. `globex` finished with `submit` and had no refusals. Switching the tenant check off made all 3 tests fail. | [p8-break-it-t21.md](p8-break-it-t21.md) |
| P8-T22 | An issue arrived on a repo whose `.argus.yml` has no `test` command (and 7 other bad-file shapes). | One comment with the typed config error, no crash, no guessed command, nothing else started. A second label event with the same problem added no second comment. | [p8-break-it-t22.md](p8-break-it-t22.md) |
| P8-T23 | A backport onto a branch where the same line had changed (edit/edit, modify/delete, add/add). | The bot commented the conflicted files, aborted the cherry-pick and moved no ref. The break found that `check_args` let through git options it should not, and this was tightened (SAFE_FLAGS). 37 tests pass. | [p8-break-it-t23.md](p8-break-it-t23.md) |
| P8-T24 | The intake label added by a user with read access, a triager and a non-collaborator. | The webhook answered 202, no workflow started, and one `intake_ignored` line went to the hash-chained audit log. A later add by a user with write access started exactly one workflow. 46 tests pass with the T08 tests. | [p8-break-it-t24.md](p8-break-it-t24.md) |

Limits that apply to all four:

- GitHub was a mock transport. No real issue, label event, App installation or PR was used.
- The model was scripted where one was needed.
- Each note lists the mutations that were made to prove the test can fail.
