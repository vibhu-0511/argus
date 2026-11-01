"""One verdict. Checks run in ORDER. The first hard failure stops the run."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace

from verify.checks import CheckResult

# The only place the order is set. ADR-012.
ORDER = ("pixel", "overflow", "axe", "console")


@dataclass(frozen=True)
class Verdict:
    ok: bool
    checks: tuple[CheckResult, ...]
    first_failure: str | None
    failed_check: str | None


def run(
    checks: Mapping[str, Callable[[], CheckResult]],
    order: tuple[str, ...] = ORDER,
) -> Verdict:
    results: list[CheckResult] = []
    for name in order:
        if name not in checks:
            missing = CheckResult(name, False, True, f"missing check {name}")
            results.append(missing)
            return Verdict(False, tuple(results), missing.reason, name)
        result = checks[name]()
        results.append(result)
        if not result.ok and result.hard:
            return Verdict(False, tuple(results), result.reason, name)
    return Verdict(True, tuple(results), None, None)


def run_routes(
    routes: Mapping[str, Mapping[str, Callable[[], CheckResult]]],
    order: tuple[str, ...] = ORDER,
) -> Verdict:
    """Ticketed route first, then the others. A failure names the route."""
    names = sorted(routes, key=lambda name: (name != "ticketed", name))
    merged: list[CheckResult] = []
    for name in names:
        verdict = run(routes[name], order)
        merged.extend(replace(item, reason=f"{name}: {item.reason}") for item in verdict.checks)
        if not verdict.ok:
            return Verdict(False, tuple(merged), f"{name}: {verdict.first_failure}", verdict.failed_check)
    return Verdict(True, tuple(merged), None, None)
