from datetime import datetime, timezone
from pathlib import Path

import pytest

from argus_core.ledger import Ledger, ModelQuota, QuotaExceeded, Usage, load_quotas

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
