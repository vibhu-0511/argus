import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from argus_core.types import Task, Ticket, Trajectory, TrajectoryStep, dump_schemas

SCHEMAS = Path(__file__).resolve().parents[1] / "schemas"

TICKET = {
    "id": "seed-001",
    "text": "The radar list overlaps the ops menu.",
    "screenshot": {"media_type": "image/png", "path": "shots/before.png"},
}

TASK = {
    "id": "seed-001",
    "ticket": TICKET,
    "bug_patch": "--- a/App.tsx\n+++ b/App.tsx\n@@\n-flex-row\n+flex-col\n",
    "golden_patch": "--- a/App.tsx\n+++ b/App.tsx\n@@\n-flex-col\n+flex-row\n",
    "checks": [{"type": "computed_style", "params": {"selector": ".radar", "prop": "flex-direction"}}],
    "meta": {"source": "seeded", "archetype": "flex-direction", "tier": "easy", "seed": None},
}

TRAJECTORY = {
    "meta": {
        "run_id": "run-1",
        "task_id": "seed-001",
        "model": "mock",
        "host": "http://127.0.0.1:9",
        "prompt_hash": "abc",
        "git_commit": "deadbee",
        "seed": 1,
    },
    "steps": [
        {
            "index": 0,
            "kind": "step",
            "tokens_in": 12,
            "tokens_out": 4,
            "raw_response": "{\"tool\": \"edit\", \"bad\": true}",
            "tool_name": "edit",
            "tool_error": "not-unique",
            "message": {"role": "assistant", "content": ""},
        }
    ],
}


def test_ticket_task_trajectory_round_trip():
    ticket = Ticket.model_validate(TICKET)
    assert Ticket.model_validate_json(ticket.model_dump_json()) == ticket

    task = Task.model_validate(TASK)
    assert Task.model_validate_json(task.model_dump_json()) == task

    trajectory = Trajectory.model_validate(TRAJECTORY)
    assert Trajectory.model_validate_json(trajectory.model_dump_json()) == trajectory
    assert Trajectory.from_jsonl(trajectory.to_jsonl()) == trajectory


def test_omitted_cached_tokens_are_zero():
    step = TrajectoryStep.model_validate({"index": 2})
    assert step.tokens_cached == 0
    assert step.tokens_in == 0
    again = Trajectory.from_jsonl(
        '{"kind":"meta","run_id":"r","task_id":"t","model":"m","host":"h","prompt_hash":"p","git_commit":"c"}\n'
        '{"index":0,"tokens_in":3,"tokens_out":1}\n'
    )
    assert again.steps[0].tokens_cached == 0


def test_invalid_samples_are_rejected():
    with pytest.raises(ValidationError):
        Ticket.model_validate({"id": "t", "text": ""})
    with pytest.raises(ValidationError):
        Ticket.model_validate(
            {"id": "t", "text": "x", "screenshot": {"media_type": "image/png", "path": "../secret.png"}}
        )
    with pytest.raises(ValidationError):
        Task.model_validate({**TASK, "checks": []})
    with pytest.raises(ValidationError):
        Task.model_validate({**TASK, "meta": {**TASK["meta"], "tier": "impossible"}})
    with pytest.raises(ValidationError):
        TrajectoryStep.model_validate({"index": 0, "tokens_in": -1})
    with pytest.raises(ValidationError):
        TrajectoryStep.model_validate({"index": 0, "stop_reason": "gave-up"})
    with pytest.raises(ValueError):
        Trajectory.from_jsonl('{"kind":"step","index":0}\n')


def test_schema_files_match_models(tmp_path: Path):
    dump_schemas(tmp_path)
    for name in ("ticket", "task", "trajectory"):
        generated = json.loads((tmp_path / f"{name}.schema.json").read_text(encoding="utf-8"))
        committed = json.loads((SCHEMAS / f"{name}.schema.json").read_text(encoding="utf-8"))
        assert generated == committed
