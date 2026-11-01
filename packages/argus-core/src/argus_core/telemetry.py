"""OpenTelemetry spans for model calls, tool calls and agent runs, with GenAI attribute names.

Names and where each is set: `docs/notes/p5-semconv.md`. Message text is never put on a span.
With no provider started the API hands out no-op spans, so a run behaves as before.

Where spans go is chosen from the environment (`trace_config`, steps in `docs/notes/p5-t07.md`):
`ARGUS_TRACE_BACKEND` is `console` (default), `langfuse` or `otlp`. Keys are read from the environment
only; they are never written to a file, a log line or a span.
"""

from __future__ import annotations

import base64
import os
import sys
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
from urllib.parse import urlparse

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
    SpanExporter,
    SpanProcessor,
)
from opentelemetry.trace import Span, SpanKind, Status, StatusCode

from argus_core.prices import UnknownModelPrice, dollar_equivalent

SCHEMA_VERSION = "1"
LANGFUSE_DEFAULT_HOST = "https://cloud.langfuse.com"  # EU region; a US project sets LANGFUSE_BASE_URL
# A dead backend must not hold a run: one export gives up after EXPORT_TIMEOUT_S (retries share that budget),
# and the queue holds QUEUE_SIZE spans and drops the rest (a batch is the whole queue, so shutdown waits at most two timeouts). ponytail: constants, not env knobs; add knobs if a run needs tuning.
EXPORT_TIMEOUT_S = 3
QUEUE_SIZE = 512
_provider: TracerProvider | None = None
_in_chat: ContextVar[bool] = ContextVar("argus_in_chat", default=False)


class TraceConfigError(ValueError):
    """The trace environment is incomplete or wrong. The message names variables, never their values."""


@dataclass(frozen=True)
class TraceConfig:
    backend: str  # console | langfuse | otlp
    endpoint: str | None = None
    headers: Mapping[str, str] = field(default_factory=dict, repr=False)  # holds the secret: kept out of repr


def _headers(raw: str) -> dict[str, str]:
    """`k=v,k=v` as in `OTEL_EXPORTER_OTLP_HEADERS`; the value is everything after the first `=`."""
    pairs = (item.split("=", 1) for item in raw.split(",") if "=" in item)
    return {k.strip(): v.strip() for k, v in pairs}


def trace_config(env: Mapping[str, str] | None = None) -> TraceConfig:
    """Read the export settings from `env` (default `os.environ`). Raises `TraceConfigError` if something is missing."""
    env = os.environ if env is None else env
    backend = (env.get("ARGUS_TRACE_BACKEND") or "console").lower()
    if backend == "console":
        return TraceConfig(backend)
    if backend == "langfuse":
        missing = [k for k in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY") if not env.get(k)]
        if missing:
            raise TraceConfigError(f"ARGUS_TRACE_BACKEND=langfuse needs {' and '.join(missing)} in the environment")
        basic = base64.b64encode(f"{env['LANGFUSE_PUBLIC_KEY']}:{env['LANGFUSE_SECRET_KEY']}".encode()).decode()
        host = (env.get("LANGFUSE_BASE_URL") or env.get("LANGFUSE_HOST") or LANGFUSE_DEFAULT_HOST).rstrip("/")
        # Langfuse takes OTLP over HTTP only. Ingestion version 4 shows new data at once instead of up to 10 minutes late.
        headers = {"Authorization": f"Basic {basic}", "x-langfuse-ingestion-version": "4"}
        return TraceConfig(backend, f"{host}/api/public/otel/v1/traces", headers)
    if backend == "otlp":
        traces = env.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
        base = env.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        if not (traces or base):
            raise TraceConfigError(
                "ARGUS_TRACE_BACKEND=otlp needs OTEL_EXPORTER_OTLP_TRACES_ENDPOINT or OTEL_EXPORTER_OTLP_ENDPOINT"
            )
        headers = _headers(env.get("OTEL_EXPORTER_OTLP_TRACES_HEADERS") or env.get("OTEL_EXPORTER_OTLP_HEADERS") or "")
        return TraceConfig(backend, traces or f"{base.rstrip('/')}/v1/traces", headers)
    raise TraceConfigError("ARGUS_TRACE_BACKEND must be console, langfuse or otlp")


def _default_exporter() -> SpanExporter:
    """The one place an exporter is chosen: read from the environment."""
    config = trace_config()
    if config.backend == "console":
        return ConsoleSpanExporter()
    return OTLPSpanExporter(endpoint=config.endpoint, headers=dict(config.headers), timeout=EXPORT_TIMEOUT_S)


def start_tracing(exporter: SpanExporter | None = None) -> TracerProvider:
    """Start (or replace) the provider argus spans go to.

    With no `exporter` the environment decides (`trace_config`). A network exporter gets a batch processor with a
    bounded queue and a short timeout, so an unreachable backend drops spans instead of blocking the run.
    A passed `exporter` (tests) gets every span as emitted, synchronously.
    """
    global _provider
    _provider = TracerProvider(resource=Resource.create({"argus.trace.schema_version": SCHEMA_VERSION}))
    processor: SpanProcessor
    if exporter is None and trace_config().backend != "console":
        processor = BatchSpanProcessor(
            _default_exporter(),
            max_queue_size=QUEUE_SIZE,
            schedule_delay_millis=2000,
            max_export_batch_size=QUEUE_SIZE,  # one batch holds the whole queue: a dead backend costs one timeout, not eight
            export_timeout_millis=EXPORT_TIMEOUT_S * 1000,
        )
    else:
        processor = SimpleSpanProcessor(exporter or _default_exporter())
    _provider.add_span_processor(processor)
    return _provider


def _tracer() -> trace.Tracer:
    return (_provider or trace.get_tracer_provider()).get_tracer("argus")


def _provider_name(host: str) -> str:
    for name in ("groq", "mistral"):
        if name in host:
            return name
    return "ollama"  # ponytail: any other host is taken to be Ollama; add a profile field if a fourth host appears


def _end_with(span: Span, exc: BaseException) -> None:
    span.set_attribute("error.type", getattr(exc, "error", None) or type(exc).__name__)
    span.set_status(Status(StatusCode.ERROR, str(exc)))


@contextmanager
def agent_span(name: str, *, run_id: str | None = None, task_id: str | None = None) -> Iterator[Span]:
    """`invoke_agent {name}`. The caller sets `argus.stop_reason` before the block ends."""
    attrs = {"gen_ai.operation.name": "invoke_agent", "gen_ai.agent.name": name}
    if run_id is not None:
        attrs["gen_ai.conversation.id"] = run_id
    if task_id is not None:
        attrs["argus.task.id"] = task_id
    with _tracer().start_as_current_span(f"invoke_agent {name}", kind=SpanKind.INTERNAL, attributes=attrs) as span:
        yield span


def traced_agent(name: str):
    """Decorator for a loop entry point: wrap the run in `invoke_agent` and put its stop reason on the span.

    Reads `run_id` and `task_id` (or `ticket.id`) from the keyword arguments; returns the loop result unchanged.
    """

    def wrap(fn):
        @wraps(fn)
        def run(**kwargs):
            task_id = kwargs.get("task_id") or getattr(kwargs.get("ticket"), "id", None)
            with agent_span(name, run_id=kwargs.get("run_id"), task_id=task_id) as span:
                result = fn(**kwargs)
                span.set_attribute("argus.stop_reason", getattr(result.stop_reason, "value", str(result.stop_reason)))
                return result

        return run

    return wrap


@contextmanager
def chat_span(model: str, base_url: str | None = None, *, step: int | None = None) -> Iterator[Span]:
    """`chat {model}`. A call inside an open chat span (a loop wrapping `ModelClient.complete`) joins it."""
    if _in_chat.get():
        span = trace.get_current_span()
        _set_endpoint(span, base_url)
        yield span
        return
    attrs: dict = {"gen_ai.operation.name": "chat", "gen_ai.request.model": model}
    if step is not None:
        attrs["argus.step.index"] = step
    token = _in_chat.set(True)
    try:
        with _tracer().start_as_current_span(f"chat {model}", kind=SpanKind.CLIENT, attributes=attrs) as span:
            _set_endpoint(span, base_url)
            try:
                yield span
            except BaseException as exc:
                _end_with(span, exc)
                raise
    finally:
        _in_chat.reset(token)


def _set_endpoint(span: Span, base_url: str | None) -> None:
    if not base_url:
        return
    parsed = urlparse(base_url)
    span.set_attribute("gen_ai.provider.name", _provider_name(parsed.hostname or ""))
    if parsed.hostname:
        span.set_attribute("server.address", parsed.hostname)
    if parsed.port:
        span.set_attribute("server.port", parsed.port)


def record_completion(span: Span, model: str, completion: object) -> None:
    """Tokens, response ids, finish reason and list-price dollars from a `Completion`."""
    usage = completion.usage
    span.set_attribute("gen_ai.usage.input_tokens", usage.tokens_in)
    span.set_attribute("gen_ai.usage.output_tokens", usage.tokens_out)
    if usage.tokens_cached:
        span.set_attribute("gen_ai.usage.cache_read.input_tokens", usage.tokens_cached)
    raw = completion.raw if isinstance(completion.raw, dict) else {}
    for key, attr in (("model", "gen_ai.response.model"), ("id", "gen_ai.response.id")):
        if raw.get(key):
            span.set_attribute(attr, str(raw[key]))
    choices = raw.get("choices")
    finish = (choices[0] or {}).get("finish_reason") if isinstance(choices, list) and choices else None
    if finish:
        span.set_attribute("gen_ai.response.finish_reasons", [str(finish)])
    try:
        span.set_attribute(
            "argus.usage.cost_usd",
            dollar_equivalent(model, usage.tokens_in, usage.tokens_out, usage.tokens_cached),
        )
    except (UnknownModelPrice, ValueError):
        pass  # no price: the attribute stays absent, the run goes on


@contextmanager
def tool_span(name: str, *, run_id: str | None = None, step: int | None = None) -> Iterator[Span]:
    """`execute_tool {name}`. The caller sets `argus.tool.error` when the tool returned an error."""
    attrs: dict = {"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": name, "gen_ai.tool.type": "function"}
    if run_id is not None:
        attrs["gen_ai.conversation.id"] = run_id
    if step is not None:
        attrs["argus.step.index"] = step
    with _tracer().start_as_current_span(f"execute_tool {name}", kind=SpanKind.INTERNAL, attributes=attrs) as span:
        try:
            yield span
        except BaseException as exc:
            _end_with(span, exc)
            raise


def record_tool_error(span: Span, error: str | None, *, failed: bool = True) -> None:
    """`failed=False` marks a tool that ran fine but whose outcome was unwanted (`not-a-repro`): no error status."""
    if error:
        span.set_attribute("argus.tool.error", error)
        if failed:
            span.set_attribute("error.type", error)
            span.set_status(Status(StatusCode.ERROR, error))


def _smoke() -> int:
    """Send one tiny fake trace (agent, model call, tool call) to the configured backend and say if it was accepted."""
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    memory = InMemorySpanExporter()
    start_tracing(memory)
    with agent_span("argus-smoke", run_id="argus-smoke", task_id="smoke") as agent:
        with chat_span("smoke-model") as chat:
            chat.set_attribute("gen_ai.usage.input_tokens", 10)
            chat.set_attribute("gen_ai.usage.output_tokens", 2)
            chat.set_attribute("argus.usage.cost_usd", 1e-06)
        with tool_span("smoke-tool", run_id="argus-smoke", step=0):
            pass
        agent.set_attribute("argus.stop_reason", "submit")
    config = trace_config()
    result = _default_exporter().export(memory.get_finished_spans())
    print(f"backend={config.backend} endpoint={config.endpoint or '-'} export={result.name}")
    return 0 if result.name == "SUCCESS" else 1


if __name__ == "__main__":
    try:
        sys.exit(_smoke())
    except TraceConfigError as exc:
        sys.exit(f"trace config error: {exc}")
