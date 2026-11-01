"""Context budget. A strategy runs when a run has used 80% of the window."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

Strategy = Callable[[list[dict], int, int], list[dict]]


@dataclass(frozen=True)
class StepUsage:
    tokens_in: int
    tokens_out: int
    tokens_cached: int

    @property
    def total(self) -> int:
        return self.tokens_in + self.tokens_out + self.tokens_cached


def apply_budget(messages: list[dict], *, used: int, budget: int, strategy: Strategy) -> list[dict]:
    if budget < 1:
        raise ValueError("budget must be at least 1")
    if used * 100 < budget * 80:
        return messages
    return strategy(messages, used, budget)
