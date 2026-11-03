"""P8-T03: installation events -> store -> a token for one installed repo, against a mock GitHub.

The store tests need a real Postgres at ARGUS_FLOW_DATABASE_URL (skipped without it). The GitHub side is the
`AppGitHub` mock of `test_app_token`: it models the token call as the GitHub docs describe it. The real GitHub and
the real App were not used; the owner steps are in docs/notes/p8-t03-owner-steps.md.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os

import pytest
from argus_core.redact import redact
from fastapi.testclient import TestClient
from test_app_token import APP_ID, INSTALLATION, PATCH, AppGitHub, client_with, keys  # noqa: F401  (keys is a fixture)

from flow.app_token import PROFILES, AppTokenError
from flow.config import DATABASE_URL_ENV
from flow.enqueue import FakeEnqueuer
from flow.github_write import GitHubWriteError
from flow.installations import InstallationStore, RepoNotInstalled, mint_for_repo
from flow.webhook import DELIVERY_HEADER, EVENT_HEADER, SECRET_ENV, SIGNATURE_HEADER, create_app

DATABASE_URL = os.environ.get(DATABASE_URL_ENV, "")

INSTALL_ID = int(INSTALLATION)
ACCOUNT = {"login": "Acme", "id": 4242}
SHOP, OTHER = "acme/shop", "acme/other"


def installation(action: str, repos: list[str], *, account: dict = ACCOUNT, installation_id: int = INSTALL_ID) -> tuple[str, dict]:
    return "installation", {
        "action": action,
        "installation": {"id": installation_id, "account": account},
        "repositories": [{"full_name": r} for r in repos],
    }


def repositories(action: str, repos: list[str], *, installation_id: int = INSTALL_ID) -> tuple[str, dict]:
    key = "repositories_added" if action == "added" else "repositories_removed"
    return "installation_repositories", {
        "action": action,
        "installation": {"id": installation_id, "account": ACCOUNT},
        key: [{"full_name": r} for r in repos],
    }


@pytest.fixture
def store():
    if not DATABASE_URL:
        pytest.skip(f"{DATABASE_URL_ENV} is not set; needs a real Postgres")
    s = InstallationStore(DATABASE_URL)
    with s._connect() as conn:  # a clean slate; this also creates the tables
        conn.execute("truncate argus_deliveries, argus_installation_repos, argus_installations cascade")
    return s


@pytest.fixture
def api(keys):  # noqa: F811
    return AppGitHub(keys[1])


def mint(store, repo, api, keys, profile="write"):  # noqa: F811
    return mint_for_repo(store, repo, profile, app_id=APP_ID, private_key=keys[0], transport=api.transport())


# -- install, then a token for the installed repo only -------------------------------------------------------


@pytest.mark.parametrize("profile", sorted(PROFILES))
def test_install_then_a_token_for_that_repo_only(store, api, keys, profile):  # noqa: F811
    assert store.apply(*installation("created", [SHOP]), "d-1") is True
    scoped = mint(store, SHOP, api, keys, profile)
    assert api.mint_bodies == [{"permissions": PROFILES[profile], "repositories": ["shop"]}]  # one bare name, explicit map
    assert (scoped.tenant_id, scoped.installation_id, scoped.repo) == ("4242", INSTALL_ID, SHOP)
    assert scoped.token.permissions == PROFILES[profile]
    if profile == "write":
        client_with(scoped.token.token, api).push_branch("argus/x", PATCH, "k")  # works on the installed repo


def test_the_token_for_repo_a_fails_on_repo_b(store, api, keys):  # noqa: F811
    store.apply(*installation("created", [SHOP]), "d-1")
    scoped = mint(store, SHOP, api, keys)
    with pytest.raises(GitHubWriteError, match="404"):
        client_with(scoped.token.token, api, repo=OTHER).push_branch("argus/x", PATCH, "k")


def test_a_repo_that_is_not_installed_is_refused_before_any_http_call(store, api, keys):  # noqa: F811
    store.apply(*installation("created", [SHOP]), "d-1")
    for repo in (OTHER, "evil/shop", "acme/sho"):
        with pytest.raises(RepoNotInstalled):
            mint(store, repo, api, keys)
    assert api.calls == 0 and api.mint_bodies == []


def test_the_lookup_ignores_case_like_github_does(store, api, keys):  # noqa: F811
    store.apply(*installation("created", ["Acme/Shop"]), "d-1")
    assert mint(store, "ACME/shop", api, keys).repo == "ACME/shop"


def test_a_repo_name_that_is_not_owner_slash_name_is_refused(store, api, keys):  # noqa: F811
    for repo in ("shop", "acme/", "/shop", "a/b/c", ""):
        with pytest.raises(ValueError):
            mint(store, repo, api, keys)
    assert api.calls == 0


def test_missing_app_id_or_key_is_named_and_makes_no_call(store, api, monkeypatch):
    store.apply(*installation("created", [SHOP]), "d-1")
    monkeypatch.delenv("ARGUS_GITHUB_APP_ID", raising=False)
    monkeypatch.delenv("ARGUS_GITHUB_APP_PRIVATE_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ARGUS_GITHUB_APP_ID, ARGUS_GITHUB_APP_PRIVATE_KEY"):
        mint_for_repo(store, SHOP, transport=api.transport())
    assert api.calls == 0


def test_app_id_and_key_come_from_the_environment(store, api, keys, monkeypatch):  # noqa: F811
    store.apply(*installation("created", [SHOP]), "d-1")
    monkeypatch.setenv("ARGUS_GITHUB_APP_ID", APP_ID)
    monkeypatch.setenv("ARGUS_GITHUB_APP_PRIVATE_KEY", keys[0].replace("\n", "\\n"))
    assert mint_for_repo(store, SHOP, transport=api.transport()).tenant_id == "4242"


def test_a_bad_permission_profile_is_refused_before_any_http_call(store, api, keys):  # noqa: F811
    store.apply(*installation("created", [SHOP]), "d-1")
    with pytest.raises(ValueError):
        mint(store, SHOP, api, keys, profile="admin")
    assert api.calls == 0


# -- the four events ------------------------------------------------------------------------------------------


def test_added_and_removed_change_the_list_and_removal_revokes(store, api, keys):  # noqa: F811
    store.apply(*installation("created", [SHOP]), "d-1")
    with pytest.raises(RepoNotInstalled):
        mint(store, OTHER, api, keys)
    assert store.apply(*repositories("added", [OTHER]), "d-2") is True
    assert store.find(OTHER).installation_id == INSTALL_ID  # the mock GitHub only knows `shop`, so the lookup is what is checked
    calls = api.calls
    assert store.apply(*repositories("removed", [SHOP]), "d-3") is True
    with pytest.raises(RepoNotInstalled):
        mint(store, SHOP, api, keys)
    assert store.repos(INSTALL_ID) == [OTHER]
    assert api.calls == calls  # the refusal did not reach GitHub


def test_deleting_the_installation_revokes_every_repo(store, api, keys):  # noqa: F811
    store.apply(*installation("created", [SHOP, OTHER]), "d-1")
    assert store.apply(*installation("deleted", [SHOP, OTHER]), "d-2") is True
    for repo in (SHOP, OTHER):
        with pytest.raises(RepoNotInstalled):
            mint(store, repo, api, keys)
    assert api.calls == 0 and store.repos(INSTALL_ID) == []


def test_other_actions_and_events_change_nothing(store):
    for event, payload in (installation("suspend", [SHOP]), installation("unsuspend", [SHOP]), ("ping", {"zen": "x"}), ("issues", {"action": "opened"})):
        assert store.apply(event, payload, "d-x") is False
    with pytest.raises(RepoNotInstalled):
        store.find(SHOP)


def test_a_handled_event_with_no_installation_is_an_error_and_writes_nothing(store):
    with pytest.raises(KeyError):
        store.apply("installation", {"action": "created", "repositories": [{"full_name": SHOP}]}, "d-1")
    with pytest.raises(RepoNotInstalled):
        store.find(SHOP)


def test_removing_a_repo_of_another_installation_does_nothing(store):
    store.apply(*installation("created", [SHOP]), "d-1")
    store.apply(*repositories("removed", [SHOP], installation_id=INSTALL_ID + 1), "d-2")
    assert store.find(SHOP).installation_id == INSTALL_ID


def test_a_reinstall_moves_the_repo_to_the_new_installation(store):
    store.apply(*installation("created", [SHOP]), "d-1")  # the `deleted` event was lost
    store.apply(*installation("created", [SHOP], installation_id=INSTALL_ID + 1), "d-2")
    assert store.find(SHOP).installation_id == INSTALL_ID + 1


# -- a redelivery is a no-op ----------------------------------------------------------------------------------


def snapshot(store):
    with store._connect() as conn:
        return [conn.execute(f"select * from {t} order by 1").fetchall() for t in ("argus_installations", "argus_installation_repos", "argus_deliveries")]


def test_a_redelivered_event_changes_nothing(store):
    store.apply(*installation("created", [SHOP]), "d-1")
    before = snapshot(store)
    assert store.apply(*installation("created", [SHOP]), "d-1") is False
    assert snapshot(store) == before


def test_a_redelivered_created_cannot_undo_a_later_removal(store):
    store.apply(*installation("created", [SHOP]), "d-1")
    store.apply(*repositories("removed", [SHOP]), "d-2")
    assert store.apply(*installation("created", [SHOP]), "d-1") is False  # GitHub's redeliver button, later
    with pytest.raises(RepoNotInstalled):
        store.find(SHOP)


def test_the_same_event_without_a_delivery_id_is_still_idempotent(store):
    store.apply(*installation("created", [SHOP]))
    before = snapshot(store)
    store.apply(*installation("created", [SHOP]))
    assert snapshot(store) == before


def test_a_failed_write_does_not_mark_the_delivery_as_seen(store):
    event, payload = installation("created", [SHOP])
    payload["installation"]["account"] = {"id": 1}  # no login: fails after the delivery row was inserted
    with pytest.raises(KeyError):
        store.apply(event, payload, "d-1")
    assert store.apply(*installation("created", [SHOP]), "d-1") is True  # GitHub's retry goes through


# -- the tenant id --------------------------------------------------------------------------------------------


def test_the_tenant_is_the_account_id_and_survives_a_rename(store):
    store.apply(*installation("created", [SHOP]), "d-1")
    assert (store.find(SHOP).tenant_id, store.find(SHOP).account) == ("4242", "Acme")
    store.apply(*repositories("added", [OTHER], installation_id=INSTALL_ID), "d-2")
    renamed = {"login": "Acme-Inc", "id": 4242}
    store.apply(*installation("created", [SHOP], account=renamed), "d-3")
    assert (store.find(SHOP).tenant_id, store.find(OTHER).tenant_id) == ("4242", "4242")


# -- the webhook path ------------------------------------------------------------------------------------------

SECRET = "test-secret-not-real"


def post(client, event, payload, delivery="d-1", secret=SECRET):
    body = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return client.post("/webhook", content=body, headers={SIGNATURE_HEADER: sig, EVENT_HEADER: event, DELIVERY_HEADER: delivery})


@pytest.fixture
def seen(monkeypatch):
    monkeypatch.setenv(SECRET_ENV, SECRET)
    return []


def test_the_webhook_answers_202_and_records_after_the_response(seen):
    enqueuer = FakeEnqueuer()
    client = TestClient(create_app(enqueuer, on_installation=lambda e, p, d: seen.append((e, p["action"], d))))
    r = post(client, *installation("created", [SHOP]), delivery="d-9")
    assert (r.status_code, r.json()) == (202, {"status": "installation", "event": "installation", "action": "created"})
    assert seen == [("installation", "created", "d-9")] and enqueuer.calls == []  # not a ticket hint
    assert post(client, *repositories("added", [OTHER]), delivery="d-10").status_code == 202 and len(seen) == 2


def test_an_unsigned_or_wrongly_signed_installation_event_is_401_and_records_nothing(seen):
    client = TestClient(create_app(FakeEnqueuer(), on_installation=lambda *a: seen.append(a)))
    assert post(client, *installation("created", [SHOP]), secret="wrong").status_code == 401
    assert client.post("/webhook", json={}, headers={EVENT_HEADER: "installation"}).status_code == 401
    assert seen == []


def test_without_a_recorder_installation_events_are_ignored_like_before(seen):
    client = TestClient(create_app(FakeEnqueuer()))
    assert post(client, *installation("created", [SHOP])).json() == {"status": "ignored", "event": "installation"}


def test_a_failing_store_still_answers_202_and_logs_the_class_only(seen, caplog):
    url = "postgresql://owner:hunter2-not-real@db.invalid/flow"

    def boom(event, payload, delivery):
        raise RuntimeError(f"cannot connect to {url}")

    client = TestClient(create_app(FakeEnqueuer(), on_installation=boom))
    with caplog.at_level(logging.DEBUG):
        assert post(client, *installation("created", [SHOP])).status_code == 202
    assert "RuntimeError" in caplog.text and "hunter2" not in caplog.text and "db.invalid" not in caplog.text


def test_the_service_path_install_event_to_token(store, api, keys, seen):  # noqa: F811
    client = TestClient(create_app(FakeEnqueuer(), on_installation=store.apply))
    assert post(client, *installation("created", [SHOP]), delivery="d-1").status_code == 202
    assert mint(store, SHOP, api, keys).tenant_id == "4242"
    assert post(client, *repositories("removed", [SHOP]), delivery="d-2").status_code == 202
    with pytest.raises(RepoNotInstalled):
        mint(store, SHOP, api, keys)


# -- no token, key or URL in a log, an error or a repr -------------------------------------------------------------


def test_the_token_and_key_stay_out_of_logs_errors_and_reprs(store, api, keys, caplog):  # noqa: F811
    caplog.set_level(logging.DEBUG)
    store.apply(*installation("created", [SHOP]), "d-1")
    scoped = mint(store, SHOP, api, keys)
    text = [repr(scoped), str(scoped), repr(scoped.token), repr(store)]
    api.leak = scoped.token.token
    with pytest.raises(GitHubWriteError) as write_error:
        client_with(scoped.token.token, api, repo=OTHER).push_branch("argus/x", PATCH, "k")
    text.append(str(write_error.value))
    with pytest.raises(AppTokenError) as bad_key:  # a key that is not a key
        mint_for_repo(store, SHOP, app_id=APP_ID, private_key="not a pem " + keys[0][:60], transport=api.transport())
    text.append(str(bad_key.value))
    with pytest.raises(RepoNotInstalled) as missing:
        mint(store, OTHER, api, keys)
    text.append(str(missing.value))
    everything = "\n".join(text + [r.getMessage() for r in caplog.records])
    body = keys[0].split("-----")[2].strip().replace("\n", "")
    assert scoped.token.token not in everything and body[:40] not in everything and "eyJ" not in everything
    assert DATABASE_URL.split("@")[0].split(":")[-1] not in everything  # the database password
    assert redact(everything) == everything  # nothing in it has the shape of a token or an env secret
