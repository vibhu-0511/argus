"""P10-T06: the live screen reads a file while the runner replaces it. On Windows that used to kill the run
(PermissionError from os.replace while a reader had the file open); the store now retries for a moment."""

import os
import threading

import pytest
from argus_core.types import Trajectory, TrajectoryMeta, TrajectoryStep

from argus_workbench import store

TICKET = {"id": "T-1", "text": "SIMULATED test ticket."}


def trajectory(n):
    meta = TrajectoryMeta(run_id="run-a", task_id="T-1", model="scripted", host="simulated", prompt_hash="none", git_commit="none")
    return Trajectory(meta=meta, steps=[TrajectoryStep(index=i, tool_name="t", message={"stage": "reproduce", "text": "x", "origin": "SIMULATED"}) for i in range(n)])


def test_a_busy_file_is_retried_then_written(monkeypatch):
    store.create_run(TICKET, scenario="normal", origin="SIMULATED", run_id="run-a")
    real, calls = os.replace, []

    def flaky(src, dst):
        calls.append(1)
        if len(calls) < 3:
            raise PermissionError("busy")
        return real(src, dst)

    monkeypatch.setattr(os, "replace", flaky)
    store.write_file("run-a", "trajectory.jsonl", trajectory(1))
    assert len(calls) == 3 and len(store.read_file("run-a", "trajectory.jsonl").steps) == 1


def test_a_file_that_stays_busy_still_fails_loudly(monkeypatch):
    store.create_run(TICKET, scenario="normal", origin="SIMULATED", run_id="run-a")
    monkeypatch.setattr(os, "replace", lambda *a: (_ for _ in ()).throw(PermissionError("locked")))
    with pytest.raises(PermissionError):
        store.write_file("run-a", "trajectory.jsonl", trajectory(1))


def test_a_reader_polling_while_the_runner_writes_never_breaks_the_write():
    store.create_run(TICKET, scenario="normal", origin="SIMULATED", run_id="run-a")
    store.write_file("run-a", "trajectory.jsonl", trajectory(0))
    done, errors = threading.Event(), []

    def reader():
        while not done.is_set():
            try:
                store.read_file("run-a", "trajectory.jsonl")
            except Exception as exc:  # noqa: BLE001  (any failure of a poll is a failure of the test)
                errors.append(exc)
                return

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    try:
        for i in range(1, 150):
            store.write_file("run-a", "trajectory.jsonl", trajectory(i))
    finally:
        done.set()
        thread.join(10)
    assert not errors and len(store.read_file("run-a", "trajectory.jsonl").steps) == 149
