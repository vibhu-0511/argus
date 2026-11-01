"""P3-T02: one test per tool, plus schema files that validate."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

SCHEMAS = Path(__file__).resolve().parents[1] / "schemas"


def _tree(tmp_path: Path) -> Path:
    root = tmp_path / "work"
    root.mkdir()
    (root / "a.txt").write_text("alpha\nbeta\nalpha\n", encoding="utf-8", newline="\n")
    (root / "sub").mkdir()
    (root / "sub" / "b.txt").write_text("a  b\n", encoding="utf-8", newline="\n")
    return root


def test_read_file_returns_text_and_rejects_a_path_outside(tmp_path: Path):
    from fix_loop.tools import ToolError, call

    root = _tree(tmp_path)
    (tmp_path / "secret.txt").write_text("nope\n", encoding="utf-8", newline="\n")
    got = call("read_file", {"path": "a.txt"}, root)
    assert got.ok is True
    assert got.text == "alpha\nbeta\nalpha\n"
    outside = call("read_file", {"path": "../secret.txt"}, root)
    assert isinstance(outside, ToolError)
    assert outside.error == "outside-worktree"
    absolute = call("read_file", {"path": str(tmp_path / "secret.txt")}, root)
    assert isinstance(absolute, ToolError)
    assert absolute.error == "outside-worktree"


def test_list_dir_lists_names(tmp_path: Path):
    from fix_loop.tools import call

    root = _tree(tmp_path)
    got = call("list_dir", {"path": "."}, root)
    assert got.ok is True
    assert got.text.splitlines() == ["a.txt", "sub"]


def test_search_returns_file_and_line(tmp_path: Path):
    from fix_loop.tools import ToolError, call

    root = _tree(tmp_path)
    got = call("search", {"query": "beta"}, root)
    assert got.ok is True
    assert got.text == "a.txt:2:beta"
    missing = call("search", {"query": "no-such-text"}, root)
    assert isinstance(missing, ToolError)
    assert missing.error == "not-found"


def test_edit_replaces_one_exact_match_and_names_lines_when_not_unique(tmp_path: Path):
    from fix_loop.tools import ALLOW, ToolError, call

    root = _tree(tmp_path)
    assert ALLOW == ("read_file", "list_dir", "search", "edit", "run_cmd", "submit", "ast_grep")
    assert "write_file" not in ALLOW
    flexed = call("edit", {"path": "sub/b.txt", "old": "a b", "new": "nope"}, root)
    assert isinstance(flexed, ToolError)
    assert flexed.error == "not-found"
    assert (root / "sub" / "b.txt").read_text(encoding="utf-8") == "a  b\n"
    unique = call("edit", {"path": "sub/b.txt", "old": "a  b", "new": "a b"}, root)
    assert unique.ok is True
    assert (root / "sub" / "b.txt").read_text(encoding="utf-8") == "a b\n"
    repeated = call("edit", {"path": "a.txt", "old": "alpha", "new": "ALPHA"}, root)
    assert isinstance(repeated, ToolError)
    assert repeated.error == "not-unique"
    assert repeated.message == "a.txt matches lines 1, 3"
    assert (root / "a.txt").read_text(encoding="utf-8") == "alpha\nbeta\nalpha\n"
    outside = call("edit", {"path": "../secret.txt", "old": "a", "new": "b"}, root)
    assert isinstance(outside, ToolError)
    assert outside.error == "outside-worktree"


def test_run_cmd_runs_in_the_worktree(tmp_path: Path):
    from fix_loop.tools import call

    root = _tree(tmp_path)
    exe = sys.executable
    command = f'"{exe}" -c "print(open(\'a.txt\', encoding=\'utf-8\').read().splitlines()[1])"'
    got = call("run_cmd", {"command": command}, root)
    assert got.ok is True
    assert got.returncode == 0
    assert "beta" in got.text


def test_submit_marks_the_run(tmp_path: Path):
    from fix_loop.tools import call

    root = _tree(tmp_path)
    got = call("submit", {}, root)
    assert got.ok is True
    assert got.tool == "submit"
    assert got.text == "submitted"


def test_schema_files_match_models_and_validate(tmp_path: Path):
    from jsonschema import Draft202012Validator

    from fix_loop.tools import dump_schemas

    examples = {
        "read_file": {"path": "a.txt"},
        "list_dir": {"path": "."},
        "search": {"query": "beta"},
        "edit": {"path": "a.txt", "old": "beta", "new": "gamma"},
        "run_cmd": {"command": "echo hello"},
        "submit": {},
        "ast_grep": {"pattern": "import $NAME from $SRC", "path": "src/main.tsx", "lang": "tsx"},
        "tool-error": {"ok": False, "error": "not-unique", "message": "a.txt matches lines 1, 3"},
    }
    dump_schemas(tmp_path)
    for name, example in examples.items():
        generated = json.loads((tmp_path / f"{name}.schema.json").read_text(encoding="utf-8"))
        committed = json.loads((SCHEMAS / f"{name}.schema.json").read_text(encoding="utf-8"))
        assert generated == committed
        Draft202012Validator.check_schema(committed)
        Draft202012Validator(committed).validate(example)
