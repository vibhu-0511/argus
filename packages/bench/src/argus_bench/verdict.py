"""JSON verdict from `bench score`. `log` is the check text, unsliced."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from argus_core.types import CheckType


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CheckResult(_Model):
    type: CheckType
    ok: bool
    reason: str


class Verdict(_Model):
    task_id: str = Field(min_length=1)
    ok: bool
    checks: list[CheckResult]
    log: str
