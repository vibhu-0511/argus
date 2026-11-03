# P8-T03 Installation flow and token minting: owner steps

Date: 2026-11-03. **Not run: "after installing on a test repo, the service mints a short-lived token scoped to that repo only; a call on another repo fails" was never seen against the real GitHub.** There is no registered App (P8-T02 is an owner step), so GitHub was not called. The code is tested against a mock GitHub (27 tests in `packages/flow/tests/test_installations.py`, real Postgres for the store). The `P8-T03` box in `TASKS.md` stays unticked.

## What is built

| Item | Where |
|---|---|
| Store: installation id, tenant id (the account's numeric id), account login, repo list, applied delivery ids | `packages/flow/src/flow/installations.py` (`InstallationStore`), three tables in the flow database |
| Webhook: `installation` (created, deleted) and `installation_repositories` (added, removed), recorded after the 202 | `packages/flow/src/flow/webhook.py` (`on_installation`), wired in `flow.service` |
| `mint_for_repo(store, "owner/name", profile)`: look up, then `flow.app_token` with that installation and that one repo | `installations.py`; the result `ScopedToken` carries `tenant_id` for P8-T07 |
| `sync: false` entries for `ARGUS_GITHUB_APP_ID` and `ARGUS_GITHUB_APP_PRIVATE_KEY` | `render.yaml` (no values) |

Nothing calls `mint_for_repo` yet in the running service: the clients still take their token from their own env var (see the ponytail note in `flow.app_token`). T04 and T08 are the first callers.

## Steps (after P8-T02 steps 1 to 7 are done, so the App exists and Render has its id, key and secret)

1. **Redeploy** the Render service so the new code and the two variables are live. The tables are created on the first installation event (`create table if not exists`); nothing to run by hand.
2. **Install the App on a test repo.** GitHub, the App page, **Install App**, pick the account, **Only select repositories**, choose one throwaway repo, **Install** (screen names from memory). Use a repo of your own, not `dcortex-ai/dcortex-platform`.
3. **See the event arrive.** App settings, **Advanced**, **Recent deliveries**: an `installation` delivery answered **202**. A 401 means `GITHUB_WEBHOOK_SECRET` differs from the App's.
4. **Check the store** with a read-only query (the URL stays in your shell, never printed):

   ```bash
   psql "$ARGUS_FLOW_DATABASE_URL" -c "select i.installation_id, i.tenant_id, i.account_login, r.repo from argus_installations i join argus_installation_repos r using (installation_id)"
   ```

   Expect one row: your installation id, your account id and login, the test repo in lowercase.
5. **Mint for the installed repo, then try another.** Run this where `ARGUS_GITHUB_APP_ID`, `ARGUS_GITHUB_APP_PRIVATE_KEY` and `ARGUS_FLOW_DATABASE_URL` are set (the service shell, or locally with the same values), and `T03_REPO_A` / `T03_REPO_B` hold the installed repo and any other repo (`owner/name`). It prints no token, only the status codes:

   ```bash
   uv run --all-packages python -c "
   import os, httpx
   from flow.installations import InstallationStore, mint_for_repo
   store = InstallationStore(os.environ['ARGUS_FLOW_DATABASE_URL'])
   a, b = os.environ['T03_REPO_A'], os.environ['T03_REPO_B']
   t = mint_for_repo(store, a, 'read')
   for repo in (a, b):
       r = httpx.get(f'https://api.github.com/repos/{repo}', headers={'Authorization': f'Bearer {t.token.token}', 'Accept': 'application/vnd.github+json'})
       print(repo, r.status_code)
   print('tenant', t.tenant_id, 'expires', t.token.expires_at)
   "
   ```

   Expected: repo A `200`, repo B `404` (for a public repo GitHub may answer 200 to any token: use a private repo as B), an `expires_at` about one hour ahead. Asking `mint_for_repo` itself for B stops with `RepoNotInstalled` before any call.
6. **Removal.** In the installation settings take the repo off the list. The next delivery is `installation_repositories` / `removed`; run step 5 again: it must stop with `RepoNotInstalled`.
7. **Redelivery.** Recent deliveries, open the `installation` delivery, **Redeliver**. Run the query of step 4: no change.
8. **Tick.** Tick `P8-T03` in `TASKS.md` only if steps 3 to 7 gave the expected output. Record the date in `docs/architecture/p8.md`.

## What was not done or not verified

- Everything in the steps above. GitHub's real payloads for the four events were not captured; the parser reads `installation.id`, `installation.account.{id,login}`, `repositories[].full_name` (created, deleted), `repositories_added[]` and `repositories_removed[]` (from GitHub's documented payloads, from memory, not from a run). If a real delivery differs, `apply` raises and the webhook logs the exception class only; fix `_installation` or `_repos`.
- A new installation with "All repositories": the `created` payload lists the repos at that time; later repos arrive as `installation_repositories` / `added`. Not seen for real.
- `suspend` / `unsuspend` and repo renames are ignored (GitHub then refuses the token call; nothing is wrongly allowed).
- The store is only as fresh as the events it got. Webhooks are hints (ADR-021), but here the event is the only source; a lost event leaves a stale row. Both stale directions are safe: a repo missing from the store is refused by `mint_for_repo`, a repo still in the store but gone at GitHub is refused by GitHub (and `AppTokenMinter` checks the answer). A reconcile from `GET /app/installations` and `/installation/repositories` would repair drift; not built.
- `ARGUS_GITHUB_APP_INSTALLATION_ID` (P7, single installation) is not used by `mint_for_repo`; the installation comes from the store. The P7 path is unchanged.
- Tests ran against a throwaway `postgres:16` container (`argus-p8t03-pg`, port 55437, generated password), removed afterwards.
