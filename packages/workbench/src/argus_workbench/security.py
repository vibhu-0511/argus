"""Request guards for a local-only server: Host allow-list, per-start token, Origin check, security headers.

What this defends: a web page in the person's own browser that tries to drive the workbench. A page on another
site cannot read the token (no CORS header is ever sent, and the index is only readable same-origin), cannot send
a request with a Host of its own after DNS rebinding (the Host allow-list), and cannot forge a POST (token and
Origin). What it does not defend: another program or user on the same machine (they can read the index and get
the token) and anything that is not 127.0.0.1. There is no login (ADR-031).

Order per request: Host (every method), then for POST, PUT, PATCH and DELETE the Origin (if one is sent) and the
token. Every refusal is the typed error body; every response, refusals and static files included, carries the
security headers. The token is random per server start, travels in the `X-Workbench-Token` header, reaches the
page in a meta tag of index.html, and is never put in a URL or logged in full (`mask`).

ponytail: the token is one secret per server start, not per session or per run. A shared machine needs a login.
"""

from __future__ import annotations

import hmac
import re
import secrets

from fastapi import FastAPI, Request
from starlette.responses import Response

from argus_workbench.errors import WorkbenchError, error_response

TOKEN_HEADER = "x-workbench-token"
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
# 127.0.0.1 or localhost, optional port. Anything else (evil.example, 127.0.0.1.evil.example, [::1], empty) is refused.
_HOST = re.compile(r"(127\.0\.0\.1|localhost)(:[0-9]{1,5})?")
_ORIGIN = re.compile(r"http://(127\.0\.0\.1|localhost)(:[0-9]{1,5})?")

# The workbench pages. default-src 'self' covers script, style, img, connect and frame (the report frame, same origin).
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-src 'self'; "
    "object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'self'"
)
# For the before/after report response itself (T07 sets it): inert page, no script, no network, own sandbox.
REPORT_CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:; sandbox; frame-ancestors 'self'"
HEADERS = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Cache-Control": "no-store",
}


def new_token() -> str:
    return secrets.token_urlsafe(32)


def mask(token: str) -> str:
    """The first four characters only. Use this wherever a token could reach a log or a message."""
    return token[:4] + "..."


def host_allowed(host: str | None) -> bool:
    return bool(host) and _HOST.fullmatch(host.lower()) is not None


def origin_allowed(origin: str) -> bool:
    return _ORIGIN.fullmatch(origin.lower()) is not None


def _check(request: Request, token: str) -> None:
    if not host_allowed(request.headers.get("host")):
        raise WorkbenchError("host_not_allowed", "the Host header must be 127.0.0.1 or localhost", field="host", status=403)
    if request.method not in UNSAFE_METHODS:
        return
    origin = request.headers.get("origin")
    if origin is not None and not origin_allowed(origin):
        raise WorkbenchError("origin_not_allowed", "the Origin header must be this server", field="origin", status=403)
    sent = request.headers.get(TOKEN_HEADER, "")
    if not sent or not hmac.compare_digest(sent.encode(), token.encode()):
        raise WorkbenchError("token_required", "send the per-start token in the X-Workbench-Token header", field="token", status=403)


def install(app: FastAPI, token: str) -> None:
    """Add the guards and headers as the outermost middleware of `app`."""

    @app.middleware("http")
    async def guard(request: Request, call_next) -> Response:
        try:
            _check(request, token)
            response = await call_next(request)
        except WorkbenchError as err:
            response = error_response(err)
        for name, value in HEADERS.items():
            response.headers.setdefault(name, value)  # a route (the report) may set its own, stricter value first
        return response
