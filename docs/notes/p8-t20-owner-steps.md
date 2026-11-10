# P8-T20 CI job: what was shown, what was not, owner steps

Date: 2026-11-04. **Not run on GitHub. The box stays unticked.** Reason: the criterion "Workflow green" needs a real Actions run, and none was possible from here (no push).

## Shown locally (every step of the job, with a throwaway Postgres 16 container on port 55446, since removed)

| Job step | Command | Result |
|---|---|---|
| Tests of `app.yml` and the structural lint | `uv run --all-packages python -m pytest packages/app/tests/test_ci_workflow.py -q` | 13 passed (1 skipped when run from PowerShell, where `sh` is not on the path; it passes from Git Bash) |
| Token minting and label permission | `pytest packages/flow/tests -q -k "test_app_token or test_installations or test_intake"` | 61 passed, 445 deselected. `test_intake.py` is not on this branch (it is on `p8/intake`), so those tests are not in the 61 |
| Budget assertion (T07 is kept) | `pytest packages/argus-core/tests/test_ledger.py packages/flow/tests/test_tenant_ledger.py -q` | 18 passed |
| App tests | `pytest packages/app/tests -q` | 85 passed without `test_ci_workflow.py`; 97 passed, 1 skipped with it and with Postgres set |

Mutation checks on `app.yml` (run once, then reverted): `contents: write` fails the read-only test; `pull_request` renamed to `pull_request_target` and the `--locked` flag removed fail the trigger test and the install-order test.

The repo secret scan (`.github/workflows/check_no_secrets.py`) finds nothing in `app.yml`. It flagged this file and `packages/app/tests/test_manifest.py` (a made-up URL with a user and password in it, from P8-T02); both are fixed on `p8/ci-fix` and the scan prints `clean`.

One test, `test_a_start_command_that_exits_is_a_failed_baseline_with_its_output`, failed once in the first full run of `packages/app/tests` and passed in the three runs after. The runner's fixture app uses a fixed local port, and other sessions were running the same suite at the same time; a server from another run answering on that port would make the baseline succeed. That was not proven. If the job ever shows it on GitHub, read the log before trusting either result.

## Lint: which one

- In the job: `rhysd/actionlint:1.7.7` as a container (pinned by tag) on `argus-reusable.yml` and `app.yml`. **Not run here**: it needs an image that is not on this machine, and pulling it was not asked for. If it flags something in `argus-reusable.yml`, fix the workflow; that is the point of the step.
- Also, and run here: `lint()` in `test_ci_workflow.py` (PyYAML): a trigger and top-level `permissions`, `runs-on` on each job, `needs` that name a job, one of `uses`/`run` per step, actions with a version, balanced `${{ }}`. A broken fixture proves it finds each problem.

## Not shown

- That the job is green on GitHub: the `actionlint` step, the Postgres service on the runner, `uv sync --all-packages --locked` there, and the run time.
- The criteria that name other tasks: the PR built through the API with a `$(...)` title (P8-T09, `test_pr.py` is on `p8/intake`) and the ADR-027 sentence on the backport head (P8-T13). The job runs the first as soon as the file is on the branch; the second is a document and is checked at T13.

## Owner steps (real run)

1. Push the branch and open a pull request that includes `.github/workflows/app.yml`. Its own file is in the `pull_request` paths, so the job starts (as in `docs/notes/p7-github-tier-runs.md`). No extra trigger was added.
2. `gh run list --workflow app.yml`, then `gh run view <id> --log`. Expected: the lint step prints nothing and exits 0, the three pytest steps pass.
3. If the lint step is red, read what `actionlint` says about `argus-reusable.yml`; it has not been run on it before.
4. Tick the box only when the run is green and the merged tree holds `test_intake.py` and `test_pr.py` (so the label and PR criteria are in the run).
