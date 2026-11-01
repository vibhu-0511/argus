"""Krippendorff's published two-observer example, to three decimals."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from verify.alpha import agreement_report, alpha_nominal, alphas_on_split, false_accept_rate, wilson


def test_published_nominal_example():
    ben = list("aabbdcccedda")
    gerry = list("babbbccceddd")
    assert round(alpha_nominal(ben, gerry), 3) == 0.692


def test_unparsed_error_stays_in_the_denominator():
    kept = alpha_nominal(["pass", "fail"], ["pass", "error"])
    dropped = alpha_nominal(["pass"], ["pass"])
    assert kept != dropped
    assert kept == alpha_nominal(["pass", "fail"], ["pass", "error"])


def test_bootstrap_interval_on_perfect_agreement():
    report = agreement_report(["pass", "fail"] * 5, ["pass", "fail"] * 5, ["pass", "fail"] * 5, iterations=40, seed=1)
    assert report.alpha == 1
    assert report.low == 1
    assert report.high == 1
    assert report.order_disagreement_rate == 0


def test_order_disagreement_is_not_averaged_into_the_label():
    report = agreement_report(["pass"], ["pass"], ["fail"], iterations=20, seed=1)
    assert report.alpha == 1
    assert report.order_disagreement_rate == 1


def test_held_out_alpha_is_not_the_dev_alpha():
    human = ["pass", "pass", "pass", "pass"]
    judge = ["pass", "pass", "fail", "fail"]
    dev_alpha, held_alpha = alphas_on_split(human, judge, {0, 1})
    assert dev_alpha == 1
    assert held_alpha < dev_alpha


def test_wilson_interval_contains_the_rate():
    rate, low, high = wilson(81, 100)
    assert round(rate, 2) == 0.81
    assert low < rate < high
    assert round(low, 2) == 0.72
    assert round(high, 2) == 0.87


def test_false_accept_rate_ignores_human_passes():
    assert false_accept_rate(["fail", "pass", "collateral"], ["pass", "fail", "fail"]) == 0.5
