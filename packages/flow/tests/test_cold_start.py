"""P6-T13 cold-start script: the signing, timing and summary code, with a fake transport and clock.

No network, no Render, no LLM. These tests show the script's bookkeeping is right; they say nothing
about how long a real Render service takes to wake. That number exists only after the owner runs
`packages/flow/scripts/p6_t13_cold_start.py` against a deployed service (docs/notes/p6-t13.md).
"""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from flow.enqueue import FakeEnqueuer
from flow.webhook import SECRET_ENV, create_app, verify_signature

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "p6_t13_cold_start.py"
SECRET = "test-secret-not-a-real-one"
BASE = "https://argus-flow.example.test"


@pytest.fixture(scope="module")
def cold():
    spec = importlib.util.spec_from_file_location("p6_t13_cold_start", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def scripted(clock: FakeClock, answers: list):
    """A transport that takes the next (seconds, status-or-exception) from `answers` and advances the fake clock."""
    calls = []

    def transport(url, headers, body, timeout):
        calls.append((url, headers, body, timeout))
        seconds, result = answers.pop(0)
        clock.t += seconds
        if isinstance(result, Exception):
            raise result
        return result

    transport.calls = calls
    return transport


def test_signature_is_the_one_the_endpoint_verifies(cold):
    headers = cold.ping_headers(SECRET)
    assert verify_signature(SECRET, cold.PING_BODY, headers["X-Hub-Signature-256"])
    assert not verify_signature("another-secret", cold.PING_BODY, headers["X-Hub-Signature-256"])
    assert headers["X-GitHub-Event"] == "ping"
    assert cold.ping_headers(SECRET)["X-GitHub-Delivery"] != headers["X-GitHub-Delivery"]


def test_the_real_webhook_app_answers_the_signed_ping_with_202_and_a_wrong_secret_with_401(cold, monkeypatch):
    monkeypatch.setenv(SECRET_ENV, SECRET)
    client = TestClient(create_app(FakeEnqueuer()))

    def transport(url, headers, body, timeout):
        return client.post("/webhook", content=body, headers=headers).status_code

    assert cold.timed_ping(transport, BASE + "/webhook", SECRET)["status"] == 202
    assert cold.timed_ping(transport, BASE + "/webhook", "wrong")["verdict"] == "error"


@pytest.mark.parametrize(
    ("status", "seconds", "expected"),
    [(202, 0.2, "ok"), (202, 9.999, "ok"), (202, 10.0, "slow"), (202, 55.0, "slow"), (401, 0.1, "error"), (503, 3.0, "error"), (None, 90.0, "no-answer")],
)
def test_verdict_against_the_ten_second_limit(cold, status, seconds, expected):
    assert cold.verdict(status, seconds) == expected


def test_run_tries_records_gap_cold_and_warm_per_try_and_sends_signed_pings_to_the_webhook(cold):
    clock = FakeClock()
    answers = [(42.5, 202), (0.05, 202), (7.0, 202), (0.04, 202), (90.0, cold.TransportError("ReadTimeout")), (0.1, 202)]
    transport = scripted(clock, answers)
    waited = []
    tries = cold.run_tries(
        transport, BASE + "/", SECRET, [1200, 1800, 3600], wait=waited.append, clock=clock, now=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc)
    )
    assert waited == [1200, 1800, 3600]
    assert [t["idle_gap_seconds"] for t in tries] == [1200, 1800, 3600]
    assert [(t["cold"]["seconds"], t["cold"]["verdict"]) for t in tries] == [(42.5, "slow"), (7.0, "ok"), (90.0, "no-answer")]
    assert tries[2]["cold"]["error"] == "ReadTimeout" and tries[2]["cold"]["status"] is None
    assert [t["warm"]["seconds"] for t in tries] == [0.05, 0.04, 0.1]
    assert tries[0]["started_at"] == "2026-01-01T00:00:00+00:00"
    assert all(url == BASE + "/webhook" for url, *_ in transport.calls)
    assert all(verify_signature(SECRET, body, headers["X-Hub-Signature-256"]) for _, headers, body, _ in transport.calls)


def test_summary_counts_verdicts_and_names_the_gaps_over_ten_seconds(cold):
    def row(gap, seconds, status=202, error=None):
        c = {"status": status, "seconds": seconds, "verdict": cold.verdict(status, seconds)}
        return {"try": 0, "idle_gap_seconds": gap, "cold": c, "warm": c}

    tries = [row(1200, 4.0), row(1200, 31.0), row(3600, 58.5), row(3600, 90.0, status=None)]
    s = cold.summarize(tries)
    assert s["cold_verdicts"] == {"ok": 1, "slow": 2, "error": 0, "no-answer": 1}
    assert (s["cold_seconds_min"], s["cold_seconds_median"], s["cold_seconds_max"]) == (4.0, 31.0, 58.5)  # the unanswered try is not a latency
    assert s["gaps_over_10s"] == [1200, 3600]
    assert s["all_within_10s"] is False
    assert cold.summarize([row(1200, 2.0), row(1200, 3.0)])["all_within_10s"] is True
    assert cold.summarize([])["all_within_10s"] is False


def test_results_json_holds_raw_timings_and_no_secret(cold):
    clock = FakeClock()
    tries = cold.run_tries(scripted(clock, [(3.0, 202), (0.1, 202)]), BASE, SECRET, [1200], wait=lambda g: None, clock=clock)
    text = json.dumps(cold.build_results(tries, BASE, "2026-01-01T00:00:00+00:00"))
    assert SECRET not in text and "sha256=" not in text
    data = json.loads(text)
    assert data["service_host"] == "argus-flow.example.test" and data["webhook_timeout_seconds"] == 10.0
    assert data["tries"][0]["cold"] == {"status": 202, "seconds": 3.0, "verdict": "ok"}
    assert "| 1 | 1200 | 202 | 3 | ok | 0.1 |" in cold.markdown_table(tries)


def test_the_real_transport_turns_a_refused_connection_into_no_answer(cold):
    row = cold.timed_ping(cold.httpx_transport, "http://127.0.0.1:1/webhook", SECRET, timeout=2.0)  # nothing listens on port 1
    assert row["status"] is None and row["verdict"] == "no-answer" and row["error"]


def test_main_refuses_without_url_and_secret(cold, monkeypatch, capsys):
    monkeypatch.delenv(cold.URL_ENV, raising=False)
    monkeypatch.delenv(cold.SECRET_ENV, raising=False)
    assert cold.main(["--gaps", "1"]) == 2
    assert "ARGUS_FLOW_SERVICE_URL" in capsys.readouterr().err
