from pathlib import Path

from argus_core.types import Trajectory

from repro_agent.replay import replay

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "replay" / "sign-in"
WORKFLOW = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "repro.yml"


def test_replay_gives_the_stored_trajectory(tmp_path: Path):
    stored = Trajectory.from_jsonl((FIXTURE / "trajectory.jsonl").read_text(encoding="utf-8"))
    assert replay(FIXTURE, tmp_path) == stored


def test_repro_workflow_has_no_secrets():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "secrets." not in text
    assert "ARGUS_MODEL_API_KEY" not in text
    lowered = text.lower()
    assert "password" not in lowered
    assert "api_key" not in lowered
