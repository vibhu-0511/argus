# P8-T22 break it: install on a repo with no test command configured

Code: `packages/app/src/argus_app/config_intake.py`. Test: `packages/app/tests/test_config_intake.py` (18 tests). The GitHub side is `httpx.MockTransport` behind the real `flow.github_write.HttpGitHubClient`. No network, no model, no real GitHub App.

**Induced failure.** An issue arrives on a repo whose `.argus.yml` has no `test` field. The same check also ran on: no file, an empty file, broken YAML, a file that is a list, `test` that is blank or a list, an unknown field, and a budget of 0.

**Expected signal.** One comment on the issue with the typed config error. No crash. No guessed command (no `npm test`, no `pytest`). Nothing else started: no label, branch, PR or push.

**Observed.** The comment for a file with `start`, `routes` and `budget` but no `test` (from `config_error_comment`, run on 2026-11-04):

````text
Argus did not start on this issue: `.argus.yml` is not usable.

```text
.argus.yml: missing required field 'test' (the test command)
```

Nothing was run, and Argus did not guess a missing value. Fix the file in the repository root and label the issue again. Fields and an example: docs/onboarding.md in vibhu-0511/argus.
````

| Check | Result |
|---|---|
| Message is the typed error from P8-T05 (`MissingFieldError`) | the line is exactly `.argus.yml: missing required field 'test' (the test command)` |
| Requests made to GitHub | only `GET .../issues/7/comments` and `POST .../issues/7/comments` (the mock answers any other path with 500, none was hit) |
| Value of the tenant's `start` or any fallback command in the comment | absent |
| Second label event, same problem | one comment in total (the hidden key marker is found first) |
| Different problem on the next event | a second comment |
| 8 kinds of bad file | each returns `None` and posts one comment; none raises |
| Valid file | the `TenantConfig` is returned, no request is made |
| More than 10 problems | first 10 shown, then "and 30 more" |
| Tenant text in a route or field name (backticks, `@everyone`, a fake token) | stays in the code block, backticks become `'`, the token becomes `***` |
| Post fails (500) | the error reaches the caller (intake decides on a retry); the token is not in it |

Mutation check: with `redact` removed from the comment text, the hostile-text test fails (run once, then reverted).

**Fix.** Validate `.argus.yml` at intake (`check_config`) and say what is missing. The check is the first step after an issue is labelled: a bad config stops here, so the runner (P8-T06) never starts on it. The runner keeps its own failure path for a config that goes bad later.

**Not shown.**

- A real issue on a real GitHub repo with the real App. The comment was only posted to a mock.
- Reading `.argus.yml` from GitHub. `check_config` takes a `read_text` callable; wiring it to the contents API is part of intake (P8-T08).
- That a comment from the App's installation token shows up as the App on GitHub (needs the owner steps in `docs/notes/p8-t03-owner-steps.md`).
