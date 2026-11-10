# P10 break-it index

Four failures were induced on purpose against the workbench. Each runs through the real routes with a test client. No model, no network, no real GitHub, no real browser inside the tests.

| Task | What was induced | Observed result | Note |
|---|---|---|---|
| P10-T10 | Script and markup (`<script>`, `onerror` images, shell syntax, `javascript:` links) put in ticket text, run ids, reviewer notes, judge and check text, patch names and `report.html`. | Everything comes back as plain text and nothing runs. Every response carries a CSP with scripts from `'self'` only, and the report is served sandboxed. The test found one real bug: a `<script>` path under `/static/` raised an untyped 500 on Windows, now a typed 404. Four mutated builds each failed the tests. Box not ticked: the PR body check was skipped before the PR route existed (see the note). | [p10-break-it-t10.md](p10-break-it-t10.md) |
| P10-T11 | Hostile files sent as the issue screenshot: HTML named `.png`, SVG, files over 5 MB, path-traversal names, a GIF named `.png`, cut-short signatures, empty files. | All refused with a typed error and nothing stored. Real images with hostile names are accepted and the name has no effect. 33 tests pass. Two mutated builds failed (name-only check: 18 failed; larger cap: 5 failed). Known limit: only the signature is checked, so a PNG header followed by junk is stored. | [p10-break-it-t11.md](p10-break-it-t11.md) |
| P10-T12 | Forged requests as another web page or a DNS-rebinding page would send them: no, empty or wrong token, a foreign or `null` Origin, a foreign Host, preflights. | Every mutating route refused them and the decision was not written. 104 tests pass. Four mutated builds failed (token check removed: 20 failed; Host check removed: 52; Origin check removed: 19; permissive CORS added: 8). The issue-create and start routes were not on that branch, so the test discovers every unsafe route and covers them once merged. | [p10-break-it-t12.md](p10-break-it-t12.md) |
| P10-T13 | Two to four approvals at the same moment: same key, different keys, approve racing the PR route, a widened race window, and Approve after a failed verifier. | Exactly one decision and one mock PR in every round. A second key gets a typed `already_decided`, the same key gets a replay, and a failed verifier gets `verifier_failed` with no state change. 14 tests pass. Removing the lock, and then the lock and the atomic create, failed the tests. Limit: locks are per process, so two server processes are not covered. | [p10-break-it-t13.md](p10-break-it-t13.md) |

Limits that apply to all four:

- The PR goes to an in-memory mock GitHub. No real issue, branch or PR was created.
- The runs are scripted or replayed. No model was called.
- Each note lists the mutations that were made to prove the test can fail.
- The counts above are from each task branch. The merged-package result is in the integration report.
