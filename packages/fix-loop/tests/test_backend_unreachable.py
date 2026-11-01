"""P5-T25: the trace backend is unreachable (closed port, or a port that accepts and never answers).

The stubbed fix-loop run must give the same result as with no backend, the exporter must log a drop, and the
extra wall time must stay within the configured export timeout. No model call; the only network is localhost.
"""

from __future__ import annotations

import logging
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from argus_core import telemetry
from argus_core.ledger import Ledger, ModelQuota

from fix_loop.loop import run_fix
from fix_loop.tools import ToolResult
from test_otel_spans import _completion

TIMEOUT_S = 1  # the exporter timeout under test; production uses telemetry.EXPORT_TIMEOUT_S (3)
SLACK_S = 2  # connect-refused on Windows can overshoot the timeout by half a second; scheduling and the stub run itself


def _stub_run(tmp_path: Path, name: str, exporter=None):
    """The T06 stub run; `exporter` None means the environment decides. Returns (result, seconds incl. flush)."""
    model = "openai/gpt-oss-20b"
    replies = iter([_completion("read_file", 100, 40), _completion("submit", 100, 0)])
    started = time.monotonic()
    provider = telemetry.start_tracing(exporter)
    result = run_fix(
        worktree=tmp_path,
        model=model,
        ledger=Ledger(tmp_path / f"ledger-{name}.json", {model: ModelQuota(100, 10**9, 100, 10**9, False)}),
        complete=lambda _messages: next(replies),
        out_dir=tmp_path / f"out-{name}",
        step_cap=5,
        token_cap=1000,
        run_id="run-1",
        host="test",
        git_commit="abc",
        task_id="bug-17",
        system="system",
        user="fix it",
        execute=lambda name, _payload: ToolResult(tool=name, text="ok"),
    )
    provider.shutdown()  # flushes the batch queue: this is where a dead backend would cost time
    return result, time.monotonic() - started


def _unreachable(kind: str) -> tuple[socket.socket, int]:
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    port = server.getsockname()[1]
    if kind == "silent":
        server.listen(128)  # accepts connections in the kernel's queue, never reads or answers
    else:
        server.close()  # nothing listens: connection refused
    return server, port


@pytest.mark.parametrize("kind", ["closed", "silent"])
def test_dead_backend_changes_nothing_but_a_bounded_delay_and_a_logged_drop(tmp_path: Path, monkeypatch, caplog, kind):
    baseline, base_s = _stub_run(tmp_path, "base", InMemorySpanExporter())

    server, port = _unreachable(kind)
    monkeypatch.setenv("ARGUS_TRACE_BACKEND", "otlp")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", f"http://127.0.0.1:{port}/v1/traces")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "authorization=Bearer sk-secret-for-the-test")
    monkeypatch.setattr(telemetry, "EXPORT_TIMEOUT_S", TIMEOUT_S)
    try:
        with caplog.at_level(logging.DEBUG):
            result, dead_s = _stub_run(tmp_path, "dead")
    finally:
        server.close()

    assert result.stop_reason == baseline.stop_reason  # the run finished the same way
    assert result.trajectory_path.read_text() == baseline.trajectory_path.read_text()
    assert dead_s - base_s < TIMEOUT_S + SLACK_S  # one timeout for the one batch, nothing more
    drops = [r for r in caplog.records if r.name == "argus.trace" and "dropped" in r.getMessage()]
    assert len(drops) == 1 and "dropped 5 spans" in drops[0].getMessage()  # agent + 2 chat + 2 tool spans
    assert "sk-secret-for-the-test" not in caplog.text and str(port) not in drops[0].getMessage()
