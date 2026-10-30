"""Repro tool schemas. The allow-list is the six tools below. `browser_run_code_unsafe` and `page.evaluate` are not tools."""

from __future__ import annotations

import json
import re
from enum import StrEnum
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

_NODE = re.compile(
    r'-\s+(?P<role>[A-Za-z][\w-]*)\s+"(?P<name>(?:\\.|[^"\\])*)"(?P<rest>[^\n]*)'
)
_REF = re.compile(r"\[ref=([A-Za-z0-9]+)\]")


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ToolErrorCode(StrEnum):
    stale_target = "stale-target"
    not_unique = "not-unique"
    not_found = "not-found"
    not_allowed = "not-allowed"
    failed = "failed"


class ToolError(_Model):
    """Typed failure from a repro tool. `stale-target` means the ref is gone. `not-unique` means the role and name match more than one node."""

    ok: Literal[False] = False
    error: ToolErrorCode
    message: str = Field(min_length=1)


class ToolResult(_Model):
    ok: Literal[True] = True
    tool: str
    text: str


class NavigateArgs(_Model):
    """Open an http or https URL."""

    url: str = Field(min_length=1, description="Absolute http or https URL.")

    @field_validator("url")
    @classmethod
    def http_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must be http or https")
        return value


class SnapshotArgs(_Model):
    """Read the accessibility snapshot. A call passes a depth, a byte cap, or both."""

    depth: int | None = Field(default=None, ge=1, description="Maximum depth of the snapshot tree.")
    max_bytes: int | None = Field(default=None, ge=1, description="Maximum UTF-8 bytes returned.")

    @model_validator(mode="after")
    def capped(self) -> SnapshotArgs:
        if self.depth is None and self.max_bytes is None:
            raise ValueError("snapshot requires a depth or a byte cap")
        return self


class ClickArgs(_Model):
    """Click the node with this role and accessible name, or this snapshot ref."""

    role: str | None = Field(default=None, description="Accessibility role, such as button.")
    name: str | None = Field(default=None, description="Accessible name.")
    ref: str | None = Field(default=None, description="Snapshot ref such as e12. A missing ref is stale-target.")

    @model_validator(mode="after")
    def target(self) -> ClickArgs:
        if self.ref or (self.role and self.name):
            return self
        raise ValueError("click needs a ref or a role and accessible name")


class TypeArgs(_Model):
    """Type text into the node with this role and accessible name."""

    role: str = Field(min_length=1, description="Accessibility role, such as textbox.")
    name: str = Field(min_length=1, description="Accessible name.")
    text: str = Field(min_length=1, description="Text to type.")
    ref: str | None = Field(default=None, description="Snapshot ref. A missing ref is stale-target.")


class AssertVisibleArgs(_Model):
    """Succeed when exactly one node has this role and accessible name."""

    role: str = Field(min_length=1, description="Accessibility role.")
    name: str = Field(min_length=1, description="Accessible name.")


class ScreenshotArgs(_Model):
    """Capture a screenshot of the page, or of the node with this role and accessible name."""

    role: str | None = Field(default=None, description="Accessibility role. Omit for the whole page.")
    name: str | None = Field(default=None, description="Accessible name. Required when role is set.")

    @model_validator(mode="after")
    def pair(self) -> ScreenshotArgs:
        if (self.role is None) != (self.name is None):
            raise ValueError("screenshot role and name are set together")
        return self


ALLOW = (
    "navigate",
    "snapshot",
    "click",
    "type",
    "assert-visible",
    "screenshot",
)

_ARGS: dict[str, type[_Model]] = {
    "navigate": NavigateArgs,
    "snapshot": SnapshotArgs,
    "click": ClickArgs,
    "type": TypeArgs,
    "assert-visible": AssertVisibleArgs,
    "screenshot": ScreenshotArgs,
}


def call_args(name: str, payload: dict) -> _Model | ToolError:
    if name not in ALLOW:
        return ToolError(error="not-allowed", message=f"{name} is not on the repro allow-list")
    return _ARGS[name].model_validate(payload)


def snapshot_nodes(text: str) -> list[tuple[str, str, str]]:
    found: list[tuple[str, str, str]] = []
    for match in _NODE.finditer(text):
        ref = _REF.search(match.group("rest"))
        if ref is None:
            continue
        found.append((match.group("role"), match.group("name"), ref.group(1)))
    return found


def resolve_target(
    snapshot: str,
    *,
    role: str | None = None,
    name: str | None = None,
    ref: str | None = None,
) -> str | ToolError:
    nodes = snapshot_nodes(snapshot)
    if ref is not None:
        if any(item[2] == ref for item in nodes):
            return ref
        return ToolError(error="stale-target", message=f"ref {ref} is not in the snapshot")
    matches = [item for item in nodes if item[0] == role and item[1] == name]
    if len(matches) > 1:
        return ToolError(
            error="not-unique",
            message=f'{role} "{name}" matches {len(matches)} nodes',
        )
    if not matches:
        return ToolError(error="not-found", message=f'{role} "{name}" is not in the snapshot')
    return matches[0][2]


def cap_text(text: str, max_bytes: int) -> str:
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    return encoded[:max_bytes].decode("utf-8", errors="ignore")


def dump_schemas(directory: str | Path) -> None:
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    models: dict[str, type[_Model]] = {**_ARGS, "tool-error": ToolError}
    for name, model in models.items():
        schema = model.model_json_schema()
        schema["$id"] = f"https://argus.local/schemas/repro/{name}.schema.json"
        (out / f"{name}.schema.json").write_text(
            json.dumps(schema, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


__all__ = [
    "ALLOW",
    "AssertVisibleArgs",
    "ClickArgs",
    "NavigateArgs",
    "ScreenshotArgs",
    "SnapshotArgs",
    "ToolError",
    "ToolErrorCode",
    "ToolResult",
    "TypeArgs",
    "ValidationError",
    "call_args",
    "cap_text",
    "dump_schemas",
    "resolve_target",
    "snapshot_nodes",
]
