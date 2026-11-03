# ADR-026: Secrets handling and token scopes

Status: proposed (P7-T16), drafted by Claude at the owner's request, for the owner to review. It is accepted when the owner approves it. **Nothing in it was checked against GitHub, Render, Neon or a model provider.** There is no GitHub App yet; the permission list below is the one stated in `docs/notes/p7-t04-app-permissions.md` before the first push, built from the calls in the code and the GitHub docs pages read on 2026-11-03, with a few rows inferred. The screen names in the rotation steps are from memory of the web UIs and were not checked. Revisit after the App is created and P7-T20 has been run against it, or when a second person gets access to any store.

## Context

Argus holds secrets in four places: the Render service (webhook secret, three GitHub tokens, the database URL), GitHub Actions secrets (model key, platform read tokens), the owner's local environment (provider and trace keys), and, once it exists, the GitHub App's private key. The full list with who can read each is `packages/guard/secrets-inventory.md`; names only, no value anywhere.

Rules the code enforces (T03, tests in `packages/guard/tests`): a secret is an environment variable and never a file in the repo; the scan `.github/workflows/check_no_secrets.py` fails on a token shape in a tracked file or a token in a git remote URL; the sandbox container gets no environment (`docker_argv` has no `-e`); trajectories and spans are masked by `argus_core.redact`. The scan has run locally (`clean`) and has never run on GitHub.

## Decision

### Lifetimes

"Fixed" means the issuer sets it. "Chosen" means the owner picks it when creating the secret. The proposed values are a proposal, not something enforced.

| Secret | Kind | Lifetime today | Proposed |
|---|---|---|---|
| `GITHUB_WEBHOOK_SECRET` | Shared HMAC key | No expiry | Rotate once a year, and at once on any suspected leak |
| `GITHUB_WRITE_TOKEN`, `GITHUB_DISPATCH_TOKEN`, `GITHUB_TOKEN` (poller) on Render | Fine-grained personal tokens | Chosen when created; the scopes on GitHub were never checked | Replaced by the App (below), then deleted. Until then an expiry of 90 days or less |
| `ARGUS_PLATFORM_TOKEN`, `PLATFORM_REPO_TOKEN` | Fine-grained personal tokens, read only, on the private platform repo | Chosen when created | An expiry of 90 days or less. The App is **not** installed on the platform repo |
| `ARGUS_MODEL_API_KEY` | Model provider key, Actions secret | No expiry set by the provider as far as the repo shows | Rotate once a year, and on a leak |
| `ARGUS_FLOW_DATABASE_URL` | Neon role password inside the URL | No expiry | Rotate once a year, and on a leak |
| Actions job `GITHUB_TOKEN` | Issued by GitHub per job | Fixed: ends with the job | Nothing to rotate; `permissions: contents: read` |
| `ARGUS_GITHUB_APP_PRIVATE_KEY` | RSA key of the App | No expiry; it works until deleted in the App settings | Rotate once a year, and at once on a leak |
| App JWT (made from the key) | Signed per use | Fixed by the code: 9 minutes (GitHub's limit is 10) | none |
| App installation token (made from the JWT) | `ghs_<APPID>_<JWT>` since 2026-04-27 | Fixed by GitHub: one hour; it cannot be made shorter. Minted per use by `flow.app_token`, kept nowhere | none |
| `ARGUS_GITHUB_APP_ID`, `ARGUS_GITHUB_APP_INSTALLATION_ID` | Identifiers, not secret | none | none |
| `MISTRAL_API_KEY`, `GROQ_API_KEY` | Provider keys, local | No expiry | Rotate on a leak or when a machine is lost |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `OTEL_EXPORTER_OTLP_*HEADERS` | Trace backend keys, local | No expiry | Rotate on a leak |

A one-hour installation token is why the App is the target: a leaked token dies by itself, a leaked personal token lives until its expiry or until someone deletes it. The three Render tokens stay long-lived until the owner creates the App and wires `flow.app_token` into the three clients (not done; the clients still take a token string from their own env var).

### Token permission list (GitHub App)

Copied from `docs/notes/p7-t04-app-permissions.md`; **not changed here**. The code that enforces it is `flow.app_token` (`MINIMUM`, `PROFILES`, `check_policy`; 34 tests on a mock GitHub).

The App is installed on **one** repository, the Argus repo, with:

| Permission | Level |
|---|---|
| Actions | write |
| Contents | write |
| Issues | write |
| Pull requests | write |
| Metadata | read (set by GitHub) |

Each token is minted for one use, with an explicit permissions map and one bare repository name:

| Profile | Used by | Permissions |
|---|---|---|
| `read` | `flow.github_read` (poller) | Metadata read, Issues read, Pull requests read, Contents read, Actions read |
| `write` | `flow.github_write` | Metadata read, Contents write, Pull requests write, Issues write |
| `dispatch` | `flow.actions` | Metadata read, Actions write |

Not granted: Administration (it could switch off the protection that matters most), Workflows, Secrets, Variables, Environments, every organization and account permission, every other repository. `check_policy` refuses any request outside the list before it sends anything.

What the list cannot do: **Contents: write covers every branch**. GitHub has no per-branch App permission, so only branch protection stops a stolen `write` token from moving the default branch (T20 mock run: with protection off the same token moves `main`).

### Rotation procedure

Rule for every rotation: create the new value first, store it, check that the service works, then delete or revoke the old one. A value is never pasted into chat, a ticket, a commit or a shell command line; it goes from the issuer's screen to the store.

| Secret | Steps |
|---|---|
| `GITHUB_WEBHOOK_SECRET` | 1. Make a long random value locally (for example 32 random bytes in hex) without printing it into a shared place. 2. Put it into the Render env var. 3. Put the same value into the repository webhook's **Secret** field. 4. Restart the service if Render has not. 5. Check that a new delivery shows a 2xx answer in the webhook's **Recent deliveries**. **Gap, no overlap:** the code accepts one secret, so between steps 2 and 3 a delivery fails the HMAC check (401). That is safe, but the event is lost. Webhooks are hints (ADR-021); the poller repairs a lost one, but it is off by default (`ARGUS_FLOW_POLL_ENABLED=false`), so do this when no ticket waits in `awaiting-qa`, or switch the poller on first. Not tried |
| `GITHUB_WRITE_TOKEN`, `GITHUB_DISPATCH_TOKEN`, `GITHUB_TOKEN` (until the App) | New fine-grained token with the same repository and the scopes in `render.yaml`'s comments, set as the Render env var, one check of a read call, then delete the old token in GitHub's token settings. After the App exists: remove these three env vars and the old tokens |
| `ARGUS_PLATFORM_TOKEN`, `PLATFORM_REPO_TOKEN` | New fine-grained token, **Contents: read** on the platform repo only, replace the Actions secret, run the checkout once, delete the old token |
| `ARGUS_MODEL_API_KEY` | New key at the provider, replace the Actions repository secret, run one workflow step that needs it, revoke the old key at the provider. GitHub does not mask the value in a file a step writes, so the redactor stays on (T03) |
| `ARGUS_FLOW_DATABASE_URL` | Reset the role password in Neon, put the new URL (direct, `sslmode=require`) into the Render env var, restart, check `/health` and one DB read. Until the service holds the new URL, new connections fail to log in; `flow.db_wake` retries a lost connection with backoff and no deadline, which does not fix a wrong password, so the restart is needed. A rotation during a running step was not tried |
| `ARGUS_GITHUB_APP_PRIVATE_KEY` | 1. In the App settings, generate a **second** private key. 2. Put it into the Render env var, restart. 3. Mint one token (`AppTokenMinter`) and use it for a read. 4. Delete the old key in the App settings. Tokens minted from the old key keep working until they expire, at most one hour. **On a leak, delete the key first** and then do steps 1 to 3. Delete the downloaded `.pem` file after storing it |
| App id and installation id | Not secret. Change only if the App is re-created: set the new ids as env vars |
| `MISTRAL_API_KEY`, `GROQ_API_KEY`, trace keys | New key at the provider or Langfuse, replace the local environment variable, revoke the old one |
| Any secret found in a file, log, trajectory or PR | Treat as leaked: rotate it first, then remove it (removing it from history does not make it safe). The scan prints `path:line: <4 characters>...` and never the value |

### Owner steps: what only the owner can create

None of these exists today.

1. Create the GitHub App with exactly the list above, generate the key, install it on the one Argus repo (steps 1 to 4 in `docs/notes/p7-t04-app-permissions.md`, section 6).
2. Set `ARGUS_GITHUB_APP_PRIVATE_KEY`, `ARGUS_GITHUB_APP_ID` and `ARGUS_GITHUB_APP_INSTALLATION_ID` on Render. `render.yaml` has no entries for them yet; add them with `sync: false`.
3. Wire the minter into the three clients so the personal tokens can be deleted. Not built.
4. Turn on branch protection or a ruleset for the default branch, nobody and no App in the bypass list. Whether the owner's plan allows it on a private repository is **not known**; if not, nothing technical stops a push to the default branch by a `write` token.
5. Run P7-T20 against the real App and record GitHub's real answer.
6. Optional: turn on GitHub secret scanning and push protection (a settings change, not done).
7. Push the branch and let `secret-scan.yml` and `guard.yml` run once.

### What was never verified on GitHub

- That an App with this exact list can do everything the pipeline does. Two rows were inferred: the GraphQL mutation `markPullRequestReadyForReview` (taken as Pull requests: write) and `GET .../issues/{n}/labels` (taken as Issues). The first real call will show.
- That Workflows: write is not needed for a push that touches no workflow file, and what GitHub does with a push that does. From memory, not on the docs page.
- That a protected-branch ref update returns 403 or 422 and what text; the mock models both.
- That the strict answer check in `flow.app_token` accepts a real GitHub answer (it fails closed).
- The scopes the three current personal tokens actually have.
- The webhook rotation window, the Neon rotation and the model-key rotation: nothing here was run.
- That `secret-scan.yml` is green on GitHub.

## Alternatives

- **Keep personal tokens, rotate them on a schedule.** Rejected as the target: a leaked token lives until its expiry. Kept as the state until the App exists.
- **One broad App token for everything.** Rejected: the three profiles cost one dictionary and limit what a leaked token can do (a `dispatch` token cannot push, a `read` token cannot comment).
- **A secrets manager or a vault.** Not chosen: one owner, two stores (Render and GitHub), no second reader. Revisit with a second person.
- **Accept more than one webhook secret during a rotation.** Not built: it would remove the gap in the webhook row, but it is a code change for a yearly event.

## Consequences

- The ADR can be accepted before the App exists, but the "short-lived" half of the phase goal is real only after owner steps 1 to 3.
- The webhook rotation loses events during the gap; the procedure says when to do it. A written procedure existed nowhere before (the threat model listed it as missing, ASI07).
- Because Contents: write cannot be limited by branch, the safety of the default branch depends on a setting the owner has not yet confirmed is available.
- A success output (the patch) and the result artifact are not redacted. A secret that reaches them through a plainly named variable or a repo file is not masked (ADR-024, risk 11).

## Amendment 2026-11-03 (P8-T04): who pushes in a tenant repository

Status: proposed, like the rest of this ADR. Written by Claude; the owner decides. Nothing here was run on GitHub.

**Choice: the App installation token pushes. The tenant workflow token never does.**

- The reusable workflow (`.github/workflows/argus-reusable.yml`) runs in the tenant's repo with the tenant's `GITHUB_TOKEN` at `contents: read`, and that token is kept out of every step that runs the agent. The workflow cannot write: it uploads the patch as an artifact.
- The App's `write` profile (`flow.app_token`, one repository, explicit permissions) creates the branch and the PR from that artifact (P8-T09).

Why:

1. A called workflow can only lower the caller's token permissions (`docs/notes/p8-t00-versions.md`). To let it push, the tenant would have to grant `contents: write` and `pull-requests: write` to a job that runs a model and the tenant's own test command.
2. A push or PR made with `GITHUB_TOKEN` does not start other workflows (same note, with the pull-request case not settled), so the tenant's CI would not run on the PR.
3. The installation token lives one hour, is minted per use, and goes through `check_policy`, `guard` and the audit log. The tenant token has none of that.

What it costs: the tenant must install the App on their repo (the permission list above stays the same, but the "one repository, the Argus repo" line now means one repository per installation), and a service of ours must read the artifact (P6 `flow.actions` already does). If the App is down, nothing is pushed. This changes owner step 1 above from one installation to one per tenant repo; it does not change the permission table.
