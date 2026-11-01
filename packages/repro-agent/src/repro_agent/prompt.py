"""Ticket prompts. The screenshot is attached only in image mode, and only when the bytes match the declared media type."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Literal

from argus_core.types import Ticket
from pydantic import BaseModel, ConfigDict

from repro_agent.tools import ToolError


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PromptImage(_Model):
    media_type: str
    data_base64: str


class Prompt(_Model):
    mode: Literal["text", "image"]
    text: str
    image: PromptImage | None = None


def _matches(data: bytes, media_type: str) -> bool:
    if media_type == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if media_type == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if media_type == "image/gif":
        return data.startswith((b"GIF87a", b"GIF89a"))
    if media_type == "image/webp":
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return False


def assemble_prompt(ticket: Ticket, mode: Literal["text", "image"], task_dir: Path) -> Prompt | ToolError:
    image = None
    if mode == "image" and ticket.screenshot is not None:
        shot = ticket.screenshot
        path = (task_dir / shot.path).resolve()
        if not path.is_relative_to(task_dir.resolve()):
            return ToolError(error="failed", message="screenshot path must stay inside the task directory")
        try:
            data = path.read_bytes()
        except OSError:
            return ToolError(error="failed", message="screenshot file is missing")
        if not _matches(data, shot.media_type):
            return ToolError(
                error="failed",
                message=f"screenshot bytes do not match {shot.media_type}",
            )
        image = PromptImage(media_type=shot.media_type, data_base64=base64.b64encode(data).decode("ascii"))
    return Prompt(mode=mode, text=ticket.text, image=image)
