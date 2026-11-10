"""The run manager: starts a run on a background thread, stops it, makes a retry. No model is called.

    manager = RunManager(tick_ms=700)           # tests: RunManager(tick_ms=0), so nothing sleeps
    manager.start(run_id)                       # created run (state received) -> reproducing, then plays on a thread
    manager.stop(run_id)                        # running -> failed ("stopped by owner", see runner.owner_stop)
    manager.retry(run_id)                       # a NEW run in state received; the old folder is only read

Which runner plays a run: origin SIMULATED plays the scenario in state.json (or the one passed to `start`, which
is stored); origin REPLAY plays the trajectory of another run of the store, named by `replay_from`. A run with
neither is refused before anything changes.

Retry rules: allowed from a terminal state other than `done`; a run that stopped with QuotaExceeded cannot be
retried until the UTC date has changed (the ledger rolls its day on the UTC date, `Ledger._roll_day`), so the Retry
button is not the only guard. A retry keeps the old scenario unless `scenario` is passed (a SIMULATED stuck run
would otherwise get stuck again), and it is not started: the caller starts it.

ponytail: threads are daemon threads of this process; a server restart leaves a running run in its state (Stop still
works on it, it is "orphaned"). One lock guards start and retry; a process per run needs a lock file.
"""

from __future__ import annotations

import logging
import threading
from datetime import UTC
from pathlib import Path

from argus_core.types import StopReason
from flow.states import TERMINAL, Event, State

from argus_workbench import store
from argus_workbench.errors import WorkbenchError
from argus_workbench.runner import ACTIVE, FAIL, ReplayRunner, Runner, ScriptedRunner, owner_stop
from argus_workbench.spec import load_spec, scenario_ids

log = logging.getLogger("argus_workbench.manager")


class RunManager:
    def __init__(self, *, tick_ms: int | None = None, clock: store.Clock = store.utc_now):
        self.tick_ms = load_spec()["sim"]["tick_ms"] if tick_ms is None else tick_ms
        self.clock = clock
        self._lock = threading.Lock()
        self._threads: dict[str, threading.Thread] = {}
        self._stops: dict[str, threading.Event] = {}

    # ---- start ------------------------------------------------------------------------------------------------

    def start(self, run_id: str, *, scenario: str | None = None, replay_from: str | None = None,
              root: Path | str | None = None) -> store.RunState:
        base = store.store_root(root).resolve()
        with self._lock:
            state = store.get_state(run_id, root=base)
            if state.state != State.RECEIVED:
                raise WorkbenchError("not_startable", f"this run is {state.state.value}; only a received run can start", field="run_id", status=409)
            runner = self._runner(state, scenario, replay_from, base)
            if state.origin == "SIMULATED" and state.scenario is None:  # the run was created without one: store the chosen one
                store.write_file(run_id, "state.json", state.model_copy(update={"scenario": scenario}), root=base)
            running = store.advance(run_id, Event.START, clock=self.clock, root=base)
            stop = threading.Event()
            thread = threading.Thread(target=self._play, args=(runner, base / run_id, stop), daemon=True, name=f"workbench-{run_id}")
            self._threads[run_id], self._stops[run_id] = thread, stop
            thread.start()
        return running

    def _runner(self, state: store.RunState, scenario: str | None, replay_from: str | None, base: Path) -> Runner:
        if state.origin == "REPLAY":
            if not replay_from:
                raise WorkbenchError("replay_source_required", "a REPLAY run needs replay_from, the id of a stored run", field="replay_from")
            if replay_from == state.run_id:
                raise WorkbenchError("bad_replay_source", "a run cannot replay itself", field="replay_from")
            return ReplayRunner(store.run_dir(replay_from, base))  # run_dir checks the id; a missing folder fails in load()
        if replay_from:
            raise WorkbenchError("bad_replay_source", "replay_from is only for a REPLAY run", field="replay_from")
        chosen = state.scenario or scenario
        if chosen is None:
            raise WorkbenchError("scenario_required", f"a SIMULATED run needs a scenario: {', '.join(scenario_ids())}", field="scenario")
        return ScriptedRunner(chosen)

    def _play(self, runner: Runner, run_dir: Path, stop: threading.Event) -> None:
        wait = lambda: stop.wait(self.tick_ms / 1000)  # noqa: E731  (a set stop event ends the wait at once)
        try:
            runner.play(run_dir, clock=self.clock, tick=wait, stop=stop)
        except Exception:  # the thread must never leave a run in a running state
            log.exception("run %s: runner failed", run_dir.name)
            self._crashed(run_dir)
        finally:
            with self._lock:
                self._threads.pop(run_dir.name, None)
                self._stops.pop(run_dir.name, None)

    def _crashed(self, run_dir: Path) -> None:
        try:
            state = store.get_state(run_dir.name, root=run_dir.parent)
            if state.state in ACTIVE:
                store.advance(run_dir.name, FAIL[state.state], stop_reason=None, clock=self.clock, root=run_dir.parent)
        except Exception:
            log.exception("run %s: could not mark the run failed", run_dir.name)

    # ---- stop -------------------------------------------------------------------------------------------------

    def stop(self, run_id: str, *, root: Path | str | None = None, timeout: float = 10.0) -> store.RunState:
        base = store.store_root(root).resolve()
        state = store.get_state(run_id, root=base)
        if state.state not in ACTIVE:
            raise WorkbenchError("not_running", f"this run is {state.state.value}, not running", field="run_id", status=409)
        with self._lock:
            thread, event = self._threads.get(run_id), self._stops.get(run_id)
        if thread is None or event is None:  # nobody plays it (the server restarted): end it here
            return owner_stop(run_id, clock=self.clock, root=base)
        event.set()
        thread.join(timeout)
        return store.get_state(run_id, root=base)

    # ---- retry ------------------------------------------------------------------------------------------------

    def retry(self, run_id: str, *, scenario: str | None = None, root: Path | str | None = None) -> store.RunState:
        base = store.store_root(root).resolve()
        with self._lock:
            old = store.get_state(run_id, root=base)  # unknown_run (404) if there is none
            if old.state not in TERMINAL or old.state == State.DONE:
                raise WorkbenchError("not_retryable", f"a {old.state.value} run cannot be retried", field="run_id", status=409)
            now = self.clock()
            if old.stop_reason == StopReason.quota_exceeded and old.updated_at.astimezone(UTC).date() >= now.astimezone(UTC).date():
                raise WorkbenchError("quota_wait", "the quota is used up; retry after the reset at 00:00 UTC", field="run_id", status=409)
            if scenario is not None and (old.origin != "SIMULATED" or scenario not in scenario_ids()):
                raise WorkbenchError("unknown_scenario", "scenario applies to SIMULATED runs and must be a known scenario", field="scenario")
            ticket = store.read_file(run_id, "ticket.json", root=base)
            new = store.create_run(ticket, scenario=scenario or old.scenario, origin=old.origin, retry_of=run_id, clock=self.clock, root=base)
            if store.has_file(run_id, "intake.json", root=base):
                store.write_file(new.run_id, "intake.json", store.read_file(run_id, "intake.json", root=base), root=base)
        return new

    # ---- tests ------------------------------------------------------------------------------------------------

    def wait(self, run_id: str | None = None, timeout: float = 10.0) -> None:
        """Block until the run (or every run) has finished playing. For tests and shutdown."""
        with self._lock:
            threads = [t for k, t in self._threads.items() if run_id in (None, k)]
        for thread in threads:
            thread.join(timeout)
