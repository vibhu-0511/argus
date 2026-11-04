"""GitHub App installations: who installed the App, on which repos, and a token for one of them (P8-T03).

GitHub sends `installation` (created, deleted) and `installation_repositories` (added, removed) to the webhook
URL of the App. `flow.webhook` verifies the HMAC, answers 202 and hands the payload to `InstallationStore.apply`
after the response. The store keeps three small tables in the flow database (the one DBOS uses, public schema):

- `argus_installations`: installation id -> tenant id, account login. The tenant id is the installation account's
  numeric id as text. It does not change when the account is renamed, so the per-tenant quota (P8-T07) can key on it.
- `argus_installation_repos`: lowercase `owner/name` -> installation id. One row per repo the App may see.
- `argus_deliveries`: the `X-GitHub-Delivery` ids already applied. A redelivery (GitHub's button, or a retry after a
  5xx) is dropped in the same transaction as the change, so it also cannot undo a later `removed` or `deleted`.

`mint_for_repo` is the only way to a token for a tenant repo: look the repo up, and only then call `flow.app_token`
with that installation id and that one repo. A repo that is not in the store (never installed, removed, installation
deleted) raises `RepoNotInstalled` before the private key is read and before any HTTP call. Permissions stay the
ADR-026 profiles; `AppTokenMinter` refuses anything above them and checks that the answer is one repo wide.

Nothing here logs or raises a token, a key or the database URL: errors carry the repo name or the exception class.

ponytail: the store is only as fresh as the events it received. A lost event leaves a stale row. The failure
direction is safe: a repo missing from the store is refused here, and a repo still in the store but gone at GitHub is
refused by GitHub (404/422 from the token call). `suspend` / `unsuspend` and repo renames are not handled; a rename
needs the `repository` event. Order between different deliveries is not tracked (last write wins); upgrade path is the
event's `updated_at` per installation if it ever shows up.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx
import psycopg
from argus_core.ledger import Ledger, TenantLedger

from flow.app_token import API_URL, APP_ID_ENV, KEY_ENV, AppTokenMinter, InstallationToken
from flow.db_wake import wait_for_database

log = logging.getLogger("flow.installations")

EVENTS = frozenset({"installation", "installation_repositories"})

_SCHEMA = (
    "create table if not exists argus_installations (installation_id bigint primary key, tenant_id text not null, account_login text not null)",
    "create table if not exists argus_installation_repos (repo text primary key, installation_id bigint not null references argus_installations on delete cascade)",
    "create table if not exists argus_deliveries (delivery_id text primary key)",
)


class RepoNotInstalled(LookupError):
    """The App is not installed on this repo (never, removed, or the installation was deleted). No HTTP call was made."""


@dataclass(frozen=True)
class Installation:
    installation_id: int
    tenant_id: str
    account: str


@dataclass(frozen=True)
class ScopedToken:
    token: InstallationToken  # its repr hides the token
    tenant_id: str
    installation_id: int
    repo: str


def _installation(payload: dict) -> Installation:
    inst = payload["installation"]
    account = inst["account"]
    return Installation(int(inst["id"]), str(account["id"]), str(account["login"]))


def _repos(items: list[dict] | None) -> list[str]:
    return [r["full_name"].lower() for r in items or []]


class InstallationStore:
    def __init__(self, database_url: str) -> None:
        self._url = database_url
        self._ready = False
        self._lock = threading.Lock()

    def __repr__(self) -> str:  # the URL has a password in it
        return "InstallationStore(database_url=<set>)"

    def _connect(self) -> psycopg.Connection:
        with self._lock:
            if not self._ready:
                wait_for_database(self._url)  # a suspended Neon compute wakes here, bounded
                with psycopg.connect(self._url, connect_timeout=10) as conn:
                    for ddl in _SCHEMA:
                        conn.execute(ddl)
                self._ready = True
        return psycopg.connect(self._url, connect_timeout=10)

    def apply(self, event: str, payload: dict, delivery_id: str | None = None) -> bool:
        """Record one webhook event. True if it changed the store, False if it was ignored or a repeat of a delivery."""
        action = payload.get("action")
        if event == "installation" and action in ("created", "deleted"):
            add, remove = _repos(payload.get("repositories")) if action == "created" else [], []
        elif event == "installation_repositories" and action in ("added", "removed"):
            add, remove = _repos(payload.get("repositories_added")), _repos(payload.get("repositories_removed"))
        else:
            return False
        inst = _installation(payload)
        with self._connect() as conn:
            if delivery_id and conn.execute("insert into argus_deliveries values (%s) on conflict do nothing", (delivery_id,)).rowcount == 0:
                return False
            if action == "deleted":  # the repos go with it (on delete cascade)
                conn.execute("delete from argus_installations where installation_id = %s", (inst.installation_id,))
                return True
            conn.execute(
                "insert into argus_installations values (%s, %s, %s) on conflict (installation_id) do update set tenant_id = excluded.tenant_id, account_login = excluded.account_login",
                (inst.installation_id, inst.tenant_id, inst.account),
            )
            for repo in add:
                conn.execute(
                    "insert into argus_installation_repos values (%s, %s) on conflict (repo) do update set installation_id = excluded.installation_id",
                    (repo, inst.installation_id),
                )
            for repo in remove:
                conn.execute("delete from argus_installation_repos where repo = %s and installation_id = %s", (repo, inst.installation_id))
        return True

    def find(self, repo: str) -> Installation:
        """The installation that covers `owner/name` (case-insensitive), else `RepoNotInstalled`."""
        if repo.count("/") != 1 or not all(repo.split("/")):
            raise ValueError("repo must be 'owner/name'")
        with self._connect() as conn:
            row = conn.execute(
                "select i.installation_id, i.tenant_id, i.account_login from argus_installation_repos r join argus_installations i using (installation_id) where r.repo = %s",
                (repo.lower(),),
            ).fetchone()
        if row is None:
            raise RepoNotInstalled(f"the App is not installed on {repo!r}")
        return Installation(*row)

    def repos(self, installation_id: int) -> list[str]:
        with self._connect() as conn:
            return [r[0] for r in conn.execute("select repo from argus_installation_repos where installation_id = %s order by repo", (installation_id,))]


def ledger_for_repo(store: InstallationStore, repo: str, ledger: Ledger) -> TenantLedger:
    """The quota ledger bound to the tenant that installed the App on `repo` (P8-T07). Unknown repo: `RepoNotInstalled`."""
    return ledger.for_tenant(store.find(repo).tenant_id)


def mint_for_repo(
    store: InstallationStore,
    repo: str,
    profile: str = "write",
    *,
    app_id: str | None = None,
    private_key: str | None = None,
    transport: httpx.BaseTransport | None = None,
    base_url: str = API_URL,
    clock: Callable[[], float] = time.time,
) -> ScopedToken:
    """A one-hour token for `owner/name` only, with the permissions of `profile` (ADR-026). App id and key come from the environment."""
    inst = store.find(repo)  # before the key is read and before any HTTP call
    app_id, private_key = app_id or os.environ.get(APP_ID_ENV, ""), private_key or os.environ.get(KEY_ENV, "")
    missing = [name for name, value in ((APP_ID_ENV, app_id), (KEY_ENV, private_key)) if not value]
    if missing:
        raise RuntimeError(f"not set: {', '.join(missing)}")
    minter = AppTokenMinter(app_id, private_key, str(inst.installation_id), repo, transport=transport, base_url=base_url, clock=clock)
    return ScopedToken(minter.mint(profile), inst.tenant_id, inst.installation_id, repo)
