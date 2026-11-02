"""Fix loop. One model call, one tool, then the next message. No agent framework.

The same tool call three times stops as `stuck`. Three command timeouts stop as
`consecutive-timeout`, which is a different reason even when the command is the same.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from argus_core.client import Completion
from argus_core.ledger import Ledger
from argus_core.ledger import QuotaExceeded
from argus_core.ledger import Usage as LedgerUsage
from argus_core.router import Router
from argus_core.telemetry import chat_span, record_completion, record_tool_error, tool_span, traced_agent
from argus_core.types import StopReason, Trajectory, TrajectoryMeta, TrajectoryStep

from fix_loop.budget import StepUsage, apply_budget
from fix_loop.gates import GateResult, gate_message
from fix_loop.prompt import system_message
from fix_loop.skills import LOAD_SKILL, catalog, load_skill, load_skills
from fix_loop.strategies import SummaryDidNotShrink
from fix_loop.tools import ToolError, ToolResult, call

REPEAT = 3
VERIFY_RETRIES = 1

Execute = Callable[[str, dict], ToolResult | ToolError]
Strategy = Callable[[list[dict], int, int], list[dict]]


@dataclass(frozen=True)
class LoopResult:
    stop_reason: StopReason
    trajectory_path: Path


@traced_agent("fix-loop")
def run_fix(
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
    execute: Execute | None = None,
    context_budget: int | None = None,
    strategy: Strategy | None = None,
    gates: Callable[[], list[GateResult]] | None = None,
    verify: Callable[[], object] | None = None,
    skills: Path | None = None,
) -> LoopResult:
    if step_cap < 1 or token_cap < 1:
        raise ValueError("step_cap and token_cap must be at least 1")
    if router is None and (ledger is None or complete is None):
        raise ValueError("pass ledger and complete, or a router")
    out_dir.mkdir(parents=True, exist_ok=True)
    act = execute or (lambda name, payload: call(name, payload, worktree))
    loadable = load_skills(skills)[0] if skills is not None else []
    loaded: set[str] = set()
    system_text = system_message(system)
    if loadable:
        system_text += "\n\n" + catalog(loadable)  # last, so the prefix bytes are unchanged when no skill is loadable
    messages: list[dict] = [
        {"role": "system", "content": system_text},
        {"role": "user", "content": user},
    ]
    steps: list[TrajectoryStep] = []
    total_in = 0
    total_out = 0
    total_cached = 0
    recent: list[str] = []
    timeouts = 0
    malformed = 0
    verify_rejects = 0
    reason = StopReason.step_cap
    for index in range(step_cap):
        trace: dict[str, str] | None = None
        try:
            if router is None:
                completion = _ask(ledger, model, complete, messages, index)
            else:
                # the router does the ledger accounting and the chat span; a second ledger call here would count twice
                routed = router.complete(stage, messages)
                completion, trace = routed.completion, routed.trace()
        except QuotaExceeded:
            steps.append(TrajectoryStep(index=index, stop_reason=StopReason.quota_exceeded, tool_error="QuotaExceeded"))
            reason = StopReason.quota_exceeded
            break
        step_usage = StepUsage(
            completion.usage.tokens_in,
            completion.usage.tokens_out,
            completion.usage.tokens_cached,
        )
        total_in += step_usage.tokens_in
        total_out += step_usage.tokens_out
        total_cached += step_usage.tokens_cached
        if total_in + total_out >= token_cap:
            steps.append(_recorded(index, completion, stop_reason=StopReason.token_cap, trace=trace))
            reason = StopReason.token_cap
            break
        parsed = _parse(completion)
        if isinstance(parsed, ToolError):
            malformed = malformed + 1 if parsed.error == "failed" else 0
            stop = StopReason.retry_cap if malformed >= REPEAT else None
            steps.append(
                _recorded(
                    index,
                    completion,
                    tool_error=parsed.error,
                    message={"error": parsed.message},
                    stop_reason=stop,
                    trace=trace,
                )
            )
            if stop is not None:
                reason = stop
                break
            messages.append({"role": "assistant", "content": completion.content})
            messages.append({"role": "user", "content": f"{parsed.error}: {parsed.message}"})
            messages, summary_stop = _apply(messages, total_in + total_out + total_cached, context_budget, strategy)
            if summary_stop is not None:
                steps[-1] = steps[-1].model_copy(update={"stop_reason": summary_stop})
                reason = summary_stop
                break
            recent.clear()
            timeouts = 0
            continue
        name, payload = parsed
        key = name + "\n" + json.dumps(payload, sort_keys=True)
        recent.append(key)
        with tool_span(name, run_id=run_id, step=index) as tool:
            result = load_skill(loadable, payload, loaded) if loadable and name == LOAD_SKILL else act(name, payload)
            record_tool_error(tool, result.error if isinstance(result, ToolError) else None)
        timed_out = isinstance(result, ToolError) and result.error == "timeout"
        timeouts = timeouts + 1 if timed_out else 0
        if isinstance(result, ToolError) and result.error == "failed":
            malformed += 1
        else:
            malformed = 0
        stop: StopReason | None = None
        feedback: str | None = None
        rejection: str | None = None
        if malformed >= REPEAT:
            stop = StopReason.retry_cap
        elif timeouts >= REPEAT:
            stop = StopReason.consecutive_timeout
        elif len(recent) >= REPEAT and len(set(recent[-REPEAT:])) == 1:
            stop = StopReason.stuck
        elif name == "submit" and isinstance(result, ToolResult):
            failed = _failed_gate(gates)
            if failed is not None:
                feedback = gate_message(failed)
            else:
                rejection = _verify_rejection(verify)
                if rejection is None:
                    stop = StopReason.submit
                else:
                    verify_rejects += 1
                    if verify_rejects > VERIFY_RETRIES:
                        stop = StopReason.verify_reject
                    else:
                        feedback = rejection
        step = _recorded(index, completion, tool_name=name, result=result, stop_reason=stop, trace=trace)
        if stop is StopReason.verify_reject and rejection is not None:
            step = step.model_copy(update={"message": {"text": rejection, "returncode": None}})
        steps.append(step)
        if stop is not None:
            reason = stop
            break
        messages.append({"role": "assistant", "content": completion.content})
        messages.append({"role": "user", "content": feedback if feedback is not None else _observation(result)})
        messages, summary_stop = _apply(messages, total_in + total_out + total_cached, context_budget, strategy)
        if summary_stop is not None:
            steps[-1] = steps[-1].model_copy(update={"stop_reason": summary_stop})
            reason = summary_stop
            break
    else:
        if steps and steps[-1].stop_reason is None:
            steps[-1] = steps[-1].model_copy(update={"stop_reason": StopReason.step_cap})
        reason = StopReason.step_cap
    path = _write(out_dir, model, host, git_commit, run_id, task_id, user, steps)
    return LoopResult(reason, path)


def _verify_rejection(verify: Callable[[], object] | None) -> str | None:
    """One retry, then stop. A passed check run is not a rejection. A raised verifier fails closed."""
    if verify is None:
        return None
    try:
        verdict = verify()
    except Exception as exc:
        return json.dumps({"error": str(exc) or "error", "verify": "error"}, sort_keys=True)
    if bool(getattr(verdict, "ok", False)):
        return None
    reason = getattr(verdict, "first_failure", None) or "error"
    check = getattr(verdict, "failed_check", None) or "verify"
    return json.dumps({"error": reason, "verify": check}, sort_keys=True)


def _failed_gate(gates: Callable[[], list[GateResult]] | None) -> GateResult | None:
    if gates is None:
        return None
    return next((item for item in gates() if not item.ok), None)


def _apply(
    messages: list[dict],
    used: int,
    context_budget: int | None,
    strategy: Strategy | None,
) -> tuple[list[dict], StopReason | None]:
    observation = messages[-1].get("content") or ""
    try:
        return _compact(messages, used + len(str(observation)), context_budget, strategy), None
    except SummaryDidNotShrink:
        return messages, StopReason.summary


def _compact(
    messages: list[dict],
    used: int,
    context_budget: int | None,
    strategy: Strategy | None,
) -> list[dict]:
    if context_budget is None or strategy is None:
        return messages
    return apply_budget(messages, used=used, budget=context_budget, strategy=strategy)


def _ask(
    ledger: Ledger, model: str, complete: Callable[[list[dict]], Completion], messages: list[dict], step: int | None = None
) -> Completion:
    held: dict[str, Completion] = {}

    def send() -> LedgerUsage:
        with chat_span(model, step=step) as span:
            completion = complete(messages)
            record_completion(span, model, completion)
        held["completion"] = completion
        return LedgerUsage(
            completion.usage.tokens_in,
            completion.usage.tokens_out,
            completion.usage.tokens_cached,
        )

    ledger.call(model, send)
    return held["completion"]


def _parse(completion: Completion) -> tuple[str, dict] | ToolError:
    raw = completion.raw if isinstance(completion.raw, dict) else {}
    if raw and "choices" not in raw:
        return ToolError(error="failed", message="provider payload missing choices")
    message = {}
    choices = raw.get("choices")
    if isinstance(choices, list) and choices:
        message = (choices[0] or {}).get("message") or {}
    tool_calls = message.get("tool_calls") if isinstance(message, dict) else None
    if isinstance(tool_calls, list) and tool_calls:
        function = (tool_calls[0] or {}).get("function") or {}
        try:
            payload = json.loads(function.get("arguments") or "{}")
        except json.JSONDecodeError:
            return ToolError(error="failed", message="tool arguments are not JSON")
        if not isinstance(payload, dict):
            return ToolError(error="failed", message="tool arguments are not an object")
        return str(function.get("name") or ""), payload
    try:
        body = json.loads(completion.content)
    except json.JSONDecodeError:
        return ToolError(error="failed", message="model response is not a tool call")
    if not isinstance(body, dict) or "tool" not in body or not isinstance(body.get("arguments"), dict):
        return ToolError(error="failed", message="model response is not a tool call")
    return str(body["tool"]), body["arguments"]


def _observation(result: ToolResult | ToolError) -> str:
    if isinstance(result, ToolError):
        return f"{result.error}: {result.message}"
    text = result.text
    if result.returncode is not None:
        return f"returncode {result.returncode}\n{text}"
    return text


def _recorded(
    index: int,
    completion: Completion,
    *,
    tool_name: str | None = None,
    result: ToolResult | ToolError | None = None,
    tool_error: str | None = None,
    message: dict | None = None,
    stop_reason: StopReason | None = None,
    trace: dict[str, str] | None = None,
) -> TrajectoryStep:
    if result is not None:
        tool_error = result.error if isinstance(result, ToolError) else None
        message = {
            "text": result.message if isinstance(result, ToolError) else result.text,
            "returncode": None if isinstance(result, ToolError) else result.returncode,
        }
    return TrajectoryStep(
        index=index,
        tokens_in=completion.usage.tokens_in,
        tokens_out=completion.usage.tokens_out,
        tokens_cached=completion.usage.tokens_cached,
        stop_reason=stop_reason,
        raw_response=completion.content,
        tool_name=tool_name,
        tool_error=tool_error,
        message=message,
        **(trace or {}),
    )


def _write(
    out_dir: Path,
    model: str,
    host: str,
    git_commit: str,
    run_id: str,
    task_id: str,
    user: str,
    steps: list[TrajectoryStep],
) -> Path:
    trajectory = Trajectory(
        meta=TrajectoryMeta(
            run_id=run_id,
            task_id=task_id,
            model=model,
            host=host,
            prompt_hash=hashlib.sha256(user.encode()).hexdigest(),
            git_commit=git_commit,
        ),
        steps=steps,
    )
    path = out_dir / "trajectory.jsonl"
    path.write_text(trajectory.to_jsonl(), encoding="utf-8")
    return path
