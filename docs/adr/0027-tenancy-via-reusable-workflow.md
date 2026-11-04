# ADR-027: Tenancy via a reusable workflow in the tenant's repo

Status: proposed (P8-T13), written by Claude, for the owner to decide. It is accepted when the owner approves it. **Nothing in it was run on GitHub.** There is no registered GitHub App, no tenant repository and no Actions run of `argus-reusable.yml` (`docs/notes/p8-t04-owner-steps.md`); the comparison below is from the code, the notes and the ADRs named in each row. **No cost figure was measured.** Where a number appears, it is the limit a source in this repo states, with the source; where a cost has no source, the row says "unmeasured". Revisit after the first real tenant run (P8-T16), or if GitHub changes the reusable-workflow rules in `docs/notes/p8-t00-versions.md`.

## Context

P8 turns Argus into a GitHub App that other people install. The first question is whose compute, quota and credentials one run uses. Two places can run the repro, fix and verify steps:

| | A: in the tenant's repo | B: on our servers |
|---|---|---|
| What it is | The tenant's five-line workflow calls `.github/workflows/argus-reusable.yml` with `workflow_call`. The job runs on a GitHub-hosted runner of the tenant's account (P8-T04) | The P6 design generalised: the Argus service on Render dispatches `agent-job.yml` in the Argus repo, one run per step (`flow.actions.ActionsRunner`, ADR-022), and reads the artifact back |
| Built | Yes, never run on GitHub | Yes for one platform repo, never run on GitHub (ADR-022, `docs/notes/p6-t04.md`). Nothing builds a per-tenant clone or a per-tenant read token |

The phase goal says the agent job runs "in the tenant's repo, not on your infrastructure, and ADR-027 records why" (`phases/P08-argus-app.md`). This ADR is that record. It compares A and B on quota, trust boundary and cost, then settles one rule for the backport bot (T10).

## Decision

**Run the agent job in the tenant's repo (A).** The tenant's runner, the tenant's Actions minutes and the tenant's own `ARGUS_MODEL_API_KEY` are used. Argus servers do only what needs the App's key: take the webhook, remember which installation covers which repo (`flow.installations`, P8-T03), mint a one-repo token (`flow.app_token`), and open the branch and the pull request from the artifact (P8-T09). The reusable workflow itself never pushes (ADR-026, amendment 2026-11-03).

The backport head rule is in its own section below.

### Quota

| Question | A: tenant repo | B: our servers | Source |
|---|---|---|---|
| Whose model key? | The tenant's secret, passed by name, only to the fix step. No `secrets: inherit` | Argus's one `secrets.ARGUS_MODEL_API_KEY`, for every tenant | `argus-reusable.yml`; `agent-job.yml` |
| What limit applies to it? | The tenant's own account limit at the provider. The numbers in `docs/quotas.md` (1000 requests/day, 200000 tokens/day, 30 requests/minute, 8000 tokens/minute) were read on 2026-10-29 for **Argus's** key. What a tenant's plan gives was not confirmed (the Groq Free-plan table is "not confirmed" in `docs/notes/p8-t00-versions.md`) | One bucket for all tenants: the ledger keys by model id and day, with no tenant until P8-T07 adds one (ADR-002 consequences) | `docs/quotas.md`, ADR-002 |
| Who stops a run that spends too much? | The runner, from the tenant's own `.argus.yml` budget: `max_steps` and `max_tokens` become the fix loop's `step_cap` and `token_cap` for one issue | Fixed caps in Argus code (`STEP_CAP`, `TOKEN_CAP`), not set by the tenant, plus the shared bucket, so one tenant can take the day from the others (this is the P8-T21 break-it) | `argus_app.runner` (`_fix_agent`); `flow.agent_job` (fix step) |
| Is a daily total counted across runs? | **No.** The ledger file is `argus-out/ledger.json` of that run, so it starts empty each run. The daily limit is then enforced by the provider's own refusal, not by Argus. This applies to the shared ledger too, as long as the runner creates it per run | Same code path today | `flow.agent_job._router` |
| Actions capacity | The tenant's plan. For the free plan the notes record 20 concurrent standard jobs and 1,000 `GITHUB_TOKEN` API requests per hour per repository | Ours: every tenant's steps queue behind the same plan, and `agent-job.yml` serialises only runs with the same run key | `docs/notes/p8-t00-versions.md`; `agent-job.yml` |
| GitHub API calls by Argus | Each installation has its own REST limit (5,000 per hour minimum) | The same | `docs/notes/p8-t00-versions.md` |
| Size of what a step hands the next | One job, so the steps share files on disk | A dispatch carries the upstream as an input. GitHub caps the whole payload at 65,535 characters, so a bigger patch fails the step | `flow/actions.py` (ponytail note) |

What A does **not** remove from our side: the Render webhook (10 s to answer, ADR-021), its cold start (about one minute, ADR-022, not measured), and the Neon allowance, because installation events and PR creation still go through the service. The per-tenant budget of P8-T07 still matters for what Argus spends on its own side; ADR-028 (P8-T14) decides that, not this ADR.

### Trust boundary

Terms are those of ADR-024 (TB numbers) and ADR-026.

| Question | A: tenant repo | B: our servers | Source |
|---|---|---|---|
| Where does the tenant's code run? | On a runner of the tenant's account, in the tenant's repo | On Argus's runner. For a private repo Argus would need a read token per tenant on that runner (today `ARGUS_PLATFORM_TOKEN` is one fine-grained token for one repo) | `agent-job.yml` |
| Whose secrets sit next to the model-written code? | The tenant's own. The token is the tenant's `GITHUB_TOKEN` at `contents: read`, kept out of every agent step; the model key reaches only the fix step; the verify step, where the tenant's test command runs, gets no key | Argus's. The single step "Run the step in the sandbox" holds `ARGUS_MODEL_API_KEY`, and it runs verify too. ADR-024 risk 1 (patched code runs on the runner with the model key) applies to every tenant's key at once: a tenant whose test command leaks the key leaks the key every tenant spends | `argus-reusable.yml`; `agent-job.yml`; ADR-024 risk 1 |
| Can one tenant reach another? | No shared runner or secret. The only shared secret is the App's private key, and it stays on Render. A token is minted for one repo and an explicit permission list, and a call on another repo fails (T03 tests) | Shared model key, shared Argus repo secrets, shared queue | `flow.installations`, `flow.app_token`; ADR-026 |
| What can a hostile tenant do to Argus? | It controls the runner, so `result.json`, `patch.diff` and `trajectory.jsonl` are **unsigned and tenant-controlled** (ADR-024 risk 13, TB9). The service must read them as data. The worst case is a bad branch and a **draft** PR in the tenant's own repo, because the installation token covers one repo (T03) and the PR stays a draft (A2) | The artifact is ours, but the code that ran is the tenant's, on our runner (row above) | ADR-024; `flow.installations` |
| What can Argus do to the tenant? | Run its code in the tenant's runner with the tenant's model key. The called workflow is fetched at `argus_ref`, **default `main`**, so a bad commit on our `main` reaches every tenant's fix step. The tenant limits this by pinning a tag or a commit (the onboarding doc says so). Actions are pinned by tag, not by commit (ADR-024 risk 13) | Read the tenant's source with a token, and send file text to the model host (ADR-024 TB7) | `argus-reusable.yml`; `docs/onboarding.md` |
| Who pushes? | The App installation token (one hour, one repo), from the service. The called workflow can only lower the caller's token permissions, and a push by `GITHUB_TOKEN` would not start other workflows (T00 note: the exception covers `workflow_dispatch` and `repository_dispatch` only) | Same | ADR-026 amendment; `docs/notes/p8-t00-versions.md` |

What A still shares with B: the patched code is run by the tenant's test command on a plain runner with network, not in a sandbox. A moves that risk from "all tenants' key" to "this tenant's own runner and key"; it does not remove it. The sandbox (`fix_loop.sandbox`, ADR-025) still confines the model's commands in the fix step.

### Cost

No figure here was measured. No real run of `argus-reusable.yml` or `agent-job.yml` with a model exists, so minutes per issue and tokens per issue are **unmeasured**. No price (money) for Actions minutes or tokens is recorded anywhere in this repo.

| Cost | A: tenant repo | B: our servers | State |
|---|---|---|---|
| Actions minutes | The tenant pays from their plan. Upper bound of one run: `timeout-minutes: 30` | We pay. Same bound per step, three steps per issue | Minutes per issue unmeasured. The included minutes of a plan are not in this repo's notes |
| Model tokens | The tenant's key. Upper bound per issue: their `.argus.yml` budget | We pay from one free-tier bucket (Groq: 200000 tokens/day published, `docs/quotas.md`) | Tokens per issue unmeasured |
| Argus hosting | Render free (750 instance hours per workspace per month, sleeps after 15 min) and Neon free (100 CU-hours, per project per month by the page's Compute wording) for webhook, store and PR creation. Fixed, the same for one tenant or ten | The same, plus dispatch and artifact reads | ADR-022. How many tenants the free tiers carry: not measured |
| Cost of the choice to the tenant | They must have Actions on, give a key and install the App. Onboarding is the five-line workflow, `.argus.yml` and one secret | None beyond installing the App | `docs/onboarding.md` |

The cost argument for A is who pays, not that A is cheaper. B turns every tenant's usage into Argus's bill and into one shared free-tier quota. A keeps Argus's costs at the fixed hosting row. Whether the free tiers are enough once real tenants exist is open.

### The backport head

The backport bot (P8-T10) opens a pull request that applies a merged fix to a configured older branch. **Its head is a branch the tenant's own workflows are allowed to test.** That means all of these, and T10 and T20 are to be checked against them:

1. **The head branch lives in the tenant's repository**, under the `argus/` prefix the fix branches already use (`flow.states.branch_name`). It is never in a fork and never in the Argus repo. The tenant's own CI runs on it with the tenant's own token and secrets, under the tenant's own rules.
2. **The App installation token creates the branch and the PR, not a workflow's `GITHUB_TOKEN`.** Events caused by `GITHUB_TOKEN` do not start workflow runs (T00 note). That is the reported cause of an open issue in another project's backport action, where backport PRs did not start CI (korthout/backport-action issue 379, `analysis/findings_ledger.md` EDGE-013; the report, not a check of ours). That an App token's push does start the tenant's CI is **not shown in this repo**; the first real backport PR (P8-T10, T16) has to show a CI run starting, or this rule is not met.
3. **The tenant's workflow must cover the PR.** If the tenant's CI is limited to some branches, the release branch the backport targets has to be in that list. Argus cannot change the tenant's CI files (the App has no Workflows permission, ADR-026), so this is a line in the onboarding doc, not code. This point is from general GitHub behaviour and was not checked in this repo's notes; check it when T10 runs.
4. **Argus never runs the head.** `argus-reusable.yml` starts only on a label event or on a pull request that changes its own file, so it does not run on a backport head. The bot's code does not check out the PR head under the installation token (a P8-T23 criterion), because that would run a branch's code with the App's write rights.
5. **Why testing it in the tenant's CI is safe enough.** The commits on the head are cherry-picks of changes that are already on the tenant's default branch, not new model output. A conflict is not resolved by Argus: the bot comments and leaves the branches alone (T10, T23).

## Alternatives

- **B: run on our servers, one `agent-job.yml` for all tenants.** Rejected for the three rows above that hurt most: one model key and one bucket for everyone, a token for every tenant's source on our runner, and the model key present while a tenant's test command runs. Kept as it is for the seeded benchmark (P6), where the repo and the key are the owner's own.
- **C: a self-hosted runner in the tenant's account that connects to us.** Not built. It would give the tenant's data to a machine Argus operates or instructs, and a runner registration token is another secret to hold. No source in this repo says it would help.
- **D: the tenant's workflow pushes with its own `GITHUB_TOKEN`.** Rejected in the ADR-026 amendment: it needs `contents: write` on a job that runs a model and the tenant's test command, and the push would not start the tenant's CI.
- **E: both, tenant picks.** Not chosen: two paths double the tests and the threat model, and nothing asks for it.

## Consequences

- Argus has no per-issue compute bill in the normal case. It still has the hosting limits of ADR-022, which were never measured on a real deployment.
- Every tenant runs our code. A version rule is needed: pin `argus_ref` to a tag or a commit in production, and do not move a published tag. The default `main` in the workflow file is a convenience for the owner's own tests.
- The service must treat the artifact as untrusted data. The artifact has one folder per step, while `flow.actions.parse_artifact` expects the three files at its root, so P8-T09 must read the verify folder or the layout must change (`docs/notes/p8-t04-owner-steps.md`).
- A daily model total is not counted across runs on the runner. If Argus ever needs one, it needs a tenant-keyed store on the service side (ADR-028).
- The backport rule adds a line to `docs/onboarding.md` about branch coverage. That file is capped at 60 lines by a test; the line has to fit.

## What was not verified

- That GitHub accepts `argus-reusable.yml` as a reusable workflow (no run), and that a called workflow's token is read-only when the tenant's default is write.
- That a push or a PR made with the App installation token starts the tenant's CI.
- Minutes and tokens per issue, the included Actions minutes of any plan, and any price. No source in the repo.
- What a tenant's own model-provider plan allows.
- How many tenants the Render and Neon free tiers carry.
