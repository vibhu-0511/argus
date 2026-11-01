"""P5-T14: the repro agent takes a Router. Each step records the tier, host and model that served it, and the ledger counts each call once."""

from pathlib import Path

import pytest

from argus_core.client import Completion, Usage
from argus_core.ledger import Ledger, ModelQuota
from argus_core.router import Router, load_policy
from argus_core.types import StopReason, Ticket, Trajectory

from repro_agent.loop import TreeRun, run_repro

GOOD = """
await page.getByRole("button", { name: "Sign in" }).click();
await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
"""


class Stub:
    def __init__(self):
        self.models: list[str] = []

    def complete(self, model: str, messages: list[dict]) -> Completion:
        self.models.append(model)
        return Completion(GOOD, Usage(3, 2, 1), {})


def _router(tmp_path: Path) -> tuple[Router, Stub, Ledger]:
    policy = load_policy()
    models = {r.model for t in policy.tiers.values() for r in (t.primary, t.fallback) if r}
    ledger = Ledger(tmp_path / "ledger.json", {m: ModelQuota(100, 10**6, 100, 10**6, False) for m in models})
    stub = Stub()
    return Router(policy, ledger, {"groq": stub, "mistral": stub, "ollama": stub}), stub, ledger


def _run(tmp_path: Path, **kwargs):
    return run_repro(
        ticket=Ticket(id="sign-in", text="The Sign in button does nothing."), task_dir=tmp_path, model="routed",
        run_trees=lambda _s: TreeRun(True, True), out_dir=tmp_path / "run", cap=3, run_id="r", host="routed", git_commit="abc", **kwargs,
    )


def test_step_records_the_cheap_tier_and_the_ledger_counts_once(tmp_path: Path):
    router, stub, ledger = _router(tmp_path)
    result = _run(tmp_path, router=router)
    assert result.stop_reason is StopReason.submit
    step = Trajectory.from_jsonl(result.trajectory_path.read_text(encoding="utf-8")).steps[0]
    cheap = load_policy().tiers["cheap"].primary
    assert (step.tier, step.host, step.model) == ("cheap", cheap.host, cheap.model)
    assert ledger._state["models"][cheap.model]["requests"] == 1
    assert stub.models == [cheap.model]


def test_without_a_router_ledger_and_complete_are_needed(tmp_path: Path):
    with pytest.raises(ValueError, match="ledger and complete, or a router"):
        _run(tmp_path)
