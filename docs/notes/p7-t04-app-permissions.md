# P7-T04 GitHub App: permissions, token life, owner steps

Date: 2026-11-03. **The permission list below is stated before the first push and before the App exists.** Nothing in the code needs the App: `flow.app_token` runs against an httpx mock transport. The owner creates the App later (section 6). The real GitHub was **not** called in this task; every statement about what GitHub does is from the docs listed in section 8 or marked "from memory, not checked".

Today the three clients use fine-grained personal tokens from Render env vars (`GITHUB_WRITE_TOKEN`, `GITHUB_DISPATCH_TOKEN`, `GITHUB_TOKEN`). The App replaces them. The clients were not changed to mint tokens themselves (section 7).

## 1. Calls the pipeline makes, and the permission each one needs

Derived from `packages/flow/src/flow/github_write.py`, `github_read.py`, `actions.py` and `.github/workflows/agent-job.yml`. The "Permission" column uses the names of the GitHub docs page *Permissions required for GitHub Apps* (section 8). "Verbatim" means I saw that row on the page; "inferred" means the row was not read and the permission is the one that fits the resource (the owner should confirm it when the App is made).

| # | Pipeline call | REST endpoint | Permission (access) | Source |
|---|---|---|---|---|
| 1 | Read the repo, default branch | `GET /repos/{owner}/{repo}` | Metadata: read | verbatim |
| 2 | Read the issue and its comments (poller, reconcile) | `GET .../issues`, `GET .../issues/{n}`, `GET .../issues/{n}/comments` | Issues: read | verbatim |
| 3 | Read the branch ref | `GET .../git/ref/heads/{branch}` | Contents: read | verbatim |
| 4 | Read commit and files at the base | `GET .../git/commits/{sha}`, `GET .../contents/{path}` | Contents: read | verbatim |
| 5 | Create the branch (ref) | `POST .../git/refs` | Contents: write | verbatim (git refs rows also carry the "additional permissions" mark, see 3) |
| 6 | Push to the one draft-PR branch (tree, commit, move the ref, never forced) | `POST .../git/trees`, `POST .../git/commits`, `PATCH .../git/refs/{ref}` | Contents: write | verbatim |
| 7 | Find a PR | `GET .../pulls` | Pull requests: read | verbatim |
| 8 | Open a draft PR; close a PR | `POST .../pulls`, `PATCH .../pulls/{n}` | Pull requests: write | verbatim |
| 9 | Mark a draft PR ready (GraphQL `markPullRequestReadyForReview`) | `POST /graphql` | Pull requests: write | inferred: the GraphQL reference says nothing about permissions |
| 10 | Comment on the issue (QA marker comments) | `POST .../issues/{n}/comments` | Issues: write | verbatim |
| 11 | Set and remove the `argus:<state>` labels | `POST .../issues/{n}/labels`, `DELETE .../issues/{n}/labels/{name}`, `GET .../issues/{n}/labels` | Issues: write | verbatim for POST and DELETE |
| 12 | Dispatch `agent-job.yml` | `POST .../actions/workflows/{id}/dispatches` | Actions: write | verbatim |
| 13 | Find the run, poll it | `GET .../actions/workflows/{id}/runs`, `GET .../actions/runs`, `GET .../actions/runs/{id}` | Actions: read | verbatim |
| 14 | List and download the artifact `argus-result` | `GET .../actions/runs/{id}/artifacts`, `GET .../actions/artifacts/{id}/{archive_format}` | Actions: read | verbatim |
| 15 | Mint the installation token | `POST /app/installations/{id}/access_tokens` | Needs the App JWT, no installation permission | docs page |

Access levels are ordered read < write < admin; a write grant includes read, so the dispatch token asks for Actions: write only and still reads runs and artifacts.

### The minimum, as three profiles

The code (`flow.app_token.PROFILES`) mints a token for one use at a time, so a token carries only what that use needs:

| Profile | Used by | Permissions |
|---|---|---|
| `read` | `flow.github_read` (poller) | Metadata: read, Issues: read, Pull requests: read, Contents: read, Actions: read |
| `write` | `flow.github_write` | Metadata: read, Contents: write, Pull requests: write, Issues: write |
| `dispatch` | `flow.actions` | Metadata: read, Actions: write |

The App itself is installed with the union (`MINIMUM` in `app_token.py`): **Actions: write, Contents: write, Issues: write, Pull requests: write, Metadata: read**. Nothing else. `check_policy` refuses any request with a permission outside that list or above those levels, before any HTTP call.

## 2. Explicitly NOT granted

| Not granted | Why the pipeline does not need it |
|---|---|
| **Administration** (any level) | No call changes repo settings, branch protection or collaborators. It could turn protection off, so it is the permission that would defeat the main control |
| **Workflows: write** | The permission "to update GitHub Actions workflow files". No call writes `.github/workflows/`. Without it a patch that edits a workflow file should be refused at the push (from memory, **not** shown on the docs page and not tested here); the dispatch of an existing workflow needs only Actions: write |
| **Secrets**, **Variables**, **Environments** (repository) | The runner gets secrets from the repository settings set by the owner; the pipeline never reads or writes them |
| **Pages, Deployments, Packages, Webhooks, Security events, Code scanning, Dependabot, Checks, Statuses, Discussions, Projects, Actions variables, Single file, Repository security advisories, Merge queues** | No call uses them |
| **Organization permissions** (members, administration, secrets, webhooks, ...) | The repo is under one owner; no org-level call |
| **Account (user) permissions** | The App acts as itself, not as a user |
| **Other repositories** | See section 3. The platform repo `dcortex-ai/dcortex-platform` is read by the runner with its own read-only secret `ARGUS_PLATFORM_TOKEN`; the App is **not** installed there |
| **Contents write on the default branch** | GitHub has no per-branch App permission: Contents: write covers every branch of the repo. The default branch is protected by the owner's branch protection (section 6), not by the token. This is the largest residual risk of the App, see 4 |

## 3. One repository

- The App is installed on **one** repository (the Argus repo). An installation token "cannot be granted access to repositories that the installation was not granted access to" ([t00 versions note](p7-t00-versions.md), from the REST page).
- Every token is also requested with `repositories: ["<name>"]` (one bare name) and an explicit `permissions` map. Without a `permissions` map GitHub gives "all of the permissions that were granted to the app", so `check_policy` refuses an empty map.
- The answer is checked: `repository_selection` must be `selected`, the repository list exactly the one name, and every permission in the answer at or below what was asked. A broader token is dropped (`AppTokenError`).
- The write client already refuses a ticket id of another repo (`HttpGitHubClient._issue`).
- A token for repo A used on repo B: modelled in the test as the 404 GitHub gives for a repo the token cannot see.

## 4. Residual risks

| Risk | State |
|---|---|
| A stolen `write` token can push to the default branch **if branch protection is off or the plan does not offer it** | Needs the owner step in section 6. **Check the plan**: from memory, branch protection and rulesets on a **private** repo need a paid plan (Pro, Team or Enterprise Cloud); the repo is private (`threat-model.md`). If the plan does not allow it, there is no technical block: the token can write any branch. Not checked |
| A stolen private key mints tokens for as long as the key exists | One owner revokes the key in the App settings (section 6, step 5). The key is read from an env var only (`ARGUS_GITHUB_APP_PRIVATE_KEY`) and never logged |
| The `markPullRequestReadyForReview` permission is not documented | Inferred as Pull requests: write; the first real call will show |
| The strict answer check could reject a real answer that lists an extra permission | It fails closed (no token). Relax `_accept` if the first real answer needs it |
| `contents: write` can push to a draft-PR branch of another ticket | Accepted: one repo, one owner |

## 5. Token lifetime and how it is minted

- GitHub fixes an installation token at **one hour** ("Installation tokens expire one hour from the time you create them"; an expired token gives 401). It cannot be made shorter. The App JWT used to ask for it lives 9 minutes (`exp` at most 10 minutes ahead is GitHub's limit; `iat` is set 60 s back for clock drift).
- Minted **per use**, never stored: `AppTokenMinter.mint(profile)` signs a JWT with the private key from the env var, posts it once, returns the token, and keeps nothing. The caller passes the token to the client constructor and lets it go.
- Intended wiring (not done in this task): the Render service mints at the start of each workflow step (`write` before the branch/PR/comment steps, `dispatch` before a dispatch, `read` per poller sweep). A poll longer than the hour needs a fresh token.
- The token shape is `ghs_<APPID>_<JWT>` since 2026-04-27 (`p7-t00-versions.md`). `flow.agent_job.scrub` did not mask it; it now goes through `argus_core.redact` (see `docs/architecture/p7.md`, section P7-T04).

## 6. OWNER STEPS (not done; only the owner can do them)

The GitHub screen names below are **from memory of the GitHub web UI, not checked in this session**; if a label differs, match the permission names in section 1.

1. **Create the App.** GitHub, top right profile picture, **Settings**, left sidebar bottom **Developer settings**, **GitHub Apps**, **New GitHub App**.
   - GitHub App name: any free name (for example `argus-fixer`). Homepage URL: the repository URL.
   - Webhook: **untick Active** (the pipeline uses the repository's own webhook).
   - Permissions, **Repository permissions** (all others stay **No access**):
     - **Actions**: Read and write
     - **Contents**: Read and write
     - **Issues**: Read and write
     - **Pull requests**: Read and write
     - **Metadata**: Read-only (set by GitHub, cannot be removed)
   - **Organization permissions** and **Account permissions**: leave all at **No access**. Do not set **Administration**, **Workflows**, **Secrets**, **Environments** or **Variables**.
   - **Where can this GitHub App be installed?**: **Only on this account**.
   - Click **Create GitHub App**.
2. **Private key.** On the App page, section **Private keys**, **Generate a private key**. A `.pem` file downloads. Put its text into the Render env var `ARGUS_GITHUB_APP_PRIVATE_KEY` (Render dashboard, the service, **Environment**; `render.yaml` needs `sync: false` for it, not added here). Do not commit it, do not paste it into a chat or a ticket. Delete the downloaded file after storing it.
3. **App id.** On the same page, **About**: the **App ID**, a number. Set it as the Render env var `ARGUS_GITHUB_APP_ID`.
4. **Install on one repository.** Left sidebar **Install App**, **Install** next to your account, choose **Only select repositories**, pick the Argus repo only, **Install**. The number at the end of the page address (`.../settings/installations/<number>`) is the installation id: set it as `ARGUS_GITHUB_APP_INSTALLATION_ID`. Do **not** install it on `dcortex-ai/dcortex-platform`.
5. **Key rotation or leak.** App page, **Private keys**, **Delete** the old key after adding a new one; every token made from the old key keeps working until it expires (at most one hour).
6. **Branch protection on the default branch** (this is what stops a push to it; see 4). Repository **Settings**, **Rules**, **Rulesets**, **New ruleset**, **New branch ruleset** (or **Settings**, **Branches**, **Add branch protection rule**). Target: the default branch. Turn on: **Restrict deletions**, **Block force pushes**, **Require a pull request before merging** (at least 1 approval). Leave the **Bypass list** empty; in particular do **not** add the App. Set **Enforcement status** to **Active**. If GitHub says the feature needs a paid plan for a private repository, say so to Claude: the plan, not the code, then decides.
7. After 1 to 6, run **P7-T20** (push to the default branch with the App token; expect 403 or a protection error) and tick `P7-T04`'s real-world part by hand. Neither was run here.

## 7. What was built and what was not

| Item | State |
|---|---|
| `packages/flow/src/flow/app_token.py`: JWT (RS256, PyJWT), mint with explicit `permissions` and one `repositories` entry, `check_policy`, answer check | Built, 34 tests on a mock GitHub (`packages/flow/tests/test_app_token.py`) |
| Wiring the minter into `github_write`, `github_read`, `actions` and the Render service | **Not done**: the clients still take a token string from their own env var. Do it when the App exists |
| `flow.agent_job.scrub` routed through `argus_core.redact` | Done; test shows the old regex left a `ghs_<APPID>_<JWT>` token whole |
| `render.yaml` entries for the three new env vars | Not added |
| The real App, real branch protection, real GitHub answers (the 403 or 422 text on a protected branch, the 422 for a missing permission) | **Not verified.** The test fake models them as the GitHub docs describe or as I remember them; a real run is P7-T20 after the owner steps |

## 8. Sources read on 2026-11-03

- [Permissions required for GitHub Apps](https://docs.github.com/en/rest/authentication/permissions-required-for-github-apps): the endpoint rows in section 1. Rows for `GET .../issues/{n}/labels` and the GraphQL mutation were not on the page (the first inferred, the second REST-only page). The page does not say that Workflows: write is needed to push workflow files, and it does not say Metadata: read is always granted.
- [Create an installation access token for an app](https://docs.github.com/en/rest/apps/apps#create-an-installation-access-token-for-an-app): body parameters `repositories`, `repository_ids`, `permissions`; "If `permissions` is not specified, the installation access token will have all of the permissions that were granted to the app"; the token cannot get permissions the App lacks; one hour; status codes 201, 401, 403, 404, 422 (the page describes 422 only as "Validation failed, or the endpoint has been spammed"; that a missing permission gives 422 is from memory, and modelled so in the test).
- [GraphQL reference, `markPullRequestReadyForReview`](https://docs.github.com/en/graphql/reference/pulls): input `pullRequestId`; no permission text.
