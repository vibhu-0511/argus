"""One call per repro tool against the sign-in surface from config/platform.md.

The page is served here. The test does not start the dcortex compose stack and does not edit that repo.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from repro_agent.browser import ReproBrowser
from repro_agent.tools import ToolError, ToolResult

_PAGE = """<!doctype html>
<html><head><title>Sign in</title></head>
<body>
<h1>Sign in</h1>
<label>Username <input /></label>
<button>Sign in</button>
<button>Open</button>
<button>Open</button>
</body></html>
"""


@pytest.fixture(scope="module")
def origin() -> str:
    body = _PAGE.encode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host, port = server.server_address[:2]
    yield f"http://{host}:{port}"
    server.shutdown()


@pytest.fixture(scope="module")
def session(origin: str):
    """Open, call, and close the MCP client on one task. anyio refuses a close from a second task."""
    loop = asyncio.new_event_loop()
    inbox: asyncio.Queue = asyncio.Queue()

    async def worker() -> None:
        browser = ReproBrowser()
        await browser.open()
        try:
            while True:
                job = await inbox.get()
                if job is None:
                    return
                name, payload, future = job
                try:
                    future.set_result(await browser.call(name, payload))
                except Exception as exc:
                    future.set_exception(exc)
        finally:
            await browser.close()

    def pump() -> None:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(worker())

    thread = threading.Thread(target=pump, daemon=True)
    thread.start()

    def call(name: str, payload: dict) -> ToolResult | ToolError:
        future: concurrent.futures.Future[ToolResult | ToolError] = concurrent.futures.Future()

        def enqueue() -> None:
            inbox.put_nowait((name, payload, future))

        loop.call_soon_threadsafe(enqueue)
        return future.result(timeout=120)

    yield origin, call
    loop.call_soon_threadsafe(inbox.put_nowait, None)
    thread.join(timeout=30)


def _login(origin: str, call) -> None:
    result = call("navigate", {"url": f"{origin}/login"})
    assert isinstance(result, ToolResult)


def test_navigate(session):
    origin, call = session
    result = call("navigate", {"url": f"{origin}/login"})
    assert isinstance(result, ToolResult)
    assert result.tool == "navigate"
    assert "/login" in result.text


def test_snapshot(session):
    origin, call = session
    _login(origin, call)
    result = call("snapshot", {"depth": 4, "max_bytes": 4000})
    assert isinstance(result, ToolResult)
    assert result.tool == "snapshot"
    assert "Sign in" in result.text
    assert len(result.text.encode("utf-8")) <= 4000
    capped = call("snapshot", {"max_bytes": 80})
    assert isinstance(capped, ToolResult)
    assert len(capped.text.encode("utf-8")) <= 80


def test_click(session):
    origin, call = session
    _login(origin, call)
    result = call("click", {"role": "button", "name": "Sign in"})
    assert isinstance(result, ToolResult)
    assert result.tool == "click"


def test_type(session):
    origin, call = session
    _login(origin, call)
    result = call("type", {"role": "textbox", "name": "Username", "text": "admin"})
    assert isinstance(result, ToolResult)
    assert result.tool == "type"


def test_assert_visible(session):
    origin, call = session
    _login(origin, call)
    result = call("assert-visible", {"role": "heading", "name": "Sign in"})
    assert isinstance(result, ToolResult)
    assert result.tool == "assert-visible"


def test_screenshot(session):
    origin, call = session
    _login(origin, call)
    result = call("screenshot", {"role": "button", "name": "Sign in"})
    assert isinstance(result, ToolResult)
    assert result.tool == "screenshot"


def test_stale_target(session):
    origin, call = session
    _login(origin, call)
    result = call("click", {"ref": "e999"})
    assert isinstance(result, ToolError)
    assert result.error == "stale-target"


def test_not_unique(session):
    origin, call = session
    _login(origin, call)
    result = call("assert-visible", {"role": "button", "name": "Open"})
    assert isinstance(result, ToolError)
    assert result.error == "not-unique"
