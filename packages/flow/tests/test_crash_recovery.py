"""P6-T19 crash-recovery experiment, the fast subset: a few kill points, one repeat each.

Each test starts a real child process, kills it at a kill point with a hard kill, starts a second one
and reads the ledger. The full run (all 15 points, N repeats, both variants) is the script
`packages/flow/scripts/p6_t19_crash_recovery.py`; its results are in packages/flow/results/p6-t19/
and docs/notes/p6-t19.md. The DBOS variant needs `ARGUS_FLOW_DATABASE_URL` and is skipped without it.
Each test takes several seconds to a minute: it starts two Python processes and, for DBOS, launches DBOS twice.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

from flow.config import DATABASE_URL_ENV

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "p6_t19_crash_recovery.py"
needs_postgres = pytest.mark.skipif(not os.environ.get(DATABASE_URL_ENV), reason=f"{DATABASE_URL_ENV} is not set; needs a real Postgres")


@pytest.fixture(scope="module")
def harness():
    spec = importlib.util.spec_from_file_location("p6_t19_crash_recovery", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_plain_function_rerun_from_the_start_completes_and_repeats_every_earlier_call(harness, tmp_path):
    r = harness.run_one("A", "verify:effect", tmp_path)
    assert r["reached"] and r["completed"] and r["final_state"] == "done"
    assert r["duplicates"] == 0 and r["every_effect_once"]  # find-before-act holds the effects at one each
    # no durability: the rerun starts at repro again and calls repro, fix and verify a second time
    assert {c.split()[0] for c in r["repeated_calls"]} == {"dispatch-repro", "dispatch-fix", "dispatch-verify"}


@needs_postgres
def test_dbos_kill_between_steps_resumes_with_no_repeated_call(harness, tmp_path):
    """Killed as `fix` starts: repro's result is stored, so the restart replays it and calls nothing twice."""
    r = harness.run_one("B", "fix:before", tmp_path)
    assert r["reached"] and r["completed"] and r["final_state"] == "done"
    assert r["stored_steps_at_kill"] == ["repro_step"]
    assert r["repeated_calls"] == [] and r["duplicates"] == 0 and r["every_effect_once"]


@needs_postgres
def test_dbos_kill_before_the_step_result_is_stored_repeats_that_one_call_and_duplicates_nothing(harness, tmp_path):
    """Killed after the fix run was made and before DBOS stored fix_step: the one expected at-least-once repeat."""
    r = harness.run_one("B", "fix:effect", tmp_path)
    assert r["reached"] and r["completed"] and r["final_state"] == "done"
    assert r["stored_steps_at_kill"] == ["repro_step"]  # fix_step's side effect exists, its result does not
    assert [c.split()[0] for c in r["repeated_calls"]] == ["dispatch-fix"]  # the second call, and only that one
    assert r["duplicates"] == 0 and r["every_effect_once"]
