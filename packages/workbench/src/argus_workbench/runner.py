"""Runners: they play one run into its folder, one trajectory step at a time. No model is called here.

    ScriptedRunner("quota").play(run_dir, clock=..., tick=..., stop=...)   # the spec's `sim` data, origin SIMULATED
    ReplayRunner(source_dir).play(run_dir, ...)                             # a stored trajectory.jsonl, origin REPLAY

A runner gets the folder of a run that `store.create_run` made, writes only files of that run, and only through
`store` (so every file is validated and every state change is a legal `flow.states` transition). `tick()` is
called after every step; the UI passes a wait of 700 ms (`sim.tick_ms`), tests pass a function that does nothing, so
no test sleeps. `stop` is a `threading.Event`: when it is set, the run ends where it is (see `owner_stop`).

Stage to state: reproduce is `reproducing`; locate and fix are `fixing`; verify is `verifying`. A normal run goes
received, reproducing, fixing, verifying, opening-pr, awaiting-qa. The ending of each scenario is in
docs/architecture/p10.md ("P10-T04").

The quota scenario is not faked: its steps are charged through a real `argus_core.ledger.Ledger` (a temp file, a
tiny `tokens_per_day` cap) and the step that stops the run carries the text of the `QuotaExceeded` the ledger raised.

Only ScriptedRunner reaches awaiting-qa, because only it writes a verdict. A replay or an adapter run never
produces a verdict, so it ends in `failed` with the recorded stop reason (see FixLoopRunner for the other adapter).

ponytail: the whole trajectory file is rewritten after every step (a few dozen steps, written atomically); an
append-only file needs a store.append_step that validates the line. Stop is checked after each step, so a run in
its last phase (writing the verdict) cannot be stopped.
ponytail: `_steps` and `_verdict` are the fixture module's own script of the spec data; the runner reuses them
so a fixture folder and a played folder cannot drift apart.
"""

from __future__ import annotations

import tempfile
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from argus_core.ledger import Ledger, ModelQuota, QuotaExceeded, Usage
from argus_core.types import StopReason, Trajectory, TrajectoryMeta, TrajectoryStep
from flow.states import Event, State

from argus_workbench import fixtures, store
from argus_workbench.errors import WorkbenchError
from argus_workbench.spec import load_spec, scenario_ids

Tick = Callable[[], None]
MODEL = "scripted-sim"  # the model name in the temp ledger; nothing is ever called with it
OWNER_STOP_TEXT = "stopped by owner"

STAGE_STATE = {
    "reproduce": State.REPRODUCING,
    "locate": State.FIXING,
    "fix": State.FIXING,
    "verify": State.VERIFYING,
}
_ORDER = [State.RECEIVED, State.REPRODUCING, State.FIXING, State.VERIFYING, State.OPENING_PR]
_FORWARD = {  # the event that leaves a state on the good path
    State.REPRODUCING: Event.REPRO_OK,
    State.FIXING: Event.FIX_OK,
    State.VERIFYING: Event.VERIFY_OK,
    State.OPENING_PR: Event.PR_OPENED,
}
FAIL = {  # the event that leaves a running state on the bad path (flow has no "stop" event)
    State.REPRODUCING: Event.REPRO_FAILED,
    State.FIXING: Event.FIX_FAILED,
    State.VERIFYING: Event.VERIFY_FAILED,
    State.OPENING_PR: Event.PR_FAILED,
}
ACTIVE = frozenset(FAIL)  # a run in one of these states can be stopped


class Runner(Protocol):
    origin: store.Origin

    def play(self, run_dir: Path, *, clock: store.Clock, tick: Tick, stop: threading.Event) -> store.RunState: ...


class Stopped(Exception):
    """Raised inside a Playback when the stop event is set; the runner turns it into `owner_stop`."""


def owner_stop(run_id: str, *, clock: store.Clock, root: Path) -> store.RunState:
    """End a running run on the owner's request. Works for a run that nobody is playing (after a server restart).

    flow.states has no stop event, so the run takes the failure event of the state it is in and ends in `failed`.
    `stop_reason` stays null (no argus-core StopReason means "stopped by owner"); the reason is the last
    trajectory step: tool `owner-stop`, tool_error "stopped by owner". The screens read it from there.
    """
    state = store.get_state(run_id, root=root)
    if state.state not in ACTIVE:
        raise WorkbenchError("not_running", "this run is not running", field="run_id", status=409)
    try:
        trajectory = store.read_file(run_id, "trajectory.jsonl", root=root)
    except WorkbenchError as exc:
        if exc.code != "missing_file":
            raise
        trajectory = None
    if trajectory is not None:
        step = TrajectoryStep(
            index=len(trajectory.steps), tool_name="owner-stop", tool_error=OWNER_STOP_TEXT,
            message={"stage": _stage_of(state.state), "text": OWNER_STOP_TEXT, "origin": state.origin},
        )
        store.write_file(run_id, "trajectory.jsonl", trajectory.model_copy(update={"steps": [*trajectory.steps, step]}), root=root)
    return store.advance(run_id, FAIL[state.state], clock=clock, root=root)


def _stage_of(state: State) -> str:
    return {State.REPRODUCING: "reproduce", State.FIXING: "fix", State.VERIFYING: "verify"}.get(state, "verify")


class Playback:
    """Writes one run folder while it plays: the trajectory after each step, the state at each stage change."""

    def __init__(self, run_dir: Path, *, origin: store.Origin, meta: TrajectoryMeta, clock: store.Clock, tick: Tick, stop: threading.Event):
        run_dir = run_dir.resolve()
        self.run_id, self.root = run_dir.name, run_dir.parent
        self.clock, self.tick, self.stop = clock, tick, stop
        self.meta, self.steps, self.origin = meta, [], origin
        if store.get_state(self.run_id, root=self.root).origin != origin:
            raise WorkbenchError("bad_origin", f"this runner plays {origin} runs only", field="origin", status=409)
        self.on_enter: dict[State, Callable[[], None]] = {}
        store.write_file(self.run_id, "trajectory.jsonl", Trajectory(meta=meta, steps=[]), root=self.root)
        if self.state().state == State.RECEIVED:
            self.advance(Event.START)

    def state(self) -> store.RunState:
        return store.get_state(self.run_id, root=self.root)

    def advance(self, event: Event, stop_reason: StopReason | None = None) -> store.RunState:
        return store.advance(self.run_id, event, stop_reason=stop_reason, clock=self.clock, root=self.root)

    def move_to(self, stage: str) -> None:
        """Walk forward along the good path until the run is in the state of `stage`. Never goes back."""
        target = STAGE_STATE[stage]
        while _ORDER.index(self.state().state) < _ORDER.index(target):
            entered = self.advance(_FORWARD[self.state().state]).state
            if entered in self.on_enter:
                self.on_enter[entered]()

    def checkpoint(self) -> None:
        if self.stop.is_set():
            raise Stopped

    def step(self, stage: str, step: TrajectoryStep) -> None:
        """Append one step (stamped with its stage and the origin tag), save, tick, then honour a stop."""
        self.move_to(stage)
        message = {**(step.message or {}), "stage": stage, "origin": self.origin}
        self.steps.append(step.model_copy(update={"index": len(self.steps), "message": message}))
        store.write_file(self.run_id, "trajectory.jsonl", Trajectory(meta=self.meta, steps=self.steps), root=self.root)
        self.tick()
        self.checkpoint()

    def fail(self, stop_reason: StopReason | None) -> store.RunState:
        return self.advance(FAIL[self.state().state], stop_reason)

    def stopped(self) -> store.RunState:
        return owner_stop(self.run_id, clock=self.clock, root=self.root)


def _meta(run_id: str, task_id: str, host: str) -> TrajectoryMeta:
    return TrajectoryMeta(run_id=run_id, task_id=task_id, model="scripted", host=host, prompt_hash="none", git_commit="none")


def _net(step: TrajectoryStep) -> int:
    return max(step.tokens_in + step.tokens_out - step.tokens_cached, 0)  # what the ledger counts (cached_counts False)


class ScriptedRunner:
    """Plays one of the five scenarios of the spec's `sim` block. Origin SIMULATED; the token counts are illustrative."""

    origin: store.Origin = "SIMULATED"

    def __init__(self, scenario: str):
        if scenario not in scenario_ids():
            raise WorkbenchError("unknown_scenario", f"scenario must be one of {', '.join(scenario_ids())}", field="scenario")
        self.scenario = scenario

    def play(self, run_dir: Path, *, clock: store.Clock = store.utc_now, tick: Tick = lambda: None,
             stop: threading.Event | None = None) -> store.RunState:
        stop = stop or threading.Event()
        run_dir = run_dir.resolve()
        ticket = store.read_file(run_dir.name, "ticket.json", root=run_dir.parent)
        pb = Playback(run_dir, origin=self.origin, meta=_meta(run_dir.name, ticket.id, "simulated"), clock=clock, tick=tick, stop=stop)
        steps = fixtures._steps(self.scenario)
        pb.on_enter[State.VERIFYING] = lambda: self._patch_and_report(pb)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                ledger = self._ledger(Path(tmp) / "ledger.json", steps)
                for step in steps:
                    pb.step(step.message["stage"], self._charge(ledger, step))
            if self.scenario in ("quota", "stuck"):
                return pb.fail(steps[-1].stop_reason)
            pb.move_to("verify")  # the verifier scenario has no verify steps; it still passes through verifying
            pb.checkpoint()
            verdict = fixtures._verdict(self.scenario, self.origin)
            store.write_file(pb.run_id, "verdict.json", verdict, root=pb.root)
            if not verdict.ok:
                return pb.advance(Event.VERIFY_FAILED, StopReason.submit)
            pb.advance(Event.VERIFY_OK)
            return pb.advance(Event.PR_OPENED, StopReason.submit)
        except Stopped:
            return pb.stopped()

    @staticmethod
    def _patch_and_report(pb: Playback) -> None:
        store.write_file(pb.run_id, "patch.diff", fixtures.PATCH, root=pb.root)
        store.write_file(pb.run_id, "report.html", fixtures.REPORT, root=pb.root)

    def _ledger(self, path: Path, steps: list[TrajectoryStep]) -> Ledger:
        # the quota scenario gets a day cap one token above what its steps before the halt use; others get no practical cap
        cap = sum(_net(s) for s in steps[:-1]) + 1 if self.scenario == "quota" else 10**9
        return Ledger(path, {MODEL: ModelQuota(10**6, cap, 10**6, 10**9, cached_counts=False)})

    def _charge(self, ledger: Ledger, step: TrajectoryStep) -> TrajectoryStep:
        """Charge the step through the ledger. The halting step of the quota scenario makes the ledger raise."""
        if step.stop_reason == StopReason.quota_exceeded:
            rule = load_spec()["sim"]["scenario"]["quota"]
            nxt = next(s for s in load_spec()["sim"]["stages"] if s["id"] == rule["haltStage"])["events"][rule["afterEvent"]]
            try:
                ledger.call(MODEL, lambda: Usage(0, 0, 0), token_estimate=nxt["in"] + nxt["out"])  # the call that would not fit
            except QuotaExceeded as exc:
                return step.model_copy(update={"tool_error": str(exc), "message": {"stage": step.message["stage"], "text": str(exc)}})
            raise AssertionError("the ledger did not stop the quota scenario")
        if step.tokens_in + step.tokens_out:
            ledger.call(MODEL, lambda: Usage(step.tokens_in, step.tokens_out, step.tokens_cached))
        return step


class ReplayRunner:
    """Plays a stored `trajectory.jsonl` from `source` (a folder). Origin REPLAY; token counts are the recorded ones.

    The steps are copied one per tick with the stage they carry (`message.stage`, kept from the previous step when a
    step has none, `reproduce` at the start) and the tag `origin: REPLAY`. Nothing is re-run and nothing is
    re-verified: no patch, report or verdict is written, so the run ends in `failed` with the stop reason of the last
    recorded step (`QuotaExceeded` shows as quota-wait, `stuck` as stuck, `submit` as failed with submit).
    """

    origin: store.Origin = "REPLAY"

    def __init__(self, source: Path):
        self.source = Path(source)

    def load(self) -> Trajectory:
        try:
            return Trajectory.from_jsonl((self.source / "trajectory.jsonl").read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise WorkbenchError("missing_file", "the replay source has no trajectory.jsonl", field="replay_from", status=404) from None
        except (ValueError, TypeError, AttributeError, UnicodeDecodeError) as exc:
            raise WorkbenchError("invalid_trajectory", f"replay source: {str(exc)[:200]}", field="replay_from") from None

    def play(self, run_dir: Path, *, clock: store.Clock = store.utc_now, tick: Tick = lambda: None,
             stop: threading.Event | None = None) -> store.RunState:
        stop = stop or threading.Event()
        run_dir = run_dir.resolve()
        source = self.load()  # validated before anything is written
        pb = Playback(run_dir, origin=self.origin, meta=source.meta.model_copy(update={"run_id": run_dir.name, "host": "replay"}), clock=clock, tick=tick, stop=stop)
        stage = "reproduce"
        try:
            for step in source.steps:
                recorded = (step.message or {}).get("stage")
                stage = recorded if recorded in STAGE_STATE and _later(recorded, stage) else stage
                pb.step(stage, step)
            return pb.fail(source.steps[-1].stop_reason if source.steps else None)
        except Stopped:
            return pb.stopped()


def _later(a: str, b: str) -> bool:
    order = list(STAGE_STATE)
    return order.index(a) >= order.index(b)
