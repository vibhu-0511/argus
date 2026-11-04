# ADR-028: Per-tenant quota budgets

Status: proposed (P8-T14). Written by Claude; the owner decides. It is accepted when the owner approves it. **Nothing in it was run against a model provider or a real tenant.** The rule below is the one in `argus_core/ledger.py` as built by P8-T07, read line by line; the limit figures are quoted from `docs/quotas.md` and nowhere else. Revisit when a second real tenant exists, when a paid provider plan is bought, or when the tenant count passes two.

## Context

Argus calls a model through one shared key on a free tier. `docs/quotas.md` (checked 2026-10-29) is the only source for the limits and says what is measured and what is only published:

| Fact cited from `docs/quotas.md` | Value | How it was obtained there |
|---|---|---|
| Groq requests per day, each of the 3 models | 1000 | response header |
| Groq tokens per minute | 8000 | response header |
| Groq tokens per day | 200000 | published table only |
| Groq requests per minute | 30 | published table only |
| Cached tokens count | no | from the Groq page; no cache field was seen in usage |
| Mistral | no row | no key on the Free plan; the ledger refuses a model with no row |
| Local Ollama `gemma4:e4b` | no cap published | no row either |

The file does not say whether a limit is per model or across the whole key. The ledger assumes per model (one bucket per model). With more than one tenant (P8), one busy tenant could use the whole shared limit and the others would be refused through no fault of their own. P8-T07 added a tenant to every ledger call and a fair-share rule. This ADR states the rule exactly as the code does it, says what happens at the host's limit, and says what is not decided.

## Decision

### The rule, exactly as implemented

A call is `Ledger.call(model, send, token_estimate=E, tenant=T)`; `Ledger.for_tenant(T)` is the same call with `T` fixed (the router and both loops take it unchanged). The tenant id is the installation's account id (`flow.installations.ledger_for_repo`). The fix loop and the router pass no estimate, so `E` is 0 there (the repro loop passes 1).

`budgets` is a dict tenant id to `TenantBudget(requests_per_day, tokens_per_day, provider_share)`. `provider_share` is above 0 and at most 1 (default 0.5); other values raise `ValueError`.

Checks run before the HTTP call, in this order. The first that fails refuses the call; nothing is sent and nothing is counted.

| # | Check | Compared with | Error and limit name |
|---|---|---|---|
| 0 | Model has a row in the quota block | | `QuotaExceeded`, `unknown-model` |
| 1 | If `budgets` is not given: skip 2 to 4. If `T` is not in `budgets`: refuse, except tenant `default`, which skips 2 to 4 unless it is listed | | `TenantQuotaExceeded`, `unknown-tenant` (0 of 0) |
| 2 | Tenant requests today over all models, plus this one | `requests_per_day` | `TenantQuotaExceeded`, `tenant_requests_per_day` |
| 3 | Tenant tokens today over all models, plus `E`; refused when strictly above | `tokens_per_day` | `TenantQuotaExceeded`, `tenant_tokens_per_day` |
| 4 | The tenant's own use of this model, against the model's limits times `provider_share`, each cut down with `max(1, int(limit * share))`: requests per day, requests in the last 60 seconds, tokens per day (refused when used is at or above, or used plus `E` is above), tokens in the last 60 seconds | the host row of the model | `TenantQuotaExceeded`, `provider_share.<requests_per_day, requests_per_minute, tokens_per_day, tokens_per_minute>` |
| 5 | The same four limits for this model with the use of **all** tenants added up (`default` included) | the full host row of the model | plain `QuotaExceeded`, the limit name without a prefix |

Counting: a call is counted only after `send` returns. Charged tokens are in plus out, minus the cached prompt tokens unless the row says `cached_counts: true`. The minute limits use a sliding 60 second window. The day is the UTC date; at the first call on a new date all counts of all tenants are dropped. State is one JSON file (`default` under `models`, the others under `tenants`).

The message names the tenant: `tenant acme: fake would exceed tenant_requests_per_day: 3 of 2`. `TenantQuotaExceeded` is a subclass of `QuotaExceeded`, so every place that stops on `QuotaExceeded` (the router's fallback, `run_fix`, `run_planned`, the repro loop) stops on it too. Two tenants under their limits are not affected by a third that is over (test: `packages/app/tests/test_break_tenant_quota.py`, [p8-break-it-t21.md](../notes/p8-break-it-t21.md)).

Example, arithmetic only, from the figures cited above with two tenants at `provider_share` 0.5: each tenant may use 500 requests a day, 100000 tokens a day, 15 requests a minute and 4000 tokens a minute of each Groq model. Together that is the whole row. This is a worked example, not a measurement.

What the rule does **not** do (read from the code):

- A share is a fixed fraction. Capacity a tenant does not use is not lent to another. If one tenant is idle, the other is still stopped at its share.
- The shares are not checked against each other. Three tenants at 0.5 add up to 1.5; then check 5 is what stops them, first come first served, and a tenant can be refused at check 5 while it is under its share.
- In the fix loop, tokens are checked before the call only by what is already used (`E` is 0), so the call that crosses a token limit goes through and the next one is refused. A tenant can end one call above `tokens_per_day`.
- The `default` tenant (every P0 to P7 caller) has no limit of its own unless listed, but its use counts in check 5.

### What happens at the host's own limit

The code has two cases. They are different.

1. **The ledger count reaches the host row** (check 5; everyone's use added up). A plain `QuotaExceeded` without a tenant is raised before the call, for every tenant, until the day rolls (UTC) or the 60 second window moves on. `run_fix` ends that run with the stop reason `quota_exceeded`. With a `Router`, the tier's fallback route on the other host is tried once (strong tier: Mistral, which has no quota row, so the ledger refuses it; cheap tier: local Ollama, which needs a row from the caller). If the fallback is refused too, the error reaches the caller. Nothing queues or waits.
2. **The host answers HTTP 429** although the ledger thought there was room (the ledger count differs from the host's count: the key is used elsewhere, or a published figure in `docs/quotas.md` is wrong). The error is raised inside the call, so **the ledger counts nothing** for it. With a `Router`, a 429 also tries the fallback once. Without a fallback, or if the fallback fails, the `httpx.HTTPStatusError` is not caught by `run_fix` (it catches only `QuotaExceeded`), so the run ends with an exception, not with the stop reason `quota_exceeded`. A script that ran `run_fix` with a model call raising a 429 saw `HTTPStatusError` raised and 0 requests counted for the tenant (the script is not in the repo). No retry, no waiting, and nothing lowers any tenant's share.

So at the host's limit every tenant is refused alike; the shares only make it less likely that one tenant caused it.

### What is decided here (proposed) and what is not built

| Item | Proposal | State |
|---|---|---|
| Rule | As in the table above, kept as built | built and tested (P8-T07) |
| Tenant key | The installation's account id | built (`ledger_for_repo`) |
| Where `budgets` live | A mapping read at service start, one entry per tenant id, next to the service config; a tenant with no entry is refused (already the behaviour) | **not built**: `budgets` is only an argument today |
| Shares | Set `provider_share` to 1 divided by the number of tenants on the shared key; check at load that the shares add up to at most 1 | **not built** (no check) |
| One ledger for all runs | One ledger file per service, not per job. The only caller that builds a ledger today, `flow.agent_job`, makes a fresh file in each job's output folder and passes no budgets, so nothing counts across jobs yet | **not built** |
| A tenant's own key | A run that uses the tenant's own model key (the reusable workflow, P8-T04) hits that key's limit, not the shared one; this ledger applies when Argus's key is shared | by design |

## Alternatives

- **No per-tenant limit, only the shared one.** Rejected: the first busy tenant takes the whole day and everybody else gets the host's error.
- **A daily budget per tenant over all models, without a share of one model.** Rejected: a tenant inside its daily budget could still use all of one model's minute or day limit. The share closes that.
- **Lend unused capacity (a tenant may go above its share while others are idle).** Not built. It makes a tenant's refusal depend on what others do and needs a place that sees all runs live. Add it when idle shares are shown to waste real capacity.
- **A queue that waits for the minute window instead of refusing.** Not built: the loops stop on a refusal by design; a wait would hold a runner.
- **Tenants bring their own key.** Kept as a way out (see the last row of the table), not as a replacement; a tenant that does not want to set one up uses the shared key.

## Consequences

- A tenant over its limit gets a refusal that names it and the limit; the other tenants go on. The stored trajectory step says only `QuotaExceeded` (the loop drops the message), so the tenant and limit are visible in the raised error and not in the trajectory. Not fixed.
- The rule is only as true as the figures behind it. The Groq numbers are from one day (2026-10-29): requests per day and tokens per minute are header values, tokens per day and requests per minute are published figures and were not measured, and Mistral and the hosted Gemma have no row.
- Nothing in the running service uses budgets yet. Until the three "not built" rows are done, the rule is tested code and not behaviour of the deployed service.
- One JSON file with one owner process: two processes on one path can lose a record (a `ponytail:` note in the ledger). Fine for one Render instance; not for two.

## What was never verified

- Any of this against a real provider, a real 429 body, or two real tenants.
- Whether a Groq limit is per model or across the key (the ledger assumes per model).
- That the published figures (200000 tokens a day, 30 requests a minute) are the ones that apply to this key.
