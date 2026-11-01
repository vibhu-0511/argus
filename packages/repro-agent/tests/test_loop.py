from pathlib import Path

from argus_core.client import Completion, Usage
from argus_core.ledger import Ledger, ModelQuota, Usage as LedgerUsage
from argus_core.types import StopReason, Ticket, Trajectory

from repro_agent.loop import TreeRun, run_repro

GOOD = """
await page.getByRole("button", { name: "Sign in" }).click();
await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
"""
REF = """
await page.locator("[ref=e5]").click();
await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
"""
NO_ASSERT = 'await page.getByRole("button", { name: "Sign in" }).click();'


def _ticket() -> Ticket:
    return Ticket(id="sign-in", text="The Sign in button does nothing.")


def _ledger(tmp_path: Path, **quota) -> Ledger:
    fields = dict(
        requests_per_day=10,
        tokens_per_day=1000,
        requests_per_minute=10,
        tokens_per_minute=1000,
        cached_counts=False,
    )
    fields.update(quota)
    return Ledger(tmp_path / "ledger.json", {"m": ModelQuota(**fields)})


def _reply(text: str) -> Completion:
    return Completion(text, Usage(3, 2, 0), {"content": text})


def _run(tmp_path: Path, replies: list[str], trees: TreeRun, cap: int = 3, ledger: Ledger | None = None):
    calls: list[int] = []
    ran: list[str] = []

    def complete(messages: list[dict]) -> Completion:
        calls.append(1)
        return _reply(replies[len(calls) - 1])

    def run_trees(script: str) -> TreeRun:
        ran.append(script)
        return trees

    result = run_repro(
        ticket=_ticket(),
        task_dir=tmp_path,
        model="m",
        ledger=ledger or _ledger(tmp_path),
        complete=complete,
        run_trees=run_trees,
        out_dir=tmp_path / "run",
        cap=cap,
        run_id="r1",
        host="local",
        git_commit="abc",
    )
    text = result.trajectory_path.read_text(encoding="utf-8")
    assert Trajectory.from_jsonl(text).meta.task_id == "sign-in"
    return result, calls, ran


def test_stops_when_the_script_reproduces(tmp_path: Path):
    result, calls, ran = _run(tmp_path, [GOOD], TreeRun(True, True))
    assert result.stop_reason is StopReason.submit
    assert result.script is not None
    assert 'getByRole("button", { name: "Sign in" })' in result.script
    assert "expect(" in result.script
    assert "e5" not in result.script
    assert calls == [1]
    assert ran == [result.script]
    saved = (tmp_path / "run" / "repro.spec.ts").read_text(encoding="utf-8")
    assert saved == result.script


def test_empty_reply_counts_toward_the_retry_cap(tmp_path: Path):
    result, calls, ran = _run(tmp_path, ["", "  "], TreeRun(True, True), cap=2)
    assert result.stop_reason is StopReason.retry_cap
    assert result.script is None
    assert calls == [1, 1]
    assert ran == []
    trajectory = Trajectory.from_jsonl(result.trajectory_path.read_text(encoding="utf-8"))
    assert trajectory.steps[-1].stop_reason is StopReason.retry_cap
    assert [step.tool_error for step in trajectory.steps] == ["empty", "empty"]


def test_quota_stop_does_not_call_the_model(tmp_path: Path):
    ledger = _ledger(tmp_path, requests_per_day=1)
    ledger.call("m", lambda: LedgerUsage(1, 0, 0))
    result, calls, ran = _run(tmp_path, [GOOD], TreeRun(True, True), ledger=ledger)
    assert result.stop_reason is StopReason.quota_exceeded
    assert calls == []
    assert ran == []
    trajectory = Trajectory.from_jsonl(result.trajectory_path.read_text(encoding="utf-8"))
    assert trajectory.steps[-1].stop_reason is StopReason.quota_exceeded


def test_a_snapshot_ref_is_not_saved(tmp_path: Path):
    result, calls, ran = _run(tmp_path, [REF, GOOD], TreeRun(True, True))
    assert result.stop_reason is StopReason.submit
    assert "ref=" not in (result.script or "")
    assert calls == [1, 1]
    assert ran == [result.script]


def test_a_script_without_an_assertion_is_revised(tmp_path: Path):
    result, calls, ran = _run(tmp_path, [NO_ASSERT], TreeRun(True, True), cap=1)
    assert result.stop_reason is StopReason.retry_cap
    assert result.script is None
    assert ran == []
    assert calls == [1]
