"""P5-T21: build.py turns results files into data.js. No model call, no network."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402


def _runs(out: Path) -> list[dict]:
    text = (out / "data.js").read_text(encoding="utf-8")
    return json.loads(text.removeprefix("window.ARGUS_RUNS = ").removesuffix(";\n"))


def test_default_files_keep_order_and_flag_the_made_up_one(tmp_path):
    build.build(build.DEFAULT_FILES, tmp_path)
    base, worse = _runs(tmp_path)
    assert (base["run_id"], base["made_up"]) == ("p3-a-claude-baseline", False)
    assert (worse["run_id"], worse["made_up"]) == ("worse-made-up", True)
    assert base["source"] == "packages/eval/fixtures/gate/baseline.json"


def test_missing_values_stay_null_not_zero(tmp_path):
    build.build(build.DEFAULT_FILES[:1], tmp_path)
    (run,) = _runs(tmp_path)
    assert run["latency_s"]["p50"] is None and run["trajectory_metrics"] is None and run["$_equivalent"] is None
    assert run["resolve_rate"]["rate"] == 0.689655


def test_unknown_schema_version_is_refused(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"schema_version": 2}', encoding="utf-8")
    with pytest.raises(SystemExit):
        build.build([str(bad)], tmp_path)
