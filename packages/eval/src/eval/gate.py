"""Regression gate: compare a results file with a stored baseline, with intervals, not point estimates.

Fails (exit 1) when this run's resolve rate is below the baseline's Wilson lower bound (minus the margin), or when
tokens per bug grew past the allowed fraction. Thresholds live in `packages/eval/gate.toml` and nowhere else.
No model call, no network. Exit 2 means the inputs could not be read.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from eval.results import Results
from eval.stats import wilson

DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "gate.toml"


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResolveRateRule(_Section):
    z: float = Field(gt=0)
    margin: float = Field(ge=0)


class TokensRule(_Section):
    max_growth: float = Field(ge=0)


class GateConfig(_Section):
    resolve_rate: ResolveRateRule
    tokens_per_bug: TokensRule


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class Verdict:
    passed: bool
    checks: list[Check]
    header: list[str]

    def format(self) -> str:
        lines = [f"gate: {'PASS' if self.passed else 'FAIL'}", *self.header]
        lines += [f"{'ok  ' if c.ok else 'FAIL'} {c.name}: {c.detail}" for c in self.checks]
        return "\n".join(lines)


def load_config(path: Path = DEFAULT_CONFIG) -> GateConfig:
    return GateConfig.model_validate(tomllib.loads(path.read_text(encoding="utf-8")))


def load_results(path: Path) -> Results:
    return Results.model_validate_json(path.read_text(encoding="utf-8"))


def _describe(label: str, r: Results, z: float) -> str:
    rate = r.resolve_rate
    if not rate.total:
        return f"{label}: {r.run_id}, no scored tasks"
    low, high = wilson(rate.successes, rate.total, z)
    return f"{label}: {r.run_id}, {rate.successes}/{rate.total} = {rate.successes / rate.total:.4f}, Wilson [{low:.4f}, {high:.4f}]"


def _tokens(r: Results) -> float | None:
    mean = r.tokens.per_task
    return None if mean is None else mean.tokens_in + mean.tokens_out  # cached tokens are part of tokens_in


def compare(run: Results, baseline: Results, config: GateConfig) -> Verdict:
    rule = config.resolve_rate
    checks: list[Check] = []

    if not baseline.resolve_rate.total:
        raise ValueError("baseline has no scored tasks, nothing to compare against")
    low, _ = wilson(baseline.resolve_rate.successes, baseline.resolve_rate.total, rule.z)
    floor = low - rule.margin
    if not run.resolve_rate.total:
        checks.append(Check("resolve rate", False, "the run has no scored tasks"))
    else:
        rate = run.resolve_rate.successes / run.resolve_rate.total
        ok = rate >= floor
        checks.append(
            Check(
                "resolve rate",
                ok,
                f"run {rate:.4f} {'>=' if ok else '<'} baseline lower bound {low:.4f}"
                f" - margin {rule.margin:.4f} = {floor:.4f} (z={rule.z})",
            )
        )

    mine, theirs = _tokens(run), _tokens(baseline)
    if mine is None or not theirs:
        checks.append(Check("tokens per bug", True, "skipped, a file has no token mean"))
    else:
        growth = mine / theirs - 1
        limit = config.tokens_per_bug.max_growth
        checks.append(
            Check(
                "tokens per bug",
                growth <= limit,
                f"run {mine:,.0f} vs baseline {theirs:,.0f} ({growth:+.1%}, limit +{limit:.0%})",
            )
        )

    header = [_describe("run     ", run, rule.z), _describe("baseline", baseline, rule.z)]
    return Verdict(all(c.ok for c in checks), checks, header)


def gate_main(results: Path, baseline: Path, config: Path | None) -> int:
    """CLI body. 0 pass, 1 regression, 2 unreadable input."""
    try:
        verdict = compare(
            load_results(results), load_results(baseline), load_config(config) if config else load_config()
        )
    except (OSError, ValueError) as exc:  # pydantic's and tomllib's errors are ValueErrors
        print(f"gate: cannot compare: {exc}")
        return 2
    print(verdict.format())
    return 0 if verdict.passed else 1
