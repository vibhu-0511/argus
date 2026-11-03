"""Tenant config `.argus.yml` (P8-T05): the four things Argus must know about a repo it has never seen.

    start:   the command that starts the app (run in the repo root, kept running until the run ends)
    test:    the command that runs the repo's tests (exit 0 means pass)
    routes:  paths that must answer once the app is up, for example /login
    budget:  how much one issue may cost: max_tokens (model tokens) and max_steps (agent tool calls)
    base_url (optional, default http://127.0.0.1:3000): where the app listens; only localhost is accepted

The file is strict: a field that is not listed is refused (a typo must not be silently ignored), every type is
checked as written (`"10"` is not an integer) and every problem is named by field.

Stable API for P8-T22 ("no test command configured"): `ConfigError` is the base class; `MissingFieldError`,
`UnknownFieldError`, `InvalidFieldError` and `ConfigNotFoundError` are its subclasses. `error.field` is the dotted
name of the first problem (`test`, `budget.max_tokens`, `routes.1`), `error.problems` lists all of them, and the
message reads `.argus.yml: missing required field 'test' (the test command)`. Do not reword these messages without
changing T22 with them.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

FILENAME = ".argus.yml"
DEFAULT_BASE_URL = "http://127.0.0.1:3000"
FIELD_HELP = {"start": "the start command", "test": "the test command", "routes": "the routes to check", "budget": "the budget",
              "budget.max_tokens": "model tokens per issue", "budget.max_steps": "agent steps per issue"}
_ROUTE = re.compile(r"/[^\s#]*")  # a path, not a URL: the host comes from base_url


@dataclass(frozen=True)
class Problem:
    field: str  # dotted: `test`, `budget.max_tokens`, `routes.1`; empty when the file as a whole is wrong
    kind: str  # `missing`, `unknown`, `invalid`, `syntax` or `not-found`
    message: str  # for example "missing required field 'test' (the test command)"


class ConfigError(ValueError):
    """`.argus.yml` is not usable. `field` and `kind` describe the first problem, `problems` has all of them."""

    def __init__(self, problems: list[Problem], source: str = FILENAME):
        self.problems = tuple(problems)
        self.field, self.kind = problems[0].field, problems[0].kind
        super().__init__(f"{source}: " + "; ".join(p.message for p in problems))


class MissingFieldError(ConfigError):
    """A required field is absent (the first problem is a `missing` one)."""


class UnknownFieldError(ConfigError):
    """A field that the file format does not have (the first problem is an `unknown` one)."""


class InvalidFieldError(ConfigError):
    """A field with the wrong type or value, or a file that is not a YAML mapping."""


class ConfigNotFoundError(ConfigError):
    """There is no `.argus.yml` at the path."""


_BY_KIND: dict[str, type[ConfigError]] = {"missing": MissingFieldError, "unknown": UnknownFieldError, "not-found": ConfigNotFoundError}


class Budget(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    max_tokens: int = Field(gt=0)
    max_steps: int = Field(gt=0)


class TenantConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    start: str
    test: str
    routes: list[str] = Field(min_length=1)
    budget: Budget
    base_url: str = DEFAULT_BASE_URL

    @field_validator("start", "test")
    @classmethod
    def _command(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be empty")
        return v.strip()

    @field_validator("routes")
    @classmethod
    def _routes(cls, v: list[str]) -> list[str]:
        for route in v:
            if not _ROUTE.fullmatch(route) or route.startswith("//"):
                raise ValueError(f"{route!r} is not a path that starts with / (the host comes from base_url)")
        return v

    @field_validator("base_url")
    @classmethod
    def _base_url(cls, v: str) -> str:
        u = urlparse(v)
        if u.scheme not in ("http", "https") or u.hostname not in ("localhost", "127.0.0.1", "::1") or u.username or u.password:
            raise ValueError("must be an http(s) URL on localhost or 127.0.0.1 without credentials")
        if u.path not in ("", "/") or u.query or u.fragment:
            raise ValueError("must be only scheme, host and port, put the paths under routes")
        return v.rstrip("/")


def _problem(error: dict) -> Problem:
    field = ".".join(str(part) for part in error["loc"])
    kind = error["type"]
    if kind == "missing":
        help_ = FIELD_HELP.get(field)
        return Problem(field, "missing", f"missing required field {field!r}" + (f" ({help_})" if help_ else ""))
    if kind == "extra_forbidden":
        known = ", ".join(Budget.model_fields if field.startswith("budget.") else TenantConfig.model_fields)
        return Problem(field, "unknown", f"unknown field {field!r} (known fields: {known})")
    return Problem(field, "invalid", f"field {field!r}: " + error["msg"].removeprefix("Value error, "))


def load_config_text(text: str, source: str = FILENAME) -> TenantConfig:
    """Parse and validate the text of a `.argus.yml`. Raises a `ConfigError` subclass; never returns a partial config."""
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ConfigError([Problem("", "syntax", "not valid YAML: " + str(e).splitlines()[0])], source) from None
    if raw is None:
        raw = {}  # an empty file is a file with every field missing
    if not isinstance(raw, dict):
        raise InvalidFieldError([Problem("", "invalid", "the file must be a YAML mapping of fields")], source)
    try:
        return TenantConfig.model_validate(raw)
    except ValidationError as e:
        problems = [_problem(err) for err in e.errors()]
        raise _BY_KIND.get(problems[0].kind, InvalidFieldError)(problems, source) from None


def load_config(path: Path | str) -> TenantConfig:
    """Read the file at `path` (a `.argus.yml`, or the repo folder that holds one)."""
    path = Path(path)
    if path.is_dir():
        path = path / FILENAME
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ConfigNotFoundError([Problem("", "not-found", f"file not found (add {FILENAME} to the repository root)")]) from None
    return load_config_text(text)
