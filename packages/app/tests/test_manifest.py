import json
import re
from pathlib import Path

import pytest
from argus_app.cli import main
from argus_app.manifest import MANIFEST_PATH, ManifestError, fill, form_page, load_manifest
from flow.app_token import MINIMUM

ROOT = Path(__file__).resolve().parents[3]
ADR = ROOT / "docs" / "adr" / "0026-secrets-handling-and-token-scopes.md"
ENV = {
    "ARGUS_APP_HOMEPAGE_URL": "https://example.test/argus",
    "ARGUS_FLOW_SERVICE_URL": "https://flow.example.test",
    "ARGUS_APP_REDIRECT_URL": "http://localhost:8765/",
}


def adr_permissions() -> dict[str, str]:
    """The `Permission | Level` table under 'Token permission list' in ADR-026, as {api name: read|write}."""
    text = ADR.read_text(encoding="utf-8").replace("\r", "")
    section = text.split("### Token permission list (GitHub App)", 1)[1].split("\n### ", 1)[0]
    rows = re.findall(r"^\| ([A-Za-z ]+) \| (read|write)\b", section, re.M)
    return {name.strip().lower().replace(" ", "_"): level for name, level in rows if name.strip() != "Permission"}


def test_adr_table_is_parsed():
    assert adr_permissions() == {"actions": "write", "contents": "write", "issues": "write", "pull_requests": "write", "metadata": "read"}


def test_manifest_permissions_equal_the_adr_list():
    raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert raw["default_permissions"] == adr_permissions() == MINIMUM


@pytest.mark.parametrize("change", [{"administration": "read"}, {"workflows": "write"}, {"contents": "write", "secrets": "read"}])
def test_an_added_permission_fails(tmp_path, change):
    raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    raw["default_permissions"] = {**raw["default_permissions"], **change}
    p = tmp_path / "m.json"
    p.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ManifestError, match="committed minimum"):
        load_manifest(ENV, p)


def test_a_higher_level_or_a_removed_permission_fails(tmp_path):
    raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    raw["default_permissions"]["metadata"] = "write"
    p = tmp_path / "m.json"
    p.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ManifestError):
        load_manifest(ENV, p)
    del raw["default_permissions"]["metadata"]
    p.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ManifestError):
        load_manifest(ENV, p)


def test_webhook_points_at_the_flow_service_webhook_route():
    m = load_manifest(ENV)
    assert m.hook_attributes.url == "https://flow.example.test/webhook" and m.hook_attributes.active
    assert m.url == ENV["ARGUS_APP_HOMEPAGE_URL"] and m.redirect_url == ENV["ARGUS_APP_REDIRECT_URL"]


def test_no_url_is_committed():
    assert "http" not in MANIFEST_PATH.read_text(encoding="utf-8").replace("{{", "").lower().replace("/webhook", "")


@pytest.mark.parametrize("name", list(ENV))
def test_a_missing_variable_is_named(name):
    env = {k: v for k, v in ENV.items() if k != name}
    with pytest.raises(ManifestError, match=name):
        load_manifest(env)


def test_blank_variable_counts_as_missing():
    with pytest.raises(ManifestError, match="ARGUS_FLOW_SERVICE_URL"):
        load_manifest({**ENV, "ARGUS_FLOW_SERVICE_URL": "  "})


@pytest.mark.parametrize("key,value", [("ARGUS_FLOW_SERVICE_URL", "http://flow.example.test"), ("ARGUS_APP_HOMEPAGE_URL", "ftp://x.test"),
                                       ("ARGUS_FLOW_SERVICE_URL", "https://u:p@flow.example.test"), ("ARGUS_APP_REDIRECT_URL", "http://evil.test/")])
def test_bad_urls_are_refused(key, value):
    with pytest.raises(ManifestError):
        load_manifest({**ENV, key: value})


def test_a_value_cannot_break_out_of_the_json():
    out = json.loads(fill('{"a": "{{X}}"}', {"X": 'q"}, "b": "c'}))
    assert out == {"a": 'q"}, "b": "c'}


def test_events_need_only_the_granted_permissions():
    assert set(load_manifest(ENV).default_events) == {"issues", "pull_request", "pull_request_review", "pull_request_review_comment"}


def test_form_page_escapes_the_manifest():
    page = form_page(load_manifest(ENV), "abc")
    assert "https://github.com/settings/apps/new?state=abc" in page
    assert "&quot;default_permissions&quot;" in page and '"default_permissions"' not in page


def test_cli_manifest(monkeypatch, capsys):
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    assert main(["manifest"]) == 0
    assert json.loads(capsys.readouterr().out)["hook_attributes"]["url"] == "https://flow.example.test/webhook"
    assert main(["manifest", "--form"]) == 0
    assert capsys.readouterr().out.startswith("<!doctype html>")


def test_cli_manifest_without_env_exits_1(monkeypatch, capsys):
    for k in ENV:
        monkeypatch.delenv(k, raising=False)
    assert main(["manifest"]) == 1
    assert "ARGUS_FLOW_SERVICE_URL" in capsys.readouterr().err
    assert main(["manifest", "--bogus"]) == 2
