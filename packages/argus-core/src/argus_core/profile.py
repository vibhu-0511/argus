"""Read the active block in config/profiles.md. A non-openai-compatible wire format is refused."""

from __future__ import annotations

import os
import re
from pathlib import Path

import yaml

from argus_core.client import ModelClient


class ProfileError(ValueError):
    pass


def load_profiles(path: Path) -> tuple[str, dict[str, dict]]:
    text = path.read_text(encoding="utf-8")
    blocks = [
        yaml.safe_load(body)
        for body in re.findall(r"```yaml\n(.*?)```", text, flags=re.DOTALL)
    ]
    active = None
    named: dict[str, dict] = {}
    for block in blocks:
        if not isinstance(block, dict):
            continue
        if "name" in block:
            named[str(block["name"])] = block
        elif "active" in block:
            active = str(block["active"])
    if active not in named:
        raise ProfileError(f"active profile {active!r} is not in {path}")
    return active, named


def client_from_profile(
    profile: dict,
    *,
    host: str | None = None,
    api_key: str | None = None,
) -> ModelClient:
    if profile.get("wire_format") != "openai-compatible":
        raise ProfileError("wire_format must be openai-compatible")
    if host is None:
        base_url = str(profile.get("base_url") or "")
    else:
        base_url = str((profile.get("hosts") or {}).get(host) or "")
    if not base_url:
        raise ProfileError("base_url is empty")
    key = api_key if api_key is not None else os.environ.get(str(profile.get("key_env") or ""), "")
    return ModelClient(base_url, key)
