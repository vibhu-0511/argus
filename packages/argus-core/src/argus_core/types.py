"""Ticket, Task, and Trajectory. A task is valid only when its checks fail before the fix and pass after it. A trajectory stores each step so a run can replay with no model call."""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Screenshot(_Model):
    media_type: str = Field(min_length=1)
    path: str = Field(min_length=1)

    @field_validator("path")
    @classmethod
    def relative_path(cls, value: str) -> str:
        path = PurePosixPath(value.replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("screenshot path must stay inside the task directory")
        return value


class Ticket(_Model):
    id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    screenshot: Screenshot | None = None


class CheckType(StrEnum):
    pixel_diff = "pixel_diff"
    bounding_box = "bounding_box"
    computed_style = "computed_style"


class Check(_Model):
    type: CheckType
    params: dict[str, Any] = Field(default_factory=dict)


class TaskSource(StrEnum):
    seeded = "seeded"
    mutated = "mutated"


class Tier(StrEnum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class TaskMeta(_Model):
    source: TaskSource
    archetype: str = Field(min_length=1)
    tier: Tier
    seed: int | None = None


class Task(_Model):
    id: str = Field(min_length=1)
    ticket: Ticket
    bug_patch: str = Field(min_length=1)
    golden_patch: str = Field(min_length=1)
    checks: list[Check] = Field(min_length=1)
    meta: TaskMeta


class StopReason(StrEnum):
    submit = "submit"
    step_cap = "step-cap"
    token_cap = "token-cap"
    quota_exceeded = "QuotaExceeded"
    stuck = "stuck"
    consecutive_timeout = "consecutive-timeout"
    retry_cap = "retry-cap"
    tool_unavailable = "tool-unavailable"
    summary = "summary"
    verify_reject = "verify-reject"


class TrajectoryMeta(_Model):
    run_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    model: str = Field(min_length=1)
    host: str = Field(min_length=1)
    prompt_hash: str = Field(min_length=1)
    git_commit: str = Field(min_length=1)
    seed: int | None = None


class TrajectoryStep(_Model):
    """One JSONL record. `tokens_cached` defaults to 0 when the field is omitted. `raw_response` keeps a rejected tool call visible to replay. `tier`, `host` and `model` say who served the call when a router chose; older records omit them."""

    index: int = Field(ge=0)
    kind: Literal["step"] = "step"
    tokens_in: int = Field(default=0, ge=0)
    tokens_out: int = Field(default=0, ge=0)
    tokens_cached: int = Field(default=0, ge=0)
    stop_reason: StopReason | None = None
    raw_response: str | None = None
    message: dict[str, Any] | None = None
    tool_name: str | None = None
    tool_error: str | None = None
    tier: str | None = None
    host: str | None = None
    model: str | None = None


class Trajectory(_Model):
    meta: TrajectoryMeta
    steps: list[TrajectoryStep]

    def to_jsonl(self) -> str:
        meta = {"kind": "meta", **self.meta.model_dump(mode="json")}
        lines = [json.dumps(meta, sort_keys=True)]
        lines.extend(
            step.model_dump_json() for step in self.steps
        )
        return "\n".join(lines) + "\n"

    @classmethod
    def from_jsonl(cls, text: str) -> Trajectory:
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
        if not rows or rows[0].pop("kind", None) != "meta":
            raise ValueError("trajectory JSONL must start with a meta record")
        steps = []
        for row in rows[1:]:
            if row.get("kind", "step") != "step":
                raise ValueError("trajectory step kind must be 'step'")
            steps.append(TrajectoryStep.model_validate(row))
        return cls(meta=TrajectoryMeta.model_validate(rows[0]), steps=steps)


def dump_schemas(directory: str) -> None:
    from pathlib import Path

    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    models = {"ticket": Ticket, "task": Task, "trajectory": Trajectory}
    for name, model in models.items():
        schema = model.model_json_schema()
        schema["$id"] = f"https://argus.local/schemas/{name}.schema.json"
        (out / f"{name}.schema.json").write_text(
            json.dumps(schema, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


__all__ = [
    "Check",
    "CheckType",
    "Screenshot",
    "StopReason",
    "Task",
    "TaskMeta",
    "TaskSource",
    "Ticket",
    "Tier",
    "Trajectory",
    "TrajectoryMeta",
    "TrajectoryStep",
    "ValidationError",
    "dump_schemas",
]
