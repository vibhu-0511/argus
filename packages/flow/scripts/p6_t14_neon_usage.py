"""P6-T14: what the flow service's own polling asks of the database, and a check of Neon's figures against it.

Three commands (`uv run --all-packages python packages/flow/scripts/p6_t14_neon_usage.py <command> -h`):

- `expected`: from the code's real settings (`flow.reconcile.PollConfig`, the DBOS 3.4.0 loop constants)
  print how often something touches the database per hour while the process is awake, and whether the
  poller alone would keep Neon's compute awake (idle timeout 5 min, `docs/notes/p6-t00-versions.md`).
  Counts are wake-ups that each run at least one statement, not a statement count.
- `compare --usage FILE --cu SIZE`: read the owner's Neon figures and set them against the compute
  being on all the time. FILE is either console readings the owner typed in (the Console shows
  "Compute" as a total since the start of the billing period, no per-day view is documented) or a saved
  answer of the Consumption API (`compute_unit_seconds`; paid plans only). Format: docs/notes/p6-t14.md.
- `idle-probe --database-url URL`: launch DBOS exactly as the service does against a LOCAL Postgres with
  no ticket at all, and count the transactions it commits per second from `pg_stat_database`. This is
  a local measurement of the polling, not a Neon measurement.

Nothing here has been run against Neon. No credential is read except the database URL passed to the
probe, which is never printed or written. ponytail: the probe counts transactions on the whole database
and subtracts nothing but its own two reads; run it on a database nobody else uses.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from flow.reconcile import PollConfig

NEON_IDLE_SECONDS = 300.0  # Free plan: "suspends after 5 minutes of inactivity", cannot be disabled (neon.com/docs/introduction/plans, read 2026-11-02)
ALLOWANCE_CU_HOURS = 100.0  # Free plan, "100 CU-hours/project"; whether that is per month is NOT settled here
AWAKE_THRESHOLD = 0.9
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results" / "p6-t14"

# Read from dbos 3.4.0 (pinned in packages/flow/pyproject.toml): the loops that run in every launched process.
DBOS_QUEUE_POLL_SECONDS = 1.0  # dbos._queue.DEFAULT_QUEUE_POLLING_INTERVAL_SEC: the "argus-flow" queue worker dequeues this often
DBOS_QUEUE_LIST_SECONDS = 1.0  # dbos._queue.queue_thread: list_queues() every check_interval = 1.0
DBOS_BACKGROUND_JOBS_SECONDS = 1.0  # dbos._workflow_commands._BACKGROUND_JOBS_INTERVAL_SEC
DBOS_SCHEDULER_SECONDS = 30.0  # literal default in dbos._dbos (scheduler_polling_interval_sec); 1.0 s during the first 60 s


def expected_load(cfg: PollConfig | None = None, tickets: int = 0) -> dict:
    """Wake-ups per hour that touch the database while the process runs. `tickets` = open tickets the poller lists."""
    cfg = cfg or PollConfig()
    polled = min(tickets, cfg.page_size * cfg.max_pages)
    polls_per_hour = 3600 / cfg.interval_s
    dbos = {
        "queue_worker": 3600 / DBOS_QUEUE_POLL_SECONDS,
        "queue_list": 3600 / DBOS_QUEUE_LIST_SECONDS,
        "background_jobs": 3600 / DBOS_BACKGROUND_JOBS_SECONDS,
        "scheduler": 3600 / DBOS_SCHEDULER_SECONDS,
    }
    return {
        "poller": {
            "interval_seconds": cfg.interval_s,
            "polls_per_hour": polls_per_hour,
            "tickets_listed_per_poll": polled,
            "workflow_lookups_per_hour": polls_per_hour * polled,  # DbosLookup.get: one DBOS.get_workflow_status per ticket
            "new_connections_per_hour": 0,  # the lookups use DBOS's pool; db_wake opens one only per enqueue
            "extra_connection_per_enqueue": 1,  # flow.db_wake.wait_for_database before each enqueue
            "alone_keeps_neon_awake": cfg.interval_s <= NEON_IDLE_SECONDS,  # 300 s leaves no margin: a poll's own run time shortens the gap
        },
        "dbos_wakeups_per_hour": dbos,
        "dbos_wakeups_per_hour_total": sum(dbos.values()),
        "longest_gap_between_dbos_wakeups_seconds": max(DBOS_QUEUE_POLL_SECONDS, DBOS_QUEUE_LIST_SECONDS, DBOS_BACKGROUND_JOBS_SECONDS),
        "neon_idle_timeout_seconds": NEON_IDLE_SECONDS,
        "dbos_alone_keeps_neon_awake_while_running": max(DBOS_QUEUE_POLL_SECONDS, DBOS_QUEUE_LIST_SECONDS) < NEON_IDLE_SECONDS,
    }


# --- the owner's Neon figures ---------------------------------------------------------------------------


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def load_usage(data: dict, project_id: str | None = None) -> list[dict]:
    """`[{start, end, cu_hours}]` from console readings (cumulative) or from a Consumption API v2 answer."""
    if "readings" in data:
        rows = sorted(data["readings"], key=lambda r: r["at"])
        out = []
        for a, b in zip(rows, rows[1:]):
            if b["cu_hours"] < a["cu_hours"]:
                raise ValueError(f"the total fell between {a['at']} and {b['at']}: a new billing period, or a typo")
            out.append({"start": a["at"], "end": b["at"], "cu_hours": b["cu_hours"] - a["cu_hours"]})
        return out
    projects = data["projects"]
    if project_id:
        projects = [p for p in projects if p["project_id"] == project_id]
    if len(projects) != 1:
        raise ValueError("the file must hold exactly one project (pass --project-id to pick one)")
    out = []
    for period in projects[0]["periods"]:
        for c in period["consumption"]:
            seconds = sum(m["value"] for m in c["metrics"] if m["metric_name"] == "compute_unit_seconds")
            out.append({"start": c["timeframe_start"], "end": c["timeframe_end"], "cu_hours": seconds / 3600})
    return out


def compare(intervals: list[dict], cu: float, threshold: float = AWAKE_THRESHOLD, allowance: float = ALLOWANCE_CU_HOURS) -> dict:
    """Set measured CU-hours against `cu` held on for the whole interval. `cu` is the compute size the owner read in the Console."""
    rows, hours_total, cu_hours_total = [], 0.0, 0.0
    for i in intervals:
        hours = (_ts(i["end"]) - _ts(i["start"])).total_seconds() / 3600
        if hours <= 0:
            raise ValueError(f"interval {i['start']} to {i['end']} is empty")
        rows.append({**i, "hours": round(hours, 4), "always_on_cu_hours": round(cu * hours, 4), "active_fraction": round(i["cu_hours"] / (cu * hours), 4)})
        hours_total += hours
        cu_hours_total += i["cu_hours"]
    fraction = cu_hours_total / (cu * hours_total) if hours_total else None
    return {
        "compute_size_cu": cu,
        "intervals": rows,
        "hours": round(hours_total, 4),
        "cu_hours": round(cu_hours_total, 4),
        "active_fraction": None if fraction is None else round(fraction, 4),  # above 1 is possible: free computes autoscale up to 2 CU
        "reading": None if fraction is None else ("awake almost all the time" if fraction >= threshold else "slept for part of the time"),
        "awake_threshold": threshold,
        "share_of_allowance": round(cu_hours_total / allowance, 4),
        "hours_until_allowance_at_this_rate": round(allowance / (cu_hours_total / hours_total), 1) if cu_hours_total else None,
        "allowance_cu_hours": allowance,
        "allowance_period": "not decided here: the plans page says 'per project' in one place and 'per project per month' in another",
    }


# --- local probe ---------------------------------------------------------------------------------------


def idle_probe(database_url: str, seconds: float, warmup: float, baseline: float = 10.0) -> dict:
    """Transactions per second a launched DBOS commits on `database_url` with no workflow at all."""
    import time

    import psycopg

    from flow.config import FlowSettings
    from flow.dbos_runtime import launch, shutdown
    from flow.workflow import Deps

    def xacts(conn) -> int:
        return conn.execute("select xact_commit + xact_rollback from pg_stat_database where datname = current_database()").fetchone()[0]

    with psycopg.connect(database_url, autocommit=True) as mon:
        version = mon.execute("show server_version").fetchone()[0]
        a = xacts(mon)
        time.sleep(baseline)
        b = xacts(mon)
        launch(FlowSettings(database_url=database_url), Deps(None, None, None, None))
        try:
            time.sleep(warmup)  # DBOS migrates and the scheduler polls every second for its first 60 s
            c, t0 = xacts(mon), time.monotonic()
            time.sleep(seconds)
            d, elapsed = xacts(mon), time.monotonic() - t0
            connections = mon.execute("select count(*) from pg_stat_activity where datname = current_database() and pid <> pg_backend_pid()").fetchone()[0]
        finally:
            shutdown()
    own = 1  # the monitor's read of c commits inside the window; the read of d commits after it is counted
    return {
        "where": "LOCAL throwaway Postgres, not Neon",
        "postgres": version,
        "measured_seconds": round(elapsed, 1),
        "baseline_seconds": baseline,
        "baseline_transactions": b - a - 1,
        "dbos_idle_transactions": d - c - own,
        "dbos_idle_transactions_per_second": round((d - c - own) / elapsed, 2),
        "open_connections_during_idle": connections,
        "queue": "argus-flow, no workflow enqueued",
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("expected")
    e.add_argument("--tickets", type=int, default=0, help="open tickets the poller would list per poll")
    c = sub.add_parser("compare")
    c.add_argument("--usage", type=Path, required=True)
    c.add_argument("--cu", type=float, required=True, help="compute size in CU shown in the Neon Console (no default: it is read, not assumed)")
    c.add_argument("--project-id")
    c.add_argument("--out", type=Path, default=RESULTS_DIR / "compare.json")
    i = sub.add_parser("idle-probe")
    i.add_argument("--database-url", required=True, help="a LOCAL throwaway Postgres")
    i.add_argument("--seconds", type=float, default=120.0)
    i.add_argument("--warmup", type=float, default=70.0)
    i.add_argument("--out", type=Path, default=RESULTS_DIR / "idle-probe-local.json")
    args = p.parse_args(argv)
    if args.cmd == "expected":
        print(json.dumps(expected_load(PollConfig(), args.tickets), indent=2))
        return 0
    if args.cmd == "compare":
        result = compare(load_usage(json.loads(args.usage.read_text(encoding="utf-8")), args.project_id), args.cu)
    else:
        result = idle_probe(args.database_url, args.seconds, args.warmup)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
