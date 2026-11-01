from pathlib import Path

import pytest

from repro_agent.verify import Verdict, run_fixture_scripts, verify

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "verify"


def test_skip_or_fixme_is_an_error():
    script = (FIXTURES / "error.mjs").read_text(encoding="utf-8")
    assert "test.fixme" in script
    assert verify(script, "pass", "pass") is Verdict.error
    assert verify("test.skip('later', async () => {})", "fail", "pass") is Verdict.error


@pytest.mark.docker
def test_four_hand_made_scripts_cover_each_verdict():
    ran = run_fixture_scripts()
    expected = {
        "valid": Verdict.valid,
        "passes-on-bug": Verdict.passes_on_bug,
        "fails-on-golden": Verdict.fails_on_golden,
    }
    for name, verdict in expected.items():
        script = (FIXTURES / f"{name}.mjs").read_text(encoding="utf-8")
        assert verify(script, ran[name]["buggy"], ran[name]["golden"]) is verdict
    error = (FIXTURES / "error.mjs").read_text(encoding="utf-8")
    assert verify(error, "pass", "pass") is Verdict.error
