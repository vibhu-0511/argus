"""Repro loop. Ask for a script, run it on both trees, revise until it reproduces or the cap hits.

ponytail: `run_trees` is injected. A real run passes the P1-T05 sandbox; this module does not start Docker.
"""

from __future__ import annotations

import hashlib
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from argus_core.client import Completion
from argus_core.ledger import Ledger
from argus_core.ledger import Usage as LedgerUsage
from argus_core.telemetry import chat_span, record_completion, record_tool_error, tool_span, traced_agent
from argus_core.types import StopReason, Ticket, Trajectory, TrajectoryMeta, TrajectoryStep

from repro_agent.browser import ToolUnavailable
from repro_agent.prompt import assemble_prompt

_FENCE = re.compile(r"```(?:javascript|js|typescript|ts)?\s*\n(.*?)```", re.DOTALL)
_REF = re.compile(r"\[ref=|(?<![A-Za-z0-9])(?:f\d+)?e\d+(?![A-Za-z0-9])")
_ASSERT = re.compile(r"expect\(|toBeVisible|toBeHidden|toHaveText|toHaveCount|\bassert\b")


@dataclass(frozen=True)
class TreeRun:
    """How the script behaved. A reproduction fails on the bug and passes on the fix."""

    failed_on_buggy: bool
    passed_on_golden: bool


@dataclass(frozen=True)
class LoopResult:
    stop_reason: StopReason
    script: str | None
    trajectory_path: Path


@traced_agent("repro-agent")
def run_repro(
    *,
    ticket: Ticket,
    task_dir: Path,
    model: str,
    ledger: Ledger,
    complete: Callable[[list[dict]], Completion],
    run_trees: Callable[[str], TreeRun],
    out_dir: Path,
    cap: int,
    run_id: str,
    host: str,
    git_commit: str,
    mode: Literal["text", "image"] = "text",
    tool_timeout: float = 120,
) -> LoopResult:
    if cap < 1:
        raise ValueError("cap must be at least 1")
    out_dir.mkdir(parents=True, exist_ok=True)
    prompt = assemble_prompt(ticket, mode, task_dir)
    if not hasattr(prompt, "text"):
        path = _write(out_dir, ticket, model, host, git_commit, run_id, "none", [
            TrajectoryStep(index=0, stop_reason=StopReason.stuck, tool_error=prompt.error, message={"error": prompt.message}),
        ], None)
        return LoopResult(StopReason.stuck, None, path)

    messages = _messages(prompt.text, getattr(prompt, "image", None))
    prompt_hash = hashlib.sha256(prompt.text.encode()).hexdigest()
    steps: list[TrajectoryStep] = []
    saved: str | None = None
    reason = StopReason.retry_cap
    for index in range(cap):
        try:
            completion = _ask(ledger, model, complete, messages, index)
        except Exception as exc:
            from argus_core.ledger import QuotaExceeded

            if not isinstance(exc, QuotaExceeded):
                raise
            steps.append(TrajectoryStep(index=index, stop_reason=StopReason.quota_exceeded, tool_error="QuotaExceeded"))
            reason = StopReason.quota_exceeded
            break
        text = completion.content.strip()
        usage = completion.usage
        if not text:
            steps.append(_step(index, usage, raw="", tool_error="empty"))
            messages.append({"role": "user", "content": "The reply was empty. Return a Playwright script."})
            continue
        script = _script_of(text)
        problem = _problem(script)
        if problem is not None:
            steps.append(_step(index, usage, raw=text, tool_error=problem))
            messages.append({"role": "user", "content": problem})
            continue
        try:
            with tool_span("run_trees", run_id=run_id, step=index) as tool:
                trees = _within(tool_timeout, run_trees, script)
                if not (trees.failed_on_buggy and trees.passed_on_golden):
                    record_tool_error(tool, "not-a-repro", failed=False)
        except (ToolUnavailable, TimeoutError):
            steps.append(_step(index, usage, raw=text, tool_error="tool-unavailable", stop_reason=StopReason.tool_unavailable))
            reason = StopReason.tool_unavailable
            break
        if trees.failed_on_buggy and trees.passed_on_golden:
            saved = script
            reason = StopReason.submit
            steps.append(_step(index, usage, raw=text, stop_reason=StopReason.submit))
            break
        steps.append(_step(index, usage, raw=text, tool_error="not-a-repro"))
        messages.append(
            {"role": "user", "content": "The script must fail on the buggy tree and pass on the golden tree."}
        )
    else:
        reason = StopReason.retry_cap
        if steps:
            last = steps[-1]
            steps[-1] = last.model_copy(update={"stop_reason": StopReason.retry_cap})
    if reason is StopReason.retry_cap and steps and steps[-1].stop_reason is None:
        steps[-1] = steps[-1].model_copy(update={"stop_reason": StopReason.retry_cap})
    path = _write(out_dir, ticket, model, host, git_commit, run_id, prompt_hash, steps, saved)
    return LoopResult(reason, saved, path)


def _ask(
    ledger: Ledger, model: str, complete: Callable[[list[dict]], Completion], messages: list[dict], step: int | None = None
) -> Completion:
    holder: list[Completion] = []

    def send() -> LedgerUsage:
        with chat_span(model, step=step) as span:
            holder.append(complete(messages))
            record_completion(span, model, holder[-1])
        usage = holder[-1].usage
        return LedgerUsage(usage.tokens_in, usage.tokens_out, usage.tokens_cached)

    ledger.call(model, send, token_estimate=1)
    return holder[0]


def _messages(text: str, image: object) -> list[dict]:
    instruction = (
        "Write one Playwright script. Use getByRole with the accessible name. "
        "Assert the symptom with expect. Do not use a snapshot ref."
    )
    if image is None:
        user: str | list[dict] = text
    else:
        user = [
            {"type": "text", "text": text},
            {
                "type": "image_url",
                "image_url": {"url": f"data:{image.media_type};base64,{image.data_base64}"},
            },
        ]
    return [{"role": "system", "content": instruction}, {"role": "user", "content": user}]


def _within(timeout: float, fn: Callable[[str], TreeRun], script: str) -> TreeRun:
    box: list[tuple[bool, object]] = []

    def work() -> None:
        try:
            box.append((True, fn(script)))
        except BaseException as exc:
            box.append((False, exc))

    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        raise TimeoutError("tool-unavailable")
    ok, value = box[0]
    if not ok:
        raise value
    return value


def _script_of(text: str) -> str:
    match = _FENCE.search(text)
    return (match.group(1) if match else text).strip()


def _problem(script: str) -> str | None:
    if "page.evaluate" in script or "browser_run_code_unsafe" in script:
        return "Do not call page.evaluate or browser_run_code_unsafe."
    if _REF.search(script):
        return "Use the role and the accessible name. A snapshot ref is not a selector."
    if _ASSERT.search(script) is None:
        return "Add an assertion for the symptom."
    return None


def _step(index: int, usage: object, *, raw: str, tool_error: str | None = None, stop_reason: StopReason | None = None) -> TrajectoryStep:
    return TrajectoryStep(
        index=index,
        tokens_in=usage.tokens_in,
        tokens_out=usage.tokens_out,
        tokens_cached=usage.tokens_cached,
        raw_response=raw,
        tool_error=tool_error,
        stop_reason=stop_reason,
    )


def _write(
    out_dir: Path,
    ticket: Ticket,
    model: str,
    host: str,
    git_commit: str,
    run_id: str,
    prompt_hash: str,
    steps: list[TrajectoryStep],
    script: str | None,
) -> Path:
    trajectory = Trajectory(
        meta=TrajectoryMeta(
            run_id=run_id,
            task_id=ticket.id,
            model=model,
            host=host,
            prompt_hash=prompt_hash,
            git_commit=git_commit,
        ),
        steps=steps,
    )
    path = out_dir / "trajectory.jsonl"
    path.write_text(trajectory.to_jsonl(), encoding="utf-8")
    Trajectory.from_jsonl(path.read_text(encoding="utf-8"))
    if script is not None:
        (out_dir / "repro.spec.ts").write_text(script, encoding="utf-8")
    return path
