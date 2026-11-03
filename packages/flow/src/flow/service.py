"""The one ASGI app Render runs: webhook, health, DBOS and the poll loop (P6-T12).

    uvicorn --factory flow.service:create_service_app --host 0.0.0.0 --port $PORT

Start-up has two parts, so the port opens fast and a missing setting still stops the process:

1. Lifespan start, synchronous: `load_config` reads the environment. A missing or bad setting
   raises `RuntimeError` naming the variables (never their values) and uvicorn exits.
2. A background task starts the workflow engine: wake the database, launch DBOS with the pinned
   version and executor id and no conductor key (`flow.dbos_runtime.launch`), then run the poll
   loop. While it runs, `/health` already answers 200 with `"engine": "starting"`, and a webhook is
   answered 202 as always; its enqueue waits (bounded) for the engine in the background task.

`GET /health` never touches the database, so a Render cold start can be timed with it (T13). It is
503 only if the engine failed to start, so Render's health check restarts the instance.
`GET /health/db` does touch the database (and so wakes a suspended Neon compute).

The runners are the T04 `ActionsRunner` (repro, fix, verify). The workflow's GitHub write client
(push branch, find or create the draft PR, ready, close, comment, label) is `HttpGitHubClient`
(`flow.github_write`); it has not talked to the real GitHub yet (docs/notes/p6-t12.md).
The MCP QA tool (`flow.qa_mcp`) is not mounted; the review-comment path (T10) is.

Secrets are read from the environment only, and no log line or error text here carries a value.

ponytail: the poll loop runs only while the instance is awake (Render free sleeps after 15 min
idle), so it cannot wake the service; a webhook or an external ping does that (T13, T23).
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import NamedTuple

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from flow.actions import ActionsRunner
from flow.actions import TOKEN_ENV as DISPATCH_TOKEN_ENV
from flow.config import DATABASE_URL_ENV, FlowSettings
from flow.db_wake import DatabaseUnavailable, wait_for_database
from flow.dbos_runtime import launch, shutdown
from flow.enqueue import Enqueuer
from flow.github_read import TOKEN_ENV as READ_TOKEN_ENV
from flow.github_read import HttpGitHubReader
from flow.github_write import TOKEN_ENV as WRITE_TOKEN_ENV
from flow.github_write import HttpGitHubClient
from flow.installations import InstallationStore
from flow.reconcile import REPO_ENV, DbosLookup, PollConfig, Reconciler, poll_forever
from flow.review_comment import ReviewSignal, send_review_signal
from flow.webhook import SECRET_ENV as WEBHOOK_SECRET_ENV
from flow.webhook import create_app
from flow.workflow import Deps

log = logging.getLogger("flow.service")

POLL_ENABLED_ENV = "ARGUS_FLOW_POLL_ENABLED"
ENGINE_WAIT_SECONDS = 120.0  # how long a background enqueue waits for the engine: wake-up (about 60 s) plus DBOS launch
_OFF = frozenset({"0", "false", "no", "off"})


@dataclass(frozen=True)
class ServiceConfig:
    settings: FlowSettings
    repo: str
    poll: PollConfig | None  # None: the poll loop is off

    def __repr__(self) -> str:  # settings and repo are safe, the secrets are not held here
        return f"ServiceConfig(settings={self.settings!r}, repo={self.repo!r}, poll={'on' if self.poll else 'off'})"


def load_config() -> ServiceConfig:
    """Read and check every setting. Raises RuntimeError that names variables, never values."""
    polling = os.environ.get(POLL_ENABLED_ENV, "1").strip().lower() not in _OFF
    required = [DATABASE_URL_ENV, WEBHOOK_SECRET_ENV, DISPATCH_TOKEN_ENV, WRITE_TOKEN_ENV, REPO_ENV] + ([READ_TOKEN_ENV] if polling else [])
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError("missing required environment variables: " + ", ".join(missing))
    settings = FlowSettings.from_env()  # TLS and number checks; its messages name the variable only
    return ServiceConfig(settings, repo=os.environ[REPO_ENV], poll=PollConfig.from_env() if polling else None)


class Engine(NamedTuple):
    enqueuer: Enqueuer
    poller: Reconciler | None


def start_engine(cfg: ServiceConfig) -> Engine:
    """Blocking: wake the database, launch DBOS, build the poller. Run it in a thread."""
    runners = {step: ActionsRunner.from_env(step, repo=cfg.repo) for step in ("repro", "fix", "verify")}
    enqueuer = launch(cfg.settings, Deps(**runners, github=HttpGitHubClient.from_env(cfg.repo)))
    poller = Reconciler(HttpGitHubReader.from_env(), DbosLookup(), enqueuer, cfg.poll) if cfg.poll else None
    return Engine(enqueuer, poller)


class _State:
    """What the webhook's background tasks and the health routes share with the lifespan."""

    def __init__(self) -> None:
        self.ready = threading.Event()
        self.engine: Engine | None = None
        self.failed = False
        self.database_url = ""
        self.installations: InstallationStore | None = None

    def engine_or_wait(self) -> Engine:
        if not self.ready.wait(ENGINE_WAIT_SECONDS) or self.engine is None:
            raise RuntimeError("the workflow engine is not running")
        return self.engine


def create_service_app(
    load: Callable[[], ServiceConfig] = load_config,
    start: Callable[[ServiceConfig], Engine] = start_engine,
    stop: Callable[[], None] = shutdown,
) -> FastAPI:
    """The app. `load`, `start` and `stop` are the seams the tests replace; production uses the defaults."""
    state = _State()

    class LateEnqueuer:  # the webhook is built before the engine exists
        def enqueue_reconcile(self, ticket_id: str) -> None:
            state.engine_or_wait().enqueuer.enqueue_reconcile(ticket_id)

    def qa_send(signal: ReviewSignal) -> None:
        state.engine_or_wait()
        send_review_signal(signal)

    def record_installation(event: str, payload: dict, delivery_id: str | None) -> None:
        assert state.installations is not None  # set in the lifespan, before the first request
        state.installations.apply(event, payload, delivery_id)

    async def run_engine(cfg: ServiceConfig, quit_: asyncio.Event) -> None:
        try:
            state.engine = await asyncio.to_thread(start, cfg)
        except Exception as e:  # DatabaseUnavailable, DBOS launch errors; the type only, a message may echo a host
            state.failed = True
            log.error("workflow engine did not start (%s)", type(e).__name__)
            return
        state.ready.set()
        log.info("workflow engine started; poll loop %s", "on" if state.engine.poller else "off")
        if state.engine.poller:
            await poll_forever(state.engine.poller, quit_)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        cfg = load()  # raises: the service does not start with a missing setting
        state.database_url = cfg.settings.database_url
        state.installations = InstallationStore(cfg.settings.database_url)
        quit_ = asyncio.Event()
        task = asyncio.create_task(run_engine(cfg, quit_))
        yield
        quit_.set()
        await task  # the poll loop ends at its next wake-up; a start in progress finishes first
        if state.engine is not None:
            await asyncio.to_thread(stop)

    app = create_app(LateEnqueuer(), qa_send=qa_send, on_installation=record_installation)
    app.router.lifespan_context = lifespan

    @app.get("/health")
    async def health() -> JSONResponse:
        engine = "failed" if state.failed else "ready" if state.ready.is_set() else "starting"
        return JSONResponse({"status": "ok" if engine != "failed" else "error", "engine": engine}, status_code=503 if state.failed else 200)

    @app.get("/health/db")
    def health_db() -> JSONResponse:
        try:
            wait_for_database(state.database_url, attempts=1)
        except DatabaseUnavailable:
            return JSONResponse({"database": "unavailable"}, status_code=503)
        return JSONResponse({"database": "ok"})

    return app
