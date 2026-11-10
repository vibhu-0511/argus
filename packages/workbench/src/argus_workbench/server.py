"""The workbench web app: security guards, typed errors, the static page, and every router in `routes/`.

    app = create_app()                      # a fresh per-start token; tests pass token="test-token-not-secret"

Groups add `argus_workbench/routes/<name>.py` with a module-level `router` (a FastAPI APIRouter); `create_app`
finds it by `pkgutil`, so nobody edits this file. A route module that fails to import stops the start, loudly.
`GET /` serves static/index.html with the token in `<meta name="argus-token">`. `/static/*` serves the packaged
static/ directory; Starlette's StaticFiles refuses any path that resolves outside it. There is no CORS middleware:
a page on another origin never gets an `Access-Control-Allow-Origin` header.

Token and Host guards are in `security.py`; this module only wires them. Routes are read by the browser through
the typed JSON API under /api; the page never builds HTML from API text (textContent only).
"""

from __future__ import annotations

import html
import importlib
import pkgutil
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from argus_workbench import routes as routes_pkg
from argus_workbench import security
from argus_workbench.errors import install_handlers

STATIC = Path(__file__).with_name("static")
TOKEN_MARK = "{{ARGUS_TOKEN}}"


def include_route_modules(app: FastAPI, package) -> list[str]:
    """Include `router` of every module in `package` (sorted by name). Returns the module names that were included."""
    names = []
    for info in sorted(pkgutil.iter_modules(package.__path__), key=lambda i: i.name):
        module = importlib.import_module(f"{package.__name__}.{info.name}")
        router = getattr(module, "router", None)
        if router is not None:
            app.include_router(router)
            names.append(info.name)
    return names


def create_app(*, token: str | None = None) -> FastAPI:
    app = FastAPI(title="argus-workbench", docs_url=None, redoc_url=None, openapi_url=None)  # no /docs page: fewer routes to guard
    app.state.token = token or security.new_token()
    install_handlers(app)
    include_route_modules(app, routes_pkg)

    @app.get("/", include_in_schema=False)
    def index() -> HTMLResponse:
        page = (STATIC / "index.html").read_text(encoding="utf-8").replace(TOKEN_MARK, html.escape(app.state.token, quote=True))
        return HTMLResponse(page)

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    security.install(app, app.state.token)  # added last, so it is the outermost middleware
    return app
