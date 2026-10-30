import json
from pathlib import Path

from argus_core.ledger import load_quotas
from argus_core.types import Trajectory

from repro_agent.batch import CRASH_TASK, LOOSE_TASK, MODEL, run_text_only, seeded_tickets

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
