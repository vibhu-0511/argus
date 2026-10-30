import json
from pathlib import Path

import pytest

SCHEMAS = Path(__file__).resolve().parents[1] / "schemas"
ERROR_CODES = ["not-found", "ambiguous", "no-source-info"]


def test_locate_schema_examples():
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import ValidationError

    schema = json.loads((SCHEMAS / "locate.schema.json").read_text(encoding="utf-8"))
    examples = json.loads((SCHEMAS / "locate.examples.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    assert list(schema["$defs"]["LocateErrorCode"]["enum"]) == ERROR_CODES
    assert set(examples) == {"input", "output", "errors"}
    assert set(examples["errors"]) == set(ERROR_CODES)

    validator.validate(examples["input"])
    validator.validate(examples["output"])
    for code in ERROR_CODES:
        body = examples["errors"][code]
        assert body["error"] == code
        assert body["message"]
        assert "file" not in body
        validator.validate(body)

    rejected = (
        {"error": "not-found", "message": "missing", "file": "apps/canvas/src/Guess.tsx"},
        {"file": "apps/canvas/src/screens/Landing.tsx", "line": 40, "col": 3, "tag": "Button"},
        {"file": "apps/canvas/src/screens/Landing.tsx:40:3:Button", "line": 40, "col": 3},
        {"file": "apps/canvas/src/screens/Landing.tsx", "line": 0, "col": 1},
        {"file": "apps/canvas/src/screens/Landing.tsx", "line": 1, "col": 0},
        {"error": "not-found", "message": ""},
        {"error": "guessed", "message": "no"},
        {},
        {"selector": ""},
    )
    for instance in rejected:
        with pytest.raises(ValidationError):
            validator.validate(instance)
