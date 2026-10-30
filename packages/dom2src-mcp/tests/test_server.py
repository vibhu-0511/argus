"""Handshake and one locate() call against the stdio server."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from mcp import Client, StdioServerParameters

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from dom2src_mcp.server import SPEC_VERSION

HTML = '<a id="sign-in" data-src="apps/canvas/src/screens/Landing.tsx:40:3">Sign in</a>\n'


def _pythonpath() -> str:
    src = str(SRC)
    current = os.environ.get("PYTHONPATH")
    if not current:
        return src
    return src + os.pathsep + current


async def _locate(html_file: Path) -> tuple[str, dict[str, object]]:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "dom2src_mcp.server", "--html-file", str(html_file)],
        env={"PYTHONPATH": _pythonpath()},
    )
    async with Client(params, mode="2026-07-28", read_timeout_seconds=30) as client:
        version = client.protocol_version
        assert version == "2026-07-28", version
        assert version == SPEC_VERSION
        result = await client.call_tool("locate", {"selector": "#sign-in"})
        assert result.is_error is False
        assert isinstance(result.structured_content, dict)
        return version, result.structured_content


def test_server_handshakes_and_locates(tmp_path: Path) -> None:
    html_file = tmp_path / "page.html"
    html_file.write_text(HTML, encoding="utf-8")
    version, body = asyncio.run(_locate(html_file))
    assert version == "2026-07-28"
    assert version == SPEC_VERSION
    assert body["file"] == "apps/canvas/src/screens/Landing.tsx"
    assert body["line"] == 40
