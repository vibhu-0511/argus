"""P3-T26: an agent-framework dependency fails the check."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fix_loop.frameworks import banned, dependency_names

_PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def test_langgraph_is_banned_and_this_package_is_not():
    assert banned(["pydantic>=2.14.1", "langgraph"]) == ["langgraph"]
    assert banned(dependency_names(_PYPROJECT.read_text(encoding="utf-8"))) == []
