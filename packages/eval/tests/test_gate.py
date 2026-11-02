"""P5-T16: the regression gate on stored fixtures. No model call, no network."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from eval.__main__ import main
from eval.gate import DEFAULT_CONFIG, load_config
from eval.stats import wilson

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "gate"
BASELINE = FIXTURES / "baseline.json"
WORSE = FIXTURES / "worse.json"


def _gate(*args: str) -> int:
    return main(["gate", *args])


def _variant(tmp_path: Path, name: str, successes: int, tokens_in_scale: float = 1.0) -> Path:
    """The baseline with a different success count (and token scale). Only the fields the gate reads."""
    data = json.loads(BASELINE.read_text(encoding="utf-8"))
    total = data["resolve_rate"]["total"]
    data["resolve_rate"].update(successes=successes, rate=successes / total)
    data["tokens"]["per_task"]["tokens_in"] *= tokens_in_scale
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_baseline_passes_against_itself(capsys):
    assert _gate(str(BASELINE), "--baseline", str(BASELINE)) == 0
    out = capsys.readouterr().out
    assert out.startswith("gate: PASS")
    assert "20/29" in out and "0.5077" in out  # the P3 cell [0.507695, 0.827246]


def test_worse_file_fails_with_a_reason(capsys):
    assert _gate(str(WORSE), "--baseline", str(BASELINE)) == 1
    out = capsys.readouterr().out
    assert out.startswith("gate: FAIL")
    assert "FAIL resolve rate: run 0.4138 < baseline lower bound 0.5077" in out
    assert "ok   tokens per bug" in out and "+59.9%" in out  # 1.6x input tokens is under the +100% limit


def test_compares_with_the_interval_not_the_point_estimate(tmp_path, capsys):
    # 17/29 = 0.586 is well below the baseline's 20/29 = 0.690 but still inside its interval: not a regression.
    assert _gate(str(_variant(tmp_path, "noise.json", 17)), "--baseline", str(BASELINE)) == 0
    # 14/29 = 0.483 is under the lower bound 0.5077.
    assert _gate(str(_variant(tmp_path, "bad.json", 14)), "--baseline", str(BASELINE)) == 1


def test_tokens_check_alone_can_fail(tmp_path, capsys):
    assert _gate(str(_variant(tmp_path, "heavy.json", 20, 2.5)), "--baseline", str(BASELINE)) == 1
    out = capsys.readouterr().out
    assert "ok   resolve rate" in out and "FAIL tokens per bug" in out


def test_config_is_read_from_the_one_file(tmp_path):
    cfg = load_config()
    assert (cfg.resolve_rate.z, cfg.resolve_rate.margin, cfg.tokens_per_bug.max_growth) == (1.96, 0.0, 1.0)
    assert DEFAULT_CONFIG.name == "gate.toml"
    run = _variant(tmp_path, "noise.json", 17)
    # A stricter file (z=0.5 narrows the interval; lower bound moves up past 0.586) flips the verdict.
    low, _ = wilson(20, 29, 0.5)
    assert low > 17 / 29
    strict = tmp_path / "strict.toml"
    strict.write_text("[resolve_rate]\nz = 0.5\nmargin = 0.0\n[tokens_per_bug]\nmax_growth = 1.0\n", encoding="utf-8")
    assert _gate(str(run), "--baseline", str(BASELINE)) == 0
    assert _gate(str(run), "--baseline", str(BASELINE), "--config", str(strict)) == 1
    # A margin is slack on the lower bound.
    slack = tmp_path / "slack.toml"
    slack.write_text("[resolve_rate]\nz = 0.5\nmargin = 0.2\n[tokens_per_bug]\nmax_growth = 1.0\n", encoding="utf-8")
    assert _gate(str(run), "--baseline", str(BASELINE), "--config", str(slack)) == 0


def test_unreadable_input_exits_2(tmp_path, capsys):
    assert _gate(str(tmp_path / "missing.json"), "--baseline", str(BASELINE)) == 2
    bad = tmp_path / "bad.toml"
    bad.write_text("[resolve_rate]\nz = 1.96\nmystery = 1\n", encoding="utf-8")
    assert _gate(str(BASELINE), "--baseline", str(BASELINE), "--config", str(bad)) == 2
    assert "cannot compare" in capsys.readouterr().out


def test_missing_baseline_argument_is_a_usage_error():
    with pytest.raises(SystemExit) as exc:
        _gate(str(BASELINE))
    assert exc.value.code == 2
