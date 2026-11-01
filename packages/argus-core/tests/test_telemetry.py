import json

import httpx
import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from argus_core.client import ModelClient
from argus_core.telemetry import chat_span, start_tracing


def _body() -> dict:
    return {
        "id": "cmpl-9",
        "model": "openai/gpt-oss-20b",
        "choices": [{"finish_reason": "length", "message": {"content": "hi"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 2, "prompt_tokens_details": {"cached_tokens": 4}},
    }


def test_client_complete_emits_one_chat_span(monkeypatch):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=_body()))
    real = httpx.Client
    monkeypatch.setattr("argus_core.client.httpx.Client", lambda **kw: real(transport=transport, **kw))
    exporter = InMemorySpanExporter()
    start_tracing(exporter)
    ModelClient("https://api.groq.com/openai/v1").complete("openai/gpt-oss-20b", [])
    (span,) = exporter.get_finished_spans()
    assert span.name == "chat openai/gpt-oss-20b"
    assert span.attributes["gen_ai.provider.name"] == "groq"
    assert span.attributes["server.address"] == "api.groq.com"
    assert span.attributes["gen_ai.response.id"] == "cmpl-9"
    assert span.attributes["gen_ai.response.finish_reasons"] == ("length",)
    assert span.attributes["gen_ai.usage.cache_read.input_tokens"] == 4


def test_failed_call_marks_the_span(monkeypatch):
    def boom(request):
        raise httpx.ConnectError("down")

    real = httpx.Client
    monkeypatch.setattr("argus_core.client.httpx.Client", lambda **kw: real(transport=httpx.MockTransport(boom), **kw))
    exporter = InMemorySpanExporter()
    start_tracing(exporter)
    with pytest.raises(httpx.ConnectError):
        ModelClient("http://localhost:11434/v1").complete("m", [])
    (span,) = exporter.get_finished_spans()
    assert span.attributes["error.type"] == "ConnectError"
    assert span.attributes["gen_ai.provider.name"] == "ollama"


def test_nested_chat_span_joins_the_outer_one():
    exporter = InMemorySpanExporter()
    start_tracing(exporter)
    with chat_span("m", step=3):
        with chat_span("m", "https://api.mistral.ai/v1"):
            pass
    (span,) = exporter.get_finished_spans()
    assert span.attributes["argus.step.index"] == 3
    assert span.attributes["gen_ai.provider.name"] == "mistral"
