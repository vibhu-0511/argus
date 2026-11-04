from datetime import datetime, timezone
from pathlib import Path

import pytest

from argus_core.ledger import Ledger, ModelQuota, QuotaExceeded, TenantBudget, TenantQuotaExceeded, Usage, load_quotas

ROOT = Path(__file__).resolve().parents[3]


def _quota(**overrides) -> ModelQuota:
    fields = dict(
        requests_per_day=10,
        tokens_per_day=100,
        requests_per_minute=10,
        tokens_per_minute=100,
        cached_counts=False,
    )
    fields.update(overrides)
    return ModelQuota(**fields)


def test_call_after_the_limit_makes_no_request(tmp_path: Path):
    sent: list[str] = []

    def send() -> Usage:
        sent.append("http")
        return Usage(1, 1, 0)

    ledger = Ledger(tmp_path / "ledger.json", {"m": _quota(requests_per_day=1)})
    ledger.call("m", send)
    with pytest.raises(QuotaExceeded):
        ledger.call("m", send)
    assert sent == ["http"]


def test_state_survives_restart(tmp_path: Path):
    path = tmp_path / "ledger.json"
    quotas = {"m": _quota(requests_per_day=1)}
    Ledger(path, quotas).call("m", lambda: Usage(1, 0, 0))
    sent: list[int] = []

    def send() -> Usage:
        sent.append(1)
        return Usage(1, 0, 0)

    with pytest.raises(QuotaExceeded):
        Ledger(path, quotas).call("m", send)
    assert sent == []


def test_cached_tokens_are_not_charged_when_the_quota_says_so(tmp_path: Path):
    path = tmp_path / "ledger.json"
    ledger = Ledger(path, {"m": _quota(tokens_per_day=5)})
    ledger.call("m", lambda: Usage(tokens_in=10, tokens_out=0, tokens_cached=8))
    state = ledger._state["models"]["m"]
    assert state["tokens"] == 2
    assert state["cached"] == 8


def test_unknown_model_is_refused_before_send(tmp_path: Path):
    sent: list[int] = []

    def send() -> Usage:
        sent.append(1)
        return Usage(1, 0, 0)

    ledger = Ledger(tmp_path / "ledger.json", {})
    with pytest.raises(QuotaExceeded):
        ledger.call("nope", send)
    assert sent == []


def test_day_boundary_resets_the_count(tmp_path: Path):
    path = tmp_path / "ledger.json"
    day_one = datetime(2026, 10, 29, 23, 0, tzinfo=timezone.utc)
    day_two = datetime(2026, 10, 30, 0, 1, tzinfo=timezone.utc)
    quotas = {"m": _quota(requests_per_day=1)}
    Ledger(path, quotas, now=lambda: day_one).call("m", lambda: Usage(1, 0, 0))
    Ledger(path, quotas, now=lambda: day_two).call("m", lambda: Usage(1, 0, 0))


def test_published_groq_table_loads_and_mistral_is_absent():
    quotas = load_quotas(ROOT / "docs" / "quotas.md")
    groq = quotas["openai/gpt-oss-20b"]
    assert groq.requests_per_day == 1000
    assert groq.tokens_per_day == 200000
    assert groq.cached_counts is False
    assert "mistral-small-latest" not in quotas


def test_cached_and_fresh_prompt_tokens_are_kept_apart(tmp_path: Path):
    path = tmp_path / "ledger.json"
    ledger = Ledger(path, {"m": _quota()})
    ledger.call("m", lambda: Usage(tokens_in=10, tokens_out=3, tokens_cached=8))
    ledger.call("m", lambda: Usage(tokens_in=10, tokens_out=3, tokens_cached=0))
    state = Ledger(path, {"m": _quota()})._state["models"]["m"]
    assert (state["cached"], state["fresh"]) == (8, 12)
    assert state["tokens"] == 26 - 8


def test_cached_tokens_count_toward_the_cap_only_when_cached_counts_is_true(tmp_path: Path):
    usage = Usage(tokens_in=10, tokens_out=0, tokens_cached=8)
    free = Ledger(tmp_path / "a.json", {"m": _quota(cached_counts=False)})
    paid = Ledger(tmp_path / "b.json", {"m": _quota(cached_counts=True)})
    free.call("m", lambda: usage)
    paid.call("m", lambda: usage)
    assert free._state["models"]["m"]["tokens"] == 2
    assert paid._state["models"]["m"]["tokens"] == 10
    assert paid._state["models"]["m"]["cached"] == 8


# --- P8-T07: per-tenant budgets and the fair-share rule -------------------------------------------------------------


def _calls(ledger, tenant: str, n: int, tokens: int = 1) -> None:
    for _ in range(n):
        ledger.for_tenant(tenant).call("m", lambda: Usage(tokens, 0, 0))


def test_tenant_at_its_budget_is_refused_and_named_while_a_second_tenant_proceeds(tmp_path: Path):
    budgets = {"acme": TenantBudget(2, 100), "globex": TenantBudget(2, 100)}
    ledger = Ledger(tmp_path / "l.json", {"m": _quota()}, budgets=budgets)
    _calls(ledger, "acme", 2)
    sent: list[int] = []

    def send() -> Usage:
        sent.append(1)
        return Usage(1, 0, 0)

    with pytest.raises(TenantQuotaExceeded) as refused:
        ledger.for_tenant("acme").call("m", send)
    assert sent == []  # refused before the HTTP call
    assert refused.value.tenant == "acme"
    assert "acme" in str(refused.value) and "tenant_requests_per_day" in str(refused.value)
    assert isinstance(refused.value, QuotaExceeded)  # loops and the router already catch this
    ledger.for_tenant("globex").call("m", send)
    assert sent == [1]


def test_tenant_token_budget_counts_over_all_models(tmp_path: Path):
    quotas = {"a": _quota(), "b": _quota()}
    ledger = Ledger(tmp_path / "l.json", quotas, budgets={"acme": TenantBudget(10, 5, 1.0)})
    ledger.for_tenant("acme").call("a", lambda: Usage(3, 0, 0))
    with pytest.raises(TenantQuotaExceeded, match="tenant acme"):
        ledger.for_tenant("acme").call("b", lambda: Usage(1, 0, 0), token_estimate=3)


def test_one_tenant_cannot_take_more_than_its_share_of_a_model(tmp_path: Path):
    quotas = {"m": _quota(requests_per_day=4, requests_per_minute=100)}
    budgets = {"acme": TenantBudget(100, 1000, 0.5), "globex": TenantBudget(100, 1000, 0.5)}
    ledger = Ledger(tmp_path / "l.json", quotas, budgets=budgets)
    _calls(ledger, "acme", 2)  # half of the 4 requests the host allows per day
    with pytest.raises(TenantQuotaExceeded, match="provider_share.requests_per_day"):
        _calls(ledger, "acme", 1)
    _calls(ledger, "globex", 2)  # the other half is still there


def test_the_shared_model_limit_counts_every_tenant(tmp_path: Path):
    quotas = {"m": _quota(requests_per_day=3)}
    budgets = {"acme": TenantBudget(100, 1000, 1.0), "globex": TenantBudget(100, 1000, 1.0)}
    ledger = Ledger(tmp_path / "l.json", quotas, budgets=budgets)
    _calls(ledger, "acme", 2)
    _calls(ledger, "globex", 1)
    with pytest.raises(QuotaExceeded) as refused:
        _calls(ledger, "acme", 1)
    assert not isinstance(refused.value, TenantQuotaExceeded)  # the host's limit, not a tenant's


def test_unlisted_tenant_is_refused_but_the_default_tenant_still_runs(tmp_path: Path):
    ledger = Ledger(tmp_path / "l.json", {"m": _quota()}, budgets={"acme": TenantBudget(5, 50)})
    with pytest.raises(TenantQuotaExceeded, match="unknown-tenant"):
        _calls(ledger, "stranger", 1)
    ledger.call("m", lambda: Usage(1, 0, 0))  # no tenant argument: the P0-P7 path


def test_default_tenant_state_keeps_the_old_layout_and_tenants_survive_a_restart(tmp_path: Path):
    path = tmp_path / "l.json"
    quotas = {"m": _quota()}
    budgets = {"acme": TenantBudget(1, 100)}
    first = Ledger(path, quotas, budgets=budgets)
    first.call("m", lambda: Usage(1, 0, 0))
    first.for_tenant("acme").call("m", lambda: Usage(1, 0, 0))
    assert first._state["models"]["m"]["requests"] == 1  # default tenant, unchanged place
    assert first._state["tenants"]["acme"]["m"]["requests"] == 1
    with pytest.raises(TenantQuotaExceeded):
        Ledger(path, quotas, budgets=budgets).for_tenant("acme").call("m", lambda: Usage(1, 0, 0))


def test_a_ledger_file_from_before_tenants_still_loads(tmp_path: Path):
    path = tmp_path / "l.json"
    path.write_text('{"day": "%s", "models": {}}' % datetime.now(timezone.utc).date().isoformat(), encoding="utf-8")
    Ledger(path, {"m": _quota()}).for_tenant("acme").call("m", lambda: Usage(1, 0, 0))


def test_budget_share_must_be_in_range():
    with pytest.raises(ValueError):
        TenantBudget(1, 1, 0)
    with pytest.raises(ValueError):
        TenantBudget(1, 1, 1.5)
