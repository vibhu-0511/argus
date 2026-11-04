# P8-T21 break it: one tenant uses up its budget while another tenant's run is going

Test: `packages/app/tests/test_break_tenant_quota.py` (3 tests). Scripted fake model only: the model is a list of canned replies, the tools are a stub, nothing touches a network, a key or a real model. The runs are the real `fix_loop.run_fix` loop and the real `argus_core.ledger.Ledger` (P8-T07) with a JSON file in a temp folder.

**Induced failure.** Two tenants, `acme` and `globex`, share one ledger and one model. `acme` gets a low limit. Its loop wants 3 model calls (list, list, submit) and is allowed 2. The `globex` run is started from inside `acme`'s run (in `acme`'s first tool step), so the two runs overlap on the same ledger file. `globex` needs 2 calls and is allowed plenty.

Two ways to be low, one test case each:

| Case | `acme` limit | Host limit for the model |
|---|---|---|
| `own-budget` | `TenantBudget(requests_per_day=2, tokens_per_day=1000, provider_share=1.0)` | 100 requests a day |
| `model-share` | `TenantBudget(requests_per_day=100, tokens_per_day=1000, provider_share=0.5)` | 4 requests a day, so `acme`'s half is 2 |

**Expected signal.** `acme` gets a typed quota refusal that names the tenant, before the model is called. `globex` finishes with `submit`.

**Observed** (`uv run --all-packages python -m pytest packages/app/tests/test_break_tenant_quota.py -v`: 3 passed):

| Check | `own-budget` | `model-share` |
|---|---|---|
| `acme` stop reason | `quota_exceeded` | `quota_exceeded` |
| Exception raised by the ledger | `TenantQuotaExceeded` (also a `QuotaExceeded`) | same |
| Message | `tenant acme: fake would exceed tenant_requests_per_day: 3 of 2` | `tenant acme: fake would exceed provider_share.requests_per_day: 3 of 2` |
| Calls that reached the model for `acme` | 2 (the refused third never left) | 2 |
| `acme` requests in the ledger | 2 (the refused call is not counted) | 2 |
| `globex` stop reason | `submit` | `submit` |
| `globex` refusals / calls / requests in the ledger | 0 / 2 / 2 | 0 / 2 / 2 |

The third test puts a `Router` (stage `fix`, strong tier: Groq primary, Mistral fallback) on top of the ledger with `acme` allowed 1 request in all and `globex` 5. `acme`'s first call goes through. Its second call is refused on the primary, the router tries the fallback on the other host, and that is refused too, so `TenantQuotaExceeded` reaches the caller; the model host was called once in total. `globex` on the same router then gets its answer.

**Does the test catch the failure?** Yes. With the check in `Ledger._check_tenant` switched off (the `budgets is None` early return forced to true, edit reverted after the run), all 3 tests fail (`DID NOT RAISE TenantQuotaExceeded`).

**Fix.** Already in P8-T07 (`argus_core.ledger`): the ledger key includes the tenant; a tenant's own daily budget and its share of one model are checked before the shared host limit; the refusal is raised before the HTTP call and names the tenant. Nothing new in this task. See ADR-028 (`docs/adr/0028-per-tenant-quota-budgets.md`) for the rule.

**Not shown, and what was found on the way.**

- The trajectory step for `acme` says only `QuotaExceeded` (`tool_error`), as `run_fix` stores it. The tenant name and the limit are in the ledger's exception, which `run_fix` catches and drops. The test sees them through a wrapper around the tenant's ledger view. A reader of the stored trajectory cannot tell which tenant or which limit; the loop was not changed here.
- The runs overlap in one process, one after the other, not in two threads or two processes. The ledger has one owner process (its `ponytail:` note), so a real service with two workers on one file could lose a record. Not tested.
- The test sets the limits by hand. Nothing in the running service builds `budgets` yet (the only caller that builds a ledger, `flow.agent_job`, makes a fresh file per job and passes none).
- The model is scripted. No real host limit, no HTTP 429 and no real latency are shown. What the code does on a 429 is in ADR-028 and was checked with one throwaway script (the loop raises, the ledger counts nothing); that script is not in the repo.
- The fair-share limits are a fixed fraction: if `globex` never runs, `acme` still stops at its half (in the `model-share` case 2 of the 4); the other half stays unused.

Run: `uv run --all-packages python -m pytest packages/app/tests/test_break_tenant_quota.py -q`. No Postgres needed.
