"""P3-T18: the no-compaction baseline over the seeded 30, without a live model."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from argus_core.client import Completion, Usage
from argus_core.ledger import Ledger, ModelQuota

from fix_loop.baseline import rate_label, run_baseline, seeded_subset

_SEEDED = Path(__file__).resolve().parents[3] / "packages" / "bench" / "tasks" / "seeded"


def test_seeded_subset_is_thirty_and_balanced():
    rows = seeded_subset(_SEEDED)
    assert len(rows) == 30
    tiers = [json.loads((path / "meta.json").read_text(encoding="utf-8"))["tier"] for path in rows]
    assert tiers.count("easy") == 10
    assert tiers.count("medium") == 10
    assert tiers.count("hard") == 10
    assert [path.name for path in rows] == sorted(path.name for path in rows)


def test_baseline_writes_verdicts_and_stays_inside_the_ledger(tmp_path: Path):
    tasks = _two_tasks(tmp_path)
    infra = tmp_path / "tasks" / "bug-infra"
    infra.mkdir()
    (infra / "ticket.json").write_text(json.dumps({"id": "bug-infra", "text": "infra"}) + "\n", encoding="utf-8")
    tasks.append(infra)
    ledger = Ledger(tmp_path / "ledger.json", {"fake": ModelQuota(10, 10**6, 10, 10**6, False)})
    calls = {"n": 0}

    def complete(_messages):
        calls["n"] += 1
        return Completion(json.dumps({"tool": "submit", "arguments": {}}), Usage(1, 1, 0), {})

    def score(task_id: str, _tree: Path) -> tuple[int, bool]:
        if task_id == "bug-ok":
            return 0, False
        if task_id == "bug-infra":
            return 2, False
        return 1, False

    label = run_baseline(
        tasks=tasks,
        out_dir=tmp_path / "runs",
        ledger=ledger,
        complete=complete,
        score=score,
        prepare=lambda _task: tmp_path / "work",
        model="fake",
        host="fixture",
        git_commit="abc",
        step_cap=2,
        token_cap=100,
    )
    assert label == rate_label(1, 2)
    assert calls["n"] == 3
    stored = json.loads((tmp_path / "ledger.json").read_text(encoding="utf-8"))
    assert stored["models"]["fake"]["requests"] == 3
    assert stored["models"]["fake"]["requests"] <= 10
    ok = json.loads((tmp_path / "runs" / "bug-ok" / "verdict.json").read_text(encoding="utf-8"))
    bad = json.loads((tmp_path / "runs" / "bug-bad" / "verdict.json").read_text(encoding="utf-8"))
    assert ok["verdict"] == "resolved"
    assert bad["verdict"] == "unresolved"
    infra_verdict = json.loads((tmp_path / "runs" / "bug-infra" / "verdict.json").read_text(encoding="utf-8"))
    assert infra_verdict["verdict"] == "excluded"
    assert (tmp_path / "runs" / "bug-ok" / "trajectory.jsonl").is_file()
    assert rate_label(0, 10) == "0/10 [0.000000, 0.277540]"


def test_one_crash_does_not_stop_the_next_task(tmp_path: Path):
    tasks = _two_tasks(tmp_path)
    ledger = Ledger(tmp_path / "ledger.json", {"fake": ModelQuota(10, 10**6, 10, 10**6, False)})

    def prepare(task: Path) -> Path:
        if task.name == "bug-ok":
            raise RuntimeError("worktree failed")
        return tmp_path / "work"

    def complete(_messages):
        return Completion(json.dumps({"tool": "submit", "arguments": {}}), Usage(1, 1, 0), {})

    run_baseline(
        tasks=tasks,
        out_dir=tmp_path / "runs",
        ledger=ledger,
        complete=complete,
        score=lambda _task_id, _tree: (1, False),
        prepare=prepare,
        model="fake",
        host="fixture",
        git_commit="abc",
        step_cap=2,
        token_cap=100,
    )
    crashed = json.loads((tmp_path / "runs" / "bug-ok" / "verdict.json").read_text(encoding="utf-8"))
    nxt = json.loads((tmp_path / "runs" / "bug-bad" / "verdict.json").read_text(encoding="utf-8"))
    assert crashed["verdict"] == "error"
    assert nxt["verdict"] == "unresolved"


def test_a_touched_check_is_not_resolved(tmp_path: Path):
    task = _two_tasks(tmp_path)[:1]
    ledger = Ledger(tmp_path / "ledger.json", {"fake": ModelQuota(10, 10**6, 10, 10**6, False)})
    run_baseline(
        tasks=task,
        out_dir=tmp_path / "runs",
        ledger=ledger,
        complete=lambda _messages: Completion(json.dumps({"tool": "submit", "arguments": {}}), Usage(1, 1, 0), {}),
        score=lambda _task_id, _tree: (0, True),
        prepare=lambda _task: tmp_path / "work",
        model="fake",
        host="fixture",
        git_commit="abc",
        step_cap=2,
        token_cap=100,
    )
    verdict = json.loads((tmp_path / "runs" / "bug-ok" / "verdict.json").read_text(encoding="utf-8"))
    assert verdict["verdict"] == "unresolved"


def test_token_cap_and_stuck_are_scored_without_rewriting_the_stop(tmp_path: Path):
    scored: list[str] = []

    def score(task_id: str, _tree: Path) -> tuple[int, bool]:
        scored.append(task_id)
        return 1, False

    def prepare(_task: Path) -> Path:
        return tmp_path / "work"

    common = dict(
        ledger=Ledger(tmp_path / "ledger.json", {"fake": ModelQuota(10, 10**6, 10, 10**6, False)}),
        score=score,
        prepare=prepare,
        model="fake",
        host="fixture",
        git_commit="abc",
    )
    capped = tmp_path / "tasks" / "bug-cap"
    capped.mkdir(parents=True)
    (capped / "ticket.json").write_text(json.dumps({"id": "bug-cap", "text": "cap"}) + "\n", encoding="utf-8")
    run_baseline(
        tasks=[capped],
        out_dir=tmp_path / "cap",
        complete=lambda _messages: Completion(json.dumps({"tool": "submit", "arguments": {}}), Usage(3, 2, 0), {}),
        step_cap=4,
        token_cap=4,
        **common,
    )
    stuck = tmp_path / "tasks" / "bug-stuck"
    stuck.mkdir(parents=True)
    (stuck / "ticket.json").write_text(json.dumps({"id": "bug-stuck", "text": "stuck"}) + "\n", encoding="utf-8")
    run_baseline(
        tasks=[stuck],
        out_dir=tmp_path / "stuck",
        complete=lambda _messages: Completion(
            json.dumps({"tool": "read_file", "arguments": {"path": "a.txt"}}),
            Usage(1, 1, 0),
            {},
        ),
        step_cap=5,
        token_cap=100,
        **common,
    )
    cap_verdict = json.loads((tmp_path / "cap" / "bug-cap" / "verdict.json").read_text(encoding="utf-8"))
    stuck_verdict = json.loads((tmp_path / "stuck" / "bug-stuck" / "verdict.json").read_text(encoding="utf-8"))
    assert scored == ["bug-cap", "bug-stuck"]
    assert cap_verdict["stop_reason"] == "token-cap"
    assert stuck_verdict["stop_reason"] == "stuck"
    assert cap_verdict["verdict"] == "unresolved"
    assert stuck_verdict["verdict"] == "unresolved"


def test_baseline_rejects_compaction():
    try:
        run_baseline(
            tasks=[],
            out_dir=Path("."),
            ledger=Ledger(Path("ledger.json"), {"fake": ModelQuota(1, 1, 1, 1, False)}),
            complete=lambda _messages: Completion("", Usage(0, 0, 0), {}),
            score=lambda _task_id, _tree: (1, False),
            prepare=lambda _task: Path("."),
            model="fake",
            host="fixture",
            git_commit="abc",
            step_cap=1,
            token_cap=1,
            compaction="caps",
        )
    except ValueError as exc:
        assert "no compaction" in str(exc)
        return
    raise AssertionError("compaction was accepted")


def _two_tasks(tmp_path: Path) -> list[Path]:
    rows = []
    for name, text in (("bug-ok", "ok"), ("bug-bad", "bad")):
        directory = tmp_path / "tasks" / name
        directory.mkdir(parents=True)
        (directory / "ticket.json").write_text(
            json.dumps({"id": name, "text": text}) + "\n",
            encoding="utf-8",
        )
        rows.append(directory)
    return rows
