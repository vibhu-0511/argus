"""P6-T11: TLS to the database and reconnect after it was suspended, against a local Postgres.

Needs `ARGUS_FLOW_DATABASE_URL`; the stop/start test also needs `ARGUS_FLOW_TEST_CONTAINER` (a
throwaway container whose name starts with `argus-p6-pg-`). Neither is a real Neon suspend:
`suspend_support` explains the stand-ins and docs/notes/p6-t11.md what stays unverified.
"""

from __future__ import annotations

import os
import time
import uuid

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict

from flow import db_wake
from flow import dbos_runtime
from flow.config import DATABASE_URL_ENV, TLS_MODES, FlowSettings, dbos_config
from flow.dbos_runtime import launch, shutdown
from flow.db_wake import DatabaseUnavailable, wait_for_database
from flow.qa import send_qa_signal
from flow.workflow import Deps
from suspend_support import World, container, dbos_log_messages, needs_container, terminate_connections, within

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(not os.environ.get(DATABASE_URL_ENV), reason=f"{DATABASE_URL_ENV} is not set; needs a real Postgres"),
]


def small_pool_config(settings: FlowSettings):
    """The production config with a pool of 4 and a 3 s connect timeout, for these tests only.

    After every session is killed each DBOS thread opens a new TLS connection at once; with the default
    pool of 20 and a 10 s timeout, a loaded machine (Docker jobs next to it) turns that into timeouts and
    long backoffs. A small pool keeps the reconnect to a handful of handshakes. The pre-ping and
    `db_retry` under test are not changed. `connect_args` replaces DBOS's, so its application name is kept.
    """
    return {
        **dbos_config(settings),
        "sys_db_pool_size": 4,
        "db_engine_kwargs": {"connect_args": {"application_name": "dbos_transact", "connect_timeout": 3}},
    }


@pytest.fixture(scope="module")
def enqueuer():
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(dbos_runtime, "dbos_config", small_pool_config)
        enq = launch(FlowSettings.from_env(), Deps(None, None, None, None))
    yield enq
    shutdown()


@pytest.fixture
def world(enqueuer):
    from flow.workflow import set_deps

    w = World()
    set_deps(w.deps)
    return w


@pytest.fixture
def ticket():
    return f"acme/{uuid.uuid4().hex[:8]}#11"


def finish(enqueuer, ticket: str) -> dict:
    handle = enqueuer.enqueue(ticket)
    send_qa_signal(ticket, "approve", "review-comment", "1")
    return handle.get_result()


def test_dbos_talks_to_the_database_over_tls(enqueuer):
    url = os.environ[DATABASE_URL_ENV]
    if conninfo_to_dict(url).get("sslmode") not in TLS_MODES:
        pytest.skip("this local URL has no sslmode; point it at a Postgres with ssl=on and add ?sslmode=require")
    with psycopg.connect(url) as conn:
        rows = conn.execute(
            "select a.application_name, s.ssl, s.version from pg_stat_activity a join pg_stat_ssl s using (pid)"
            " where a.application_name = 'dbos_transact'"
        ).fetchall()
    assert rows, "DBOS has no open connection"
    assert all(ssl for _, ssl, _ in rows), rows
    print(f"\n{len(rows)} DBOS connections, all {rows[0][2]}")


def test_the_next_operation_after_every_connection_was_killed_reconnects(enqueuer, world, ticket):
    assert within(60, finish, enqueuer, f"{ticket}-warm")["state"] == "done"  # the pool now holds open connections
    killed = terminate_connections(os.environ[DATABASE_URL_ENV])
    assert killed >= 1
    started = time.monotonic()
    with dbos_log_messages() as log:
        out = within(60, finish, enqueuer, ticket)  # fails after 60 s instead of waiting in DBOS's retry
    took = time.monotonic() - started
    print(f"\nkilled {killed} sessions; enqueue and a full run afterwards took {took:.1f} s")
    assert out["state"] == "done"
    assert not [m for m in log if "Database connection failed" in m]  # pool_pre_ping replaced them before any query failed
    assert os.environ[DATABASE_URL_ENV].split(":")[2].split("@")[0] not in " ".join(log)  # the password


@needs_container
def test_a_stopped_server_fails_bounded_and_a_started_one_is_reached_again(enqueuer, world, ticket, monkeypatch):
    monkeypatch.setattr(db_wake, "ATTEMPTS", 2)
    monkeypatch.setattr(db_wake, "CONNECT_TIMEOUT_SECONDS", 2)
    server = container()
    server.stop()
    try:
        started = time.monotonic()
        with pytest.raises(DatabaseUnavailable, match="2 attempts"):
            enqueuer.enqueue(ticket)  # would block inside DBOS forever without the probe
        print(f"\nenqueue against a stopped server gave up after {time.monotonic() - started:.1f} s")
        assert world.repro.calls == []  # nothing ran
        monkeypatch.undo()
        restart = server.start_later(1)
        # the probe's own backoff, but with short waits so the test ends soon after the server is back
        attempt = wait_for_database(os.environ[DATABASE_URL_ENV], attempts=60, first_delay=0.25, max_delay=1.0, connect_timeout=2)
        restart.join()
        print(f"database answered on attempt {attempt}")
        assert attempt > 1
    finally:
        server.start()  # a no-op when it is already running
    print(f"server accepts plain connections {server.wait_ready(os.environ[DATABASE_URL_ENV]):.1f} s after the probe saw it")
    out = within(90, finish, enqueuer, ticket)  # the pool's connections died with the server; DBOS replaces them
    assert out["state"] == "done"
    world.assert_each_effect_happened_once(ticket)
