"""P6-T12: the Render service. Health without a database, refusing to start, the poll loop's life, the webhook.

Everything but the last test uses fakes for the engine (`start`) and needs no database and no network.
The last test starts the real service against the Postgres at `ARGUS_FLOW_DATABASE_URL` and is skipped
without it.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from fastapi.testclient import TestClient

from flow.config import DATABASE_URL_ENV, FlowSettings
from flow.db_wake import DatabaseUnavailable
from flow.enqueue import FakeEnqueuer
from flow import service
from flow.github_write import HttpGitHubClient
from flow.service import Engine, ServiceConfig, create_service_app, load_config, start_engine

REAL_URL = os.environ.get(DATABASE_URL_ENV)  # read at import: the `env` fixture replaces the variable with a fake
SECRET = "hook-secret-not-real"
PASSWORD = "pw-not-real-9f3a"
URL = f"postgresql://user:{PASSWORD}@localhost:5432/db"
BODY = b'{"action":"opened","issue":{"number":7},"repository":{"full_name":"acme/shop"}}'
ENV = {
    DATABASE_URL_ENV: URL,
    "GITHUB_WEBHOOK_SECRET": SECRET,
    "GITHUB_DISPATCH_TOKEN": "dispatch-token-not-real",
    "GITHUB_WRITE_TOKEN": "write-token-not-real",
    "GITHUB_TOKEN": "read-token-not-real",
    "ARGUS_FLOW_REPO": "acme/shop",
}


def sign(body: bytes) -> dict[str, str]:
    return {"X-Hub-Signature-256": "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()}


class FakePoller:
    def __init__(self, interval_s: float = 0.02) -> None:
        self.config = SimpleNamespace(interval_s=interval_s)
        self.calls = 0

    def poll_once(self) -> None:
        self.calls += 1


def fake_config() -> ServiceConfig:
    return ServiceConfig(FlowSettings(database_url=URL), repo="acme/shop", poll=None)


def wait_for(predicate, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


@pytest.fixture
def env(monkeypatch):
    for name in (DATABASE_URL_ENV, "ARGUS_FLOW_POLL_ENABLED", "ARGUS_FLOW_REPO", "GITHUB_TOKEN", "GITHUB_DISPATCH_TOKEN", "GITHUB_WRITE_TOKEN", "GITHUB_WEBHOOK_SECRET"):
        monkeypatch.delenv(name, raising=False)
    for name, value in ENV.items():
        monkeypatch.setenv(name, value)
    return monkeypatch


def test_health_answers_200_while_the_engine_is_still_starting_and_touches_no_database():
    release = threading.Event()
    started = threading.Event()

    def slow_start(cfg):
        started.set()
        release.wait(5)  # a database that is still waking up
        return Engine(FakeEnqueuer(), None)

    with TestClient(create_service_app(load=fake_config, start=slow_start)) as client:
        assert started.wait(3)
        response = client.get("/health")
        assert (response.status_code, response.json()) == (200, {"status": "ok", "engine": "starting"})
        release.set()
        assert wait_for(lambda: client.get("/health").json()["engine"] == "ready")


def test_health_is_503_when_the_engine_failed_to_start_and_the_log_has_no_secret(caplog):
    def broken_start(cfg):
        raise RuntimeError(f"could not connect to {URL}")  # a driver message that echoes the URL

    with caplog.at_level(logging.DEBUG), TestClient(create_service_app(load=fake_config, start=broken_start)) as client:
        assert wait_for(lambda: client.get("/health").status_code == 503)
        assert client.get("/health").json() == {"status": "error", "engine": "failed"}
    assert "RuntimeError" in caplog.text
    assert PASSWORD not in caplog.text


def test_a_database_that_never_answers_fails_health_with_the_class_only(caplog):
    def down(cfg):
        raise DatabaseUnavailable("database did not answer after 6 attempts (OperationalError)")

    with caplog.at_level(logging.DEBUG), TestClient(create_service_app(load=fake_config, start=down)) as client:
        assert wait_for(lambda: client.get("/health").status_code == 503)
    assert "DatabaseUnavailable" in caplog.text and PASSWORD not in caplog.text


def test_the_service_refuses_to_start_without_its_settings_and_names_only_variables(env):
    env.delenv("GITHUB_WEBHOOK_SECRET")
    env.delenv("GITHUB_DISPATCH_TOKEN")
    env.delenv("GITHUB_WRITE_TOKEN")
    with pytest.raises(RuntimeError) as raised, TestClient(create_service_app()):
        pass
    message = str(raised.value)
    assert "GITHUB_WEBHOOK_SECRET" in message and "GITHUB_DISPATCH_TOKEN" in message and "GITHUB_WRITE_TOKEN" in message
    assert PASSWORD not in message and SECRET not in message and ENV["GITHUB_TOKEN"] not in message


def test_the_service_refuses_a_remote_database_url_without_tls_and_does_not_echo_it(env):
    env.setenv(DATABASE_URL_ENV, f"postgresql://user:{PASSWORD}@db.example.test:5432/db")
    with pytest.raises(RuntimeError) as raised, TestClient(create_service_app()):
        pass
    assert "sslmode" in str(raised.value) and PASSWORD not in str(raised.value)


def test_load_config_with_everything_set(env):
    cfg = load_config()
    assert cfg.repo == "acme/shop" and cfg.poll is not None and cfg.poll.repo == "acme/shop"
    assert PASSWORD not in repr(cfg) and SECRET not in repr(cfg)


def test_polling_can_be_switched_off_and_then_needs_no_read_token(env):
    env.setenv("ARGUS_FLOW_POLL_ENABLED", "false")
    env.delenv("GITHUB_TOKEN")
    assert load_config().poll is None


def test_polling_on_needs_the_read_token(env):
    env.delenv("GITHUB_TOKEN")
    with pytest.raises(RuntimeError, match="GITHUB_TOKEN"):
        load_config()


def test_the_lifespan_starts_the_poll_loop_and_stops_it_and_the_engine_on_shutdown():
    poller, stopped = FakePoller(), []
    app = create_service_app(load=fake_config, start=lambda cfg: Engine(FakeEnqueuer(), poller), stop=lambda: stopped.append(1))
    with TestClient(app):
        assert wait_for(lambda: poller.calls >= 3), "the loop ran more than once at the short interval"
        assert stopped == []
    after = poller.calls
    time.sleep(0.15)
    assert poller.calls == after, "no poll after shutdown"
    assert stopped == [1]


def test_a_failing_poll_does_not_stop_the_loop():
    class Flaky(FakePoller):
        def poll_once(self):
            super().poll_once()
            raise RuntimeError("github is down")

    poller = Flaky()
    with TestClient(create_service_app(load=fake_config, start=lambda cfg: Engine(FakeEnqueuer(), poller), stop=lambda: None)):
        assert wait_for(lambda: poller.calls >= 3)


def test_the_webhook_is_mounted_and_rejects_a_bad_signature(env):
    enqueuer = FakeEnqueuer()
    app = create_service_app(load=fake_config, start=lambda cfg: Engine(enqueuer, None), stop=lambda: None)
    with TestClient(app) as client:
        assert wait_for(lambda: client.get("/health").json()["engine"] == "ready")
        bad = client.post("/webhook", content=BODY, headers={"X-Hub-Signature-256": "sha256=" + "0" * 64})
        assert bad.status_code == 401
        assert client.post("/webhook", content=BODY).status_code == 401
        assert enqueuer.calls == []
        good = client.post("/webhook", content=BODY, headers=sign(BODY))
        assert good.status_code == 202 and enqueuer.calls == ["acme/shop#7"]


def test_a_webhook_during_start_up_is_answered_202_and_enqueued_when_the_engine_is_ready(env):
    enqueuer = FakeEnqueuer()
    release = threading.Event()
    app = create_service_app(load=fake_config, start=lambda cfg: (release.wait(5), Engine(enqueuer, None))[1], stop=lambda: None)
    with TestClient(app) as client:
        threading.Timer(0.2, release.set).start()
        response = client.post("/webhook", content=BODY, headers=sign(BODY))  # returns after its background task
        assert response.status_code == 202
        assert enqueuer.calls == ["acme/shop#7"]


def test_start_engine_hands_the_workflow_the_real_github_client(env, monkeypatch):
    seen = []
    monkeypatch.setattr(service, "launch", lambda settings, deps: seen.append(deps) or FakeEnqueuer())
    start_engine(fake_config())
    (deps,) = seen
    assert isinstance(deps.github, HttpGitHubClient)
    assert ENV["GITHUB_WRITE_TOKEN"] not in repr(deps.github)


def test_render_blueprint_is_a_free_web_service_with_secrets_as_keys_only():
    blueprint = yaml.safe_load((Path(__file__).parents[3] / "render.yaml").read_text(encoding="utf-8"))
    (service,) = blueprint["services"]
    assert (service["type"], service["plan"], service["runtime"], service["healthCheckPath"]) == ("web", "free", "python", "/health")
    assert "flow.service:create_service_app" in service["startCommand"] and "--factory" in service["startCommand"]
    keys = {e["key"]: e for e in service["envVars"]}
    for name in (DATABASE_URL_ENV, "GITHUB_WEBHOOK_SECRET", "GITHUB_DISPATCH_TOKEN", "GITHUB_WRITE_TOKEN", "GITHUB_TOKEN"):
        assert keys[name] == {"key": name, "sync": False}, f"{name} must not carry a value"
    assert not [k for k in keys if k.startswith("DBOS") or "CONDUCTOR" in k.upper()]


@pytest.mark.postgres
@pytest.mark.skipif(not REAL_URL, reason=f"{DATABASE_URL_ENV} is not set; needs a real Postgres")
def test_the_whole_service_starts_against_a_real_postgres_and_stops(env, caplog):
    """Real wake-up probe, real DBOS launch, real `/health/db`. No ticket is enqueued, so no GitHub call is made."""
    real_url = REAL_URL
    env.setenv(DATABASE_URL_ENV, real_url)
    env.setenv("ARGUS_FLOW_POLL_ENABLED", "false")
    password = real_url.split(":")[2].split("@")[0]
    with caplog.at_level(logging.DEBUG), TestClient(create_service_app()) as client:
        assert wait_for(lambda: client.get("/health").json()["engine"] == "ready", timeout=120)
        assert client.get("/health/db").json() == {"database": "ok"}
        ping = b'{"zen":"hello"}'
        assert client.post("/webhook", content=ping, headers=sign(ping)).json()["status"] == "ignored"
    assert password not in caplog.text
