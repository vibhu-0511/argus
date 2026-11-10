"""P10-T09: the history list and the four metrics. Result files and ledgers here are tmp_path files with obviously
fake names; no model is called. Simulated and replay runs must change no number."""

import json
from datetime import UTC, datetime

import pytest
from argus_core.types import Trajectory, TrajectoryMeta, TrajectoryStep
from eval.results import Results
from eval.stats import wilson

from argus_workbench import history_metrics, store
from argus_workbench.fixtures import write_all_fixtures, write_fixture_run

TOKEN = "test-token-not-secret"
DASH_KEYS = ("resolve_rate", "tokens_per_bug", "latency", "quota_share")


def results_file(path, run_id="fake-run", successes=3, total=10, p50=None, p95=None, tokens=(1000.0, 50.0, 200.0), host="fake-host"):
    r = Results.model_validate({
        "schema_version": 1, "run_id": run_id, "created_at": "2026-01-01T00:00:00Z",
        "agent": {"name": "fake-agent", "model": "fake-model", "host": host, "params": {}},
        "counts": {"resolved": successes, "unresolved": total - successes, "excluded": 0, "error": 0},
        "resolve_rate": {"successes": successes, "total": total, "rate": successes / total if total else None,
                         "ci_low": None, "ci_high": None, "interval": "wilson95"},
        "tokens": {"total": {"tokens_in": 0, "tokens_out": 0, "tokens_cached": 0},
                   "per_task": None if tokens is None else {"tokens_in": tokens[0], "tokens_out": tokens[1], "tokens_cached": tokens[2]}},
        "latency_s": {"p50": p50, "p95": p95, "n": 0 if p50 is None else total},
        "trajectory_metrics": None, "$_equivalent": None, "tasks": [],
    })
    path.write_text(r.to_json(), encoding="utf-8")
    return path


def ledger_file(path, models=None, tenants=None):
    bucket = lambda tokens, requests: {"requests": requests, "tokens": tokens, "cached": 0, "fresh": 0, "events": []}  # noqa: E731
    state = {"day": "2026-01-01", "models": {m: bucket(*v) for m, v in (models or {}).items()},
             "tenants": {t: {m: bucket(*v) for m, v in ms.items()} for t, ms in (tenants or {}).items()}}
    path.write_text(json.dumps(state), encoding="utf-8")
    return path


@pytest.fixture
def point(monkeypatch, tmp_path):
    """Point the metrics at tmp files: point(results=[paths], ledger=path-or-None)."""
    def _point(results=(), ledger=None):
        monkeypatch.setenv(history_metrics.ENV_RESULTS, history_metrics.os.pathsep.join(str(p) for p in results))
        monkeypatch.setenv(history_metrics.ENV_LEDGER, str(ledger or tmp_path / "no-ledger.json"))
    return _point


def metrics(client):
    r = client.get("/api/history/metrics")
    assert r.status_code == 200
    return r.json()


# ---- the run list ---------------------------------------------------------------------------------------------


def test_empty_store_gives_a_typed_empty_state(client):
    body = client.get("/api/history").json()
    assert body["runs"] == [] and body["count"] == 0
    assert body["empty"]["code"] == "no_runs" and body["empty"]["message"]


def test_runs_are_listed_with_state_stop_reason_scenario_and_origin_badge(client):
    write_all_fixtures()
    body = client.get("/api/history").json()
    assert body["empty"] is None and body["count"] == 5
    rows = {r["scenario"]: r for r in body["runs"]}
    assert set(rows) == {"normal", "quota", "stuck", "verifier", "judge"}
    assert {r["origin"] for r in body["runs"]} == {"SIMULATED"}
    assert (rows["normal"]["state"], rows["normal"]["stop_reason"], rows["normal"]["display_state"]) == ("awaiting-qa", "submit", "awaiting-qa")
    assert (rows["quota"]["state"], rows["quota"]["stop_reason"], rows["quota"]["display_state"]) == ("failed", "QuotaExceeded", "quota-wait")
    assert (rows["stuck"]["state"], rows["stuck"]["stop_reason"], rows["stuck"]["display_state"]) == ("failed", "stuck", "stuck")
    assert (rows["verifier"]["state"], rows["verifier"]["display_state"]) == ("failed", "failed")
    for r in body["runs"]:
        assert r["decision"] is None and r["pr"] is False and r["retry_of"] is None
        assert datetime.fromisoformat(r["created_at"]).tzinfo is not None


def test_decision_pr_and_retry_columns(client):
    write_fixture_run("normal", run_id="fixture-a")
    store.write_file("fixture-a", "decision.json", {"decision": "approve", "idempotency_key": "k1", "decided_at": datetime(2026, 1, 1, tzinfo=UTC)})
    store.write_file("fixture-a", "pr.json", {"number": 1, "url": "https://example.invalid/pr/1", "draft": True, "origin": "SIMULATED"})
    store.create_run({"id": "T-2", "text": "retry of a"}, retry_of="fixture-a", run_id="retry-a")
    rows = {r["run_id"]: r for r in client.get("/api/history").json()["runs"]}
    assert (rows["fixture-a"]["decision"], rows["fixture-a"]["pr"]) == ("approve", True)
    assert (rows["retry-a"]["state"], rows["retry-a"]["retry_of"], rows["retry-a"]["decision"], rows["retry-a"]["pr"]) == ("received", "fixture-a", None, False)


def test_a_decision_file_that_no_longer_validates_is_shown_as_unreadable(client, runs_root):
    write_fixture_run("normal", run_id="fixture-a")
    (runs_root / "fixture-a" / "decision.json").write_text("{not json", encoding="utf-8")
    assert client.get("/api/history").json()["runs"][0]["decision"] == "unreadable"


def test_filter_by_origin_and_a_typed_error_for_a_bad_origin(client):
    write_all_fixtures()
    write_fixture_run("normal", run_id="fixture-replay", origin="REPLAY")
    assert client.get("/api/history?origin=REPLAY").json()["count"] == 1
    assert client.get("/api/history?origin=SIMULATED").json()["count"] == 5
    assert client.get("/api/history").json()["count"] == 6
    r = client.get("/api/history?origin=LIVE")
    assert r.status_code == 400 and r.json() == {"error": {"code": "bad_origin", "field": "origin", "message": "origin is one of SIMULATED, REPLAY"}}


def test_an_empty_filter_result_is_the_empty_state(client):
    write_all_fixtures()
    body = client.get("/api/history?origin=REPLAY").json()
    assert body["runs"] == [] and body["empty"]["code"] == "no_runs"


def test_a_corrupt_run_is_skipped_not_fatal(client, runs_root):
    write_fixture_run("normal", run_id="fixture-a")
    (runs_root / "fixture-a" / "state.json").write_text("{", encoding="utf-8")
    write_fixture_run("quota", run_id="fixture-b")
    assert [r["run_id"] for r in client.get("/api/history").json()["runs"]] == ["fixture-b"]


# ---- the metrics: real files or dashes -------------------------------------------------------------------------


def test_no_result_file_and_no_ledger_is_all_dashes_with_the_banner(client, point):
    point()
    body = metrics(client)
    for key in DASH_KEYS:
        assert body["metrics"][key]["value"] is None and body["metrics"][key]["reason"]
    assert body["banner"] == "No run id backs any number yet." and body["files"] == []


def test_metrics_come_from_the_file_and_name_it(client, point, tmp_path):
    f = results_file(tmp_path / "res.json", run_id="fake-run-1", successes=3, total=10, p50=12.5, p95=40.0, tokens=(1000.0, 50.0, 200.0))
    point([f])
    body = metrics(client)
    rr = body["metrics"]["resolve_rate"]
    low, high = wilson(3, 10)
    assert (rr["value"], rr["successes"], rr["total"]) == (0.3, 3, 10)
    assert rr["ci_low"] == pytest.approx(low, abs=1e-6) and rr["ci_high"] == pytest.approx(high, abs=1e-6) and rr["interval"] == "wilson95"
    assert rr["source"] == {"file": "res.json", "run_id": "fake-run-1", "host": "fake-host", "n": 10}
    tk = body["metrics"]["tokens_per_bug"]
    assert (tk["tokens_in"], tk["tokens_out"], tk["tokens_cached"], tk["value"]) == (1000.0, 50.0, 200.0, 1050.0)
    lt = body["metrics"]["latency"]
    assert (lt["p50"], lt["p95"], lt["source"]["n"]) == (12.5, 40.0, 10)
    assert body["banner"] is None and body["metrics"]["quota_share"]["value"] is None


def test_a_metric_the_file_lacks_is_a_dash_with_a_reason(client, point, tmp_path):
    point([results_file(tmp_path / "res.json", p50=None, tokens=None)])
    m = metrics(client)["metrics"]
    assert m["resolve_rate"]["value"] == 0.3
    assert m["latency"] == {"value": None, "reason": "no result file records a latency"}
    assert m["tokens_per_bug"]["value"] is None and m["tokens_per_bug"]["reason"]


def test_zero_scored_tasks_is_a_dash_not_zero(client, point, tmp_path):
    point([results_file(tmp_path / "res.json", successes=0, total=0, tokens=None)])
    assert metrics(client)["metrics"]["resolve_rate"] == {"value": None, "reason": "no result file with scored tasks"}


def test_small_n_interval_and_zero_lower_bound_are_clamped(client, point, tmp_path):
    point([results_file(tmp_path / "res.json", successes=0, total=1)])
    rr = metrics(client)["metrics"]["resolve_rate"]
    assert rr["value"] == 0.0 and rr["ci_low"] == 0.0 and rr["ci_high"] == pytest.approx(0.793, abs=1e-3)


def test_the_last_file_with_a_value_backs_each_metric_and_files_are_not_pooled(client, point, tmp_path):
    old = results_file(tmp_path / "old.json", run_id="fake-old", successes=1, total=2, p50=5.0, p95=6.0)
    new = results_file(tmp_path / "new.json", run_id="fake-new", successes=9, total=10, p50=None)
    point([old, new])
    m = metrics(client)["metrics"]
    assert m["resolve_rate"]["source"]["file"] == "new.json" and (m["resolve_rate"]["successes"], m["resolve_rate"]["total"]) == (9, 10)
    assert m["latency"]["source"]["file"] == "old.json" and m["latency"]["p50"] == 5.0


def test_made_up_and_invalid_files_are_left_out_with_a_reason(client, point, tmp_path):
    made_up = results_file(tmp_path / "madeup.json", run_id="fake-made-up-run")
    bad = tmp_path / "bad.json"
    bad.write_text('{"schema_version": 2}', encoding="utf-8")
    point([made_up, bad, tmp_path / "missing.json"])
    body = metrics(client)
    assert body["files"] == [] and body["metrics"]["resolve_rate"]["value"] is None
    assert {s["file"] for s in body["skipped"]} == {"madeup.json", "bad.json", "missing.json"}
    assert [s["reason"] for s in body["skipped"]][0] == "labelled made up"


def test_default_files_are_the_dashboard_files_and_the_numbers_are_the_recorded_ones(client, monkeypatch):
    monkeypatch.delenv(history_metrics.ENV_RESULTS, raising=False)
    body = metrics(client)
    assert body["files"], "the repo's real result files should load"
    rr = body["metrics"]["resolve_rate"]
    recorded = json.loads((history_metrics.repo_root() / rr["source"]["file"]).read_text("utf-8"))
    assert recorded["run_id"] == rr["source"]["run_id"]
    assert rr["successes"] == recorded["resolve_rate"]["successes"] and rr["total"] == recorded["resolve_rate"]["total"]
    assert rr["value"] == pytest.approx(recorded["resolve_rate"]["rate"], abs=1e-6)
    assert rr["ci_low"] == pytest.approx(recorded["resolve_rate"]["ci_low"], abs=1e-6)
    assert rr["ci_high"] == pytest.approx(recorded["resolve_rate"]["ci_high"], abs=1e-6)


# ---- simulated and replay runs are in no aggregate -------------------------------------------------------------


def test_simulated_and_replay_runs_with_huge_numbers_change_no_metric(client, point, tmp_path):
    point([results_file(tmp_path / "res.json", p50=3.0, p95=9.0)], ledger_file(tmp_path / "led.json", models={"m": (500, 5)}, tenants={"acme": {"m": (500, 5)}}))
    before = metrics(client)
    for i, origin in enumerate(["SIMULATED", "REPLAY", "SIMULATED"]):
        write_fixture_run("normal", run_id=f"big-{i}", origin=origin)
        meta = TrajectoryMeta(run_id=f"big-{i}", task_id="T", model="scripted", host="simulated", prompt_hash="none", git_commit="none")
        step = TrajectoryStep(index=0, tokens_in=10**9, tokens_out=10**9, tokens_cached=10**9, message={"stage": "fix", "text": "x", "origin": origin})
        store.write_file(f"big-{i}", "trajectory.jsonl", Trajectory(meta=meta, steps=[step]))
    after = metrics(client)
    assert client.get("/api/history").json()["count"] == 3
    assert after["metrics"] == before["metrics"] and after["files"] == before["files"]
    assert after["excluded"] == {"SIMULATED": 2, "REPLAY": 1} and before["excluded"] == {"SIMULATED": 0, "REPLAY": 0}


def test_history_metrics_does_not_read_the_run_store():
    import inspect
    source = inspect.getsource(history_metrics)
    assert "import store" not in source and "argus_workbench.store" not in source and "list_runs" not in source


# ---- quota share per tenant ------------------------------------------------------------------------------------


def test_quota_share_per_tenant_from_the_ledger(client, point, tmp_path):
    led = ledger_file(tmp_path / "led.json", models={"m": (100, 2)}, tenants={"acme": {"m": (300, 3), "n": (100, 1)}, "globex": {"m": (500, 4)}})
    point([], led)
    qs = metrics(client)["metrics"]["quota_share"]
    shares = {t["tenant"]: (t["tokens"], t["requests"], t["share"]) for t in qs["tenants"]}
    assert shares == {"default": (100, 2, 0.1), "acme": (400, 4, 0.4), "globex": (500, 4, 0.5)}
    assert [t["tenant"] for t in qs["tenants"]] == ["globex", "acme", "default"]
    assert sum(t["share"] for t in qs["tenants"]) == pytest.approx(1.0) and qs["day"] == "2026-01-01" and qs["total_tokens"] == 1000


@pytest.mark.parametrize("make, reason", [
    (lambda p: p / "missing.json", "no ledger file"),
    (lambda p: ledger_file(p / "default-only.json", models={"m": (100, 1)}), "the ledger has no tenant dimension (default tenant only)"),
    (lambda p: ledger_file(p / "zero.json", tenants={"acme": {"m": (0, 0)}}), "the ledger has no tokens charged on its day"),
])
def test_no_tenant_data_is_a_dash(client, point, tmp_path, make, reason):
    point([], make(tmp_path))
    assert metrics(client)["metrics"]["quota_share"] == {"value": None, "reason": reason}


def test_a_broken_ledger_is_a_dash(client, point, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"tenants": {"acme": 5}}', encoding="utf-8")
    point([], bad)
    assert metrics(client)["metrics"]["quota_share"]["reason"] == "the ledger file could not be read"


def test_tenant_names_pass_through_as_data_only(client, point, tmp_path):
    point([], ledger_file(tmp_path / "led.json", tenants={"<script>alert(1)</script>": {"m": (10, 1)}}))
    qs = metrics(client)["metrics"]["quota_share"]
    assert qs["tenants"][0]["tenant"] == "<script>alert(1)</script>"


# ---- page ------------------------------------------------------------------------------------------------------


def test_the_screen_is_served_and_sets_text_only(client):
    js = client.get("/static/screens/history.js")
    assert js.status_code == 200
    assert "not built yet" not in js.text and "/api/history" in js.text and "innerHTML" not in js.text
    assert client.get("/static/screens/history.css").status_code == 200


def test_the_route_is_discovered_without_editing_server_py(app):
    assert {"/api/history", "/api/history/metrics"} <= set(app.openapi()["paths"])
