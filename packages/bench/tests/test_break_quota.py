import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from argus_bench.baseline import baseline_many
from argus_core.ledger import ModelQuota, QuotaExceeded


def test_tiny_cap_stops_before_next_task_and_resumes_next_day(tmp_path: Path) -> None:
    quotas = {
        "openai/gpt-oss-20b": ModelQuota(
            requests_per_day=1,
            tokens_per_day=1000,
            requests_per_minute=10,
            tokens_per_minute=1000,
            cached_counts=False,
        )
    }
    ledger_path = tmp_path / "ledger.json"
    partial_path = tmp_path / "partial.json"
    sent: list[str] = []

    def complete(task_id: str) -> str:
        sent.append(task_id)
        return "patch-" + task_id

    now_day = datetime(2026, 10, 29, 12, tzinfo=timezone.utc)
    with pytest.raises(QuotaExceeded):
        baseline_many(
            ["task-a", "task-b"],
            ledger_path=ledger_path,
            partial_path=partial_path,
            quotas=quotas,
            complete=complete,
            now=lambda: now_day,
        )
    assert sent == ["task-a"]
    assert json.loads(partial_path.read_text(encoding="utf-8")) == {"task-a": "patch-task-a"}

    now = datetime(2026, 10, 30, 12, tzinfo=timezone.utc)
    code = baseline_many(
        ["task-a", "task-b"],
        ledger_path=ledger_path,
        partial_path=partial_path,
        quotas=quotas,
        complete=complete,
        now=lambda: now,
    )
    assert code == 0
    assert sent == ["task-a", "task-b"]
    assert json.loads(partial_path.read_text(encoding="utf-8")) == {
        "task-a": "patch-task-a",
        "task-b": "patch-task-b",
    }
