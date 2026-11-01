"""Tokens to list-price dollar equivalent, from the dated table in `prices.json`.

This is what the calls would cost at the vendor's public price. Free-tier runs
still get a number here. A model with no confirmed price is not in the table
and raises `UnknownModelPrice`; nothing is guessed.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

PRICES_PATH = Path(__file__).with_name("prices.json")


class UnknownModelPrice(KeyError):
    """The model has no row in prices.json."""


@lru_cache(maxsize=1)
def load_prices(path: Path = PRICES_PATH) -> dict[str, dict]:
    return json.loads(path.read_text(encoding="utf-8"))["models"]


def dollar_equivalent(model: str, tokens_in: int, tokens_out: int, tokens_cached: int = 0) -> float:
    """`tokens_in` is the total prompt size; `tokens_cached` is the part of it that hit the cache."""
    row = load_prices().get(model)
    if row is None:
        raise UnknownModelPrice(f"no price for model {model!r} in {PRICES_PATH.name}")
    if not 0 <= tokens_cached <= tokens_in:
        raise ValueError(f"tokens_cached {tokens_cached} must be between 0 and tokens_in {tokens_in}")
    cached_rate = row["cached_input"] if row["cached_input"] is not None else row["input"]
    fresh = tokens_in - tokens_cached
    return (fresh * row["input"] + tokens_cached * cached_rate + tokens_out * row["output"]) / 1_000_000
