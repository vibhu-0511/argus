<!--
OWNER NOTE (delete this block when you copy the file).
This is the landing README for the public repo (P8-T17). Copy it to the repo root as README.md.
Links are relative to the repo root (docs/..., packages/...), so copy those folders too, or change the links.
Every place marked OWNER TO FILL is empty on purpose: no issue, PR, trace, video, App page or licence exists yet.
Do not fill one with a guess. Details: docs/notes/p8-t17.md.
-->

# Argus

Argus fixes UI bugs. You label a GitHub issue `argus`. It reproduces the bug, writes a fix, checks the fix, and opens a **draft pull request** with the evidence. A person reads it and decides.

> **Status, read this first.** Argus is built and tested on one machine. It has **not** yet run end to end on GitHub: the GitHub App is registered (id 5699242) but installed on no repository, the reusable workflow has never run in a tenant repo, and no real issue has become a real pull request. The code that opens the PR after a finished run is built and tested but is not called by the running service yet. The "one real run" table below is empty for that reason. Nobody has timed the install, so "under 10 minutes" is a goal, not a measurement.

## What it does

1. **Repro.** Starts your app with your `start` command, waits for your `routes` to answer, runs your `test` command. A failing test is the evidence of the bug.
2. **Fix.** A model-driven loop reads the issue and your code, edits files, and runs commands inside a Docker sandbox with no network. It stops at the step and token budget you set.
3. **Verify.** Applies the patch to a fresh copy and runs the same start, routes and tests. It passes only if they pass.
4. **Pull request.** The Argus GitHub App opens a draft PR with the verdict and links. If your `.argus.yml` is missing or wrong, it comments the exact problem instead of guessing a command.

The work runs in **your** repo, on **your** GitHub Actions minutes, with **your** model key. Argus servers only receive the webhook, mint a short-lived token for your one repo, and open the branch and the PR.

| Part | Where |
|---|---|
| Reusable workflow (what your five lines call) | `.github/workflows/argus-reusable.yml` |
| Tenant config reader and the runner | `packages/app` |
| The fix loop and its sandbox | `packages/fix-loop` |
| Webhook, install records, token minting | `packages/flow` |
| Escape tests, audit log, redaction | `packages/guard`, `packages/argus-core` |

## Quickstart

Needs: a GitHub repo with Actions on, an app that you can start with one command and that answers on localhost, and a model key (Groq, per the workflow).

1. **Install the Argus GitHub App** on the repo: https://github.com/apps/argus-fixer (the page answered 200 on 2026-11-10; nobody has installed the App on a repo yet, see `docs/notes/p8-t16-owner-steps.md`).
2. **Add `.github/workflows/argus.yml`** (five lines):

   ```yaml
   on: {issues: {types: [labeled]}}
   jobs:
     argus:
       uses: vibhu-0511/argus/.github/workflows/argus-reusable.yml@main
       secrets: {ARGUS_MODEL_API_KEY: "${{ secrets.ARGUS_MODEL_API_KEY }}"}
   ```

   Pin `@main` to a tag or a commit once you trust a version. `main` moves.
3. **Add `.argus.yml`** to the repo root:

   ```yaml
   start: npm run dev
   test: npm test
   routes:
     - /
     - /login
   budget:
     max_tokens: 200000
     max_steps: 20
   ```

   `start`, `test`, `routes` and `budget` are required. `base_url` is optional (localhost only, default `http://127.0.0.1:3000`). An unknown field or a wrong type is refused and the error names the field. Your commands run on a bare Ubuntu runner, so put the install in the command, for example `npm ci && npm test`. Full field table: [docs/onboarding.md](docs/onboarding.md).
4. **Add the repository secret** `ARGUS_MODEL_API_KEY` (your own key).
5. **Label an issue `argus`.** Read the run under Actions. Your five-line workflow starts on any `argus` label event. The App's own intake code ignores and logs a label added by someone without write access, but it is tested only against a mock and the running service does not turn it on yet.

Try it on the demo shop first: `packages/app/examples/demo-repo` (a made-up two-page shop with one seeded bug, no private code).

### One real run

| What | Link |
|---|---|
| Issue | OWNER TO FILL |
| Pull request | OWNER TO FILL |
| Trace | OWNER TO FILL |
| Demo video (under 4 minutes: a success, a verifier rejection, a quota refusal) | OWNER TO FILL |

## Limits

Written down so you do not find them by surprise.

**Model quota.** Source: [docs/quotas.md](docs/quotas.md), checked 2026-10-29, on Argus's own Groq key.

| Limit | Value | How it was obtained |
|---|---|---|
| Requests per day (each of 3 models) | 1000 | response header |
| Tokens per minute | 8000 | response header |
| Tokens per day | 200000 | published table only, not seen in a header |
| Requests per minute | 30 | published table only, not seen in a header |

- These are the limits of **Argus's** key. What **your** plan allows was not confirmed. Your run is stopped by your `.argus.yml` budget first, and then by your provider's own refusal. A daily total is not counted across runs on the runner.
- Mistral: no key on its Free plan when checked, so not measured and refused. Hosted Gemma: free, but no daily limit is published, so not measured.
- Per-tenant budgets (a fair-share rule for the one key Argus holds itself) exist in the ledger; nothing in the running service builds them yet ([ADR-028](docs/adr/0028-per-tenant-quota-budgets.md)).
- One run per issue at a time. A run is cut off after 30 minutes. Hosting for the webhook is on free tiers (Render sleeps after 15 minutes idle; a cold start takes about a minute, not measured).

**Sandbox.** The fix loop runs model-written commands in Docker with `--network none`, 1 CPU, 512 MB and no environment ([ADR-025](docs/adr/0025-sandbox-tier-selection.md)). That is the default tier. gVisor and Firecracker were measured but are not the default and do not run in the tenant workflow. The escape suite (14 probes) passes on Docker, but it checks how the sandbox is configured; it does not try kernel exploits. The fix sandbox does not yet set a process limit or drop capabilities.

**What is not measured.**
- The resolve rate on real issues. No real tenant run exists.
- Minutes and tokens per issue, and the install time.
- That a push made with the App token starts your own CI (a rule the backport bot relies on).
- Anything about the production model's resistance to prompt injection: the red-team ran 15 times on one small local model.
- How many tenants the free hosting tiers carry.

**Scope.** UI bugs in apps that start with one command and answer on localhost. The patch arrives as a draft PR for a person to review.

## Security model

Full threat model: [ADR-024](docs/adr/0024-threat-model-and-trust-boundaries.md). Secrets and token scopes: [ADR-026](docs/adr/0026-secrets-handling-and-token-scopes.md). Why the job runs in your repo: [ADR-027](docs/adr/0027-tenancy-via-reusable-workflow.md). These ADRs are written as *proposed*; the owner has not accepted them yet.

- **Least privilege App.** Permissions: Actions write, Contents write, Issues write, Pull requests write, Metadata read. Nothing else. Not granted: Administration, Workflows, Secrets, Variables, Environments, organisation and account permissions. Contents write covers every branch of the repo; protect your default branch with branch protection, because the token does not.
- **Short-lived, one repo.** Each token is minted for one use, for one repo, with an explicit permission list, and lives one hour at most. The App private key stays on the Argus service, never in your repo.
- **No `GITHUB_TOKEN` in the agent step.** The workflow runs at `contents: read`. No step sets the token in its environment, and both checkouts drop their credentials after the clone. Nothing in the workflow pushes; the patch leaves as an artifact and the App opens the PR.
- **Your key goes to one step.** `ARGUS_MODEL_API_KEY` is passed by name (no `secrets: inherit`) and only the fix step holds it. The verify step, where your test command runs on the patched code, has no key. Your own commands run with secret-named variables removed.
- **The patch cannot change its own check.** `.argus.yml` is read once from the tree as checked out, so a patch that edits it does not change what verify runs.
- **Text from an issue is data.** The ticket, your files and command output go to the model, and its reply is treated as untrusted: a fixed tool set, a sandbox, and a human reading a draft PR.
- **Secrets are masked.** Trajectories and spans pass through a redactor. A repo secret scan runs in CI. Known gap: a secret in a plainly named variable or in a repo file is not always masked.

Open risks you should know about:
- Your test command runs patched code on the runner with network. The runner is yours and has no model key in that step, but it is not a sandbox.
- The result files (`result.json`, `patch.diff`) come from your runner and are unsigned; the service reads them as data. The worst case is a bad branch and a draft PR in your own repo.
- Everything in the workflow is fetched at the Argus ref you choose. Pin a tag or a commit.

## Free-tier data caveat

**Do not use private code with a free-tier model key.** Everything the agent reads (the issue text, file contents, command output) is sent to the model provider. Prompts sent to a free tier may be used by the provider for training. This repo was checked only for what Argus sends, not for the provider's terms (not verified here; read your provider's). So Argus is only tried on **synthetic or public code**, such as the demo shop. If your code is private, use a paid plan whose terms say it does not train on your data, or do not install Argus.

## Licence

OWNER TO FILL. No licence has been chosen, and there is no `LICENSE` file. Until one is added, nobody else has the right to use or copy this code.

## More

- Install guide and field table: [docs/onboarding.md](docs/onboarding.md)
- Design and what is built, per task: [docs/architecture/p8.md](docs/architecture/p8.md)
- Release checklist: [docs/release-checklist.md](docs/release-checklist.md)
