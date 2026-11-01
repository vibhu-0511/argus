"""P3-T03: ast-grep over the Canvas worktree, and a bad pattern is typed."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fix_loop.tools import ToolError, call

_REPO = Path(__file__).resolve().parents[3]


def _canvas() -> Path:
    text = (_REPO / "config" / "platform.md").read_text(encoding="utf-8")
    for line in text.splitlines():
        if not line.startswith("| Repo |"):
            continue
        start = line.find("`")
        end = line.find("`", start + 1)
        return Path(line[start + 1 : end]) / "apps" / "canvas"
    raise FileNotFoundError("config/platform.md has no Repo path")


def test_pattern_returns_file_and_line_and_a_bad_pattern_is_typed():
    root = _canvas()
    got = call(
        "ast_grep",
        {"pattern": "import $NAME from $SRC", "path": "src/main.tsx", "lang": "tsx"},
        root,
    )
    assert got.ok is True
    assert "src/main.tsx:1" in got.text.splitlines()
    bad = call("ast_grep", {"pattern": "(((((", "path": "src/main.tsx", "lang": "tsx"}, root)
    assert isinstance(bad, ToolError)
    assert bad.error == "bad-pattern"
