"""Rename span attributes to the names a trace backend reads, between the spans and the exporter.

Argus writes the OpenTelemetry GenAI names (`docs/notes/p5-semconv.md`). Backends read their own: Langfuse wants
`gen_ai.usage.cost` and `langfuse.session.id`, Phoenix wants OpenInference (`llm.token_count.prompt`, `openinference.span.kind`).
A profile is a table: argus attribute -> (backend attribute, optional value change). A mapped attribute is moved, not copied.

`KNOWN` is every name argus emits. A name outside it passes through unchanged and is counted in `unmapped`, so a
semconv rename (the spec is still `Development`) shows up as a number, not as a silent hole in the backend.
Strict mode (`strict=True` or `ARGUS_TRACE_STRICT=1`, for tests and CI, off by default) raises `UnmappedAttribute` instead of
passing the name through. Run inside a span processor the SDK catches and logs that error, so the run is not broken.
"""

from __future__ import annotations

import logging
import os
from collections import Counter
from collections.abc import Callable, Sequence
from typing import Any

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

log = logging.getLogger("argus.trace")

KNOWN = frozenset(
    {
        "gen_ai.operation.name",
        "gen_ai.provider.name",
        "gen_ai.request.model",
        "gen_ai.response.model",
        "gen_ai.response.id",
        "gen_ai.response.finish_reasons",
        "gen_ai.usage.input_tokens",
        "gen_ai.usage.output_tokens",
        "gen_ai.usage.cache_read.input_tokens",
        "gen_ai.agent.name",
        "gen_ai.conversation.id",
        "gen_ai.tool.name",
        "gen_ai.tool.type",
        "error.type",
        "server.address",
        "server.port",
        "argus.stop_reason",
        "argus.step.index",
        "argus.task.id",
        "argus.tool.error",
        "argus.usage.cost_usd",
        "argus.tier",
        "argus.stage",
        "argus.verdict",
        "argus.replay",
        "argus.replay.source_run",
        "argus.replay.note",
    }
)

Rule = tuple[str, Callable[[Any], Any] | None]  # backend attribute, change applied to the value (None: keep it)

_SPAN_KIND = {"chat": "LLM", "execute_tool": "TOOL", "invoke_agent": "AGENT"}


def _metadata(name: str) -> Rule:
    """Langfuse keeps unmapped attributes under an unfilterable `metadata.attributes`; this prefix makes the key filterable."""
    return f"langfuse.observation.metadata.{name.replace('.', '_')}", str


PROFILES: dict[str, dict[str, Rule]] = {
    "none": {},
    "langfuse": {
        "argus.usage.cost_usd": ("gen_ai.usage.cost", None),
        "gen_ai.conversation.id": ("langfuse.session.id", None),
        **{n: _metadata(n) for n in (
            "argus.stop_reason", "argus.step.index", "argus.task.id", "argus.tool.error", "argus.tier",
            "argus.stage", "argus.verdict", "argus.replay", "argus.replay.source_run", "argus.replay.note",
        )},
    },
    "phoenix": {
        "gen_ai.operation.name": ("openinference.span.kind", lambda v: _SPAN_KIND.get(v, "CHAIN")),
        "gen_ai.request.model": ("llm.model_name", None),
        "gen_ai.provider.name": ("llm.provider", None),
        "gen_ai.usage.input_tokens": ("llm.token_count.prompt", None),
        "gen_ai.usage.output_tokens": ("llm.token_count.completion", None),
        "gen_ai.usage.cache_read.input_tokens": ("llm.token_count.prompt_details.cache_read", None),
        "argus.usage.cost_usd": ("llm.cost.total", None),
        "gen_ai.conversation.id": ("session.id", None),
        "gen_ai.tool.name": ("tool.name", None),
        "gen_ai.agent.name": ("agent.name", None),
    },
}


class UnmappedAttribute(ValueError):
    """Strict mode met an attribute name argus does not know. The message holds the name, never the value."""


class NormalizingExporter(SpanExporter):
    """Wraps another exporter; every span gets the profile's names before it is exported."""

    def __init__(self, inner: SpanExporter, profile: str = "none", strict: bool = False) -> None:
        self.inner = inner
        self.rules = PROFILES[profile]
        self.strict = strict or os.environ.get("ARGUS_TRACE_STRICT") == "1"
        self.unmapped: Counter[str] = Counter()

    def normalize(self, attributes: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for name, value in attributes.items():
            if name in self.rules:
                name, change = self.rules[name]
                value = change(value) if change else value
            elif name not in KNOWN:
                if name not in self.unmapped:
                    log.warning("trace attribute %r is not one argus knows; sent unchanged", name)  # name only, never the value
                self.unmapped[name] += 1
                if self.strict:
                    raise UnmappedAttribute(f"trace attribute {name!r} is not one argus knows; add it to KNOWN and the profiles")
            out[name] = value
        return out

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        result = self.inner.export([self._rewrite(s) for s in spans])
        if result is not SpanExportResult.SUCCESS:  # the OTLP exporter has already retried until its timeout
            log.warning("dropped %d spans: the trace backend did not take them", len(spans))  # a count only, no endpoint or header
        return result

    def _rewrite(self, span: ReadableSpan) -> ReadableSpan:
        return ReadableSpan(
            name=span.name,
            context=span.context,
            parent=span.parent,
            resource=span.resource,
            attributes=self.normalize(dict(span.attributes or {})),
            events=span.events,
            links=span.links,
            kind=span.kind,
            status=span.status,
            start_time=span.start_time,
            end_time=span.end_time,
            instrumentation_scope=span.instrumentation_scope,
        )

    def shutdown(self) -> None:
        self.inner.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self.inner.force_flush(timeout_millis)
