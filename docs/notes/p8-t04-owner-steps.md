# P8-T04 reusable workflow: what was shown, what was not, owner steps

Date: 2026-11-03. **Not run on GitHub. The box stays unticked.** Reason: the criterion "a tenant workflow of five lines calls it ... and runs repro, fix and verify" needs a real Actions run, and none was possible from here (no push, no tenant repo, `P6-T04` waived, no real App).

## Shown locally

| Criterion | How it was shown |
|---|---|
| A five-line tenant workflow calls it with `workflow_call` | `packages/app/docs/tenant-workflow.yml` (5 lines). `test_the_tenant_workflow_is_five_lines_and_calls_the_reusable_workflow` parses it and checks that `uses:` names `.github/workflows/argus-reusable.yml` in this repo |
| The agent step's environment has no `GITHUB_TOKEN` | `test_the_agent_step_environment_has_no_github_token` parses the YAML and checks workflow, job and step `env` of each of the 3 steps that run `flow.agent_job`. A second test checks both `actions/checkout` steps set `persist-credentials: false` (else the clone keeps the token in `.git/config`). Mutation check: adding `GITHUB_TOKEN` to the verify step, or removing `persist-credentials: false`, makes the tests fail (run once, then reverted) |
| Permissions are minimal | Workflow `permissions: {contents: read}`; the test also checks no job widens it and that nothing in the file pushes |
| No secret is passed except through the tenant's own secrets | Only `secrets.ARGUS_MODEL_API_KEY` appears; the caller passes it by name; no `secrets: inherit`; only the fix step holds it |
| ADR-026 names the principal that pushes | Amendment dated 2026-11-03: the App installation token pushes, the tenant workflow token never does |
| Lint | YAML parses with PyYAML (all tests). **`actionlint` was not run**: it is not installed here and installing it needs a download that was not asked for |

## Not shown

- That GitHub accepts the file as a reusable workflow (`workflow_call` plus `pull_request` in one file, job-level `if` on the caller's event, `run-name` with an expression).
- That the workflow runs repro, fix and verify. The T04 commit ran `flow.agent_job`, whose default steps refuse a live issue ("not a seeded task"). P8-T06 swapped the entry point for `argus_app.runner`, which takes the target from `.argus.yml`; its steps ran locally on a fixture repo with a fake fix agent (`packages/app/tests/test_runner.py`) but never on a runner, and the fix agent's real model wiring never ran at all.
- That the called workflow's token really is read-only when the tenant's default is write (the docs say a called workflow can only lower permissions; not seen).
- Whether the artifact layout (`argus-out/<step>/result.json`, one folder per step) is what P8-T09 will read. `flow.actions.parse_artifact` expects the three files at the artifact root; T09 must read the verify folder or this layout must change.

## Owner steps (real run)

1. Push the branch and open a pull request that includes `.github/workflows/argus-reusable.yml`. The `pull_request` trigger starts the workflow (paths limited to that file, as in P7). On that event the repro and fix steps are skipped and verify runs with no model, no ticket and no secret. Read the job log: `gh run view <id> --log`. Expected: the two checkouts, `uv sync --package argus-app`, then verify on the fixture repo (`packages/app/tests/fixtures/second-repo`): the app starts, two routes answer and the test command exits 0, so the job is green. Locally the same check passes (`test_verify_with_no_patch_checks_the_checkout_as_it_is`). A red job here means the setup on GitHub differs from this machine; read the log.
2. Make a throwaway tenant repo (public, no private code). Add the example from `packages/app/docs/tenant-workflow.yml` as `.github/workflows/argus.yml`, change `@main` to the branch or commit that holds the workflow, and add the repository secret `ARGUS_MODEL_API_KEY` (an own key; Groq free tier).
3. Create the label `argus`, open an issue, label it. The caller run should start; check in its log that no step prints a token and that the called workflow's token shows `Contents: read` in the "Set up job" block.
4. Tick the box only when step 3 shows repro, fix and verify each ran on the tenant's repo.
