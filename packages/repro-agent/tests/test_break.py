from pathlib import Path

from argus_core.client import Completion, Usage
from argus_core.ledger import Ledger, ModelQuota
from argus_core.types import StopReason, Ticket, Trajectory

from repro_agent.loop import run_repro
from repro_agent.verify import Verdict, verify

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "verify"


def test_vague_ticket_hits_the_retry_cap(tmp_path: Path):
    def complete(_messages: list[dict]) -> Completion:
        return Completion("", Usage(1, 1, 0), {})

    result = run_repro(
        ticket=Ticket(id="vague", text="the page looks wrong"),
        task_dir=tmp_path,
        model="m",
        ledger=_ledger(tmp_path),
        complete=complete,
        run_trees=_no_script,
        out_dir=tmp_path / "run",
        cap=2,
        run_id="vague",
        host="local",
        git_commit="break",
    )
    assert result.stop_reason is StopReason.retry_cap
    assert result.script is None
    trajectory = Trajectory.from_jsonl(result.trajectory_path.read_text(encoding="utf-8"))
    assert trajectory.steps[-1].stop_reason is StopReason.retry_cap


def test_loose_selector_is_passes_on_bug():
    script = (FIXTURES / "passes-on-bug.mjs").read_text(encoding="utf-8")
    assert verify(script, "pass", "pass") is Verdict.passes_on_bug


def _no_script(_script: str):
    raise AssertionError("no script should run")


def _ledger(tmp_path: Path) -> Ledger:
    return Ledger(
        tmp_path / "ledger.json",
        {
            "m": ModelQuota(
                requests_per_day=10,
                tokens_per_day=1000,
                requests_per_minute=10,
                tokens_per_minute=1000,
                cached_counts=False,
            )
        },
    )
