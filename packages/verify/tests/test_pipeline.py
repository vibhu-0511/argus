"""Fixed order, short-circuit, one verdict, and a route that is not the ticketed one."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from verify.checks import CheckResult
from verify.pipeline import ORDER, run, run_routes


def _ok(name: str) -> CheckResult:
    return CheckResult(name, True, True, "ok")


def _checks(fail: str | None = None, called: list[str] | None = None) -> dict:
    def make(name: str):
        def run_check() -> CheckResult:
            if called is not None:
                called.append(name)
            if name == fail:
                return CheckResult(name, False, True, f"{name} broken")
            return _ok(name)

        return run_check

    return {name: make(name) for name in ORDER}


def test_order_is_configured_in_one_place():
    assert ORDER == ("pixel", "overflow", "axe", "console")


def test_four_broken_trees_short_circuit():
    for name in ORDER:
        called: list[str] = []
        verdict = run(_checks(name, called))
        assert not verdict.ok
        assert verdict.failed_check == name
        assert verdict.first_failure == f"{name} broken"
        assert called == list(ORDER[: ORDER.index(name) + 1])
        assert len(verdict.checks) == len(called)


def test_clean_tree_returns_every_check():
    verdict = run(_checks())
    assert verdict.ok
    assert verdict.first_failure is None
    assert tuple(item.name for item in verdict.checks) == ORDER


def test_soft_failure_continues():
    called: list[str] = []

    def soft() -> CheckResult:
        called.append("pixel")
        return CheckResult("pixel", False, False, "advisory")

    checks = _checks(called=called)
    checks["pixel"] = soft
    verdict = run(checks)
    assert verdict.ok
    assert called == list(ORDER)


def test_other_route_failure_names_the_route():
    verdict = run_routes({"ticketed": _checks(), "other": _checks("pixel")})
    assert not verdict.ok
    assert verdict.failed_check == "pixel"
    assert verdict.first_failure is not None
    assert verdict.first_failure.startswith("other:")
