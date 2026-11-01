"""P6-T11: the service starts while the database is down (a cold Neon, a restarting server).

Without the wake-up probe `DBOS.launch()` fails after one 10 s connect attempt (probe in
docs/notes/p6-t11.md). Needs `ARGUS_FLOW_DATABASE_URL` and `ARGUS_FLOW_TEST_CONTAINER`.
"""

from __future__ import annotations

import logging
import os
import time
import uuid

import pytest

from flow.config import DATABASE_URL_ENV, FlowSettings
from flow.dbos_runtime import launch, shutdown
from flow.qa import send_qa_signal
from flow.workflow import set_deps
from suspend_support import World, container, dbos_log_messages, needs_container

pytestmark = [
    pytest.mark.postgres,
    needs_container,
    pytest.mark.skipif(not os.environ.get(DATABASE_URL_ENV), reason=f"{DATABASE_URL_ENV} is not set; needs a real Postgres"),
]


def test_launch_waits_for_a_database_that_is_down_and_then_runs_a_ticket(caplog):
    world, server = World(), container()
    ticket = f"acme/{uuid.uuid4().hex[:8]}#11"
    server.stop()
    restart = server.start_later(4)
    try:
        started = time.monotonic()
        with caplog.at_level(logging.INFO, logger="flow.db_wake"), dbos_log_messages() as dbos_log:
            enqueuer = launch(FlowSettings.from_env(), world.deps)
        restart.join()
        print(f"\nlaunch returned {time.monotonic() - started:.1f} s after the server was stopped (it restarted after 4 s)")
        assert "database not ready, attempt 1" in caplog.text and "database answered on attempt" in caplog.text
        password = os.environ[DATABASE_URL_ENV].split(":")[2].split("@")[0]
        assert password not in caplog.text + " ".join(dbos_log)
        set_deps(world.deps)
        handle = enqueuer.enqueue(ticket)
        send_qa_signal(ticket, "approve", "review-comment", "1")
        assert handle.get_result()["state"] == "done"
        world.assert_each_effect_happened_once(ticket)
    finally:
        server.start()
        shutdown()
