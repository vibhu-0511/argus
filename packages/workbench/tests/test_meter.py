"""P10-T06: the quota meter reads the argus-core ledger, or shows nothing. The ledger file in these tests is written by the real Ledger."""

import json
from datetime import UTC, datetime

import pytest
from argus_core.ledger import Ledger, ModelQuota, Usage, load_quotas
from fastapi.testclient import TestClient

from argus_workbench import fixtures, meter, store
from argus_workbench.server import create_app

NOW = datetime(2026, 5, 4, 12, 0, tzinfo=UTC)
MODEL = "openai/gpt-oss-20b"  # a model of docs/quotas.md


@pytest.fixture
def ledger_file(tmp_path, monkeypatch):
    path = tmp_path / "ledger.json"
    monkeypatch.setenv("ARGUS_WORKBENCH_LEDGER", str(path))
    return path


def real_ledger(path, **kw):
    return Ledger(path, {MODEL: ModelQuota(10**6, 10**9, 10**6, 10**9, False), "other/unlisted": ModelQuota(10**6, 10**9, 10**6, 10**9, False)}, now=lambda: NOW, **kw)


def test_rows_come_from_the_ledger_file_against_the_caps_in_docs_quotas(ledger_file):
    ledger = real_ledger(ledger_file)
    ledger.call(MODEL, lambda: Usage(1000, 200, 300))  # charged 900: cached tokens do not count (docs/quotas.md)
    rows, note = meter.ledger_rows(NOW)
    cap = load_quotas(meter._repo() / "docs" / "quotas.md")[MODEL].tokens_per_day
    assert rows == [{"model": MODEL, "limit": "tokens_per_day", "used": 900, "cap": cap, "percent": 0, "over": False, "illustrative": False}]
    assert "2026-05-04 UTC" in note


def test_tenant_use_counts_against_the_shared_cap(ledger_file):
    ledger = real_ledger(ledger_file)
    ledger.call(MODEL, lambda: Usage(500, 0), tenant="default")
    ledger.call(MODEL, lambda: Usage(250, 0), tenant="acme")
    (row,), _ = meter.ledger_rows(NOW)
    assert row["used"] == 750


def test_a_model_without_a_quota_row_has_no_cap_not_zero_percent(ledger_file):
    real_ledger(ledger_file).call("other/unlisted", lambda: Usage(100, 0))
    (row,), _ = meter.ledger_rows(NOW)
    assert row["cap"] is None and row["percent"] is None and row["over"] is False


def test_no_data_gives_no_rows_and_says_why(ledger_file, tmp_path):
    assert meter.ledger_rows(NOW) == ([], "no ledger file on this machine")
    ledger_file.write_text("{ not json", encoding="utf-8")
    assert meter.ledger_rows(NOW)[0] == []
    ledger_file.write_text(json.dumps({"day": "2026-05-03", "models": {MODEL: {"tokens": 5}}, "tenants": {}}), encoding="utf-8")
    rows, note = meter.ledger_rows(NOW)
    assert rows == [] and "2026-05-03" in note  # yesterday's file is not shown as today's usage
    ledger_file.write_text("[]", encoding="utf-8")
    assert meter.ledger_rows(NOW)[0] == []


def test_the_endpoint_shows_the_ledger_for_a_run_that_did_not_stop_on_quota(ledger_file):
    today = datetime.now(UTC)
    Ledger(ledger_file, {MODEL: ModelQuota(10**6, 10**9, 10**6, 10**9, False)}, now=lambda: today).call(MODEL, lambda: Usage(2000, 0))
    fixtures.write_fixture_run("stuck")
    view = TestClient(create_app(token="test-token-not-secret"), base_url="http://127.0.0.1").get("/api/runs/fixture-stuck").json()
    (row,) = view["meter"]["rows"]
    assert (row["model"], row["used"], row["illustrative"]) == (MODEL, 2000, False) and "not the usage of this run" in view["meter"]["note"]


def test_quota_stop_text_is_parsed_only_when_it_has_the_ledger_shape():
    row = meter.quota_stop_row("scripted-sim would exceed tokens_per_day: 120 of 100")
    assert (row["model"], row["used"], row["cap"], row["over"], row["percent"], row["illustrative"]) == ("scripted-sim", 120, 100, True, 100, True)
    assert meter.quota_stop_row("tenant acme: m would exceed provider_share.tokens_per_day: 5 of 4")["cap"] == 4
    for text in (None, "", "quota exceeded", "m would exceed tokens_per_day: x of 100", "evil <script> would exceed a: 1 of 2"):
        assert meter.quota_stop_row(text) is None
