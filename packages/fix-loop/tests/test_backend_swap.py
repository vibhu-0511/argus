"""P5-T09 (local half): the same stubbed fix-loop run goes to two OTLP receivers; only endpoint and profile differ.

The receivers are plain local HTTP servers that decode the OTLP protobuf. This shows what is sent. It is not a
check against Phoenix or Langfuse themselves (see docs/notes/p5-t09.md).
"""

from __future__ import annotations

import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

from argus_core import telemetry
from argus_core.ledger import Ledger, ModelQuota

from fix_loop.loop import run_fix
from fix_loop.tools import ToolResult
from test_otel_spans import _completion


class Receiver:
    """Collects the spans of every OTLP/HTTP POST: `spans` is a list of (path, name, attributes)."""

    def __init__(self):
        self.spans: list[tuple[str, str, dict]] = []
        spans = self.spans

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                request = ExportTraceServiceRequest.FromString(body)
                for resource in request.resource_spans:
                    for scope in resource.scope_spans:
                        for span in scope.spans:
                            spans.append((self.path, span.name, {kv.key: _value(kv.value) for kv in span.attributes}))
                self.send_response(200)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *_):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_port}"

    def by_name(self) -> dict[str, dict]:
        return {name: attrs for _, name, attrs in self.spans}


def _value(any_value):
    kind = any_value.WhichOneof("value")
    return getattr(any_value, kind) if kind != "array_value" else [_value(v) for v in any_value.array_value.values]


def _stub_run(tmp_path: Path, run_id: str) -> None:
    model = "openai/gpt-oss-20b"
    replies = iter([_completion("read_file", 100, 40), _completion("submit", 100, 0)])
    provider = telemetry.start_tracing()  # exporter and profile come from the environment
    run_fix(
        worktree=tmp_path,
        model=model,
        ledger=Ledger(tmp_path / f"ledger-{run_id}.json", {model: ModelQuota(100, 10**9, 100, 10**9, False)}),
        complete=lambda _messages: next(replies),
        out_dir=tmp_path / f"out-{run_id}",
        step_cap=5,
        token_cap=1000,
        run_id=run_id,
        host="test",
        git_commit="abc",
        task_id="bug-17",
        system="system",
        user="fix it",
        execute=lambda name, _payload: ToolResult(tool=name, text="ok"),
    )
    provider.shutdown()  # flushes the batch queue


def test_same_run_two_backends_only_endpoint_and_profile_change(tmp_path: Path, monkeypatch):
    langfuse_like, phoenix_like = Receiver(), Receiver()
    try:
        monkeypatch.setenv("ARGUS_TRACE_BACKEND", "langfuse")
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
        monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")
        monkeypatch.setenv("LANGFUSE_BASE_URL", langfuse_like.url)
        _stub_run(tmp_path, "run-1")

        monkeypatch.delenv("LANGFUSE_BASE_URL")
        monkeypatch.setenv("ARGUS_TRACE_BACKEND", "otlp")
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", f"{phoenix_like.url}/v1/traces")
        monkeypatch.setenv("ARGUS_TRACE_PROFILE", "phoenix")
        _stub_run(tmp_path, "run-1")
    finally:
        langfuse_like.server.shutdown()
        phoenix_like.server.shutdown()

    assert {p for p, _, _ in langfuse_like.spans} == {"/api/public/otel/v1/traces"}
    assert {p for p, _, _ in phoenix_like.spans} == {"/v1/traces"}
    names = sorted(n for _, n, _ in langfuse_like.spans)
    assert names == sorted(n for _, n, _ in phoenix_like.spans)  # same run: same span tree
    assert names == ["chat openai/gpt-oss-20b"] * 2 + ["execute_tool read_file", "execute_tool submit", "invoke_agent fix-loop"]

    lf, px = langfuse_like.by_name(), phoenix_like.by_name()
    assert lf["invoke_agent fix-loop"]["langfuse.session.id"] == "run-1"
    assert lf["invoke_agent fix-loop"]["langfuse.observation.metadata.argus_task_id"] == "bug-17"
    assert "gen_ai.usage.cost" in {k for s in langfuse_like.spans for k in s[2]}
    assert px["invoke_agent fix-loop"]["openinference.span.kind"] == "AGENT"
    assert px["invoke_agent fix-loop"]["session.id"] == "run-1"
    assert px["execute_tool submit"]["openinference.span.kind"] == "TOOL" and px["execute_tool submit"]["tool.name"] == "submit"
    chats = [a for _, n, a in phoenix_like.spans if n.startswith("chat ")]
    assert {c["openinference.span.kind"] for c in chats} == {"LLM"}
    assert sorted(c["llm.token_count.prompt"] for c in chats) == [100, 100]
    assert sorted(c.get("llm.token_count.prompt_details.cache_read", 0) for c in chats) == [0, 40]
    assert all(c["llm.model_name"] == "openai/gpt-oss-20b" for c in chats)
    assert not any(k.startswith("gen_ai.usage.") for c in chats for k in c)  # moved, not copied
    assert dict(telemetry.unmapped_attributes()) == {}  # every attribute argus emits is one the normalizer knows
