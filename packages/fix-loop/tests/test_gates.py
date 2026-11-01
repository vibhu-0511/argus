"""P3-T14: a broken tree fails the gate that looks at it."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fix_loop.gates import NAMES, run_gates


def _pass() -> list[str]:
    return [sys.executable, "-c", "raise SystemExit(0)"]


def test_broken_tree_fails_typecheck_only(tmp_path: Path):
    (tmp_path / "marker.txt").write_text("bad\n", encoding="utf-8", newline="\n")
    check = (
        "import pathlib, sys; "
        "sys.exit(0 if pathlib.Path('marker.txt').read_text(encoding='utf-8') == 'ok\\n' else 1)"
    )
    commands = {name: _pass() for name in NAMES}
    commands["typecheck"] = [sys.executable, "-c", check]
    results = run_gates(tmp_path, commands)
    by_name = {item.name: item.ok for item in results}
    assert list(by_name) == list(NAMES)
    assert by_name["typecheck"] is False
    assert by_name["build"] is True
    assert by_name["lint"] is True
    assert by_name["unit"] is True
    assert by_name["bench"] is True
