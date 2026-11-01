"""OpenTelemetry spans for model calls, tool calls and agent runs, with GenAI attribute names.

Names and where each is set: `docs/notes/p5-semconv.md`. Message text is never put on a span.
With no provider started the API hands out no-op spans, so a run behaves as before.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from urllib.parse import urlparse

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor, SpanExporter
from opentelemetry.trace import Span, SpanKind, Status, StatusCode

from argus_core.prices import UnknownModelPrice, dollar_equivalent

SCHEMA_VERSION = "1"
_provider: TracerProvider | None = None
_in_chat: ContextVar[bool] = ContextVar("argus_in_chat", default=False)


def _default_exporter() -> SpanExporter:
    """The one place an exporter is chosen. The OTLP exporter (T07) replaces this."""
    return ConsoleSpanExporter()


def start_tracing(exporter: SpanExporter | None = None) -> TracerProvider:
    """Start (or replace) the provider argus spans go to. Console exporter unless one is passed."""
    global _provider
    _provider = TracerProvider(resource=Resource.create({"argus.trace.schema_version": SCHEMA_VERSION}))
    _provider.add_span_processor(SimpleSpanProcessor(exporter or _default_exporter()))
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
