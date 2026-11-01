"""Helpers that force a "suspended database" against a local Postgres (P6-T11, P6-T24).

Neon suspends its compute after 5 minutes idle: every connection is dropped, and the first new
connection wakes it. Two things imitate that without a Neon account:

- `terminate_connections(url)` ends every other session of the database with `pg_terminate_backend`.
  It works against any Postgres reachable through `ARGUS_FLOW_DATABASE_URL`, a CI service container
  included.
- `Container` stops and starts the Docker container named in `ARGUS_FLOW_TEST_CONTAINER`, so the
  server itself is gone for a while: refused or timed-out connections, then a server that starts
  again. It touches only that one container, and only if its name starts with `argus-p6-pg-`.

Neither is a real Neon suspend; they are the closest local stand-in. See docs/notes/p6-t11.md.
"""

from __future__ import annotations

import contextlib
import logging
import os
import subprocess
import threading
import time

import psycopg
import pytest
from dbos._logger import dbos_logger

from flow.fakes import FakeGitHub, FakeRunner
from flow.workflow import Deps, Outcome

CONTAINER_ENV = "ARGUS_FLOW_TEST_CONTAINER"
NAME_PREFIX = "argus-p6-pg-"


def terminate_connections(url: str) -> int:
    """End every other session in this database and return how many there were."""
    with psycopg.connect(url, autocommit=True, connect_timeout=5) as conn:
        return conn.execute(
            "select count(pg_terminate_backend(pid)) from pg_stat_activity"
            " where pid <> pg_backend_pid() and datname = current_database()"
        ).fetchone()[0]


class Container:
    def __init__(self, name: str) -> None:
        assert name.startswith(NAME_PREFIX), f"{CONTAINER_ENV} must name a container that starts with {NAME_PREFIX}"
        self.name = name
        self.stopped_at = self.started_at = 0.0  # time.monotonic() when `docker stop` / `docker start` returned

    def _docker(self, *args: str) -> None:
        subprocess.run(["docker", *args, self.name], check=True, capture_output=True, timeout=60)

    def stop(self) -> None:
        self._docker("stop")
        self.stopped_at = time.monotonic()

    def start(self) -> None:
        self._docker("start")
        if self.started_at < self.stopped_at:  # the first start after a stop; a later no-op start does not move it
            self.started_at = time.monotonic()  # the process is up; it may need a moment more to accept connections

    @property
    def down_seconds(self) -> float:
        return self.started_at - self.stopped_at

    def start_later(self, seconds: float) -> threading.Thread:
        """Start the server again after `seconds`, from another thread, and return that thread."""

        def later() -> None:
            time.sleep(seconds)
            self.start()

        thread = threading.Thread(target=later, name="restart-container", daemon=True)
        thread.start()
        return thread


def container() -> Container:
    return Container(os.environ[CONTAINER_ENV])


needs_container = pytest.mark.skipif(
    not os.environ.get(CONTAINER_ENV), reason=f"{CONTAINER_ENV} is not set; needs a throwaway Docker Postgres to stop and start"
)


# --- a small world of fakes, and a way to see DBOS's own reconnect messages --------------------------


class World:
    """The fakes of one test, wired in as the workflow's deps (same shape as test_workflow.World)."""

    def __init__(self, repro: FakeRunner | None = None, fix: FakeRunner | None = None) -> None:
        self.repro = repro or FakeRunner(Outcome(True, "repro.sh"))
        self.fix = fix or FakeRunner(Outcome(True, "the patch"))
        self.verify = FakeRunner()
        self.github = FakeGitHub()
        self.deps = Deps(self.repro, self.fix, self.verify, self.github, qa_timeout_seconds=60.0)

    def assert_each_effect_happened_once(self, ticket: str) -> None:
        from flow.states import branch_name, effect_key

        assert len(self.repro.calls) == len(self.fix.calls) == len(self.verify.calls) == 1
        assert len(self.github.prs) == 1 and self.github.calls.count("create_draft_pr") == 1
        assert self.github.branches[branch_name(ticket)] == {effect_key(ticket, "push-branch")}
        assert len(self.github.comments) == 2 and self.github.labels[ticket] == "done"


@contextlib.contextmanager
def dbos_log_messages():
    """Collect what DBOS logs, e.g. 'Database connection failed: ... Retrying in 1.3s (attempt 1)'."""
    messages: list[str] = []

    class Collect(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            messages.append(record.getMessage())

    handler = Collect(level=logging.INFO)
    dbos_logger.addHandler(handler)
    try:
        yield messages
    finally:
        dbos_logger.removeHandler(handler)
