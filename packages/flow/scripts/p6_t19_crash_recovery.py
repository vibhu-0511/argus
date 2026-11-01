"""P6-T19 crash-recovery experiment: kill a real process at each step boundary, restart it, count.

Two variants run the same ticket pipeline with the same fakes (`flow.ledger_fakes`, whose world is a
file, so effects outlive the killed process):

- A, no durability: `ticket_workflow.__wrapped__`, the body of the DBOS workflow called as a plain
  function with the steps run as plain functions (DBOS runs a step outside a workflow as a normal
  call). Only the QA wait differs: `DBOS.recv` is replaced by polling a signal file. After a kill the
  restart is what a plain function can do: run again from the start when the ticket is seen again.
- B, DBOS: `flow.dbos_runtime.launch` with the pinned application version and executor id, as the
  service does. After a kill the restart is `launch` again; DBOS recovers the pending workflow.

For each kill point of `flow.ledger_fakes.KILL_POINTS` the harness starts a child process that stops
itself at that point (`AT <point>` on stdout), kills its whole process tree from outside (TerminateProcess
on Windows, SIGKILL elsewhere), starts a second process, and measures: did the run reach `done`,
effects made more than once in the ledger (duplicates), calls repeated, and recovery time = from
spawning the second process to its `DONE` line (interpreter start, imports and DBOS launch included).

Run (from the repo root, Postgres for B, see docs/notes/p6-t19.md for the container commands):

    uv run --all-packages python packages/flow/scripts/p6_t19_crash_recovery.py --repeats 10

Needs `ARGUS_FLOW_DATABASE_URL` for variant B (`--variants A` needs nothing). Writes
`packages/flow/results/p6-t19/results.json`. No model, no network, no GitHub: the runners and the
GitHub client are fakes.

ponytail: recovery time is wall clock on a loaded machine, N per kill point is small (see the
JSON); p95 over a handful of runs is close to the maximum. Raise `--repeats` for a tighter number.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import queue
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any

from flow.ledger_fakes import BEFORE_STORED, KILL_POINTS, Hook, Ledger, LedgerGitHub, LedgerRunner, duplicates, repeated_calls
from flow.workflow import Deps, Outcome

SCRIPT = Path(__file__).resolve()
RESULTS_DIR = SCRIPT.parent.parent / "results" / "p6-t19"
QA_TIMEOUT = 120.0
FIRST_TIMEOUT = 180.0  # the first process must reach its kill point (B migrates the database the first time)
RECOVERY_TIMEOUT = 120.0
ATTEMPTS = 3  # a first process that never reaches its kill point is retried; every attempt stays in the JSON
SIGNAL = {"decision": "approve", "source": "review-comment", "by": "", "key": "t19"}
EXPECTED_MADE = {"dispatch-repro": 1, "dispatch-fix": 1, "dispatch-verify": 1, "push-branch": 1, "create-pr": 1, "comment": 2, "label": 2, "ready-pr": 1}


# --- the child process ---------------------------------------------------------------------------------


def make_deps(ledger: Ledger, hook: Hook) -> Deps:
    return Deps(
        LedgerRunner("repro", ledger, hook, Outcome(True, "repro.sh")),
        LedgerRunner("fix", ledger, hook, Outcome(True, "the patch")),
        LedgerRunner("verify", ledger, hook, Outcome(True, "ok")),
        LedgerGitHub(ledger, hook),
        qa_timeout_seconds=QA_TIMEOUT,
    )


def hook_qa_wait(hook: Hook, probe) -> None:
    """Add the two kill points around the QA wait. `probe()` returns once the workflow is inside the wait."""
    import flow.workflow as wf

    original = wf.await_qa

    def await_qa(ticket_id: str):
        hook.hit("qa:before-wait")
        if hook.kill_at == "qa:waiting":
            threading.Thread(target=lambda: (probe(), hook.hit("qa:waiting")), daemon=True).start()
        return original(ticket_id)

    wf.await_qa = await_qa


def run_plain(ticket: str, run_dir: Path, hook: Hook, send_signal: bool) -> dict[str, Any]:
    import flow.workflow as wf

    signal_file, waiting = run_dir / "qa-signal.json", threading.Event()

    class PlainDBOS:  # the one thing `await_qa` uses from DBOS
        @staticmethod
        def recv(topic: str, timeout_seconds: float) -> dict | None:
            waiting.set()
            deadline = time.monotonic() + timeout_seconds  # a rerun starts a new deadline; DBOS keeps the stored one
            while time.monotonic() < deadline:
                if signal_file.exists():
                    return json.loads(signal_file.read_text())
                time.sleep(0.05)
            return None

    wf.DBOS = PlainDBOS
    wf.set_deps(make_deps(Ledger(run_dir / "ledger.jsonl"), hook))
    hook_qa_wait(hook, waiting.wait)
    if send_signal:
        signal_file.write_text(json.dumps(SIGNAL))
    return wf.ticket_workflow.__wrapped__(ticket)


def sleep_row_exists(ticket: str) -> bool:
    import psycopg

    with psycopg.connect(os.environ["ARGUS_FLOW_DATABASE_URL"], autocommit=True, connect_timeout=5) as conn:
        return conn.execute(
            "select 1 from dbos.operation_outputs where workflow_uuid = %s and function_name = 'DBOS.sleep'", (ticket,)
        ).fetchone() is not None


def run_dbos(ticket: str, run_dir: Path, hook: Hook, role: str, send_signal: bool) -> dict[str, Any]:
    from dbos import DBOS

    from flow.config import FlowSettings
    from flow.dbos_runtime import launch, shutdown
    from flow.qa import send_qa_signal

    def probe() -> None:  # the wait is durable once DBOS has stored its deadline (the `DBOS.sleep` row)
        while not sleep_row_exists(ticket):
            time.sleep(0.05)

    hook_qa_wait(hook, probe)
    enqueuer = launch(FlowSettings.from_env(), make_deps(Ledger(run_dir / "ledger.jsonl"), hook))
    handle = DBOS.retrieve_workflow(ticket) if role == "recover" else enqueuer.enqueue(ticket)
    if send_signal:
        send_qa_signal(ticket, "approve", "review-comment", "1")
    out = handle.get_result()
    print("DONE " + json.dumps({"state": out["state"], "trail": out["trail"]}), flush=True)
    shutdown()
    return out


def child_main(args: argparse.Namespace) -> None:
    run_dir, hook = Path(args.dir), Hook(None if args.kill_at == "none" else args.kill_at)
    if args.variant == "A":
        out = run_plain(args.ticket, run_dir, hook, args.signal == "1")
        print("DONE " + json.dumps({"state": out["state"], "trail": out["trail"]}), flush=True)
    else:
        run_dbos(args.ticket, run_dir, hook, args.role, args.signal == "1")


# --- the harness ---------------------------------------------------------------------------------------


class Child:
    def __init__(self, variant: str, ticket: str, run_dir: Path, role: str, kill_at: str | None, send_signal: bool) -> None:
        argv = [
            sys.executable, str(SCRIPT), "child", "--variant", variant, "--ticket", ticket, "--dir", str(run_dir),
            "--role", role, "--kill-at", kill_at or "none", "--signal", "1" if send_signal else "0",
        ]
        log = open(run_dir / f"{role}.stderr.log", "wb")
        self.started = time.monotonic()
        self.proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=log, text=True, start_new_session=os.name != "nt")
        log.close()
        self.lines: queue.Queue[str | None] = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        for line in self.proc.stdout:
            self.lines.put(line.strip())
        self.lines.put(None)  # EOF: every holder of the pipe is gone

    def wait_for(self, prefixes: tuple[str, ...], timeout: float) -> tuple[str, float] | None:
        """The first stdout line that starts with a prefix and the monotonic seconds since spawn, or None (EOF or timeout)."""
        deadline = self.started + timeout
        while (left := deadline - time.monotonic()) > 0:
            try:
                line = self.lines.get(timeout=left)
            except queue.Empty:
                return None
            if line is None:
                return None
            if line.startswith(prefixes):
                return line, time.monotonic() - self.started
        return None

    def kill(self) -> None:
        """Hard-kill the process and everything it started. A venv `python.exe` on Windows is a launcher that runs the real one."""
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.proc.pid)], capture_output=True)
        else:
            import signal

            os.killpg(self.proc.pid, signal.SIGKILL)
        self.proc.wait(timeout=30)

    def finish(self) -> None:
        try:
            self.proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.kill()


def stored_steps(ticket: str) -> list[str]:
    import psycopg

    with psycopg.connect(os.environ["ARGUS_FLOW_DATABASE_URL"], autocommit=True, connect_timeout=5) as conn:
        rows = conn.execute("select function_name from dbos.operation_outputs where workflow_uuid = %s order by function_id", (ticket,)).fetchall()
    return [r[0] for r in rows]


def cancel_workflow(ticket: str) -> None:
    """A run that did not recover must not be picked up by the next process's recovery."""
    import psycopg

    with psycopg.connect(os.environ["ARGUS_FLOW_DATABASE_URL"], autocommit=True, connect_timeout=5) as conn:
        conn.execute("update dbos.workflow_status set status = 'CANCELLED' where workflow_uuid = %s and status in ('PENDING', 'ENQUEUED')", (ticket,))


def run_one(variant: str, point: str, base: Path, recovery_timeout: float = RECOVERY_TIMEOUT, keep_rows: bool = False) -> dict[str, Any]:
    ticket = f"acme/t19-{uuid.uuid4().hex[:8]}#19"
    run_dir = Path(tempfile.mkdtemp(prefix="run-", dir=base))
    ledger = Ledger(run_dir / "ledger.jsonl")
    rec: dict[str, Any] = {"variant": variant, "point": point, "ticket": ticket, "reached": False, "completed": False, "recovery_seconds": None}
    first = Child(variant, ticket, run_dir, "first", point, send_signal=point.startswith("finish"))
    got = first.wait_for(("AT ", "DONE"), FIRST_TIMEOUT)
    if got is None or not got[0].startswith("AT "):
        first.kill()
        rec["error"] = "the first process did not reach the kill point" + (" (it finished)" if got else "")
        if variant == "B":
            cancel_workflow(ticket)
        return rec
    first.kill()
    rec["reached"] = True
    before = ledger.rows()
    rec["rows_at_kill"] = len(before)
    if variant == "B":
        rec["stored_steps_at_kill"] = [s for s in stored_steps(ticket) if s.endswith("_step")]
    second = Child(variant, ticket, run_dir, "recover", None, send_signal=True)
    got = second.wait_for(("DONE",), recovery_timeout)
    if got is None:
        second.kill()
        rec["error"] = f"no DONE within {recovery_timeout:g} s after the restart"
        if variant == "B":
            cancel_workflow(ticket)
    else:
        second.finish()
        done = json.loads(got[0].removeprefix("DONE "))
        rec.update(final_state=done["state"], completed=done["state"] == "done", recovery_seconds=round(got[1], 3))
    log = run_dir / "recover.stderr.log"
    rec["recovery_db_connection_errors"] = log.read_text(errors="replace").count("ConnectionTimeout") if log.exists() else 0
    rows = ledger.rows()
    made = {}
    for r in rows:
        made[r["op"]] = made.get(r["op"], 0) + r["made"]
    made = {op: n for op, n in made.items() if n}  # reads (find-pr) make nothing
    rec.update(
        duplicates=duplicates(rows),
        repeated_calls=repeated_calls(rows),
        effects_made=made,
        every_effect_once=made == EXPECTED_MADE,
        kill_before_result_stored=point in BEFORE_STORED,
    )
    if rec["recovery_seconds"] is None and rec["recovery_db_connection_errors"]:
        rec["infra"] = True  # the restarted process could not reach Docker's Postgres: not a result about recovery
    if keep_rows:
        rec["ledger"] = rows
    return rec


def report(paths: list[str]) -> str:
    """Markdown tables from results files: the Ablation table, then one row per kill point."""
    out = ["| Variant | Kills | Completed after crash | Duplicate side effects | Recovery p50 | Recovery p95 | Repeated calls per kill |", "|---|---|---|---|---|---|---|"]
    points = []
    for path in paths:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        for v, s in d["summary"].items():
            if not s["kills"]:
                continue
            out.append(
                f"| {v} | {s['kills']} | {s['completed']} of {s['kills']} | {s['duplicate_effects']} (in {s['runs_with_duplicates']} runs) | "
                f"{s['recovery_p50_s']:.2f} s | {s['recovery_p95_s']:.2f} s | {s['repeated_calls_mean']} |"
            )
            for p, q in d["by_point"][v].items():
                points.append((p, v, q))
    out += ["", "| Kill point | Variant | Completed | Duplicates | Repeated calls (mean) | p50 | p95 | max |", "|---|---|---|---|---|---|---|---|"]
    for p in KILL_POINTS:
        for _, v, q in sorted((x for x in points if x[0] == p), key=lambda x: x[1]):
            out.append(f"| `{p}` | {v} | {q['completed']} of {q['kills']} | {q['duplicate_effects']} | {q['repeated_calls_mean']} | {q['recovery_p50_s']:.2f} | {q['recovery_p95_s']:.2f} | {q['recovery_max_s']:.2f} |")
    return "\n".join(out)


def baseline(variant: str, base: Path) -> float:
    """Seconds from spawn to DONE for a run nobody kills, the process start and DBOS launch included."""
    for attempt in range(ATTEMPTS):
        try:
            return baseline_once(variant, base)
        except RuntimeError as e:  # Docker's port forwarding drops connections under load
            print(f"{e}; retrying", flush=True)
    return baseline_once(variant, base)


def baseline_once(variant: str, base: Path) -> float:
    ticket = f"acme/t19-{uuid.uuid4().hex[:8]}#19"
    run_dir = Path(tempfile.mkdtemp(prefix="base-", dir=base))
    child = Child(variant, ticket, run_dir, "solo", None, send_signal=True)
    got = child.wait_for(("DONE",), RECOVERY_TIMEOUT)
    child.finish()
    if got is None:
        raise RuntimeError(f"baseline run of {variant} did not finish; see {run_dir}")
    return round(got[1], 3)


# --- numbers ---------------------------------------------------------------------------------------------


def percentile(values: list[float], p: float) -> float | None:
    """Nearest rank: the smallest value with at least p percent of the values at or below it."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(p / 100 * len(ordered)) - 1)]


def summarise(records: list[dict[str, Any]]) -> dict[str, Any]:
    reached = [r for r in records if r["reached"]]
    times = [r["recovery_seconds"] for r in reached if r["completed"]]
    return {
        "kills": len(reached),
        "not_reached": len(records) - len(reached),
        "completed": sum(r["completed"] for r in reached),
        "runs_with_duplicates": sum(r["duplicates"] > 0 for r in reached),
        "duplicate_effects": sum(r["duplicates"] for r in reached),
        "repeated_calls_mean": round(statistics.fmean(len(r["repeated_calls"]) for r in reached), 2) if reached else None,
        "recovery_p50_s": percentile(times, 50),
        "recovery_p95_s": percentile(times, 95),
        "recovery_max_s": max(times) if times else None,
        "n_timed": len(times),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("report", help="print markdown tables from the results files given as arguments").add_argument("files", nargs="+")
    c = sub.add_parser("child")
    c.add_argument("--variant", choices="AB", required=True)
    c.add_argument("--ticket", required=True)
    c.add_argument("--dir", required=True)
    c.add_argument("--role", choices=["first", "recover", "solo"], required=True)
    c.add_argument("--kill-at", default="none")
    c.add_argument("--signal", choices=["0", "1"], default="0")
    ap.add_argument("--variants", default="A,B")
    ap.add_argument("--points", default=",".join(KILL_POINTS))
    ap.add_argument("--repeats", type=int, default=10)
    ap.add_argument("--baseline", type=int, default=5, help="runs nobody kills, per variant")
    ap.add_argument("--out", default=str(RESULTS_DIR / "results.json"))
    args = ap.parse_args()
    if args.cmd == "child":
        return child_main(args)
    if args.cmd == "report":
        return print(report(args.files))

    variants, points = args.variants.split(","), args.points.split(",")
    if "B" in variants and not os.environ.get("ARGUS_FLOW_DATABASE_URL"):
        sys.exit("variant B needs ARGUS_FLOW_DATABASE_URL (a throwaway Postgres); use --variants A to skip it")
    base = Path(tempfile.mkdtemp(prefix="p6t19-"))
    records: list[dict[str, Any]] = []
    discarded: list[dict[str, Any]] = []
    base_times: dict[str, list[float]] = {}

    def save() -> dict[str, Any]:  # after every run, so a long run that dies keeps what it has
        out = {
            "experiment": "P6-T19 crash recovery",
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "machine": platform.platform(),
            "python": platform.python_version(),
            "dbos": version("dbos"),
            "repeats_per_kill_point": args.repeats,
            "qa_timeout_seconds": QA_TIMEOUT,
            "no_crash_run_seconds": base_times,
            "summary": {v: summarise([r for r in records if r["variant"] == v]) for v in variants},
            "by_point": {v: {p: summarise([r for r in records if r["variant"] == v and r["point"] == p]) for p in points} for v in variants},
            "discarded_attempts": discarded,
            "runs": records,
        }
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
        return out

    for v in variants:
        if v == "B":
            baseline(v, base)  # warm-up: the first launch applies the DBOS migrations
        base_times[v] = [baseline(v, base) for _ in range(args.baseline)]
        print(f"{v} no-crash run: {base_times[v]} s", flush=True)
        for p in points:
            for i in range(args.repeats):
                for attempt in range(1, ATTEMPTS + 1):
                    r = run_one(v, p, base)
                    r["rep"], r["attempt"] = i + 1, attempt
                    if r["reached"] and not r.get("infra"):
                        break
                    discarded.append(r)  # not a result: no kill point reached, or Docker's Postgres did not answer
                    print(f"{v} {p} #{i + 1} attempt {attempt} discarded: {r['error']}", flush=True)
                records.append(r)
                save()
                print(f"{v} {p} #{i + 1}: completed={r['completed']} dup={r.get('duplicates')} repeats={len(r.get('repeated_calls', []))} t={r['recovery_seconds']} {r.get('error', '')}", flush=True)
    print(json.dumps({"summary": save()["summary"], "no_crash_run_seconds": base_times}, indent=1))


if __name__ == "__main__":
    main()
