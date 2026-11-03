"""Wake a suspended database and wait for it, bounded (P6-T11).

Neon's free compute suspends after 5 minutes idle and starts again on the next connection. What
dbos 3.4.0 already does about that (read from the installed source, docs/notes/p6-t11.md):

- Its system-database engine has `pool_pre_ping=True`, so a pooled connection the server dropped is
  replaced on checkout.
- Every system-database operation (enqueue, step result, recv, ...) runs under `db_retry`: a lost
  connection is retried with exponential backoff (1 s doubling to 60 s, jittered) and NO deadline.
- Launch is not covered. `DBOS.launch()` connects once with a 10 s timeout and fails with the
  SQLAlchemy error; a cold database that answers slower, or a refused connection, kills the start.

So the only gap is bounded waiting. `wait_for_database` fills it with a plain connect-and-`select 1`
probe, retried with exponential backoff, a short per-attempt connect timeout and a limit on the
attempts. `flow.dbos_runtime.launch` calls it before DBOS starts, and `DbosEnqueuer.enqueue` calls it
before handing a ticket to DBOS, so a database that stays down turns into a `DatabaseUnavailable`
the webhook and poller already handle (the delivery id is forgotten; the poller repairs the miss)
instead of a thread blocked inside DBOS forever.

The URL has a password in it: it is never logged, and the error texts here name only the exception
class, because a driver message can carry host names.

ponytail: the probe opens one extra connection per enqueue. Fine at ticket rates; a pooled
connection or a cache of the last success would cut it if enqueues become frequent.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

import psycopg

log = logging.getLogger("flow.db_wake")

ATTEMPTS = 6  # with the delays below and 5 s connect timeouts: at most about 60 s before giving up
FIRST_DELAY_SECONDS = 1.0
MAX_DELAY_SECONDS = 15.0
CONNECT_TIMEOUT_SECONDS = 5  # per attempt; a Neon wake-up takes "a few hundred milliseconds"


class DatabaseUnavailable(RuntimeError):
    """The database did not answer within the attempts. The text never contains the URL."""


def wait_for_database(
    url: str,
    *,
    attempts: int | None = None,
    first_delay: float = FIRST_DELAY_SECONDS,
    max_delay: float = MAX_DELAY_SECONDS,
    connect_timeout: int | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Return the number of the attempt that got an answer, or raise `DatabaseUnavailable`."""
    attempts = ATTEMPTS if attempts is None else attempts
    connect_timeout = CONNECT_TIMEOUT_SECONDS if connect_timeout is None else connect_timeout
    delay = first_delay
    for attempt in range(1, attempts + 1):
        try:
            with psycopg.connect(url, connect_timeout=connect_timeout, autocommit=True) as conn:
                conn.execute("select 1")
        except psycopg.OperationalError as e:  # refused, timed out, or the server is starting or shutting down
            if attempt == attempts:
                log.error("database did not answer after %d attempts (%s)", attempts, type(e).__name__)
                raise DatabaseUnavailable(f"database did not answer after {attempts} attempts ({type(e).__name__})") from None
            log.warning("database not ready, attempt %d of %d (%s); retrying in %.1f s", attempt, attempts, type(e).__name__, delay)
            sleep(delay)
            delay = min(delay * 2, max_delay)
        else:
            if attempt > 1:
                log.info("database answered on attempt %d", attempt)
            return attempt
    raise DatabaseUnavailable("attempts must be at least 1")
