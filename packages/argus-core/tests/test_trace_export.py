"""P5-T07: the trace exporter is chosen from the environment; a missing key is a clear error; nothing secret leaks; a dead backend does not hold the run."""

from __future__ import annotations

import base64
import logging
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from argus_core import telemetry
from argus_core.telemetry import TraceConfigError, trace_config

PK, SK = "pk-lf-test-public-0001", "sk-lf-test-secret-0002"
LANGFUSE = {"ARGUS_TRACE_BACKEND": "langfuse", "LANGFUSE_PUBLIC_KEY": PK, "LANGFUSE_SECRET_KEY": SK}


def test_default_is_console():
    assert trace_config({}).backend == "console"


def test_langfuse_endpoint_and_basic_auth_come_from_env():
    config = trace_config(LANGFUSE)
    assert config.endpoint == "https://cloud.langfuse.com/api/public/otel/v1/traces"
    assert base64.b64decode(config.headers["Authorization"].removeprefix("Basic ")).decode() == f"{PK}:{SK}"
    assert config.headers["x-langfuse-ingestion-version"] == "4"


def test_langfuse_region_comes_from_base_url():
    config = trace_config({**LANGFUSE, "LANGFUSE_BASE_URL": "https://us.cloud.langfuse.com/"})
    assert config.endpoint == "https://us.cloud.langfuse.com/api/public/otel/v1/traces"


@pytest.mark.parametrize("missing", ["LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"])
def test_missing_langfuse_key_names_the_variable_and_nothing_else(missing):
    env = {k: v for k, v in LANGFUSE.items() if k != missing}
    with pytest.raises(TraceConfigError, match=missing) as err:
        trace_config(env)
    assert PK not in str(err.value) and SK not in str(err.value)


def test_both_langfuse_keys_missing_are_both_named():
    with pytest.raises(TraceConfigError, match="LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY"):
        trace_config({"ARGUS_TRACE_BACKEND": "langfuse"})


def test_generic_otlp_uses_the_traces_endpoint_as_given_and_parses_headers():
    env = {
        "ARGUS_TRACE_BACKEND": "otlp",
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "http://localhost:6006/v1/traces",
        "OTEL_EXPORTER_OTLP_HEADERS": "authorization=Bearer abc=,x-team=argus",
    }
    config = trace_config(env)
    assert config.endpoint == "http://localhost:6006/v1/traces"
    assert dict(config.headers) == {"authorization": "Bearer abc=", "x-team": "argus"}


def test_generic_otlp_base_endpoint_gets_the_traces_path():
    env = {"ARGUS_TRACE_BACKEND": "otlp", "OTEL_EXPORTER_OTLP_ENDPOINT": "http://collector:4318/"}
    assert trace_config(env).endpoint == "http://collector:4318/v1/traces"


def test_otlp_without_an_endpoint_is_an_error():
    with pytest.raises(TraceConfigError, match="OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"):
        trace_config({"ARGUS_TRACE_BACKEND": "otlp"})


def test_unknown_backend_is_an_error():
    with pytest.raises(TraceConfigError, match="console, langfuse or otlp"):
        trace_config({"ARGUS_TRACE_BACKEND": "datadog"})


def _blackhole():
    """A local port that accepts connections and never answers: the worst kind of unreachable backend."""
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(128)
    return server


def _point_at(monkeypatch, endpoint: str, timeout: float):
    for key, value in {**LANGFUSE, "LANGFUSE_BASE_URL": endpoint}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(telemetry, "EXPORT_TIMEOUT_S", timeout)


def test_langfuse_request_has_the_path_and_headers_on_the_wire(monkeypatch):
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            seen.append((self.path, self.headers))
            self.send_response(200)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *_):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        _point_at(monkeypatch, f"http://127.0.0.1:{server.server_port}", 2)
        provider = telemetry.start_tracing()
        with telemetry.agent_span("a", run_id="r"):
            pass
        provider.shutdown()
    finally:
        server.shutdown()
    path, headers = seen[0]
    assert path == "/api/public/otel/v1/traces"
    assert headers["Authorization"] == trace_config(LANGFUSE).headers["Authorization"]
    assert headers["x-langfuse-ingestion-version"] == "4"
    assert headers["Content-Type"] == "application/x-protobuf"


def test_nothing_secret_in_repr_logs_or_spans(monkeypatch, caplog):
    config = trace_config(LANGFUSE)
    basic = config.headers["Authorization"]
    assert SK not in repr(config) and basic not in repr(config)

    server = _blackhole()
    try:
        _point_at(monkeypatch, f"http://127.0.0.1:{server.getsockname()[1]}", 0.5)
        with caplog.at_level(logging.DEBUG):
            provider = telemetry.start_tracing()
            with telemetry.agent_span("a", run_id="r"):
                pass
            provider.shutdown()
    finally:
        server.close()
    assert caplog.records, "the failed export should have been logged"
    assert not any(s in caplog.text for s in (PK, SK, basic.removeprefix("Basic ")))


def test_unreachable_backend_does_not_hold_the_run(monkeypatch):
    server = _blackhole()
    try:
        _point_at(monkeypatch, f"http://127.0.0.1:{server.getsockname()[1]}", 1)
        provider = telemetry.start_tracing()
        started = time.monotonic()
        for _ in range(telemetry.QUEUE_SIZE * 2):  # more spans than the queue holds
            with telemetry.agent_span("a", run_id="r"):
                pass
        emitting = time.monotonic() - started
        provider.shutdown()
        total = time.monotonic() - started
    finally:
        server.close()
    assert emitting < 2  # emitting never waits for the network
    assert total < 2 * telemetry.EXPORT_TIMEOUT_S + 4  # one batch in flight plus the last one, then it gives up
