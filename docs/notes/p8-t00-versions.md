# P8-T00 version re-check

Checked on 2026-11-03. Every row has the page or API it came from. "not confirmed" means the source did not say, or could not be read. No number below is from memory. Format follows `docs/notes/p7-t00-versions.md`.

How the checks were made: version and date facts come from the registries' own JSON (`registry.npmjs.org`, `pypi.org/pypi/<name>/json`, the GitHub releases API), because search snippets were stale in P7. GitHub prose facts come from the docs pages named in each row, fetched by a web-fetch helper that reports verbatim quotes. Where the rendered page did not state a fact, the docs source in the `github/docs` repository (raw markdown on `main`) was read; those rows say so. Model limits come from the provider pages; no provider key was used and no model was called.

Dependency: P8-T00 depends on P7-T22, which is done.

## Pinned versions (the PLAN.md table)

| Item | Value now | Was | Source | Changed |
|---|---|---|---|---|
| React | 19.3.1, published 2026-10-14 | 19.3.1 | [npm](https://registry.npmjs.org/react) | no |
| Vite | 8.3.5, published 2026-10-21 | 8.3.5 | [npm](https://registry.npmjs.org/vite) | no |
| Tailwind | **4.3.4**, published 2026-11-02 | 4.3.3 | [npm](https://registry.npmjs.org/tailwindcss) | **yes** |
| Playwright | 1.64.1, published 2026-10-14 (`next` is 1.65.0-alpha-2026-11-03) | 1.64.1 | [npm](https://registry.npmjs.org/playwright) | no |
| `@playwright/mcp` | **0.0.84**, published 2026-10-31 | 0.0.83 | [npm](https://registry.npmjs.org/@playwright/mcp) | **yes** |
| MCP spec | tag `2026-07-28`, published 2026-07-28, not prerelease. A `2026-07-28-RC` prerelease also exists | 2026-07-28 | [GitHub releases](https://api.github.com/repos/modelcontextprotocol/modelcontextprotocol/releases?per_page=2) | no |
| MCP Python SDK (`mcp`) | 2.3.0, MIT, uploaded 2026-10-02 | 2.3.0 | [PyPI](https://pypi.org/pypi/mcp/json) | no |
| DBOS Python (`dbos`) | 3.4.0, MIT, uploaded 2026-10-28 | 3.4.0 | [PyPI](https://pypi.org/pypi/dbos/json) | no |
| promptfoo | 0.125.1, published 2026-10-25 | 0.125.1 | [npm](https://registry.npmjs.org/promptfoo) | no |
| gVisor | **release-20261102.0**, published 2026-11-02T22:00:15Z (previous: release-20261026.0, 2026-10-28) | release 20261026.0 | [GitHub releases API](https://api.github.com/repos/google/gvisor/releases?per_page=2) | **yes** |
| Firecracker | v1.17.0, published 2026-09-10 (v1.16.2 the same day) | v1.17.0 | [GitHub releases API](https://api.github.com/repos/firecracker-microvm/firecracker/releases?per_page=2) | no |
| `opentelemetry-api`, `-sdk`, `-exporter-otlp-proto-http` | 1.45.2 each, uploaded 2026-10-29 | 1.45.2 | PyPI JSON of each | no |
| `langfuse` | 5.1.0, MIT, uploaded 2026-10-30 | 5.1.0 | [PyPI](https://pypi.org/pypi/langfuse/json) | no |
| `arize-phoenix` | 21.0.0, Elastic-2.0, uploaded 2026-10-30 | 21.0.0 | [PyPI](https://pypi.org/pypi/arize-phoenix/json) | no |

Not re-checked in this task (outside P8): the OTel GenAI semconv manifest and the OWASP edition keep their earlier checks (2026-11-01 and 2026-11-03). The gVisor tarball checksum and the `runsc` install path are P7 matters and untouched.

## GitHub App: installation token

| Item | Value | Source | Notes |
|---|---|---|---|
| Lifetime | "Installation tokens expire one hour from the time you create them." An expired token gives 401 | [REST: create an installation access token](https://docs.github.com/en/rest/apps/apps#create-an-installation-access-token-for-an-app) | Unchanged from P7 |
| Default scope | "By default the installation token has access to all repositories that the installation can access" | same | |
| Narrowing | `repositories` (names) or `repository_ids`: "Up to 500 repositories can be listed in this manner." `permissions` is an object of permission name to `read` or `write`; if omitted, the token gets all permissions the App was granted. A token "cannot be granted permissions that the app was not granted" | same | P8-T03 must pass one repo name and an explicit `permissions` map, as `flow.app_token` does |
| Response | 201 with `token`, `expires_at`, `permissions` | same | |
| Token format | Staged rollout since 2026-04-27 of a stateless format `ghs_APPID_JWT`; code that expects exactly 40 characters may fail | same | Unchanged; the redactor already matches a prefix and a length range |
| REST rate limit | Installation token: minimum 5,000 requests/hour; Enterprise Cloud org installation 15,000; +50/hour per repository beyond 20 repositories; "cannot increase beyond 12,500" (not Enterprise Cloud) | [rate limits for the REST API](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api) | Per installation, so each tenant has its own budget |
| Secondary limits | No more than 100 concurrent requests; 900 points/minute per REST endpoint; 80 content-generating requests/minute and 500/hour; 2,000 OAuth access token requests/hour for GitHub Apps and OAuth apps | same | Whether minting installation tokens counts against the 2,000/hour is not stated |

## GitHub App: manifest flow

Source for all rows: [Registering a GitHub App from a manifest](https://docs.github.com/en/apps/sharing-github-apps/registering-a-github-app-from-a-manifest), read in full on 2026-11-03.

| Item | Value |
|---|---|
| Fields | `name` (string); `url` (string, required, the homepage); `hook_attributes` (object: `url` required, `active` boolean, defaults to true); `redirect_url`; `callback_urls` (array, up to 10); `setup_url`; `description`; `public` (boolean); `default_events` (array); `default_permissions` (object, e.g. `"issues": "write"`); `request_oauth_on_install` (boolean); `setup_on_update` (boolean) |
| Step 1 | The user's browser POSTs the manifest, as JSON in a form field named `manifest`, to `https://github.com/settings/apps/new` (personal account) or `https://github.com/organizations/ORGANIZATION/settings/apps/new` (organization). An optional `state` query parameter is "an unguessable random string" against CSRF |
| Step 2 | GitHub redirects to `redirect_url` with a temporary `code` (and `state` echoed back) |
| Step 3 | `POST /app-manifests/{code}/conversions` returns 201 with `id`, `pem` (private key), `webhook_secret`; the API reference schema also lists `client_id`, `client_secret`, `slug`. The endpoint is rate limited |
| Time limit | "You must complete all three steps in the GitHub App Manifest flow within one hour." |
| Owner | The person who registers from the manifest owns the App |
| Not stated | Whether `hook_attributes.url` may be a placeholder that is edited later (the page does not say); whether `default_permissions` accepts every permission name (the page shows the shape, not the full list) |

## GitHub webhooks

| Item | Value | Source |
|---|---|---|
| Response time | "Your server should respond with a 2XX response within 10 seconds of receiving a webhook delivery." Otherwise GitHub terminates the connection and counts a failure | [best practices](https://docs.github.com/en/webhooks/using-webhooks/best-practices-for-using-webhooks) |
| Retry | No automatic retry schedule is stated. "If your server goes down, you should redeliver missed webhooks once your server is back up" (manual redelivery) | same |
| Payload cap | "Payloads are capped at 25 MB." Above that, GitHub does not deliver | [webhook events and payloads](https://docs.github.com/en/webhooks/webhook-events-and-payloads) (first part of the page read) |
| Headers | `X-Hub-Signature-256` (HMAC SHA-256 hex digest of the body, sent when a secret is set), `X-GitHub-Delivery` (GUID; the same value on a redelivery), `X-GitHub-Event`, `X-GitHub-Hook-ID`, `User-Agent` prefix `GitHub-Hookshot/` | same, and best practices |

## Reusable workflows

| Item | Value | Source | Notes |
|---|---|---|---|
| Nesting depth | "ten levels of workflows - that is, the top-level caller workflow and up to nine levels of reusable workflows." Loops are not permitted | [reuse workflows](https://docs.github.com/en/actions/sharing-automations/reusing-workflows) (rendered page, verbatim) | Free, Pro, Team and Enterprise Cloud; the page source gives 4 levels for GitHub Enterprise Server |
| Calls per workflow file | **50** unique reusable workflows from a single workflow file, counting nested trees (20 on Enterprise Server) | docs source `content/actions/reference/workflows-and-actions/reusing-workflow-configurations.md` on `github/docs` `main`, section "Limitations of reusable workflows" | The rendered page read first did not state a count. This row comes from the raw docs source, not the rendered page. Argus needs one call |
| Inputs and secrets | Declared under `on.workflow_call` with `inputs` and `secrets` keys | reuse workflows page | The count limit of `workflow_call` inputs was not found; not confirmed |
| `secrets: inherit` | Passes all caller secrets to the directly called workflow; meant for the same organization or enterprise | reuse workflows page | Across different owners (a tenant repo calling the Argus repo) use explicit `secrets:` |
| Secrets through nesting | Passed only to the directly called workflow; each hop passes them again | same | |
| Access | `{owner}/{repo}/.github/workflows/{file}@{ref}` works for public and private repositories; nested workflows must all be accessible to the caller. Whether a private repo may call a public one and the reverse follows the access rules page, which was not read in full: not confirmed beyond "public and private repositories" | same | A tenant calling a reusable workflow in a public Argus repo is the case P8 uses |
| `GITHUB_TOKEN` in a called workflow | The `github` context stays that of the caller; the called workflow gets `github.token` and `secrets.GITHUB_TOKEN`. If the calling job sets no `permissions`, the called workflow gets the default permissions. Permissions passed from the caller "can be only downgraded (not elevated)" by the called workflow, also down a nested chain | docs source `reusing-workflow-configurations.md` (sections on `permissions` and `github` context) | The token is the caller's, so the tenant's workflow token is what a called job holds, not the Argus repo's |
| `GITHUB_TOKEN` lifetime | Expires when the job finishes or at its effective maximum lifetime: 6 hours on GitHub-hosted runners (the job maximum). On self-hosted runners it can only be refreshed for up to 24 hours | docs source `content/actions/concepts/security/github_token.md` on `github/docs` `main` | From the docs source, not the rendered page |
| Events started by `GITHUB_TOKEN` | "With the exception of `workflow_dispatch` and `repository_dispatch`, other `GITHUB_TOKEN`-triggered events do not create workflow runs at all." | [events that trigger workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows) | Matters for P8-T09/T10: a PR the workflow opens with its token does not start a `pull_request` run (the page's text on `pull_request` says such runs can need approval; the two statements are on the same page and the exact rule for PR events was not settled here) |
| Event payload in a called workflow | "the event payload in the called workflow is the same event payload from the calling workflow"; `GITHUB_SHA` and `GITHUB_REF` are the caller's | same page, `workflow_call` section (docs source) | |
| `env` | `env` set at workflow level in the caller is not passed to the called workflow, and the reverse; use outputs. `GITHUB_ENV` cannot pass values to caller steps because the call is a whole job | docs source `reusing-workflow-configurations.md` | The tenant's five-line workflow cannot pass settings through `env` |
| Keywords on the calling job | Only a fixed list is allowed in the job that calls (for example `uses`, `with`, `secrets`, `needs`, `if`, `permissions`, `concurrency`, `strategy`). A `uses:` job cannot have `steps` or `runs-on` | same | Full list not copied; read the page when T04 is written |
| Workflow file size | 500 KB | [Actions limits](https://docs.github.com/en/actions/reference/limits) | |
| `workflow_dispatch` input limits | **Not confirmed.** Not on the pages read. The 10-top-level-property and 65,535-character limits found on the events page belong to `repository_dispatch` `client_payload`, not to `workflow_dispatch` inputs | events page, docs source | |
| `GITHUB_TOKEN` API limit | 1,000 requests per hour per repository (15,000 for Enterprise Cloud account resources) | Actions limits | |
| Matrix | 256 jobs per workflow run | same | |
| Run and job time | Job 6 hours on GitHub-hosted (5 days self-hosted); workflow run 35 days including waiting | same | The agent job must fit in 6 hours; it should finish far sooner |
| Concurrent jobs, Free plan | 20 for a standard GitHub-hosted runner, 5 macOS | same | A tenant on the free plan gets these, not Argus |
| Reusable workflows in the queue | "Reusable workflows are viewed as a single entity" (in the queue limit text) | same | |

## Free-tier model limits

None of these was called with a key in this task. They are page readings.

| Provider | Free-tier value | Source | Status |
|---|---|---|---|
| Groq | Developer-plan base limits for `openai/gpt-oss-20b`, `openai/gpt-oss-120b`, `qwen/qwen3.8-27b`: 30 RPM, 1K RPD, 8K TPM, 200K TPD. Cached tokens do not count. The page also has a "Free Plan Limits" heading, but its table did not come through the fetch | [Groq rate limits](https://console.groq.com/docs/rate-limits) | **Matches `docs/quotas.md`** (checked 2026-10-29). Free-plan values for these models: **not confirmed**. The page shows no date |
| Gemini API | Free of charge for Gemma 4 (input, output, caching) and several Gemini models, with "Content used to improve our products" on the free card. RPM, TPM and RPD per model: **not stated** on the page ("Limits vary depending on the specific model being used", see AI Studio). RPD resets at midnight Pacific. Gemini 4 Argon is not available on the Free tier | [rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) and [pricing](https://ai.google.dev/gemini-api/docs/pricing) (both redirect to `aistudio.google.com/docs/...`) | Per-model numbers **not confirmed**. The pricing page was truncated in the fetch, so the per-model free table is partly a summary. No date on either page. Gemma 4 free-of-charge is the same as `docs/quotas.md` |
| OpenRouter | Models with an id ending in `:free`: 20 requests per minute; 50 requests per day with fewer than 10 credits bought, 1,000 per day with at least 10. A paid variant of the same model "has no platform-level request cap". `GET /api/v1/key` returns `free_model_daily_requests` (used, limit, remaining) | [OpenRouter limits](https://openrouter.ai/docs/api-reference/limits) | Confirmed from the page. Not in `docs/quotas.md` and there is no ledger row for it; the page's own text has an unfilled placeholder for the exact credit threshold ("slightly early"), so the 10-credit line is approximate. No date |
| Mistral | **Not confirmed.** The URL tried (`docs.mistral.ai/deployment/laplateforme/tier/`) gave 404, and no other page was tried. `docs/quotas.md` records that the console on 2026-10-29 showed the Free plan with no usable API key | n/a | Unchanged from `docs/quotas.md` |
| Ollama `gemma4:e4b` (local) | No cap | `docs/quotas.md` | The only model P8 task sessions use (`docs/notes/p8-waves.md`) |

## Result

- Changed pins: Tailwind 4.3.4, `@playwright/mcp` 0.0.84, gVisor release 20261102.0. Everything else matches the earlier check.
- Reusable-workflow limits that shape the design: 10 levels deep, 50 unique called workflows per file, no `env` passing, `GITHUB_TOKEN` is the caller's (so the tenant's) token and a called workflow can only reduce its permissions, secrets across owners must be passed by name, `workflow_dispatch` input limits unconfirmed.
- Webhook: 10 s to answer, 25 MB cap, no automatic retry stated.
- Manifest flow: three steps inside one hour; the conversion returns the private key and webhook secret once.
- Not confirmed, carried forward: Groq Free-plan table, Gemini per-model free limits, Mistral Free tier, `workflow_dispatch` input limits, the exact rule for pull-request runs started by `GITHUB_TOKEN`, and `workflow_call` input count.
