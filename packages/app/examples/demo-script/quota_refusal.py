"""P8-T18 rehearsal: a quota refusal, no model and no network. The second call is refused BEFORE anything is sent.

    uv run --all-packages python packages/app/examples/demo-script/quota_refusal.py

With the per-tenant budgets of P8-T07 (`TenantBudget`) it shows a tenant over its own budget while another tenant goes on.
Without them (before T07 is merged) it shows the shared hard stop of P0-T07 on a one-request day. `send` is a fake model call
that only counts; the numbers are made up for the demo and are not the real limits in docs/quotas.md.
"""
import tempfile
from pathlib import Path

from argus_core.ledger import Ledger, ModelQuota, QuotaExceeded, Usage

try:
    from argus_core.ledger import TenantBudget
except ImportError:  # the repo does not have P8-T07 yet
    TenantBudget = None

sent = []


def send() -> Usage:
    sent.append(1)
    return Usage(10, 5)


def attempt(who: str, ledger) -> None:
    try:
        ledger.call("demo-model", send)
        print(f"{who}: call allowed (model requests sent so far: {len(sent)})")
    except QuotaExceeded as refused:
        print(f"{who}: REFUSED before sending: {refused} (model requests sent so far: {len(sent)})")


quota = ModelQuota(requests_per_day=100 if TenantBudget else 1, tokens_per_day=10_000, requests_per_minute=100, tokens_per_minute=10_000, cached_counts=False)
with tempfile.TemporaryDirectory() as tmp:
    if TenantBudget:
        ledger = Ledger(Path(tmp) / "ledger.json", {"demo-model": quota}, budgets={"acme": TenantBudget(1, 1000), "globex": TenantBudget(1, 1000)})
        print("per-tenant budget: 1 request a day each")
        attempt("acme   call 1", ledger.for_tenant("acme"))
        attempt("acme   call 2", ledger.for_tenant("acme"))
        attempt("globex call 1", ledger.for_tenant("globex"))  # another tenant is not blocked
    else:
        ledger = Ledger(Path(tmp) / "ledger.json", {"demo-model": quota})
        print("shared limit: 1 request a day")
        attempt("call 1", ledger)
        attempt("call 2", ledger)
