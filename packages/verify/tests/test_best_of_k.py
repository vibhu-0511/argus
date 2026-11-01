"""Checks first. The judge can rank a passed run and cannot reject it."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from verify.best_of_k import UsageLedger, best_of_k
from verify.pipeline import Verdict


def _ok() -> Verdict:
    return Verdict(True, (), None, None)


def _bad() -> Verdict:
    return Verdict(False, (), "pixel shifted", "pixel")


def test_k_returns_every_candidate_and_records_tokens():
    for k in (1, 3, 5):
        ledger = UsageLedger()
        selection = best_of_k(
            k,
            draw=lambda index: (f"patch-{index}", (index + 1, 2, 0)),
            verify=lambda _patch: _ok(),
            judge=lambda _patch: "pass",
            ledger=ledger,
        )
        assert selection.reason == "checks-pass"
        assert selection.selected is not None
        assert len(selection.candidates) == k
        assert [row["candidate"] for row in ledger.rows] == list(range(k))
        assert ledger.rows[0]["tokens_in"] == 1


def test_judge_does_not_override_a_passed_check_run():
    ledger = UsageLedger()
    selection = best_of_k(
        1,
        draw=lambda _index: ("patch", (3, 4, 1)),
        verify=lambda _patch: _ok(),
        judge=lambda _patch: "fail",
        ledger=ledger,
    )
    assert selection.selected is not None
    assert selection.selected.patch == "patch"
    assert selection.reason == "checks-pass; judge did not override"
    assert ledger.rows == [{"candidate": 0, "tokens_in": 3, "tokens_out": 4, "tokens_cached": 1}]


def test_judge_is_not_called_when_checks_fail():
    seen: list[str] = []
    selection = best_of_k(
        2,
        draw=lambda index: (f"patch-{index}", (1, 1, 0)),
        verify=lambda _patch: _bad(),
        judge=lambda patch: seen.append(patch) or "pass",
        ledger=UsageLedger(),
    )
    assert selection.selected is None
    assert selection.reason == "checks-fail"
    assert seen == []
    assert len(selection.candidates) == 2


def test_judge_prefers_pass_among_check_passing_patches():
    labels = iter(["collateral", "pass", "fail"])
    selection = best_of_k(
        3,
        draw=lambda index: (f"patch-{index}", (1, 1, 0)),
        verify=lambda _patch: _ok(),
        judge=lambda _patch: next(labels),
        ledger=UsageLedger(),
    )
    assert selection.selected is not None
    assert selection.selected.patch == "patch-1"
    assert selection.reason == "checks-pass; judge preferred pass"
