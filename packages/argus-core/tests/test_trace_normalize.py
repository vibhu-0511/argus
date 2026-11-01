"""P5-T08: argus span attributes are renamed to the backend's names; unknown ones pass through and are counted."""

from __future__ import annotations

import logging
from collections import Counter

import pytest
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import Status, StatusCode

from argus_core import telemetry
from argus_core.telemetry import TraceConfigError, trace_config
from argus_core.trace_normalize import KNOWN, PROFILES, NormalizingExporter

# Written out by hand, not read from PROFILES: (profile, argus attribute) -> (sample value, backend attribute, expected value).
EXPECTED = {
    ("langfuse", "argus.usage.cost_usd"): (1.5e-05, "gen_ai.usage.cost", 1.5e-05),
    ("langfuse", "gen_ai.conversation.id"): ("run-1", "langfuse.session.id", "run-1"),
    ("langfuse", "argus.stop_reason"): ("submit", "langfuse.observation.metadata.argus_stop_reason", "submit"),
    ("langfuse", "argus.step.index"): (3, "langfuse.observation.metadata.argus_step_index", "3"),
    ("langfuse", "argus.task.id"): ("bug-17", "langfuse.observation.metadata.argus_task_id", "bug-17"),
    ("langfuse", "argus.tool.error"): ("timeout", "langfuse.observation.metadata.argus_tool_error", "timeout"),
    ("langfuse", "argus.tier"): ("cheap", "langfuse.observation.metadata.argus_tier", "cheap"),
    ("phoenix", "gen_ai.operation.name"): ("chat", "openinference.span.kind", "LLM"),
    ("phoenix", "gen_ai.request.model"): ("openai/gpt-oss-20b", "llm.model_name", "openai/gpt-oss-20b"),
    ("phoenix", "gen_ai.provider.name"): ("groq", "llm.provider", "groq"),
    ("phoenix", "gen_ai.usage.input_tokens"): (100, "llm.token_count.prompt", 100),
    ("phoenix", "gen_ai.usage.output_tokens"): (7, "llm.token_count.completion", 7),
    ("phoenix", "gen_ai.usage.cache_read.input_tokens"): (40, "llm.token_count.prompt_details.cache_read", 40),
    ("phoenix", "argus.usage.cost_usd"): (1.5e-05, "llm.cost.total", 1.5e-05),
    ("phoenix", "gen_ai.conversation.id"): ("run-1", "session.id", "run-1"),
    ("phoenix", "gen_ai.tool.name"): ("submit", "tool.name", "submit"),
    ("phoenix", "gen_ai.agent.name"): ("fix-loop", "agent.name", "fix-loop"),
}


def _export(profile: str, attributes: dict, **span_fields):
    """One span with `attributes` through a real provider and `NormalizingExporter(profile)`; returns (span, exporter)."""
    memory = InMemorySpanExporter()
    exporter = NormalizingExporter(memory, profile)
    provider = TracerProvider(resource=Resource.create({"argus.trace.schema_version": "1"}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    with provider.get_tracer("argus").start_as_current_span("chat m", attributes=attributes, **span_fields):
        pass
    return memory.get_finished_spans()[0], exporter


def test_every_rule_has_a_test_row():
    rules = {(profile, name) for profile, table in PROFILES.items() for name in table}
    assert rules == set(EXPECTED)
    assert all(name in KNOWN for _, name in rules)


@pytest.mark.parametrize("profile,name", sorted(EXPECTED))
def test_mapped_attribute(profile, name):
    value, target, expected = EXPECTED[profile, name]
    span, exporter = _export(profile, {name: value})
    assert span.attributes == {target: expected}
    assert not exporter.unmapped


def test_phoenix_span_kind_for_each_operation():
    kinds = {}
    for op in ("chat", "execute_tool", "invoke_agent"):
        span, _ = _export("phoenix", {"gen_ai.operation.name": op})
        kinds[op] = span.attributes["openinference.span.kind"]
    assert kinds == {"chat": "LLM", "execute_tool": "TOOL", "invoke_agent": "AGENT"}


@pytest.mark.parametrize("profile", sorted(PROFILES))
def test_unknown_attribute_passes_through_unchanged_and_is_counted(profile):
    memory = InMemorySpanExporter()
    exporter = NormalizingExporter(memory, profile)
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("argus")
    for _ in range(2):
        with tracer.start_as_current_span("s", attributes={"gen_ai.usage.prompt_tokens": 9, "gen_ai.operation.name": "chat"}):
            pass
    with tracer.start_as_current_span("s", attributes={"vendor.thing": "x"}):
        pass
    first, _, third = memory.get_finished_spans()
    assert first.attributes["gen_ai.usage.prompt_tokens"] == 9  # same name, same value
    assert third.attributes == {"vendor.thing": "x"}
    assert exporter.unmapped == Counter({"gen_ai.usage.prompt_tokens": 2, "vendor.thing": 1})


def test_the_warning_names_the_attribute_but_never_its_value(caplog):
    with caplog.at_level(logging.WARNING, logger="argus.trace"):
        _export("none", {"vendor.token": "sk-very-secret-value"})
    assert "vendor.token" in caplog.text
    assert "sk-very-secret-value" not in caplog.text


def test_everything_but_the_attributes_is_kept():
    span, _ = _export("phoenix", {"gen_ai.usage.input_tokens": 1}, kind=telemetry.SpanKind.CLIENT)
    assert (span.name, span.kind) == ("chat m", telemetry.SpanKind.CLIENT)
    assert span.resource.attributes["argus.trace.schema_version"] == "1"
    assert span.start_time and span.end_time and span.context.trace_id
    assert span.status.status_code == StatusCode.UNSET


def test_error_status_and_parent_survive():
    memory = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(NormalizingExporter(memory, "langfuse")))
    tracer = provider.get_tracer("argus")
    with tracer.start_as_current_span("parent") as parent:
        with tracer.start_as_current_span("child") as child:
            child.set_status(Status(StatusCode.ERROR, "boom"))
    child_out, parent_out = memory.get_finished_spans()
    assert child_out.status.status_code == StatusCode.ERROR and child_out.status.description == "boom"
    assert child_out.parent.span_id == parent.get_span_context().span_id == parent_out.context.span_id


def test_profile_comes_from_the_environment():
    langfuse = {"ARGUS_TRACE_BACKEND": "langfuse", "LANGFUSE_PUBLIC_KEY": "p", "LANGFUSE_SECRET_KEY": "s"}
    otlp = {"ARGUS_TRACE_BACKEND": "otlp", "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:6006"}
    assert trace_config(langfuse).profile == "langfuse"
    assert trace_config(otlp).profile == "none"
    assert trace_config({**otlp, "ARGUS_TRACE_PROFILE": "Phoenix"}).profile == "phoenix"
    with pytest.raises(TraceConfigError, match="ARGUS_TRACE_PROFILE must be one of"):
        trace_config({**otlp, "ARGUS_TRACE_PROFILE": "datadog"})


def test_start_tracing_exposes_the_unmapped_counter(monkeypatch):
    memory = InMemorySpanExporter()
    monkeypatch.setattr(telemetry, "_default_exporter", lambda: NormalizingExporter(memory, "phoenix"))
    provider = telemetry.start_tracing()
    with telemetry.agent_span("a", run_id="r") as span:
        span.set_attribute("vendor.thing", 1)
    provider.force_flush()
    out = memory.get_finished_spans()[0]
    assert out.attributes["openinference.span.kind"] == "AGENT" and out.attributes["session.id"] == "r"
    assert telemetry.unmapped_attributes() == Counter({"vendor.thing": 1})
    provider.shutdown()
    telemetry.start_tracing(InMemorySpanExporter())  # a passed exporter is not normalized, so nothing is counted
    assert telemetry.unmapped_attributes() == Counter()
