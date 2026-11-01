"""stdio MCP server for locate() on spec 2026-07-28.

The document is process argv (``--html-file``). The tool takes a selector only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.shared.exceptions import MCPError
from mcp.types import UNSUPPORTED_PROTOCOL_VERSION, CallToolResult, TextContent

from dom2src_mcp.locate import Ambiguous, Location, NoSourceInfo, NotFound, UnsupportedSelector
from dom2src_mcp.locate import locate as resolve

SPEC_VERSION = "2026-07-28"


async def _only_spec_version(ctx, call_next):
    """This process speaks SPEC_VERSION only. Veto any other initialize offer."""
    if ctx.method == "initialize":
        requested = (ctx.params or {}).get("protocolVersion")
        if requested != SPEC_VERSION:
            raise MCPError(
                UNSUPPORTED_PROTOCOL_VERSION,
                f"protocol versions do not match: client {requested}, server {SPEC_VERSION}",
                {"supported": [SPEC_VERSION], "requested": requested},
            )
    return await call_next(ctx)


def _result(selector: str, html: str) -> CallToolResult:
    found = resolve(selector, html)
    if isinstance(found, Location):
        body: dict[str, object] = {"file": found.file, "line": found.line, "col": found.col}
        failed = False
    elif isinstance(found, NotFound):
        body = {"error": found.error, "message": f"no element matches {selector}"}
        failed = True
    elif isinstance(found, NoSourceInfo):
        body = {"error": found.error, "message": "matched element has no data-src"}
        failed = True
    elif isinstance(found, UnsupportedSelector):
        body = {"error": found.error, "message": f"{selector} is not #id or [data-testid=\"...\"]"}
        failed = True
    elif isinstance(found, Ambiguous):
        body = {
            "error": found.error,
            "message": f"{selector} has {len(found.candidates)} candidate source locations, ranked best first",
            "candidates": [
                {"file": item.file, "line": item.line, "col": item.col, "rank": item.rank}
                for item in found.candidates
            ],
        }
        failed = True
    else:
        raise TypeError(type(found).__name__)
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(body))],
        structured_content=body,
        is_error=failed,
    )


def server(html: str) -> MCPServer:
    mcp = MCPServer("dom2src", middleware=[_only_spec_version])

    @mcp.tool(name="locate")
    def locate(selector: str) -> CallToolResult:
        """Resolve one selector to the file and line stamped on data-src."""
        return _result(selector, html)

    return mcp


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="dom2src-mcp")
    parser.add_argument("--html-file", type=Path, required=True)
    args = parser.parse_args(argv)
    html = args.html_file.read_text(encoding="utf-8")
    server(html).run(transport="stdio")


if __name__ == "__main__":
    main()
