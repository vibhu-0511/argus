"""P6-T14 Neon usage script: the arithmetic, on made-up inputs. No Postgres, no Neon, no network.

The numbers in these tests are invented to check the code. They are not measurements, and nothing
here says how many CU-hours the service uses; that needs the owner's 48-hour run (docs/notes/p6-t14.md).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from flow.reconcile import PollConfig

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "p6_t14_neon_usage.py"


@pytest.fixture(scope="module")
def usage():
    spec = importlib.util.spec_from_file_location("p6_t14_neon_usage", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_expected_load_follows_the_real_poll_defaults(usage):
    e = usage.expected_load(tickets=10)
    cfg = PollConfig()
    assert e["poller"]["interval_seconds"] == cfg.interval_s == 300.0
    assert e["poller"]["polls_per_hour"] == 12
    assert e["poller"]["workflow_lookups_per_hour"] == 12 * 10
    assert usage.expected_load(tickets=10_000)["poller"]["tickets_listed_per_poll"] == cfg.page_size * cfg.max_pages  # the page bound


@pytest.mark.parametrize(("interval", "alone_awake"), [(60, True), (299, True), (300, True), (301, False), (900, False)])
def test_a_poller_alone_keeps_neon_awake_only_when_it_polls_within_the_idle_timeout(usage, interval, alone_awake):
    assert usage.expected_load(PollConfig(interval_s=interval))["poller"]["alone_keeps_neon_awake"] is alone_awake


def test_dbos_loops_are_shorter_than_the_idle_timeout_whatever_the_poll_interval(usage):
    e = usage.expected_load(PollConfig(interval_s=3600))
    assert e["poller"]["alone_keeps_neon_awake"] is False
    assert e["dbos_alone_keeps_neon_awake_while_running"] is True
    assert e["dbos_wakeups_per_hour_total"] >= 3 * 3600


def test_console_readings_become_intervals_and_a_fall_is_refused(usage):
    data = {"readings": [{"at": "2026-01-02T00:00:00Z", "cu_hours": 3.0}, {"at": "2026-01-01T00:00:00Z", "cu_hours": 1.0}, {"at": "2026-01-03T00:00:00Z", "cu_hours": 5.5}]}
    assert [i["cu_hours"] for i in usage.load_usage(data)] == [2.0, 2.5]  # sorted by time, then differenced
    data["readings"][0]["cu_hours"] = 0.5
    with pytest.raises(ValueError, match="fell"):
        usage.load_usage(data)


def test_api_answer_becomes_cu_hours_from_compute_unit_seconds(usage):
    day = lambda d, v: {"timeframe_start": f"2026-01-0{d}T00:00:00Z", "timeframe_end": f"2026-01-0{d + 1}T00:00:00Z", "metrics": [{"metric_name": "compute_unit_seconds", "value": v}, {"metric_name": "root_branch_bytes_month", "value": 9}]}
    data = {"projects": [{"project_id": "p1", "periods": [{"consumption": [day(1, 7200), day(2, 3600)]}]}]}
    assert [i["cu_hours"] for i in usage.load_usage(data)] == [2.0, 1.0]
    data["projects"].append({"project_id": "p2", "periods": []})
    with pytest.raises(ValueError, match="exactly one project"):
        usage.load_usage(data)
    assert usage.load_usage(data, "p1")[0]["cu_hours"] == 2.0


def test_compare_against_an_always_on_compute(usage):
    on = [{"start": "2026-01-01T00:00:00Z", "end": "2026-01-03T00:00:00Z", "cu_hours": 12.0}]  # 0.25 CU for 48 h is 12 CU-hours
    r = usage.compare(on, 0.25)
    assert (r["hours"], r["active_fraction"], r["reading"]) == (48.0, 1.0, "awake almost all the time")
    assert r["share_of_allowance"] == 0.12 and r["hours_until_allowance_at_this_rate"] == 400.0
    asleep = usage.compare([{**on[0], "cu_hours": 1.2}], 0.25)
    assert (asleep["active_fraction"], asleep["reading"]) == (0.1, "slept for part of the time")
    assert "not decided" in r["allowance_period"]
    with pytest.raises(ValueError, match="empty"):
        usage.compare([{"start": "2026-01-01T00:00:00Z", "end": "2026-01-01T00:00:00Z", "cu_hours": 0}], 0.25)
    assert usage.compare([{**on[0], "cu_hours": 0.0}], 0.25)["hours_until_allowance_at_this_rate"] is None
