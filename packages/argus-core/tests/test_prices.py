import json

import pytest

from argus_core.prices import PRICES_PATH, UnknownModelPrice, dollar_equivalent, load_prices


def test_known_model():
    # 1M in at $0.15 + 1M out at $0.60
    assert dollar_equivalent("openai/gpt-oss-120b", 1_000_000, 1_000_000) == pytest.approx(0.75)


def test_cached_tokens_use_cached_rate_and_are_not_counted_twice():
    # 400k fresh at 0.15, 600k cached at 0.075, no output
    assert dollar_equivalent("openai/gpt-oss-120b", 1_000_000, 0, 600_000) == pytest.approx(0.4 * 0.15 + 0.6 * 0.075)


def test_model_without_cached_price_bills_cached_at_input_rate():
    assert dollar_equivalent("qwen/qwen3.8-27b", 1_000_000, 0, 1_000_000) == pytest.approx(0.80)


def test_cached_larger_than_input_is_rejected():
    with pytest.raises(ValueError):
        dollar_equivalent("openai/gpt-oss-20b", 10, 0, 11)


def test_unknown_model_raises():
    with pytest.raises(UnknownModelPrice):
        dollar_equivalent("devstral-2512", 1, 1)


def test_every_entry_has_url_and_date():
    models = load_prices()
    assert models
    for name, row in models.items():
        assert row["source"].startswith("https://"), name
        assert len(row["date"]) == 10 and row["date"][4] == "-", name
        assert row["input"] > 0 and row["output"] > 0, name
        assert json.loads(PRICES_PATH.read_text())["unit"]
