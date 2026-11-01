"""Nominal Krippendorff alpha for two coders, plus a bootstrap interval.

An unparsed judge string is the label `error` and stays in the denominator.
Presentation order is a separate rate. Disagreeing orders are not averaged.
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True)
class Agreement:
    alpha: float
    low: float
    high: float
    order_disagreement_rate: float


def alpha_nominal(left: list[str], right: list[str]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("alpha needs at least one pair of labels")
    marginal: Counter[str] = Counter()
    diagonal: Counter[str] = Counter()
    for a, b in zip(left, right, strict=True):
        marginal[a] += 1
        marginal[b] += 1
        if a == b:
            diagonal[a] += 2
    n = 2 * len(left)
    sum_occ = sum(diagonal.values())
    sum_nc = sum(count * (count - 1) for count in marginal.values())
    numerator = (n - 1) * sum_occ - sum_nc
    denominator = n * (n - 1) - sum_nc
    if denominator == 0:
        return 1.0 if numerator == 0 else float("nan")
    return numerator / denominator


def bootstrap_alpha(
    left: list[str],
    right: list[str],
    *,
    iterations: int = 1000,
    seed: int = 0,
) -> tuple[float, float, float]:
    point = alpha_nominal(left, right)
    rng = random.Random(seed)
    n = len(left)
    samples = []
    for _ in range(iterations):
        pick = [rng.randrange(n) for _ in range(n)]
        samples.append(alpha_nominal([left[i] for i in pick], [right[i] for i in pick]))
    samples.sort()
    low = samples[int(0.025 * (iterations - 1))]
    high = samples[min(iterations - 1, int(0.975 * (iterations - 1)) + 1)]
    return point, low, high


def order_disagreement_rate(forward: list[str], reverse: list[str]) -> float:
    if len(forward) != len(reverse) or not forward:
        raise ValueError("order rate needs the same labels twice")
    return sum(a != b for a, b in zip(forward, reverse, strict=True)) / len(forward)


def agreement_report(
    human: list[str],
    forward: list[str],
    reverse: list[str],
    *,
    iterations: int = 1000,
    seed: int = 0,
) -> Agreement:
    """Alpha uses the fixed before/after order. The reverse labels are only the disagreement rate."""
    point, low, high = bootstrap_alpha(human, forward, iterations=iterations, seed=seed)
    return Agreement(point, low, high, order_disagreement_rate(forward, reverse))


def split_dev_held_out(n: int, *, seed: int = 0) -> tuple[set[int], set[int]]:
    order = list(range(n))
    random.Random(seed).shuffle(order)
    cut = n // 2
    return set(order[:cut]), set(order[cut:])


def alphas_on_split(
    human: list[str],
    judge: list[str],
    dev: set[int],
) -> tuple[float, float]:
    dev_h, dev_j, held_h, held_j = [], [], [], []
    for index, (left, right) in enumerate(zip(human, judge, strict=True)):
        if index in dev:
            dev_h.append(left)
            dev_j.append(right)
        else:
            held_h.append(left)
            held_j.append(right)
    return alpha_nominal(dev_h, dev_j), alpha_nominal(held_h, held_j)


def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    if n < 1:
        raise ValueError("wilson needs at least one trial")
    p = successes / n
    z2 = z * z
    denom = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / denom
    margin = z * ((p * (1 - p) / n + z2 / (4 * n * n)) ** 0.5) / denom
    return p, centre - margin, centre + margin


def false_accept_rate(human: list[str], judge: list[str]) -> float:
    bad = [index for index, label in enumerate(human) if label != "pass"]
    if not bad:
        return 0.0
    return sum(judge[index] == "pass" for index in bad) / len(bad)
