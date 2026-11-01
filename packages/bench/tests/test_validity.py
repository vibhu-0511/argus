from __future__ import annotations

from argus_bench.validity import judge_mutant


def test_keep_when_mutant_fails_and_original_passes():
    assert judge_mutant(1, 0, ["pixel"]) == (True, "keep")


def test_no_observable_change_when_mutant_already_passes():
    assert judge_mutant(0, 0, ["pixel"]) == (False, "no-observable-change")


def test_build_break_when_mutant_does_not_score():
    assert judge_mutant(None, 0, ["pixel"]) == (False, "build-break")


def test_build_break_when_original_does_not_score():
    assert judge_mutant(1, None, ["pixel"]) == (False, "build-break")


def test_infra_on_the_mutant():
    assert judge_mutant(2, 0, ["pixel"]) == (False, "infra")


def test_infra_on_the_original():
    assert judge_mutant(1, 2, ["pixel"]) == (False, "infra")


def test_exit_2_is_not_no_observable_change():
    assert judge_mutant(0, 2, ["pixel"]) == (False, "infra")


def test_empty_checks():
    assert judge_mutant(1, 0, []) == (False, "empty-checks")


def test_empty_checks_before_build_break():
    assert judge_mutant(None, 0, []) == (False, "empty-checks")


def test_mutant_pass_before_original_build_break():
    assert judge_mutant(0, None, ["pixel"]) == (False, "no-observable-change")


def test_not_fail_then_pass():
    assert judge_mutant(1, 1, ["pixel"]) == (False, "not-fail-then-pass")
