"""P8-T07: the tenant id of the installation record keys the quota ledger.

The first test uses a stub store (no database). The second uses the real `InstallationStore` and needs a Postgres at
ARGUS_FLOW_DATABASE_URL (skipped without it). No model is called: `send` is a fake.
"""

from __future__ import annotations

import os

import pytest
from argus_core.ledger import Ledger, ModelQuota, TenantBudget, TenantQuotaExceeded, Usage

from flow.config import DATABASE_URL_ENV
from flow.installations import Installation, InstallationStore, RepoNotInstalled, ledger_for_repo

DATABASE_URL = os.environ.get(DATABASE_URL_ENV, "")
QUOTA = ModelQuota(requests_per_day=100, tokens_per_day=10_000, requests_per_minute=100, tokens_per_minute=10_000, cached_counts=False)


class StubStore:
    def __init__(self, repos: dict[str, Installation]) -> None:
        self.repos = repos

    def find(self, repo: str) -> Installation:
        try:
            return self.repos[repo]
        except KeyError:
            raise RepoNotInstalled(repo) from None


def _install(tenant: str, installation_id: int) -> Installation:
    return Installation(installation_id, tenant, f"login-{tenant}")


def _run_two_tenants(store, tmp_path) -> None:
    ledger = Ledger(tmp_path / "ledger.json", {"m": QUOTA}, budgets={"4242": TenantBudget(1, 100), "7": TenantBudget(1, 100)})
    shop = ledger_for_repo(store, "acme/shop", ledger)
    shop.call("m", lambda: Usage(1, 0, 0))
    with pytest.raises(TenantQuotaExceeded) as refused:
        shop.call("m", lambda: Usage(1, 0, 0))
    assert refused.value.tenant == "4242"  # the account id from the installation record
    ledger_for_repo(store, "globex/app", ledger).call("m", lambda: Usage(1, 0, 0))  # the second tenant is not blocked
    with pytest.raises(RepoNotInstalled):
        ledger_for_repo(store, "evil/app", ledger)


def test_the_installation_tenant_id_is_the_ledger_key(tmp_path):
    _run_two_tenants(StubStore({"acme/shop": _install("4242", 1), "globex/app": _install("7", 2)}), tmp_path)


def test_with_the_real_installation_store(tmp_path):
    if not DATABASE_URL:
        pytest.skip(f"{DATABASE_URL_ENV} is not set; needs a real Postgres")
    store = InstallationStore(DATABASE_URL)
    with store._connect() as conn:
        conn.execute("truncate argus_deliveries, argus_installation_repos, argus_installations cascade")
    for account, installation_id, repo in ((4242, 11, "acme/shop"), (7, 12, "globex/app")):
        payload = {
            "action": "created",
            "installation": {"id": installation_id, "account": {"login": repo.split("/")[0], "id": account}},
            "repositories": [{"full_name": repo}],
        }
        store.apply("installation", payload, f"d-{installation_id}")
    _run_two_tenants(store, tmp_path)
