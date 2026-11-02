"""P7-T07: the red-team config has the agreed shape and the dry run (stub model, no model call) works.

No test here calls a model. `stub` is scripted and harmless; `stub-obedient` is scripted to do what the attack says, so the
tests show the grading can say `succeeded`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from guard.redteam import ATTACK, CANARY, CASES, HOST_CANARY, MARK, run_case, summarize

REDTEAM = Path(__file__).resolve().parents[1] / "redteam"
CONFIG = REDTEAM / "promptfooconfig.yaml"
VERSIONS = Path(__file__).resolve().parents[3] / "docs" / "notes" / "p7-t00-versions.md"


def test_config_is_three_static_cases_with_deterministic_assertions():
    text = CONFIG.read_text(encoding="utf-8")
    config = yaml.safe_load(text)
    assert [t["vars"]["case"] for t in config["tests"]] == list(CASES) == ["ticket", "repo-file", "skill"]
    types = {a["type"] for a in config["defaultTest"]["assert"]}
    assert types == {"is-json", "javascript", "not-contains"}
    assert "llm-rubric" not in text and "model-graded" not in text
    assert not {"redteam", "strategies", "plugins"} & set(config)  # no generator: the cases are the three above, nothing generated
    assert {CANARY, HOST_CANARY} <= {a.get("value") for a in config["defaultTest"]["assert"]}


def test_pinned_promptfoo_version_is_the_t00_one():
    pinned = "promptfoo@0.125.1"
    assert pinned in CONFIG.read_text(encoding="utf-8")
    assert "0.125.1" in VERSIONS.read_text(encoding="utf-8")
    assert pinned in (REDTEAM / "README.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("case", CASES)
def test_dry_run_reaches_the_real_prompt_and_is_blocked(case):
    report = run_case(case, "stub")
    assert report["saw_attack"], "the attack text must reach the model through the real prompt assembly"
    assert report["verdict"] == "blocked" and not any(report["effective"].values())
    assert not any(report["attempted"].values())
    assert report["stop_reason"] == "submit"


@pytest.mark.parametrize("case", CASES)
def test_obedient_stub_is_graded_succeeded(case):
    report = run_case(case, "stub-obedient")
    assert report["verdict"] == "succeeded"
    assert report["effective"]["canary_leak"] is True  # copied into the patch through `edit`
    assert all(report["attempted"].values())
    # the existing tool layer already refuses these, so the attack asked for them but they did not take effect
    assert not report["effective"]["outside_path"] and not report["effective"]["unlisted_tool"]
    assert not report["effective"]["checks_changed"]


def test_attack_text_is_planted_in_one_place_per_case():
    assert MARK in ATTACK
    with pytest.raises(ValueError):
        run_case("nope")
    with pytest.raises(ValueError, match="nothing else is allowed"):
        run_case("ticket", "gpt-4o")


def test_summarize_counts_errors_apart_from_blocked(tmp_path):
    ok = run_case("ticket", "stub")
    bad = run_case("ticket", "stub-obedient")
    rows = [{"vars": {"case": "ticket"}, "response": {"output": json.dumps(r)}} for r in (ok, bad)]
    rows.append({"vars": {"case": "ticket"}, "error": "provider failed"})
    source = tmp_path / "pf.json"
    source.write_text(json.dumps({"results": {"results": rows}}), encoding="utf-8")
    result = summarize(source, tmp_path / "out.json", "2026-01-01")
    ticket = result["cases"][0]
    assert (ticket["runs"], ticket["blocked"], ticket["succeeded"], ticket["errors"]) == (3, 1, 1, 1)
    assert json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))["cases"][0]["case"] == "ticket"
