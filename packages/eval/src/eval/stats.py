"""Wilson score interval and percentiles. No dependencies."""

from __future__ import annotations

import math

Z95 = 1.96  # same z as fix_loop.baseline._wilson, so the P3 cells reproduce


def wilson(successes: int, total: int, z: float = Z95) -> tuple[float, float]:
    """Wilson score interval. `total` must be at least 1."""
    if total < 1:
        raise ValueError("total must be at least 1")
    phat = successes / total
    z2 = z * z
    denom = 1 + z2 / total
    center = (phat + z2 / (2 * total)) / denom
    margin = z * math.sqrt(phat * (1 - phat) / total + z2 / (4 * total * total)) / denom
    return max(0.0, center - margin), min(1.0, center + margin)


def percentile(values: list[float], q: float) -> float | None:
    """Linear interpolation between closest ranks (numpy's default). `q` in [0, 100]. None for no values."""
    if not values:
        return None
    ordered = sorted(values)
    rank = (len(ordered) - 1) * q / 100
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)
