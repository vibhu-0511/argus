# app

P8: Argus as a GitHub App. A tenant adds a five-line workflow to their own repo; the agent job runs there, on their minutes and with their model key. Argus servers only take the webhook, mint a one-repo token and open the pull request.

**Status, in one paragraph.** Everything below was built and run **locally** on one Windows 11 machine. **Nothing has run on GitHub** (the branch was not pushed). **The GitHub App is not registered**, so no tenant has installed it, no reusable workflow has run in a tenant repo, no issue has become a real pull request, and no demo video exists. The fix agent has never run against a model for P8, and the single agent vs planner ablation ran **0 of 20 tasks** for both variants (no local model on this machine). The code that opens a PR, checks `.argus.yml` at intake and runs the backport bot is built and tested but **no running service calls it yet**. Read the "State" column; it is the honest one.

Run everything from the repo root. `argus-app` is the console script; on a machine that blocks it (the owner's Windows one does, error 4551), use `uv run --all-packages python -c "from argus_app.cli import main; import sys; sys.exit(main([...]))"` or `python -m argus_app.runner`, which is the same code.

## App setup

The App is described by a manifest, `src/argus_app/manifest.json`. Its permission list is the P7 least-privilege list (Actions write, Contents write, Issues write, Pull requests write, Metadata read) and a test fails if it differs from `flow.app_token.MINIMUM` or from the table in ADR-026. No URL is committed; three environment variables fill the placeholders:

```bash
export ARGUS_FLOW_SERVICE_URL=https://<your-service>.onrender.com   # webhook goes to <this>/webhook
export ARGUS_APP_HOMEPAGE_URL=https://github.com/<owner>/<repo>
export ARGUS_APP_REDIRECT_URL=http://localhost:8765/
uv run --all-packages python -c "from argus_app.cli import main; import sys; sys.exit(main(['manifest']))"           # print the filled JSON
uv run --all-packages python -c "from argus_app.cli import main; import sys; sys.exit(main(['manifest', '--form']))" > form.html   # local registration page
```

Registering the App, installing it, and putting its id, key and webhook secret into Render are **owner-only steps**. None has been done:

| Step | Owner steps |
|---|---|
| Register the App from the manifest, store the secrets in Render, delete the old P7 test App | [`p8-t02-owner-steps.md`](../../docs/notes/p8-t02-owner-steps.md) |
| Install it on a test repo, mint a token for that repo, show a second repo fails | [`p8-t03-owner-steps.md`](../../docs/notes/p8-t03-owner-steps.md) |
| Run the reusable workflow once on GitHub (pull-request trigger, then a tenant repo) | [`p8-t04-owner-steps.md`](../../docs/notes/p8-t04-owner-steps.md) |
| Run the tenant runner on the real dcortex repo | [`p8-t06-owner-steps.md`](../../docs/notes/p8-t06-owner-steps.md) |
| Publish the demo repo, install, set the model key, run one real issue | [`p8-t16-owner-steps.md`](../../docs/notes/p8-t16-owner-steps.md) |
| Record the demo video (success, verifier rejection, quota refusal) | [`p8-t18-demo-script.md`](../../docs/notes/p8-t18-demo-script.md) |
| Fill the landing README blanks and time the install | [`p8-t17.md`](../../docs/notes/p8-t17.md) |
| Push, first CI run of `app.yml` and its `actionlint` step | [`p8-t20-owner-steps.md`](../../docs/notes/p8-t20-owner-steps.md) |
| Pick a licence, decide what of `docs/` ships | [`release-checklist.md`](../../docs/release-checklist.md) |
| Install Ollama and `gemma4:e4b`, run the 20-task ablation | [`p8-t12.md`](../../docs/notes/p8-t12.md) |

## Workflow usage (for a tenant)

Full text: [`docs/onboarding.md`](../../docs/onboarding.md) (under one page). Three things in the tenant's repo:

1. **The five-line workflow**, `.github/workflows/argus.yml` ([`docs/tenant-workflow.yml`](docs/tenant-workflow.yml)):

   ```yaml
   on: {issues: {types: [labeled]}}
   jobs:
     argus:
       uses: vibhu-0511/argus/.github/workflows/argus-reusable.yml@main
       secrets: {ARGUS_MODEL_API_KEY: "${{ secrets.ARGUS_MODEL_API_KEY }}"}
   ```

   `@main` only resolves once the reusable workflow is on `main` of that repo; until then name the branch or commit that has it.
2. **`.argus.yml` at the repo root** ([`docs/argus.example.yml`](docs/argus.example.yml)). All four fields are required; unknown fields and wrong types are refused.

   | Field | Meaning |
   |---|---|
   | `start` | command that starts the app |
   | `test` | command that runs the tests (a failing test is the evidence of the bug) |
   | `routes` | paths that must answer (status below 400) before tests run |
   | `budget` | `max_tokens` and `max_steps` for one issue |
   | `base_url` | optional, localhost only, default `http://127.0.0.1:3000` |

   A missing field gives a typed error, for example `.argus.yml: missing required field 'test' (the test command)`, and the run ends there. There is no guessed command.
3. **The secret** `ARGUS_MODEL_API_KEY` in the repo's own secrets, and the label `argus`. Adding the label (as someone with write access) starts one run for that issue.

A run is three steps in the tenant's repo: **repro** (start, routes, tests on the untouched tree), **fix** (the P3 fix loop in the Docker sandbox; the only step that holds the model key), **verify** (patch applied to a fresh tree, same start, routes and tests). The agent steps have no `GITHUB_TOKEN`; the App installation token is the principal that pushes and opens the draft PR ([ADR-026](../../docs/adr/0026-secrets-handling-and-token-scopes.md) amendment, [ADR-027](../../docs/adr/0027-tenancy-via-reusable-workflow.md)).

**Free-tier caveat.** Prompts sent to free-tier model providers may be used for training. Use Argus on synthetic or public code only. The demo target is a made-up shop in [`examples/demo-repo`](examples/demo-repo).

## Commands

| Command | What it does |
|---|---|
| `argus-app manifest [--form]` | Print the filled App manifest, or the local registration page. Names any missing environment variable |
| `python -m argus_app.runner plan <repo folder or .argus.yml>` | Print what a run would start and check; starts nothing. `plan config/dcortex.argus.yml` shows the dcortex repo as a tenant |
| `python -m argus_app.runner` | The entry point of `argus-reusable.yml`. Reads `ARGUS_STEP` (`repro`, `fix`, `verify`), `ARGUS_TARGET_REPO`, `ARGUS_OUT`, `ARGUS_TICKET_ID`, `ARGUS_RUN_KEY`; writes `result.json` last |
| `python packages/app/examples/demo-script/rehearse.py good` or `bad` | Repro and verify on the demo shop with a hand-fed patch (exit 0 and exit 1). A rehearsal, not a run |
| `python packages/app/examples/demo-script/quota_refusal.py` | A quota refusal before a fake model call is sent |
| `python -m eval.ablation tasks --count 20`, `python -m eval run ...`, `python -m eval.ablation table A.json B.json` | The T12 ablation. Exact commands and order: [`p8-t12.md`](../../docs/notes/p8-t12.md). Not run |
| `python .github/workflows/check_no_secrets.py` | Secret scan; the release checklist item |

Tests, one package at a time (never one pytest run across packages):

```bash
uv sync --all-packages --locked
uv run --all-packages python -m pytest packages/app/tests -q
uv run --all-packages python -m pytest packages/argus-core/tests/test_ledger.py -q
uv run --all-packages python -m pytest packages/fix-loop/tests/test_planner.py -q
uv run --all-packages python -m pytest packages/eval/tests/test_ablation_run.py -q
uv run --all-packages python -m pytest packages/flow/tests -q   # the installation and tenant-ledger tests need ARGUS_FLOW_DATABASE_URL (Postgres) and skip without it
```

No test calls a model. `test_break_it_t23.py` takes about three and a half minutes because every case clones and picks with real `git`.

## The controls

State words: **tested locally** = there is a test from a run on this machine. **never run on GitHub** = the code or workflow is written and nothing on GitHub has run it. **not run** = it was not run at all, anywhere.

| Control | What it does | File or command | State |
|---|---|---|---|
| App manifest | Permission list equals ADR-026; webhook at the flow service | `src/argus_app/manifest.json`, `manifest.py`; `tests/test_manifest.py` | Tested locally. **The App was never registered from it** |
| Installation store and token minting | Records installs; mints a one-hour token for exactly one installed repo; a repo not installed is refused before any HTTP call | `packages/flow/src/flow/installations.py`; `packages/flow/tests/test_installations.py` | Tested locally against a **mock** GitHub. Never seen against the real App. Nothing in the running service calls `mint_for_repo` yet except intake |
| Reusable workflow | Runs repro, fix, verify in the tenant repo; read-only job token; key only in the fix step | `.github/workflows/argus-reusable.yml`; `tests/test_reusable_workflow.py` | Parsed and checked locally. **Never run on GitHub; `actionlint` not run** |
| No `GITHUB_TOKEN` in the agent step | Test reads the YAML for the token in workflow, job and step `env`, and for `persist-credentials: false` | `tests/test_reusable_workflow.py` | Tested locally (fails when the token is added). Not seen on a runner |
| Tenant config | Strict `.argus.yml` with typed errors | `src/argus_app/config.py`; `tests/test_config.py` | Tested locally |
| Target-agnostic runner | Takes start, test, routes and budget from `.argus.yml`; no repo command in its source | `src/argus_app/runner.py`; `tests/test_runner.py` | Tested locally on a second small repo (repro, fix with a **fake** agent, verify). dcortex only **planned**. The real fix agent has **never run**, on a runner or against a model |
| Per-tenant quota budgets | Ledger keys include tenant id; a tenant over its own budget or share is refused with a typed error while another goes on | `argus_core.ledger` (`TenantBudget`, `for_tenant`); ADR-028 | Tested locally. Budgets are an argument: **nothing in the running service builds them** |
| Ticket intake | Label starts exactly one workflow; label from a user without write access is ignored and logged | `packages/flow/src/flow/intake.py`; `test_intake.py` | Tested locally on mocks. Never run on a real label event |
| Config check at intake | Posts one typed config error as a comment and starts nothing | `src/argus_app/config_intake.py`; `tests/test_config_intake.py` | Tested locally on a mock transport. **No running code calls `check_config`** |
| PR creation with evidence | One draft PR per ticket with verdict, judge label, trajectory link and screenshots; title and body as JSON fields; empty patch gives no PR; re-run updates the same PR | `src/argus_app/pr.py`; `tests/test_pr.py` | Tested locally against a fake GitHub. **No running code calls `open_or_update_pr`**, so a finished run does not become a PR yet |
| Backport bot | Cherry-picks a merged fix onto a configured branch; a conflict becomes one comment | `src/argus_app/backport.py`; `tests/test_backport.py` | Tested locally with real `git` on local bare repositories and a fake GitHub. Never run against GitHub; not called from the webhook |
| Planner and subagents | One planner call, 1 to 5 sub-tasks, each run by the single-agent loop with its own cap; tokens counted across all agents | `packages/fix-loop/src/fix_loop/planner.py` | Tested locally with stub models. **No real model run** |
| Ablation, single vs planner (T12) | 20 tasks, same model, Wilson 95% intervals | `packages/eval/src/eval/ablation.py`, `packages/eval/policies/p8-t12-*.json` | Harness built and tested with stubs. **Not run: 0 of 20 tasks for A and B** |
| CI job | App tests, token and label tests, budget tests, lint of the reusable workflow, no model, read-only | `.github/workflows/app.yml`; `tests/test_ci_workflow.py` | Same steps passed locally. **Never run on GitHub**; its `actionlint` container step has not been seen to run |
| Break it: budget (T21) | Tenant at its limit refused, a second tenant finishes | `tests/test_break_tenant_quota.py`; [`p8-break-it-t21.md`](../../docs/notes/p8-break-it-t21.md) | Tested locally with a scripted fake model |
| Break it: no test command (T22) | Typed comment, no crash, no guess | `tests/test_config_intake.py`; [`p8-break-it-t22.md`](../../docs/notes/p8-break-it-t22.md) | Tested locally on a mock transport |
| Break it: cherry-pick conflict (T23) | Comment only, no force-push, no PR from a stale branch | `tests/test_break_it_t23.py`; [`p8-break-it-t23.md`](../../docs/notes/p8-break-it-t23.md) | Tested locally with real `git`; clauses also shown failing against a mutated bot |
| Break it: label without write access (T24) | Ignored and logged | `packages/flow/tests/test_break_it_t24.py`; [`p8-break-it-t24.md`](../../docs/notes/p8-break-it-t24.md) | Tested locally; found and fixed three defects in intake |
| ADR-027, 028, 029 | Tenancy via a reusable workflow; per-tenant budgets; single agent vs planner | `docs/adr/0027` to `0029` | Written by Claude, **proposed**, the owner decides. ADR-029 draws no decision: the T12 rows are dashes |
| Landing README | What it does, quickstart, limits, security model, free-tier caveat | [`docs/landing/README.md`](../../docs/landing/README.md) | Written. 6 places marked OWNER TO FILL (App page, issue, PR, trace, video, licence). "Under 10 minutes" is untested |
| Release checklist | Licence, secret scan, private data, quota limits | [`docs/release-checklist.md`](../../docs/release-checklist.md) | 2 of 4 done (secret scan, quota limits). Licence and the `docs/` private-data sweep are open, the owner decides |
| Demo repo and script | A made-up shop with one seeded bug; storyboard and local rehearsal | `examples/demo-repo`, `examples/demo-script` | Rehearsed locally with hand-written patches. **No video recorded; no real run to show** |
| One real issue end to end (T16) | A labelled issue on a public repo becomes a PR | [`p8-t16-owner-steps.md`](../../docs/notes/p8-t16-owner-steps.md) | **Not run** |

## What did not run

- Registering the App, installing it, and every call to the real GitHub API from P8 code.
- The reusable workflow on a GitHub runner, and `actionlint` on it.
- The default fix agent (`argus_app.runner._fix_agent`) against any model; a run on the real dcortex repo.
- The 20-task ablation. No Ollama server, binary or `gemma4:e4b` on this machine, and no other model is allowed for it.
- The demo video and the first real issue, PR and trace links.
- Opening a PR and making a backport from a webhook: the functions exist, no running code calls them.
- Licence, and the sweep of `docs/` for the private platform repo name.

## Where things are

| Path | What |
|---|---|
| `src/argus_app/` | `manifest`, `config`, `config_intake`, `runner`, `pr`, `backport`, `cli` |
| `docs/` | `tenant-workflow.yml`, `argus.example.yml` |
| `examples/` | `demo-repo` (the tenant to publish), `demo-script` (rehearsal files) |
| `tests/` | tests; `tests/fixtures/second-repo` is the second small repo with a different layout |
| `.github/workflows/argus-reusable.yml`, `app.yml` | the reusable workflow and the CI job |
| `docs/architecture/p8.md`, `docs/notes/p8-*.md`, `docs/adr/0027` to `0029` | one section per task, the owner steps, the ADRs |
| `phases/P08-argus-app.md` | tasks, Ablation table and the phase report |
