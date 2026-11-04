"""P8-T21 break it: one tenant uses up its budget while another tenant's run is going.

Scripted fake model only: no network, no model, no key. The runs are the real `fix_loop.run_fix` loop and the real
`argus_core.ledger.Ledger`; the model is a list of canned replies and the tools are a stub. The second tenant's run is
started from inside the first tenant's run (in its tool step), so the two runs really overlap on one ledger file.
Write-up: docs/notes/p8-break-it-t21.md.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from argus_core.client import Completion, Usage
from argus_core.ledger import Ledger, ModelQuota, QuotaExceeded, TenantBudget, TenantQuotaExceeded
from argus_core.router import Router, load_policy
from argus_core.types import StopReason, Trajectory
from fix_loop.loop import run_fix
from fix_loop.tools import ToolResult


def reply(tool: str) -> str:
    return json.dumps({"tool": tool, "arguments": {}})


class Model:
    """A scripted model host: returns the next canned reply and counts the calls that really reached it."""

    def __init__(self, tools: list[str]) -> None:
        self.tools = tools
        self.calls = 0

    def complete(self, model: str, messages: list[dict]) -> Completion:
        text = reply(self.tools[self.calls])
        self.calls += 1
        return Completion(text, Usage(1, 1, 0), {})


class Spy:
    """The tenant's ledger view, keeping every refusal the loop would otherwise swallow into a stop reason."""

    def __init__(self, inner) -> None:
        self.inner = inner
        self.refused: list[QuotaExceeded] = []

    def call(self, model, send, *, token_estimate=0):
        try:
            return self.inner.call(model, send, token_estimate=token_estimate)
        except QuotaExceeded as exc:
            self.refused.append(exc)
            raise


def fix_run(tmp_path: Path, name: str, ledger, model: Model, on_tool=None):
    def execute(tool: str, payload: dict) -> ToolResult:
        if on_tool is not None:
            on_tool()
        return ToolResult(tool=tool, text="ok")

    return run_fix(
        worktree=tmp_path, model="fake", ledger=ledger, complete=lambda messages: model.complete("fake", messages),
        out_dir=tmp_path / name, step_cap=10, token_cap=1000, run_id=name, host="test", git_commit="abc", task_id=name,
        system="system", user="fix it", execute=execute,
    )


# acme's loop asks the model three times (list, list, submit). Its own budget allows two, or its share of the model does.
OWN_BUDGET = (TenantBudget(requests_per_day=2, tokens_per_day=1000, provider_share=1.0), 100, "tenant_requests_per_day")
MODEL_SHARE = (TenantBudget(requests_per_day=100, tokens_per_day=1000, provider_share=0.5), 4, "provider_share.requests_per_day")


@pytest.mark.parametrize("acme, host_requests_per_day, limit", [OWN_BUDGET, MODEL_SHARE], ids=["own-budget", "model-share"])
def test_one_tenant_is_refused_with_a_typed_message_while_the_other_run_completes(tmp_path, acme, host_requests_per_day, limit):
    quota = ModelQuota(host_requests_per_day, 10**6, 100, 10**6, False)
    globex_budget = TenantBudget(requests_per_day=100, tokens_per_day=1000, provider_share=0.5)
    ledger = Ledger(tmp_path / "ledger.json", {"fake": quota}, budgets={"acme": acme, "globex": globex_budget})
    acme_view, globex_view = Spy(ledger.for_tenant("acme")), Spy(ledger.for_tenant("globex"))
    acme_model, globex_model = Model(["list_dir", "list_dir", "submit"]), Model(["list_dir", "submit"])
    globex_result: list = []
    started = []

    def start_globex() -> None:  # runs once, while acme's loop is between two of its model calls
        if not started:
            started.append(1)
            globex_result.append(fix_run(tmp_path, "globex", globex_view, globex_model))

    acme_result = fix_run(tmp_path, "acme", acme_view, acme_model, on_tool=start_globex)

    # the first tenant: stopped as quota-exceeded on its third call, the model host was never reached for it
    assert acme_result.stop_reason is StopReason.quota_exceeded
    assert acme_model.calls == 2
    (refusal,) = acme_view.refused
    assert isinstance(refusal, TenantQuotaExceeded) and isinstance(refusal, QuotaExceeded)
    assert refusal.tenant == "acme" and refusal.limit == limit and (refusal.used, refusal.cap) == (3, 2)
    assert str(refusal) == f"tenant acme: fake would exceed {limit}: 3 of 2"
    last = Trajectory.from_jsonl(acme_result.trajectory_path.read_text(encoding="utf-8")).steps[-1]
    assert (last.stop_reason, last.tool_error) == (StopReason.quota_exceeded, "QuotaExceeded")

    # the second tenant: its run started in the middle of acme's and went all the way to submit, with no refusal
    (globex,) = globex_result
    assert globex.stop_reason is StopReason.submit
    assert globex_model.calls == 2 and globex_view.refused == []
    assert ledger._state["tenants"]["globex"]["fake"]["requests"] == 2
    assert ledger._state["tenants"]["acme"]["fake"]["requests"] == 2  # the refused call was not counted


def test_the_router_fallback_does_not_give_an_exhausted_tenant_a_second_budget(tmp_path):
    policy = load_policy()
    routes = policy.tiers["strong"]
    quota = ModelQuota(100, 10**6, 100, 10**6, False)
    ledger = Ledger(
        tmp_path / "ledger.json", {routes.primary.model: quota, routes.fallback.model: quota},
        budgets={"acme": TenantBudget(1, 1000, 1.0), "globex": TenantBudget(5, 1000, 1.0)},
    )
    host = Model(["list_dir"] * 5)
    clients = {"groq": host, "mistral": host}
    acme = Router(policy, ledger.for_tenant("acme"), clients)
    acme.complete("fix", [])
    with pytest.raises(TenantQuotaExceeded, match="tenant acme"):
        acme.complete("fix", [])  # primary refused, fallback on the other host refused too: the budget is over all models
    assert host.calls == 1
    assert Router(policy, ledger.for_tenant("globex"), clients).complete("fix", []).completion.content == reply("list_dir")
