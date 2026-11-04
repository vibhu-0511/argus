# P8-T24 Break it: the intake label added by a user without write access

Test: `packages/flow/tests/test_break_it_t24.py` (27 cases). It goes through the real T08 code: a signed delivery to `flow.webhook.create_app`, `flow.intake.Intake`, the guard audit log. GitHub is a mock transport. No network, no model, no real App.

## The induced failure

A person with read access (`mallory`), a triager, and someone who is not a collaborator add the `argus` label to issue `acme/shop#7`.

## Expected signal

| Signal | Where it is checked |
|---|---|
| The webhook still answers 202 (GitHub must not retry) | `test_a_read_only_user_adds_the_label_nothing_starts_and_the_ignore_is_logged` |
| No workflow starts: `enqueuer.workflows == set()` | same |
| Log line `intake_ignored {"actor":"mallory","label":"argus","reason":"actor has read access, write is needed","ticket":"acme/shop#7"}` | same |
| One `intake_ignored` record in the hash-chained audit log, and `guard.auditlog.verify` finds no bad line | same |
| One GET, to `/repos/acme/shop/collaborators/mallory/permission`, and no token in the log or the audit file | same |
| Four ignores (three people, one of them twice, so two lines for that one), then a user with write access starts exactly one workflow: an ignore does not poison the ticket | `test_the_ignore_does_not_block_a_real_start_and_every_ignore_is_logged` |
| An unsigned body gets 401 before intake and logs no ignore | `test_a_forged_delivery_without_the_signature_is_rejected_before_intake` |

## Observed output

```
$ uv run --all-packages python -m pytest packages/flow/tests/test_break_it_t24.py packages/flow/tests/test_intake.py -q
..............................................                           [100%]
46 passed in 2.77s
```

Proof that the test can fail. Mutation A: the write check in `Intake._may_start` replaced by `return True, role` (everyone passes):

```
INFO     flow.intake:intake.py:110 intake_started {"actor": "mallory", "ticket": "acme/shop#7"}
FAILED test_break_it_t24.py::test_a_read_only_user_adds_the_label_nothing_starts_and_the_ignore_is_logged
FAILED test_break_it_t24.py::test_the_ignore_does_not_block_a_real_start_and_every_ignore_is_logged
2 failed, 25 passed in 2.47s
```

The mutation was reverted; the 46 tests pass again.

## What the break-it found (three real defects in the T08 code), and the fix

| Defect | How it showed | Fix in `flow/intake.py` |
|---|---|---|
| The login goes into a URL path. `mallory/../maya` was normalised by the HTTP client to `/collaborators/maya/permission`, so the label of a read-only user was judged by a writer's permission. `maya?x=1` and `maya#x` cut the path the same way. A repo name such as `acme/shop/../x` did the same | probe in the session: all four logins gave `started` and the request path was another user's. This needs a body signed with the webhook secret, so it is defence in depth, not an open door | `LOGIN` and `REPO` patterns (what GitHub allows); anything else is ignored and logged and never reaches GitHub |
| `number: true` (a JSON bool is an `int` in Python) started a workflow for the ticket `acme/shop#True` | `test_..._broken_event...[number-is-a-bool]`: `enqueuer.calls == ['acme/shop#True']` | `type(number) is int and number > 0` |
| The intake label on a pull request, or on an event with no sender, no issue or a wrong-typed field, was dropped without a log line, and a string `sender` made `handle` raise `AttributeError` (the webhook's safety net caught it as `intake failed`) | `test_..._broken_event...[sender-is-a-string]` | `_field()` reads nested values without raising; every such case is an `intake_ignored` line and audit record with a plain reason. The login in that line is cut at 100 characters and JSON-escaped, so a hostile login stays one line |

Mutation B: `intake.py` put back to the T08 version, same test file:

```
24 failed, 3 passed in 2.52s
```

(the failures are the path-rewriting logins and repos, the broken events, the pull request and the hostile log line; the three passes are the read-only user, the ignore-does-not-block case and the forged delivery). The fixed file was restored; 46 pass.

## Not done, not verified

- Not run against a real App or a real label event; the permission answer is mocked in the shape the GitHub docs describe.
- A role that is a custom role built on `write` has a `role_name` that is not in the list, so it is refused (fail closed). Not exercised against GitHub.
- A bot login (`name[bot]`) is let through to the permission call; what GitHub answers for a bot is not known here.
