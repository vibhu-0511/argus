"""P10-T01: the run store. Every test points the store at tmp_path; no model is called."""

import json
import os

import pytest
from argus_core.types import StopReason, Ticket
from flow.states import TRANSITIONS, Event, State

from argus_workbench import store
from argus_workbench.errors import WorkbenchError
from argus_workbench.spec import load_spec, scenario_ids

TICKET = {"id": "T-1", "text": "button is cut off at 375 px"}


def make(tmp_path, run_id="run-a", **kw):
    return store.create_run(TICKET, run_id=run_id, root=tmp_path, **kw)


def test_create_run_writes_ticket_and_state(tmp_path):
    state = make(tmp_path)
    folder = tmp_path / "run-a"
    assert sorted(p.name for p in folder.iterdir()) == ["state.json", "ticket.json"]
    assert Ticket.model_validate_json((folder / "ticket.json").read_text("utf-8")).id == "T-1"
    on_disk = json.loads((folder / "state.json").read_text("utf-8"))
    assert on_disk["state"] == "received" and on_disk["stop_reason"] is None
    assert on_disk["origin"] == "SIMULATED" and on_disk["display_state"] == "received"
    assert on_disk["created_by_retry_of"] is None
    assert state == store.get_state("run-a", root=tmp_path)


def test_store_root_comes_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv(store.ENV_ROOT, str(tmp_path / "from-env"))
    store.create_run(TICKET, run_id="run-env")
    assert (tmp_path / "from-env" / "run-env" / "state.json").is_file()


def test_default_root_is_git_ignored_local_folder(monkeypatch):
    monkeypatch.delenv(store.ENV_ROOT, raising=False)
    root = store.store_root()
    assert root.parts[-3:] == (".local", "workbench", "runs")


@pytest.mark.parametrize(
    "bad",
    ["../x", "..", "a/b", "a\\b", "/etc/passwd", "C:\\x", "C:/x", "Run-A", "UPPER", "", "x" * 65, "ünï", "a b", "a.b", "a\n",
     "run\x00", "con", "nul", "com1", ".", "a:b"],
)
def test_bad_run_id_refused_and_nothing_written(tmp_path, bad):
    with pytest.raises(WorkbenchError) as exc:
        store.create_run(TICKET, run_id=bad, root=tmp_path)
    assert exc.value.code == "bad_run_id" and exc.value.field == "run_id"
    assert list(tmp_path.iterdir()) == []
    with pytest.raises(WorkbenchError):
        store.run_dir(bad, tmp_path)
    with pytest.raises(WorkbenchError):
        store.read_file(bad, "state.json", root=tmp_path)


def test_run_id_edges_accepted(tmp_path):
    for ok in ["a", "0", "-", "x" * 64, "run-123-abc"]:
        store.create_run(TICKET, run_id=ok, root=tmp_path)


def test_non_string_run_id_refused(tmp_path):
    for bad in (None, 5, b"abc", ["a"]):
        with pytest.raises(WorkbenchError):
            store.check_run_id(bad)


def test_trailing_newline_is_not_accepted_by_the_pattern():
    # re.match with $ would accept "abc\n"; the store uses fullmatch
    with pytest.raises(WorkbenchError):
        store.check_run_id("abc\n")


def test_folder_that_resolves_outside_root_refused(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "root"
    root.mkdir()
    try:
        os.symlink(outside, root / "evil", target_is_directory=True)
    except (OSError, NotImplementedError):
        # no symlink privilege: a Windows directory junction resolves outside the root the same way
        import subprocess
        made = os.name == "nt" and subprocess.run(["cmd", "/c", "mklink", "/J", str(root / "evil"), str(outside)], capture_output=True).returncode == 0
        if not made:
            pytest.skip("neither symlinks nor junctions can be made here")
    with pytest.raises(WorkbenchError) as exc:
        store.run_dir("evil", root)
    assert exc.value.code == "bad_run_id"


def test_unknown_state_refused(tmp_path):
    make(tmp_path)
    bad = {**json.loads((tmp_path / "run-a" / "state.json").read_text("utf-8")), "state": "quota-wait"}
    with pytest.raises(WorkbenchError) as exc:
        store.write_file("run-a", "state.json", bad, root=tmp_path)
    assert exc.value.code == "unknown_state" and exc.value.field == "state"
    assert store.get_state("run-a", root=tmp_path).state == State.RECEIVED


def test_unknown_stop_reason_and_origin_refused(tmp_path):
    make(tmp_path)
    base = json.loads((tmp_path / "run-a" / "state.json").read_text("utf-8"))
    with pytest.raises(WorkbenchError) as exc:
        store.write_file("run-a", "state.json", {**base, "stop_reason": "because"}, root=tmp_path)
    assert exc.value.code == "unknown_stop_reason"
    with pytest.raises(WorkbenchError) as exc:
        store.write_file("run-a", "state.json", {**base, "origin": "REAL"}, root=tmp_path)
    assert exc.value.code == "bad_origin"
    with pytest.raises(WorkbenchError) as exc:
        store.create_run(TICKET, run_id="run-b", origin="LIVE", root=tmp_path)  # type: ignore[arg-type]
    assert exc.value.code == "bad_origin"
    assert not (tmp_path / "run-b").exists()


def test_every_flow_state_and_stop_reason_is_accepted(tmp_path):
    make(tmp_path)
    base = json.loads((tmp_path / "run-a" / "state.json").read_text("utf-8"))
    for s in State:
        for r in [None, *StopReason]:
            base_i = {**base, "state": s.value, "stop_reason": r.value if r else None, "display_state": None}
            got = store.write_file("run-a", "state.json", base_i, root=tmp_path)
            assert got.display_state == store.display_state(s, r)


def test_display_state_is_derived_and_checked(tmp_path):
    assert store.display_state(State.FAILED, StopReason.quota_exceeded) == "quota-wait"
    assert store.display_state(State.FAILED, StopReason.stuck) == "stuck"
    assert store.display_state(State.FAILED, StopReason.submit) == "failed"
    assert store.display_state(State.AWAITING_QA, None) == "awaiting-qa"
    make(tmp_path)
    base = json.loads((tmp_path / "run-a" / "state.json").read_text("utf-8"))
    with pytest.raises(WorkbenchError):
        store.write_file("run-a", "state.json", {**base, "display_state": "done"}, root=tmp_path)


def test_unknown_scenario_and_bad_retry_id_refused(tmp_path):
    with pytest.raises(WorkbenchError):
        make(tmp_path, scenario="nope")
    with pytest.raises(WorkbenchError) as exc:
        make(tmp_path, retry_of="../a")
    assert exc.value.code == "bad_run_id" and exc.value.field == "created_by_retry_of"
    with pytest.raises(WorkbenchError) as exc:
        make(tmp_path, retry_of="missing")
    assert exc.value.code == "unknown_run"
    assert list(tmp_path.iterdir()) == []


def test_invalid_ticket_refused_and_nothing_written(tmp_path):
    for bad in [{"id": "", "text": "x"}, {"id": "a", "text": ""}, {"id": "a"}, {"id": "a", "text": "x", "extra": 1},
                {"id": "a", "text": "x", "screenshot": {"media_type": "image/png", "path": "../x.png"}}]:
        with pytest.raises(WorkbenchError) as exc:
            store.create_run(bad, run_id="run-t", root=tmp_path)
        assert exc.value.code == "invalid_ticket"
    assert list(tmp_path.iterdir()) == []


def test_duplicate_run_id_refused_and_old_run_untouched(tmp_path):
    make(tmp_path)
    before = (tmp_path / "run-a" / "state.json").read_bytes()
    with pytest.raises(WorkbenchError) as exc:
        store.create_run({"id": "other", "text": "other"}, run_id="run-a", root=tmp_path)
    assert exc.value.code == "run_exists"
    assert (tmp_path / "run-a" / "state.json").read_bytes() == before


def test_retry_makes_new_folder_and_never_changes_old(tmp_path):
    old = make(tmp_path)
    snapshot = {p.name: p.read_bytes() for p in (tmp_path / "run-a").iterdir()}
    new = make(tmp_path, run_id="run-b", retry_of="run-a")
    assert new.created_by_retry_of == "run-a" and new.state == State.RECEIVED and new.run_id != old.run_id
    assert {p.name: p.read_bytes() for p in (tmp_path / "run-a").iterdir()} == snapshot


def test_injected_clock_sets_timestamps(tmp_path):
    from datetime import UTC, datetime
    fixed = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    state = make(tmp_path, clock=lambda: fixed)
    assert state.created_at == fixed and state.updated_at == fixed
    state2 = store.advance("run-a", Event.START, clock=lambda: datetime(2026, 1, 2, 3, 4, 6, tzinfo=UTC), root=tmp_path)
    assert state2.created_at == fixed and state2.updated_at.second == 6 and state2.state == State.REPRODUCING


def test_naive_timestamp_refused(tmp_path):
    from datetime import datetime
    with pytest.raises(WorkbenchError):
        make(tmp_path, clock=lambda: datetime(2026, 1, 1))


def test_advance_follows_flow_transitions_and_refuses_illegal(tmp_path):
    make(tmp_path)
    store.advance("run-a", Event.START, root=tmp_path)
    with pytest.raises(WorkbenchError) as exc:
        store.advance("run-a", Event.PR_OPENED, root=tmp_path)
    assert exc.value.code == "illegal_transition" and exc.value.status == 409
    assert store.get_state("run-a", root=tmp_path).state == State.REPRODUCING
    # the whole table is reachable through advance
    for frm, ev, to, _ in TRANSITIONS:
        rid = f"t-{frm.value}-{ev.value}".replace("_", "-")
        make(tmp_path, run_id=rid)
        path = {
            State.RECEIVED: [], State.REPRODUCING: [Event.START], State.FIXING: [Event.START, Event.REPRO_OK],
            State.VERIFYING: [Event.START, Event.REPRO_OK, Event.FIX_OK],
            State.OPENING_PR: [Event.START, Event.REPRO_OK, Event.FIX_OK, Event.VERIFY_OK],
            State.AWAITING_QA: [Event.START, Event.REPRO_OK, Event.FIX_OK, Event.VERIFY_OK, Event.PR_OPENED],
        }[frm]
        for e in path:
            store.advance(rid, e, root=tmp_path)
        assert store.advance(rid, ev, root=tmp_path).state == to


def test_advance_derives_quota_wait_and_stuck(tmp_path):
    for rid, reason, shown in [("q", StopReason.quota_exceeded, "quota-wait"), ("s", StopReason.stuck, "stuck")]:
        make(tmp_path, run_id=rid)
        for e in (Event.START, Event.REPRO_OK):
            store.advance(rid, e, root=tmp_path)
        end = store.advance(rid, Event.FIX_FAILED, stop_reason=reason, root=tmp_path)
        assert end.state == State.FAILED and end.display_state == shown
        assert json.loads((tmp_path / rid / "state.json").read_text("utf-8"))["state"] == "failed"


def test_only_contract_file_names_are_allowed(tmp_path):
    make(tmp_path)
    for bad in ["../state.json", "evil.json", "state.json/../../x", "", "STATE.JSON", "ticket.json "]:
        with pytest.raises(WorkbenchError) as exc:
            store.write_file("run-a", bad, "x", root=tmp_path)
        assert exc.value.code == "unknown_file"
        with pytest.raises(WorkbenchError):
            store.read_file("run-a", bad, root=tmp_path)


def test_text_files_roundtrip_exactly_and_are_capped(tmp_path):
    make(tmp_path)
    text = "<p>a</p>\r\nline two\n"
    store.write_file("run-a", "report.html", text, root=tmp_path)
    assert store.read_file("run-a", "report.html", root=tmp_path) == text
    store.write_file("run-a", "patch.diff", "", root=tmp_path)  # empty patch means no PR
    assert store.read_file("run-a", "patch.diff", root=tmp_path) == ""
    with pytest.raises(WorkbenchError) as exc:
        store.write_file("run-a", "report.html", "x" * (store.MAX_TEXT_BYTES + 1), root=tmp_path)
    assert exc.value.code == "file_too_large"
    with pytest.raises(WorkbenchError):
        store.write_file("run-a", "report.html", b"bytes", root=tmp_path)


def test_missing_file_and_unknown_run(tmp_path):
    make(tmp_path)
    with pytest.raises(WorkbenchError) as exc:
        store.read_file("run-a", "verdict.json", root=tmp_path)
    assert exc.value.code == "missing_file" and exc.value.status == 404
    with pytest.raises(WorkbenchError) as exc:
        store.read_file("nope", "state.json", root=tmp_path)
    assert exc.value.code == "unknown_run"
    assert store.has_file("run-a", "state.json", root=tmp_path) and not store.has_file("run-a", "pr.json", root=tmp_path)


def test_hand_edited_invalid_file_is_refused_on_read(tmp_path):
    make(tmp_path)
    (tmp_path / "run-a" / "state.json").write_text('{"run_id": "run-a", "state": "bogus"}', encoding="utf-8")
    with pytest.raises(WorkbenchError):
        store.get_state("run-a", root=tmp_path)
    (tmp_path / "run-a" / "state.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(WorkbenchError):
        store.get_state("run-a", root=tmp_path)
    (tmp_path / "run-a" / "state.json").write_bytes(b"\xff\xfe\x00")
    with pytest.raises(WorkbenchError):
        store.get_state("run-a", root=tmp_path)


def test_overwrite_false_keeps_the_first_write(tmp_path):
    make(tmp_path)
    d1 = {"decision": "approve", "idempotency_key": "k1", "decided_at": "2026-01-01T00:00:00Z"}
    store.write_file("run-a", "decision.json", d1, overwrite=False, root=tmp_path)
    with pytest.raises(WorkbenchError) as exc:
        store.write_file("run-a", "decision.json", {**d1, "decision": "reject"}, overwrite=False, root=tmp_path)
    assert exc.value.code == "already_written" and exc.value.status == 409
    assert store.read_file("run-a", "decision.json", root=tmp_path).decision == "approve"


def test_decision_and_pr_and_intake_validation(tmp_path):
    make(tmp_path)
    with pytest.raises(WorkbenchError):
        store.write_file("run-a", "decision.json", {"decision": "maybe", "idempotency_key": "k", "decided_at": "2026-01-01T00:00:00Z"}, root=tmp_path)
    with pytest.raises(WorkbenchError):
        store.write_file("run-a", "decision.json", {"decision": "approve", "idempotency_key": "", "decided_at": "2026-01-01T00:00:00Z"}, root=tmp_path)
    store.write_file("run-a", "pr.json", {"number": 1, "url": "https://mock.invalid/pull/1", "draft": True, "origin": "SIMULATED", "branch": "argus/x"}, root=tmp_path)
    assert store.read_file("run-a", "pr.json", root=tmp_path).draft is True
    with pytest.raises(WorkbenchError):
        store.write_file("run-a", "pr.json", {"number": 0, "url": "u", "draft": True, "origin": "SIMULATED"}, root=tmp_path)
    store.write_file("run-a", "intake.json", {"repo": "dcortex", "route": "/ops/radar", "ack_public_or_synthetic": True}, root=tmp_path)


def test_verdict_rules(tmp_path):
    make(tmp_path)
    chk = lambda n, ok=True: {"name": n, "ok": ok, "reason": "r"}  # noqa: E731
    good = {"ok": True, "checks": [chk(n) for n in ("pixel", "overflow", "axe", "console")], "origin": "SIMULATED"}
    store.write_file("run-a", "verdict.json", good, root=tmp_path)
    bad = [
        {**good, "checks": good["checks"][:3]},                                     # ok verdict must list all four
        {**good, "checks": list(reversed(good["checks"]))},                         # order is verify's order
        {**good, "checks": [chk("pixel"), chk("pixel")] + good["checks"][1:]},      # no duplicates
        {**good, "checks": [chk("pixel"), chk("overflow", False), chk("axe"), chk("console")]},  # ok but one failed
        {"ok": False, "checks": [chk("pixel", False)], "origin": "SIMULATED"},      # failure must be named
        {**good, "checks": [chk("zoom")] + good["checks"]},                         # unknown check
        {**good, "origin": "REAL"},
        {**good, "judge_label": "maybe"},
    ]
    for v in bad:
        with pytest.raises(WorkbenchError):
            store.write_file("run-a", "verdict.json", v, root=tmp_path)
    failed = {"ok": False, "checks": [chk("pixel"), chk("overflow", False)], "first_failure": "overflow on /x", "failed_check": "overflow", "origin": "REPLAY"}
    assert store.write_file("run-a", "verdict.json", failed, root=tmp_path).judge_advisory is True


def test_trajectory_is_validated_against_the_argus_core_schema(tmp_path):
    make(tmp_path)
    with pytest.raises(WorkbenchError) as exc:
        store.write_file("run-a", "trajectory.jsonl", "not json\n", root=tmp_path)
    assert exc.value.code == "invalid_trajectory"
    with pytest.raises(WorkbenchError):
        store.write_file("run-a", "trajectory.jsonl", '{"kind": "step", "index": 0}\n', root=tmp_path)  # no meta
    with pytest.raises(WorkbenchError):
        store.write_file("run-a", "trajectory.jsonl", 42, root=tmp_path)


def test_list_runs_newest_first_skips_broken_and_empty_root(tmp_path):
    assert store.list_runs(root=tmp_path / "none") == []
    from datetime import UTC, datetime, timedelta
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    for i, rid in enumerate(["r1", "r2", "r3"]):
        make(tmp_path, run_id=rid, clock=lambda i=i: t0 + timedelta(seconds=i))
    (tmp_path / "broken").mkdir()
    (tmp_path / "broken" / "state.json").write_text("{", encoding="utf-8")
    (tmp_path / "Not-A-Run").mkdir()
    (tmp_path / "stray.txt").write_text("x", encoding="utf-8")
    assert [s.run_id for s in store.list_runs(root=tmp_path)] == ["r3", "r2", "r1"]


def test_no_temp_files_left_behind(tmp_path):
    make(tmp_path)
    store.write_file("run-a", "report.html", "<p>x</p>", root=tmp_path)
    store.advance("run-a", Event.START, root=tmp_path)
    assert not [p for p in (tmp_path / "run-a").iterdir() if p.name.endswith(".tmp")]


def test_scenario_ids_are_the_spec_scenarios():
    assert scenario_ids() == tuple(s["id"] for s in load_spec()["scenarios"]) == ("normal", "quota", "stuck", "verifier", "judge")
