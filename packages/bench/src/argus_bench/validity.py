"""Keep a mutant only when checks fail on it and pass on the original.

None means that side does not score (build-break). Exit 2 is infra.
"""

from __future__ import annotations


def judge_mutant(
    mutant_exit: int | None,
    original_exit: int | None,
    checks: list,
) -> tuple[bool, str]:
    if not checks:
        return False, "empty-checks"
    if mutant_exit is None:
        return False, "build-break"
    if mutant_exit == 2 or original_exit == 2:
        return False, "infra"
    if mutant_exit == 0:
        return False, "no-observable-change"
    if original_exit is None:
        return False, "build-break"
    if mutant_exit == 1 and original_exit == 0:
        return True, "keep"
    return False, "not-fail-then-pass"
