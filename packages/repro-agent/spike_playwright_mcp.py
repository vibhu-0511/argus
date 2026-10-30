# /// script
# requires-python = ">=3.12"
# dependencies = ["mcp==2.3.0"]
# ///
"""P1-T01 spike: MCP Python SDK 2.3.0 against pinned @playwright/mcp 0.0.83.

Launches the server, records the negotiated protocol version and the tool
names from this process, then calls browser_navigate and browser_snapshot.
Does not call browser_run_code_unsafe or browser_evaluate, and does not add
page.evaluate.
"""

from __future__ import annotations

import asyncio
import importlib.metadata
import json
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from mcp import Client, StdioServerParameters

SERVER_PACKAGE = "@playwright/mcp@0.0.83"
PAGE_TITLE = "argus-p1-spike"
TEXT_CAP = 400


def _version_of(result: Any) -> str | None:
    if result is None:
        return None
    data = result.model_dump(mode="json")
    value = data.get("protocol_version") or data.get("protocolVersion")
    return str(value) if value else None


def _text(result: Any) -> str:
    parts: list[str] = []
    for block in getattr(result, "content", None) or []:
        if getattr(block, "type", None) == "text" and getattr(block, "text", None):
            parts.append(block.text)
    text = "\n".join(parts)
    if len(text) <= TEXT_CAP:
        return text
    return text[:TEXT_CAP] + "…"


def _call_summary(result: Any) -> dict[str, Any]:
    return {"is_error": bool(result.is_error), "text_prefix": _text(result)}


async def _tool_names(client: Client) -> list[str]:
    names: list[str] = []
    cursor: str | None = None
    while True:
        page = await client.list_tools(cursor=cursor)
        names.extend(tool.name for tool in page.tools)
        cursor = page.next_cursor
        if not cursor:
            return names


def _serve_local_page() -> tuple[ThreadingHTTPServer, str]:
    body = (
        "<!doctype html><title>"
        + PAGE_TITLE
        + "</title><h1>"
        + PAGE_TITLE
        + "</h1>"
    ).encode()

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
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    return server, f"http://{host}:{port}/"


async def main() -> int:
    report: dict[str, Any] = {
        "mcp_sdk": importlib.metadata.version("mcp"),
        "server_package": SERVER_PACKAGE,
        "launch": ["npx", "-y", SERVER_PACKAGE, "--headless", "--isolated"],
    }
    page_server, navigate_url = _serve_local_page()
    report["navigate_url"] = navigate_url
    # The server writes its snapshot file into its cwd. Keep that out of the repo.
    scratch = tempfile.TemporaryDirectory(prefix="argus-p1-spike-")
    params = StdioServerParameters(
        command="npx",
        args=["-y", SERVER_PACKAGE, "--headless", "--isolated"],
        cwd=scratch.name,
    )
    try:
        async with Client(params, read_timeout_seconds=180) as client:
            session = client.session
            initialize_result = getattr(session, "initialize_result", None)
            discover_result = getattr(session, "discover_result", None)
            info = client.server_info
            report["protocol_version"] = client.protocol_version
            report["initialize_protocol_version"] = _version_of(initialize_result)
            report["discover_protocol_version"] = _version_of(discover_result)
            report["handshake"] = "initialize" if initialize_result is not None else "discover"
            report["server_info"] = (
                None
                if info is None
                else {"name": info.name, "version": info.version}
            )
            names = await _tool_names(client)
            report["tools"] = names
            report["browser_run_code_unsafe_present"] = "browser_run_code_unsafe" in names
            if "browser_navigate" not in names or "browser_snapshot" not in names:
                report["error"] = "server tool list has no browser_navigate or browser_snapshot"
            else:
                navigate = await client.call_tool(
                    "browser_navigate",
                    {"url": navigate_url},
                    read_timeout_seconds=180,
                )
                snapshot = await client.call_tool(
                    "browser_snapshot",
                    None,
                    read_timeout_seconds=180,
                )
                report["navigate"] = _call_summary(navigate)
                report["snapshot"] = _call_summary(snapshot)
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        page_server.shutdown()
        try:
            scratch.cleanup()
        except OSError:
            pass

    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")
    navigate_ok = report.get("navigate", {}).get("is_error") is False
    snapshot_ok = report.get("snapshot", {}).get("is_error") is False
    saw_page = PAGE_TITLE in (
        (report.get("navigate", {}).get("text_prefix") or "")
        + (report.get("snapshot", {}).get("text_prefix") or "")
    )
    connected = "protocol_version" in report and "error" not in report
    return 0 if connected and navigate_ok and snapshot_ok and saw_page else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
