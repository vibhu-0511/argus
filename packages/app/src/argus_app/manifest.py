"""GitHub App manifest (P8-T02): load, fill in the three owner-supplied URLs, validate, print.

`manifest.json` is the committed manifest. Three values are not known at commit time and are written as
`{{NAME}}` placeholders that are filled from environment variables: the service URL (the webhook goes to
`<service url>/webhook` on the P6 flow service), the App homepage and the redirect URL of the manifest flow.
A missing variable is an error; no default URL is invented.

The permission list is not decided here. It is the one `flow.app_token` enforces (`MINIMUM`, ADR-026): the
manifest is refused unless its `default_permissions` equal that list exactly, so a permission added to the JSON
fails at load. A test also compares both to the table in the ADR.

Registering the App from the manifest is an owner step: docs/notes/p8-t02-owner-steps.md.
"""
import html
import json
import os
import re
import secrets
import sys
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlparse

from flow.app_token import MINIMUM
from pydantic import BaseModel, ConfigDict, field_validator

MANIFEST_PATH = Path(__file__).with_name("manifest.json")
_PLACEHOLDER = re.compile(r"\{\{([A-Z0-9_]+)\}\}")
NEW_APP_URL = "https://github.com/settings/apps/new"  # personal account; an organization uses /organizations/<org>/settings/apps/new


class ManifestError(ValueError):
    """The manifest is not usable: a missing variable, a bad URL, or a permission list that is not the minimum."""


class HookAttributes(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str
    active: bool


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid")  # a field GitHub's manifest page does not list is a typo
    name: str
    url: str
    description: str
    public: bool
    hook_attributes: HookAttributes
    redirect_url: str
    request_oauth_on_install: bool
    setup_on_update: bool
    default_events: list[str]
    default_permissions: dict[str, str]

    @field_validator("default_permissions")
    @classmethod
    def _permissions(cls, v: dict[str, str]) -> dict[str, str]:
        if v != MINIMUM:
            raise ValueError(f"default_permissions must equal the committed minimum {MINIMUM} (ADR-026), got {v}")
        return v


def _check_url(label: str, value: str, *, https_only: bool) -> None:
    u = urlparse(value)
    ok = u.scheme == "https" or (not https_only and u.scheme == "http" and u.hostname in ("localhost", "127.0.0.1"))
    if not ok or not u.hostname or u.username or u.password:
        raise ManifestError(f"{label} must be an https URL without credentials" + ("" if https_only else " (http only for localhost)"))


def fill(raw: str, env: Mapping[str, str]) -> str:
    """Replace every `{{NAME}}` with `env[NAME]`; raise `ManifestError` naming each variable that is missing."""
    missing = sorted({n for n in _PLACEHOLDER.findall(raw) if not env.get(n, "").strip()})
    if missing:
        raise ManifestError("set these environment variables: " + ", ".join(missing))
    # json.dumps(...)[1:-1] escapes the value so it cannot break out of the JSON string
    return _PLACEHOLDER.sub(lambda m: json.dumps(env[m.group(1)].strip())[1:-1], raw)


def load_manifest(env: Mapping[str, str] | None = None, path: Path = MANIFEST_PATH) -> Manifest:
    """Read the manifest file, fill the placeholders from `env` (default: the process environment) and validate."""
    env = os.environ if env is None else env
    try:
        m = Manifest.model_validate_json(fill(path.read_text(encoding="utf-8"), env))
    except ValueError as e:
        if isinstance(e, ManifestError):
            raise
        raise ManifestError(str(e)) from None
    _check_url("url", m.url, https_only=True)
    _check_url("hook_attributes.url", m.hook_attributes.url, https_only=True)
    _check_url("redirect_url", m.redirect_url, https_only=False)
    return m


def form_page(manifest: Manifest, state: str) -> str:
    """A local HTML page that POSTs the manifest to GitHub (step 1 of the manifest flow). The owner opens it in a browser."""
    body = html.escape(json.dumps(manifest.model_dump(), indent=2), quote=True)
    return (
        "<!doctype html><meta charset=utf-8><title>Register argus-app</title>"
        f'<form method=post action="{html.escape(NEW_APP_URL)}?state={html.escape(state)}">'
        f'<input type=hidden name=manifest value="{body}">'
        "<button>Create the GitHub App</button></form>\n"
    )


def run(args: list[str]) -> int:
    """`argus-app manifest [--form]`: print the filled manifest JSON, or with `--form` the local registration page."""
    if args not in ([], ["--form"]):
        print("usage: argus-app manifest [--form]", file=sys.stderr)
        return 2
    try:
        m = load_manifest()
    except ManifestError as e:
        print(f"argus-app manifest: {e}", file=sys.stderr)
        return 1
    if args:
        state = secrets.token_urlsafe(16)
        print(f"state (GitHub echoes it back on the redirect; compare it): {state}", file=sys.stderr)
        sys.stdout.write(form_page(m, state))
    else:
        print(m.model_dump_json(indent=2))
    return 0
