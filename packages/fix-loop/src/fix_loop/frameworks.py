"""Fail when fix-loop depends on an agent framework."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

BANNED = (
    "langgraph",
    "langchain",
    "smolagents",
    "autogen",
    "crewai",
    "mini-swe-agent",
    "sweagent",
    "pydantic-ai",
    "llama-index",
    "llamaindex",
)


def package_name(spec: str) -> str:
    name = spec.strip().lower()
    for sep in "=<>!~[ ;":
        name = name.split(sep, 1)[0]
    return name


def banned(specs: list[str]) -> list[str]:
    found = []
    for spec in specs:
        name = package_name(spec)
        if any(name == item or name.startswith(item + "-") for item in BANNED):
            found.append(spec)
    return found


def dependency_names(text: str) -> list[str]:
    data = tomllib.loads(text)
    return list(data["project"]["dependencies"])


def main() -> int:
    path = Path(__file__).resolve().parents[2] / "pyproject.toml"
    found = banned(dependency_names(path.read_text(encoding="utf-8")))
    if found:
        print(", ".join(found), file=sys.stderr)
        return 1
    print("clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
