"""DBOS settings for argus-flow, decided before the first migration (P6-T03).

Three values are fixed in code on purpose: they must not change by accident between deploys.
Only the database URL comes from the environment (`ARGUS_FLOW_DATABASE_URL`); it carries a
password, so it is never logged, never put in an error message and never written to a file.

- `USE_LISTEN_NOTIFY = False`. DBOS creates its notification triggers when the system database is
  first created and the setting "may not be changed after" that. Polling works through any
  Postgres endpoint, including Neon's pooled one (pgbouncer does not carry LISTEN), and it leaves
  no long-lived LISTEN connection to go stale when Neon suspends the compute (T11, T24). The cost
  is up to `notification_listener_polling_interval_sec` (1 s default) of latency on `recv` and
  events, which is nothing against a QA wait that lasts hours. Whether polling keeps Neon awake is
  measured in T14. To switch later, reset the system database and migrate again.
- `APPLICATION_VERSION`: DBOS recovers only workflows of the current version, and its default is a
  hash of the workflow source. Pinned, a redeploy with new code still recovers old PENDING
  workflows. Bump it by hand only when a change makes old workflow histories unreplayable (the
  steps' order or names changed).
- `EXECUTOR_ID`: DBOS tags each workflow with its executor and a restarted process recovers only
  its own. Unset, DBOS uses "local". Explicit, a replaced Render instance claims the work of the
  one it replaces.

No conductor key: `dbos_config` never sets one. Notes: docs/notes/p6-t03.md.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dbos import DBOSConfig

DATABASE_URL_ENV = "ARGUS_FLOW_DATABASE_URL"
APP_NAME = "argus-flow"
APPLICATION_VERSION = "argus-flow-1"
EXECUTOR_ID = "argus-flow-0"
USE_LISTEN_NOTIFY = False


@dataclass(frozen=True)
class FlowSettings:
    database_url: str = ""

    def __repr__(self) -> str:  # the URL has a password in it
        return "FlowSettings(database_url=<set>)" if self.database_url else "FlowSettings(database_url=<unset>)"

    @classmethod
    def from_env(cls) -> FlowSettings:
        url = os.environ.get(DATABASE_URL_ENV, "")
        if not url:
            raise RuntimeError(f"{DATABASE_URL_ENV} is not set")
        return cls(database_url=url)


def dbos_config(settings: FlowSettings) -> DBOSConfig:
    return {
        "name": APP_NAME,
        "system_database_url": settings.database_url,
        "application_version": APPLICATION_VERSION,
        "executor_id": EXECUTOR_ID,
        "use_listen_notify": USE_LISTEN_NOTIFY,
    }
