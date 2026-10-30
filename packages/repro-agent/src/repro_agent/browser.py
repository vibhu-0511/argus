"""Playwright MCP session for the six repro tools."""

from __future__ import annotations

import asyncio
import re
import tempfile
from pathlib import Path
from typing import Any

from mcp import Client, StdioServerParameters

from repro_agent.tools import (
    AssertVisibleArgs,
    ClickArgs,
    NavigateArgs,
    ScreenshotArgs,
    SnapshotArgs,
    ToolError,
    ToolResult,
    TypeArgs,
    call_args,
    cap_text,
    resolve_target,
)

_SERVER = "@playwright/mcp@0.0.83"
_SNAPSHOT_FILE = re.compile(r"\[Snapshot\]\(([^)]+)\)")


class ToolUnavailable(RuntimeError):
    """The Playwright MCP server died. One restart was already tried."""


def _text(result: Any) -> str:
    parts: list[str] = []
    for block in getattr(result, "content", None) or []:
        if getattr(block, "type", None) == "text" and getattr(block, "text", None):
            parts.append(block.text)
        elif getattr(block, "type", None) == "image":
            parts.append("image")
    return "\n".join(parts)


class ReproBrowser:
    """One Playwright MCP process. Calls stay on the allow-list."""

    def __init__(self, *, timeout: float = 120) -> None:
        self.timeout = timeout
        self._restarted = False
        self._client: Client | None = None
        self._cm: Client | None = None
        self._scratch: tempfile.TemporaryDirectory[str] | None = None

    async def open(self) -> None:
        self._scratch = tempfile.TemporaryDirectory(prefix="argus-repro-")
        params = StdioServerParameters(
            command="npx",
            args=["-y", _SERVER, "--headless", "--isolated"],
            cwd=self._scratch.name,
        )
        self._cm = Client(params, read_timeout_seconds=120)
        self._client = await self._cm.__aenter__()

    async def close(self) -> None:
        if self._cm is not None:
            await self._cm.__aexit__(None, None, None)
        self._cm = None
        self._client = None
        if self._scratch is not None:
            try:
                self._scratch.cleanup()
            except OSError:
                pass
            self._scratch = None

    async def call(self, name: str, payload: dict) -> ToolResult | ToolError:
        parsed = call_args(name, payload)
        if isinstance(parsed, ToolError):
            return parsed
        if isinstance(parsed, NavigateArgs):
            return await self._mcp(name, "browser_navigate", {"url": parsed.url})
        if isinstance(parsed, SnapshotArgs):
            return await self._snapshot(parsed)
        if isinstance(parsed, AssertVisibleArgs):
            return await self._visible(parsed)
        if isinstance(parsed, ClickArgs):
            return await self._click(parsed)
        if isinstance(parsed, TypeArgs):
            return await self._type(parsed)
        if isinstance(parsed, ScreenshotArgs):
            return await self._shot(parsed)
        return ToolError(error="not-allowed", message=f"{name} is not on the repro allow-list")

    async def _snapshot(self, args: SnapshotArgs) -> ToolResult | ToolError:
        payload: dict[str, int] = {}
        if args.depth is not None:
            payload["depth"] = args.depth
        result = await self._mcp("snapshot", "browser_snapshot", payload or None)
        if isinstance(result, ToolError) or args.max_bytes is None:
            return result
        return result.model_copy(update={"text": cap_text(result.text, args.max_bytes)})

    async def _visible(self, args: AssertVisibleArgs) -> ToolResult | ToolError:
        snap = await self._read_snapshot()
        if isinstance(snap, ToolError):
            return snap
        found = resolve_target(snap, role=args.role, name=args.name)
        if isinstance(found, ToolError):
            return found
        return ToolResult(tool="assert-visible", text=f'{args.role} "{args.name}" {found}')

    async def _click(self, args: ClickArgs) -> ToolResult | ToolError:
        ref = await self._ref(args.role, args.name, args.ref)
        if isinstance(ref, ToolError):
            return ref
        return await self._mcp("click", "browser_click", {"target": ref})

    async def _type(self, args: TypeArgs) -> ToolResult | ToolError:
        ref = await self._ref(args.role, args.name, args.ref)
        if isinstance(ref, ToolError):
            return ref
        return await self._mcp("type", "browser_type", {"target": ref, "text": args.text})

    async def _shot(self, args: ScreenshotArgs) -> ToolResult | ToolError:
        payload: dict[str, str] = {}
        if args.role is not None and args.name is not None:
            ref = await self._ref(args.role, args.name, None)
            if isinstance(ref, ToolError):
                return ref
            payload["target"] = ref
        return await self._mcp("screenshot", "browser_take_screenshot", payload or None)

    async def _ref(self, role: str | None, name: str | None, ref: str | None) -> str | ToolError:
        snap = await self._read_snapshot()
        if isinstance(snap, ToolError):
            return snap
        return resolve_target(snap, role=role, name=name, ref=ref)

    async def _read_snapshot(self) -> str | ToolError:
        result = await self._mcp("snapshot", "browser_snapshot", {"depth": 8})
        if isinstance(result, ToolError):
            return result
        return self._inline(result.text)

    def _inline(self, text: str) -> str:
        if "[ref=" in text and _SNAPSHOT_FILE.search(text) is None:
            return text
        roots: list[Path] = []
        if self._scratch is not None:
            roots.append(Path(self._scratch.name))
        roots.append(Path.cwd() / ".playwright-mcp")
        match = _SNAPSHOT_FILE.search(text)
        names: list[Path] = []
        if match:
            raw = match.group(1).replace("\\", "/")
            names.append(Path(raw))
            names.append(Path(Path(raw).name))
        for root in roots:
            for name in names:
                candidate = root / name
                if candidate.is_file():
                    return candidate.read_text(encoding="utf-8")
            if root.is_dir():
                files = [path for path in root.rglob("*.yml") if path.is_file()]
                if files:
                    newest = max(files, key=lambda path: path.stat().st_mtime)
                    body = newest.read_text(encoding="utf-8")
                    if "[ref=" in body:
                        return body
        return text

    async def _restart(self) -> None:
        await self.close()
        await self.open()

    async def _attempt(self, remote: str, payload: dict | None) -> Any:
        if self._client is None:
            raise ToolUnavailable("browser is not open")
        return await asyncio.wait_for(
            self._client.call_tool(remote, payload, read_timeout_seconds=self.timeout),
            timeout=self.timeout,
        )

    async def _mcp(self, tool: str, remote: str, payload: dict | None) -> ToolResult | ToolError:
        try:
            result = await self._attempt(remote, payload)
        except Exception:
            if self._restarted:
                raise ToolUnavailable("tool-unavailable") from None
            self._restarted = True
            try:
                await asyncio.wait_for(self._restart(), timeout=self.timeout)
                result = await self._attempt(remote, payload)
            except Exception:
                raise ToolUnavailable("tool-unavailable") from None
        text = _text(result)
        if result.is_error:
            return ToolError(error="failed", message=text or f"{remote} failed")
        return ToolResult(tool=tool, text=text)
