import json
from pathlib import Path

import pytest
from pydantic import ValidationError

SCHEMAS = Path(__file__).resolve().parents[1] / "schemas"


def test_allow_list_is_the_six_repro_tools():
    from repro_agent.tools import ALLOW, ToolError, call_args

    assert ALLOW == (
        "navigate",
        "snapshot",
        "click",
        "type",
        "assert-visible",
        "screenshot",
    )
    blocked = call_args("browser_run_code_unsafe", {})
    assert isinstance(blocked, ToolError)
    assert blocked.error == "not-allowed"
    blocked = call_args("page.evaluate", {"expression": "1"})
    assert blocked.error == "not-allowed"


def test_snapshot_refs_include_frame_prefixes():
    from repro_agent.tools import resolve_target

    text = '- heading "Sign in" [level=1] [ref=f2e2]\n- button "Open" [ref=f2e6]\n- button "Open" [ref=f2e7]\n'
    assert resolve_target(text, role="heading", name="Sign in") == "f2e2"
    missed = resolve_target(text, ref="e999")
    assert missed.error == "stale-target"
    duplicate = resolve_target(text, role="button", name="Open")
    assert duplicate.error == "not-unique"


def test_snapshot_requires_a_depth_or_byte_cap():
    from repro_agent.tools import SnapshotArgs

    with pytest.raises(ValidationError):
        SnapshotArgs.model_validate({})
    SnapshotArgs.model_validate({"max_bytes": 200})
    SnapshotArgs.model_validate({"depth": 2})


def test_assert_visible_is_role_plus_accessible_name():
    from repro_agent.tools import AssertVisibleArgs

    with pytest.raises(ValidationError):
        AssertVisibleArgs.model_validate({"role": "button"})
    args = AssertVisibleArgs.model_validate({"role": "button", "name": "Sign in"})
    assert args.role == "button"
    assert args.name == "Sign in"


def test_schema_files_match_models_and_validate(tmp_path: Path):
    from jsonschema import Draft202012Validator

    from repro_agent.tools import dump_schemas

    examples = {
        "navigate": {"url": "http://127.0.0.1/login"},
        "snapshot": {"max_bytes": 200},
        "click": {"role": "button", "name": "Sign in"},
        "type": {"role": "textbox", "name": "Username", "text": "admin"},
        "assert-visible": {"role": "heading", "name": "Sign in"},
        "screenshot": {},
        "tool-error": {"ok": False, "error": "stale-target", "message": "ref e9 is gone"},
    }
    dump_schemas(tmp_path)
    for name, example in examples.items():
        generated = json.loads((tmp_path / f"{name}.schema.json").read_text(encoding="utf-8"))
        committed = json.loads((SCHEMAS / f"{name}.schema.json").read_text(encoding="utf-8"))
        assert generated == committed
        Draft202012Validator.check_schema(committed)
        Draft202012Validator(committed).validate(example)
