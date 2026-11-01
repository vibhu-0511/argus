"""Older MCP client: the handshake fails with a version error, not a hang."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters
from mcp.shared.exceptions import MCPError

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from dom2src_mcp.server import SPEC_VERSION

HTML = '<a id="sign-in" data-src="apps/canvas/src/screens/Landing.tsx:40:3">Sign in</a>\n'
_HANDSHAKE_ERA = "2025-11-25"


def _pythonpath() -> str:
    src = str(SRC)
    current = os.environ.get("PYTHONPATH")
    if not current:
        return src
    return src + os.pathsep + current


def _old_mode() -> str:
    """Use 2025-11-25 when Client accepts it; otherwise the handshake-era mode."""
    try:
        Client(StdioServerParameters(command=sys.executable, args=["-V"]), mode=_HANDSHAKE_ERA)
    except ValueError as exc:
        if _HANDSHAKE_ERA not in str(exc):
            raise
        return "legacy"
    return _HANDSHAKE_ERA


async def _handshake(html_file: Path, mode: str) -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "dom2src_mcp.server", "--html-file", str(html_file)],
        env={"PYTHONPATH": _pythonpath()},
    )
    async with Client(params, mode=mode, read_timeout_seconds=10) as client:
        raise AssertionError(f"handshake succeeded at {client.protocol_version}")


def _mcp_text(exc: BaseException) -> str:
    """The handshake error, including one nested in the stdio task-group teardown."""
    found: list[str] = []

    def walk(err: BaseException) -> None:
        if isinstance(err, MCPError):
            found.append(str(err))
        if isinstance(err, BaseExceptionGroup):
            for nested in err.exceptions:
                walk(nested)

    walk(exc)
    return "\n".join(found)


def test_old_client_handshake_version_error(tmp_path: Path) -> None:
    html_file = tmp_path / "page.html"
    html_file.write_text(HTML, encoding="utf-8")
    mode = _old_mode()
    with pytest.raises((MCPError, BaseExceptionGroup)) as caught:
        asyncio.run(_handshake(html_file, mode))
    text = _mcp_text(caught.value)
    assert text, caught.value
    assert "timed out" not in text.lower()
    names_version = SPEC_VERSION in text or _HANDSHAKE_ERA in text
    says_mismatch = "do not match" in text.lower() or "does not match" in text.lower()
    assert names_version or says_mismatch, text
