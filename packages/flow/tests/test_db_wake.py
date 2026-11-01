"""P6-T11: the bounded wake-up probe. No database: `psycopg.connect` is replaced and time is a list."""

from __future__ import annotations

import logging

import psycopg
import pytest

from flow import db_wake
from flow.db_wake import DatabaseUnavailable, wait_for_database

URL = "postgresql://owner:hunter2@ep-quiet-dust-1.neon.tech/neondb?sslmode=require"


class FakeConnect:
    """Fails `failures` times with a driver error whose text carries the URL, then answers."""

    def __init__(self, failures: int) -> None:
        self.failures, self.calls, self.kwargs = failures, 0, []

    def __call__(self, url, **kwargs):
        self.calls += 1
        self.kwargs.append(kwargs)
        if self.calls <= self.failures:
            raise psycopg.OperationalError(f"connection failed: could not reach {URL}")
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql):
        assert sql == "select 1"


@pytest.fixture
def connect(monkeypatch):
    def install(failures: int) -> FakeConnect:
        fake = FakeConnect(failures)
        monkeypatch.setattr(db_wake.psycopg, "connect", fake)
        return fake

    return install


def test_an_awake_database_is_probed_once_with_a_short_connect_timeout(connect):
    fake, slept = connect(0), []
    assert wait_for_database(URL, sleep=slept.append) == 1
    assert fake.calls == 1 and slept == []
    assert fake.kwargs[0]["connect_timeout"] == db_wake.CONNECT_TIMEOUT_SECONDS == 5


def test_a_suspended_database_is_retried_with_doubling_delays_until_it_answers(connect, caplog):
    fake, slept = connect(3), []
    with caplog.at_level(logging.INFO, logger="flow.db_wake"):
        assert wait_for_database(URL, sleep=slept.append) == 4
    assert fake.calls == 4 and slept == [1.0, 2.0, 4.0]
    assert [r.levelno for r in caplog.records] == [logging.WARNING] * 3 + [logging.INFO]


def test_the_delay_is_capped(connect):
    slept = []
    connect(5)
    wait_for_database(URL, attempts=6, first_delay=4.0, max_delay=10.0, sleep=slept.append)
    assert slept == [4.0, 8.0, 10.0, 10.0, 10.0]


def test_it_gives_up_after_the_attempts_and_says_nothing_about_the_url(connect, caplog):
    fake, slept = connect(99), []
    with caplog.at_level(logging.DEBUG, logger="flow.db_wake"):
        with pytest.raises(DatabaseUnavailable) as e:
            wait_for_database(URL, attempts=3, sleep=slept.append)
    assert fake.calls == 3 and slept == [1.0, 2.0]  # no sleep after the last attempt
    assert "3 attempts" in str(e.value) and "OperationalError" in str(e.value)
    assert e.value.__suppress_context__ and e.value.__cause__ is None
    everything = str(e.value) + caplog.text
    assert "hunter2" not in everything and "neon.tech" not in everything and "owner" not in everything


def test_only_connection_errors_are_retried(monkeypatch):
    def broken(url, **kwargs):
        raise psycopg.ProgrammingError("bad option")

    monkeypatch.setattr(db_wake.psycopg, "connect", broken)
    with pytest.raises(psycopg.ProgrammingError):
        wait_for_database(URL, sleep=lambda s: pytest.fail("must not retry"))
