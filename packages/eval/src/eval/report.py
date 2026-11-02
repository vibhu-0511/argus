"""Phase report: two results files in, the markdown table from phases/P05-argus-eval.md out.

Rows: Previous phase, This phase, Delta. Tokens/bug is tokens_in + tokens_out per task (cached tokens are
already inside tokens_in). $-equivalent is per task too, so runs with different task counts compare.
Anything a file cannot give (null, no tasks) prints as a dash, and a delta needs both sides.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from eval.results import Results

DASH = "—"
HEADER = (
    "| Report | Resolve rate | Tokens/bug | $-equivalent | p50 latency | p95 latency |\n"
    "|---|---|---|---|---|---|"
)
Values = tuple[float | None, ...]  # rate, tokens/bug, $/bug, p50, p95


def _values(r: Results) -> Values:
    per = r.tokens.per_task
    total = r.resolve_rate.total
    return (
        r.resolve_rate.rate,
        None if per is None else per.tokens_in + per.tokens_out,
        None if r.dollar_equivalent is None or not total else r.dollar_equivalent / total,
        r.latency_s.p50,
        r.latency_s.p95,
    )


def _cells(r: Results, v: Values) -> list[str]:
    rate, tokens, dollars, p50, p95 = v
    rr = r.resolve_rate
    return [
        DASH if rate is None else f"{rate:.1%} ({rr.successes}/{rr.total})",
        DASH if tokens is None else f"{tokens:,.0f}",
        DASH if dollars is None else f"${dollars:.4f}",
        DASH if p50 is None else f"{p50:.1f} s",
        DASH if p95 is None else f"{p95:.1f} s",
    ]


def _pct(new: float, old: float) -> str:
    return f" ({(new - old) / old:+.1%})" if old else ""


def _delta(prev: Values, this: Values) -> list[str]:
    def d(i: int, fmt) -> str:
        a, b = prev[i], this[i]
        return DASH if a is None or b is None else fmt(b, a)

    return [
        d(0, lambda b, a: f"{(b - a) * 100:+.1f} pp"),
        d(1, lambda b, a: f"{b - a:+,.0f}{_pct(b, a)}"),
        d(2, lambda b, a: f"{'+' if b >= a else '-'}${abs(b - a):.4f}{_pct(b, a)}"),
        d(3, lambda b, a: f"{b - a:+.1f} s"),
        d(4, lambda b, a: f"{b - a:+.1f} s"),
    ]


def render(previous: Results | None, this: Results | None) -> str:
    empty = [DASH] * 5
    pv = _values(previous) if previous else None
    tv = _values(this) if this else None
    rows = [
        ("Previous phase", _cells(previous, pv) if previous else empty),
        ("This phase", _cells(this, tv) if this else empty),
        ("Delta", _delta(pv, tv) if pv and tv else empty),
    ]
    return "\n".join([HEADER, *(f"| {name} | " + " | ".join(cells) + " |" for name, cells in rows)]) + "\n"


def report_files(paths: Sequence[Path]) -> str:
    """No files: empty template. One file: it is this phase. Two: previous, this."""
    if len(paths) > 2:
        raise ValueError("report takes at most two results files: <previous> <this>")
    loaded = [Results.model_validate_json(p.read_text(encoding="utf-8")) for p in paths]
    return render(loaded[0] if len(loaded) == 2 else None, loaded[-1] if loaded else None)
