"""Trajectory metrics over stored JSONL. The formulas are in docs/metrics.md."""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from pathlib import Path

from argus_core.types import StopReason, Trajectory, TrajectoryStep
from pydantic import BaseModel, ConfigDict

REPEAT = 3  # same as fix_loop.loop.REPEAT


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Ratio(_Model):
    """`value` is null when the denominator is zero."""

    value: float | None
    num: int
    den: int


class StepStats(_Model):
    total: int
    mean: float | None
    median: float | None


class MetricsSummary(_Model):
    trajectories: int
    steps: StepStats
    tool_error_rate: Ratio
    redundant_call_rate: Ratio
    stuck_rate: Ratio
    recover_after_gate_failure_rate: Ratio


@dataclass(frozen=True)
class RunMetrics:
    """Counts for one trajectory. Rates are formed from sums, so the counts are kept."""

    run_id: str
    task_id: str
    steps: int
    tool_errors: int
    calls: int  # calls other than submit
    redundant: int
    stuck: bool
    gate_failures: int
    recovered: int


def call_key(step: TrajectoryStep) -> str:
    try:
        args = json.loads(step.raw_response or "")
    except json.JSONDecodeError:
        args = step.raw_response
    if isinstance(args, dict) and isinstance(args.get("arguments"), dict):
        args = args["arguments"]
    return f"{step.tool_name}\n{json.dumps(args, sort_keys=True)}"


def run_metrics(trajectory: Trajectory) -> RunMetrics:
    steps = trajectory.steps
    keys = [call_key(s) if s.tool_name else None for s in steps]
    seen: set[str] = set()
    calls = redundant = 0
    for step, key in zip(steps, keys):
        if key is None or step.tool_name == "submit":
            continue
        calls += 1
        if step.tool_name == "edit":
            seen.clear()
            continue
        redundant += key in seen
        seen.add(key)
    stuck = any(
        keys[i] is not None and len(set(keys[i : i + REPEAT])) == 1
        for i in range(len(keys) - REPEAT + 1)
    )
    rejected = [
        i
        for i, s in enumerate(steps)
        if s.tool_name == "submit" and s.tool_error is None and s.stop_reason is None
    ]
    accepted = [i for i, s in enumerate(steps) if s.stop_reason == StopReason.submit]
    last_accept = max(accepted, default=-1)
    return RunMetrics(
        run_id=trajectory.meta.run_id,
        task_id=trajectory.meta.task_id,
        steps=len(steps),
        tool_errors=sum(s.tool_error is not None for s in steps),
        calls=calls,
        redundant=redundant,
        stuck=stuck,
        gate_failures=len(rejected),
        recovered=sum(i < last_accept for i in rejected),
    )


def _ratio(num: int, den: int) -> Ratio:
    return Ratio(value=round(num / den, 6) if den else None, num=num, den=den)


def summarize(runs: list[RunMetrics]) -> MetricsSummary:
    steps = [r.steps for r in runs]
    return MetricsSummary(
        trajectories=len(runs),
        steps=StepStats(
            total=sum(steps),
            mean=round(statistics.fmean(steps), 6) if steps else None,
            median=statistics.median(steps) if steps else None,
        ),
        tool_error_rate=_ratio(sum(r.tool_errors for r in runs), sum(steps)),
        redundant_call_rate=_ratio(sum(r.redundant for r in runs), sum(r.calls for r in runs)),
        stuck_rate=_ratio(sum(r.stuck for r in runs), len(runs)),
        recover_after_gate_failure_rate=_ratio(
            sum(r.recovered for r in runs), sum(r.gate_failures for r in runs)
        ),
    )


def load_trajectory(path: Path) -> Trajectory:
    return Trajectory.from_jsonl(path.read_text(encoding="utf-8"))


def load_dir(directory: Path, pattern: str = "**/trajectory.jsonl") -> list[RunMetrics]:
    return [run_metrics(load_trajectory(p)) for p in sorted(directory.glob(pattern))]


def format_summary(summary: MetricsSummary) -> str:
    def line(name: str, r: Ratio) -> str:
        value = "n/a" if r.value is None else f"{r.value:.4f}"
        return f"{name}: {value} ({r.num}/{r.den})"

    s = summary.steps
    mean = "n/a" if s.mean is None else f"{s.mean:.2f}"
    return "\n".join(
        [
            f"trajectories: {summary.trajectories}",
            f"steps: total {s.total}, mean {mean}, median {s.median}",
            line("tool_error_rate", summary.tool_error_rate),
            line("redundant_call_rate", summary.redundant_call_rate),
            line("stuck_rate", summary.stuck_rate),
            line("recover_after_gate_failure_rate", summary.recover_after_gate_failure_rate),
        ]
    )
