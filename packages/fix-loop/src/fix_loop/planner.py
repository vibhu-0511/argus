"""P8-T11 planner and subagents variant of the fix loop. Same call shape as `run_fix`, so a harness switches with `select(variant)`.

One planner call turns the ticket plus repo context into 1 to 5 sub-tasks. Each sub-task then runs the existing
`run_fix` with its own message history and its own token and step cap, one after the other in the same worktree.
Every model call (planner and subagents) goes through the one `Ledger` (or `Router`) the caller passes and carries the
same `run_id`, so the ledger total is the sum over all agents. Layout under `out_dir`: `planner/`, `sub-1/`, `sub-2/`
... each with its own `trajectory.jsonl`, plus `trajectory.jsonl` here (all steps in order, so a harness that reads one
trajectory per bug sums every agent) and `agents.json` (per-agent tokens and call counts).

ponytail: subagents run in sequence, not in parallel, and share one worktree; the later ones see the earlier edits.
Upgrade path is one worktree per subagent plus a merge step, only if the P8-T12 ablation shows the variant is worth it.
ponytail: the planner is one call, no retry. A malformed plan raises PlanError; the caller decides what a failed plan scores.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from argus_core.client import Completion
from argus_core.ledger import Ledger, QuotaExceeded
from argus_core.router import Router
from argus_core.types import StopReason, Trajectory, TrajectoryStep
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from fix_loop.loop import LoopResult, _ask, _recorded, _write, run_fix

MAX_SUBTASKS = 5
PLAN_SYSTEM = """You split a bug ticket into small sub-tasks, each one a separate fix attempt by its own agent.
Reply with exactly one JSON object and nothing else:
{"subtasks": [{"title": "<short>", "instructions": "<what to change and where>"}]}
Give 1 to 5 sub-tasks. One sub-task is right when the bug has one cause. Do not fix anything yourself."""


class SubTask(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1)
    instructions: str = Field(min_length=1)


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subtasks: list[SubTask] = Field(min_length=1, max_length=MAX_SUBTASKS)


class PlanError(ValueError):
    """The planner's reply is not a valid plan. `raw` is the reply, kept so the failure can be read."""

    def __init__(self, reason: str, raw: str):
        super().__init__(reason)
        self.reason = reason
        self.raw = raw


def parse_plan(text: str) -> Plan:
    body = text.strip()
    if body.startswith("```"):  # small local models fence their JSON
        body = body.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return Plan.model_validate_json(body)
    except ValidationError as exc:
        raise PlanError(f"not a valid plan: {exc.errors()[0]['msg']}", text) from exc


@dataclass(frozen=True)
class AgentUsage:
    agent: str
    calls: int
    tokens_in: int
    tokens_out: int
    tokens_cached: int
    stop_reason: str | None


@dataclass(frozen=True)
class PlanResult(LoopResult):
    """`stop_reason` is `submit` only when every subagent submitted; otherwise the first subagent's reason that was not."""

    agents: tuple[AgentUsage, ...] = ()

    @property
    def tokens_in(self) -> int:
        return sum(a.tokens_in for a in self.agents)

    @property
    def tokens_out(self) -> int:
        return sum(a.tokens_out for a in self.agents)

    @property
    def tokens_cached(self) -> int:
        return sum(a.tokens_cached for a in self.agents)

    @property
    def subagent_calls(self) -> int:
        return sum(a.calls for a in self.agents if a.agent != "planner")


def run_planned(
    *,
    worktree: Path,
    model: str,
    out_dir: Path,
    step_cap: int,
    token_cap: int,
    run_id: str,
    host: str,
    git_commit: str,
    task_id: str,
    system: str,
    user: str,
    ledger: Ledger | None = None,
    complete: Callable[[list[dict]], Completion] | None = None,
    router: Router | None = None,
    stage: str = "fix",
    context: str = "",
    **loop_kwargs,
) -> PlanResult:
    """`step_cap` and `token_cap` are for the whole bug: the planner's tokens come off `token_cap`, the rest is split
    evenly, so each subagent has its own cap and the sum over all agents stays near the single agent's. The planner
    uses `stage` too (the strong tier); `loop_kwargs` (execute, gates, verify, harden ...) go to every subagent."""
    if router is None and (ledger is None or complete is None):
        raise ValueError("pass ledger and complete, or a router")
    out_dir.mkdir(parents=True, exist_ok=True)
    messages = [
        {"role": "system", "content": PLAN_SYSTEM},
        {"role": "user", "content": f"{user}\n\nRepo context:\n{context or 'none'}\n"},
    ]
    try:
        if router is None:
            completion, trace = _ask(ledger, model, complete, messages, 0), None
        else:
            routed = router.complete(stage, messages)
            completion, trace = routed.completion, routed.trace()
    except QuotaExceeded:
        step = TrajectoryStep(index=0, stop_reason=StopReason.quota_exceeded, tool_error="QuotaExceeded")
        path = _write(out_dir, model, host, git_commit, run_id, task_id, user, [step])
        return PlanResult(StopReason.quota_exceeded, path, (AgentUsage("planner", 0, 0, 0, 0, StopReason.quota_exceeded.value),))
    planner = _recorded(0, completion, trace=trace)
    (out_dir / "planner").mkdir(exist_ok=True)
    _write(out_dir / "planner", model, host, git_commit, run_id, task_id, user, [planner])
    plan = parse_plan(completion.content)  # raises PlanError; the planner's call is already in the ledger and on disk
    usage = [AgentUsage("planner", 1, planner.tokens_in, planner.tokens_out, planner.tokens_cached, None)]
    count = len(plan.subtasks)
    sub_tokens = max(1, (token_cap - planner.tokens_in - planner.tokens_out) // count)
    sub_steps = max(1, step_cap // count)
    outline = "\n".join(f"{i}. {t.title}" for i, t in enumerate(plan.subtasks, 1))
    steps = [planner]
    reason = StopReason.submit
    for i, task in enumerate(plan.subtasks, 1):
        name = f"sub-{i}"
        result = run_fix(
            worktree=worktree, model=model, out_dir=out_dir / name, step_cap=sub_steps, token_cap=sub_tokens,
            run_id=run_id, host=host, git_commit=git_commit, task_id=task_id, system=system,
            user=f"{user}\n\nPlan:\n{outline}\n\nYour sub-task ({i} of {count}): {task.title}\n{task.instructions}\n"
            "Earlier sub-tasks have already changed the worktree. Do only this one.",
            ledger=ledger, complete=complete, router=router, stage=stage, **loop_kwargs,
        )
        done = Trajectory.from_jsonl(result.trajectory_path.read_text(encoding="utf-8")).steps
        steps += done
        usage.append(AgentUsage(
            name, len(done), sum(s.tokens_in for s in done), sum(s.tokens_out for s in done),
            sum(s.tokens_cached for s in done), result.stop_reason.value,
        ))
        if reason is StopReason.submit and result.stop_reason is not StopReason.submit:
            reason = result.stop_reason
        if result.stop_reason is StopReason.quota_exceeded:
            break  # the ledger refuses every agent, so the rest would only be refused too
    merged = [s.model_copy(update={"index": n}) for n, s in enumerate(steps)]
    path = _write(out_dir, model, host, git_commit, run_id, task_id, user, merged)
    (out_dir / "agents.json").write_text(json.dumps([asdict(a) for a in usage], indent=2) + "\n", encoding="utf-8")
    return PlanResult(reason, path, tuple(usage))


VARIANTS = {"single": run_fix, "planner": run_planned}


def select(variant: str):
    """The fix runner for a variant name. Both take the `run_fix` arguments; `planner` also takes `context`."""
    try:
        return VARIANTS[variant]
    except KeyError:
        raise ValueError(f"variant must be one of {sorted(VARIANTS)}, not {variant!r}") from None
