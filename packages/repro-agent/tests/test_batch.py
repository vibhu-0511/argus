import json
from pathlib import Path

from argus_core.ledger import load_quotas
from argus_core.types import Trajectory

from repro_agent.batch import (
    CRASH_TASK,
    LOOSE_TASK,
    MODEL,
    rate_label,
    run_text_only,
    run_with_screenshot,
    seeded_tickets,
    valid_count,
    wilson_interval,
)

_REPO = Path(__file__).resolve().parents[3]


def test_text_only_saves_thirty_and_continues_after_a_crash(tmp_path: Path):
    assert len(seeded_tickets()) == 30
    ledger_path = run_text_only(tmp_path)
    verdicts = list(tmp_path.glob("*/verdict.json"))
    trajectories = list(tmp_path.glob("*/trajectory.jsonl"))
    assert len(verdicts) == 30
    assert len(trajectories) == 30
    for path in trajectories:
        Trajectory.from_jsonl(path.read_text(encoding="utf-8"))
    crashed = json.loads((tmp_path / CRASH_TASK / "verdict.json").read_text(encoding="utf-8"))
    assert crashed["verdict"] == "error"
    assert crashed["stop_reason"] == "tool-unavailable"
    followed = json.loads((tmp_path / "seed-e02" / "verdict.json").read_text(encoding="utf-8"))
    assert followed["verdict"] == "valid"
    loose = json.loads((tmp_path / LOOSE_TASK / "verdict.json").read_text(encoding="utf-8"))
    assert loose["verdict"] == "passes-on-bug"
    state = json.loads(ledger_path.read_text(encoding="utf-8"))
    used = state["models"][MODEL]
    quota = load_quotas(_REPO / "docs" / "quotas.md")[MODEL]
    assert used["requests"] == 30
    assert used["requests"] <= quota.requests_per_day
    assert used["requests"] <= quota.requests_per_minute
    assert used["tokens"] <= quota.tokens_per_day
    assert used["tokens"] <= quota.tokens_per_minute


def test_screenshot_run_uses_the_same_tasks_and_model(tmp_path: Path):
    run_with_screenshot(tmp_path)
    names = sorted(path.name for path in tmp_path.iterdir() if path.is_dir())
    assert names == [name for name, _ticket in seeded_tickets()]
    assert len(list(tmp_path.glob("*/verdict.json"))) == 30
    sample = Trajectory.from_jsonl((tmp_path / "seed-e02" / "trajectory.jsonl").read_text(encoding="utf-8"))
    assert sample.meta.model == MODEL
    text_root = _REPO / "packages" / "repro-agent" / "runs" / "text-only"
    for name, _ticket in seeded_tickets():
        image = json.loads((tmp_path / name / "verdict.json").read_text(encoding="utf-8"))
        text = json.loads((text_root / name / "verdict.json").read_text(encoding="utf-8"))
        assert image["task_id"] == text["task_id"]
        assert image["verdict"] == text["verdict"]
    assert json.loads((tmp_path / "bug-17" / "verdict.json").read_text(encoding="utf-8"))["stop_reason"] == "submit"


def test_wilson_matches_the_p0_zero_of_ten_cell():
    low, high = wilson_interval(0, 10)
    assert f"[{low:.6f}, {high:.6f}]" == "[0.000000, 0.277540]"
    label = "28/30 [0.786762, 0.981523]"
    runs = _REPO / "packages" / "repro-agent" / "runs"
    assert rate_label(*valid_count(runs / "text-only")) == label
    assert rate_label(*valid_count(runs / "text-plus-image")) == label
