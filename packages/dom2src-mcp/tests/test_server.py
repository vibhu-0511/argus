"""Handshake and one locate() call against the stdio server."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from mcp import Client, StdioServerParameters

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from dom2src_mcp.server import SPEC_VERSION

HTML = '<a id="sign-in" data-src="apps/canvas/src/screens/Landing.tsx:40:3">Sign in</a>\n'
WRAPPER = (
    '<div id="page" data-src="apps/canvas/src/screens/Page.tsx:8:5">'
    '<button id="save" data-src="apps/canvas/src/ui/Button.tsx:4:3">Save</button>'
    "</div>\n"
)
SCHEMA = json.loads((Path(__file__).resolve().parents[1] / "schemas" / "locate.schema.json").read_text(encoding="utf-8"))


def _pythonpath() -> str:
    src = str(SRC)
    current = os.environ.get("PYTHONPATH")
    if not current:
        return src
    return src + os.pathsep + current


async def _call(html_file: Path, selector: str) -> tuple[bool, dict[str, object]]:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "dom2src_mcp.server", "--html-file", str(html_file)],
        env={"PYTHONPATH": _pythonpath()},
    )
    async with Client(params, mode="2026-07-28", read_timeout_seconds=30) as client:
        version = client.protocol_version
        assert version == "2026-07-28", version
        assert version == SPEC_VERSION
        result = await client.call_tool("locate", {"selector": selector})
        assert isinstance(result.structured_content, dict)
        return result.is_error, result.structured_content


def test_server_handshakes_and_locates(tmp_path: Path) -> None:
    html_file = tmp_path / "page.html"
    html_file.write_text(HTML, encoding="utf-8")
    failed, body = asyncio.run(_call(html_file, "#sign-in"))
    assert failed is False
    assert body["file"] == "apps/canvas/src/screens/Landing.tsx"
    assert body["line"] == 40


def test_ambiguous_wrapper_button_returns_ranked_candidates(tmp_path: Path) -> None:
    html_file = tmp_path / "page.html"
    html_file.write_text(WRAPPER, encoding="utf-8")
    failed, body = asyncio.run(_call(html_file, "#save"))
    assert failed is True
    assert body["error"] == "ambiguous"
    assert body["candidates"] == [
        {"file": "apps/canvas/src/screens/Page.tsx", "line": 8, "col": 5, "rank": 1},
        {"file": "apps/canvas/src/ui/Button.tsx", "line": 4, "col": 3, "rank": 2},
    ]
    Draft202012Validator(SCHEMA).validate(body)


def test_unsupported_selector_is_a_typed_error(tmp_path: Path) -> None:
    html_file = tmp_path / "page.html"
    html_file.write_text(HTML, encoding="utf-8")
    failed, body = asyncio.run(_call(html_file, "a.cta > span"))
    assert failed is True
    assert body["error"] == "unsupported-selector"
    assert "file" not in body
    Draft202012Validator(SCHEMA).validate(body)
