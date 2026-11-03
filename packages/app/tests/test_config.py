import re
from pathlib import Path

import pytest
import yaml
from argus_app.config import (
    ConfigError,
    ConfigNotFoundError,
    InvalidFieldError,
    MissingFieldError,
    UnknownFieldError,
    load_config,
    load_config_text,
)

ROOT = Path(__file__).resolve().parents[3]
ONBOARDING = ROOT / "docs" / "onboarding.md"
DOCS = ROOT / "packages" / "app" / "docs"
VALID = {"start": "npm run dev", "test": "npm test", "routes": ["/", "/login"], "budget": {"max_tokens": 1000, "max_steps": 5}}


def text(**change) -> str:
    return yaml.safe_dump({**VALID, **change})


def without(*names: str) -> str:
    return yaml.safe_dump({k: v for k, v in VALID.items() if k not in names})


def test_a_valid_config_loads_from_text_and_from_a_path(tmp_path):
    c = load_config_text(text())
    assert (c.start, c.test, c.routes, c.budget.max_tokens, c.budget.max_steps) == ("npm run dev", "npm test", ["/", "/login"], 1000, 5)
    assert c.base_url == "http://127.0.0.1:3000"
    (tmp_path / ".argus.yml").write_text(text(), encoding="utf-8")
    assert load_config(tmp_path / ".argus.yml") == load_config(tmp_path) == c  # a file or the repo folder


@pytest.mark.parametrize("field", ["start", "test", "routes", "budget"])
def test_each_missing_field_is_a_typed_error_that_names_it(field):
    with pytest.raises(MissingFieldError) as e:
        load_config_text(without(field))
    assert e.value.field == field and e.value.kind == "missing" and isinstance(e.value, ConfigError)
    assert str(e.value).startswith(f".argus.yml: missing required field '{field}'")


def test_the_missing_test_command_message_is_the_one_p8_t22_shows():
    with pytest.raises(MissingFieldError) as e:
        load_config_text(without("test"))
    assert str(e.value) == ".argus.yml: missing required field 'test' (the test command)"


def test_every_problem_is_listed_not_only_the_first():
    with pytest.raises(MissingFieldError) as e:
        load_config_text(without("start", "test"))
    assert [p.field for p in e.value.problems] == ["start", "test"]
    assert "'start'" in str(e.value) and "'test'" in str(e.value)


def test_an_empty_file_has_every_field_missing():
    with pytest.raises(MissingFieldError) as e:
        load_config_text("")
    assert [p.field for p in e.value.problems] == ["start", "test", "routes", "budget"]


@pytest.mark.parametrize("extra, name", [({"tset": "npm test"}, "tset"), ({"budget": {**VALID["budget"], "dollars": 3}}, "budget.dollars")])
def test_an_unknown_field_is_refused_and_named(extra, name):
    with pytest.raises(UnknownFieldError) as e:
        load_config_text(text(**extra))
    assert e.value.field == name and f"unknown field '{name}'" in str(e.value)


@pytest.mark.parametrize(
    "change, field",
    [
        ({"start": 5}, "start"),
        ({"test": ["npm", "test"]}, "test"),
        ({"start": "  "}, "start"),
        ({"routes": "/login"}, "routes"),
        ({"routes": []}, "routes"),
        ({"routes": ["/ok", "login"]}, "routes"),
        ({"routes": ["https://evil.example/"]}, "routes"),
        ({"routes": ["//evil.example/x"]}, "routes"),
        ({"budget": "cheap"}, "budget"),
        ({"budget": {"max_tokens": "1000", "max_steps": 5}}, "budget.max_tokens"),
        ({"budget": {"max_tokens": 1000, "max_steps": 0}}, "budget.max_steps"),
        ({"budget": {"max_tokens": -1, "max_steps": 5}}, "budget.max_tokens"),
        ({"budget": {"max_tokens": True, "max_steps": 5}}, "budget.max_tokens"),
        ({"budget": {"max_tokens": 1.5, "max_steps": 5}}, "budget.max_tokens"),
        ({"base_url": "https://example.com"}, "base_url"),
        ({"base_url": "http://localhost:3000/app"}, "base_url"),
        ({"base_url": "http://user:pw@localhost:3000"}, "base_url"),
    ],
)
def test_bad_types_and_values_are_refused_and_name_the_field(change, field):
    with pytest.raises(InvalidFieldError) as e:
        load_config_text(text(**change))
    assert e.value.field.split(".")[0] == field.split(".")[0] and e.value.problems[0].field.startswith(field) and e.value.kind == "invalid"


@pytest.mark.parametrize("budget", [{}, None])
def test_an_empty_budget_is_refused(budget):
    with pytest.raises(ConfigError) as e:
        load_config_text(text(budget=budget))
    assert e.value.field in ("budget", "budget.max_tokens")
    assert "max_tokens" in str(e.value) or "budget" in str(e.value)
    if budget == {}:
        assert [p.field for p in e.value.problems] == ["budget.max_tokens", "budget.max_steps"]


def test_a_localhost_base_url_is_accepted_and_trimmed():
    assert load_config_text(text(base_url="http://localhost:19080/")).base_url == "http://localhost:19080"


def test_not_a_mapping_bad_yaml_and_no_file(tmp_path):
    with pytest.raises(InvalidFieldError, match="must be a YAML mapping"):
        load_config_text("- a\n- b\n")
    with pytest.raises(ConfigError) as e:
        load_config_text("start: [unclosed")
    assert e.value.kind == "syntax"
    with pytest.raises(ConfigNotFoundError, match="add .argus.yml to the repository root"):
        load_config(tmp_path)


def test_the_error_classes_are_all_config_errors():
    assert all(issubclass(c, ConfigError) for c in (MissingFieldError, UnknownFieldError, InvalidFieldError, ConfigNotFoundError))
    assert issubclass(ConfigError, ValueError)


# --- the onboarding doc ------------------------------------------------------------------------------------------


def blocks() -> list[str]:
    return re.findall(r"```yaml\n(.*?)```", ONBOARDING.read_text(encoding="utf-8").replace("\r", ""), re.S)


def test_the_onboarding_doc_is_under_one_page():
    lines = ONBOARDING.read_text(encoding="utf-8").splitlines()
    assert len(lines) <= 60, len(lines)  # one printed page


def test_the_onboarding_examples_are_the_tested_files_and_the_config_is_valid():
    tenant, config = blocks()
    assert tenant == (DOCS / "tenant-workflow.yml").read_text(encoding="utf-8").replace("\r", "")
    assert config == (DOCS / "argus.example.yml").read_text(encoding="utf-8").replace("\r", "")
    assert load_config_text(config).routes == ["/", "/login"]
