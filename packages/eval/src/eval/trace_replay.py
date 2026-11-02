"""P5-T23: replay a finished stored run as spans, send them to the configured trace backend, and check they arrived.

    python -m eval.trace_replay <run folder> [--session ID] [--evidence PATH]

A run folder is `<task>/{repro,fix}/trajectory.jsonl` + `verdict.json` + `answers.jsonl` (the T14 layout). Nothing here calls a model.
The spans use the helpers' attribute names (`argus_core.telemetry`, `docs/notes/p5-semconv.md`) and go through `start_tracing()`,
so `ARGUS_TRACE_BACKEND`, `LANGFUSE_*` and the normalizer profile come from the environment. Message text is never put on a span.

Every span carries `argus.replay=true` and `argus.replay.source_run`. A trajectory stores no per-step clock, so the recorded
wall time (`verdict.json`) is split evenly across the steps; the root span says so. The Langfuse session id is `argus-replay-<run id>`.

Keys: this module never reads a Langfuse key. The Basic header is taken ready-made from `trace_config()` and is only sent.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from opentelemetry import trace
from opentelemetry.trace import Span, SpanKind

from argus_core import telemetry
from argus_core.types import Trajectory

STAGES = (("repro", "repro-agent"), ("fix", "fix-loop"))  # folder, agent name; the repro agent runs first
CHAT_SHARE = 0.7  # ponytail: a step's slot is 70% model call, 30% tool call; real per-step times are not stored
OTLP_SUFFIX = "/api/public/otel/v1/traces"
DEFAULT_EVIDENCE = Path(__file__).resolve().parents[4] / "docs" / "notes" / "p5-t23-trace-evidence.md"


@dataclass(frozen=True)
class Replay:
    trace_id: str
    session: str
    source_run: str
    spans: int
    start: float  # seconds since the epoch, the laid-out window
    end: float


def _ns(seconds: float) -> int:
    return int(seconds * 1e9)


def replay(run: Path, session: str | None = None, *, clock: Callable[[], float] = time.time) -> Replay:
    """Emit the spans of `run` on the provider `start_tracing()` set up. The caller flushes."""
    stages = [(agent, Trajectory.from_jsonl((run / d / "trajectory.jsonl").read_text(encoding="utf-8")), d)
              for d, agent in STAGES if (run / d / "trajectory.jsonl").is_file()]
    if not stages:
        raise FileNotFoundError(f"no repro/ or fix/ trajectory.jsonl under {run}")
    verdict_path = run / "verdict.json"
    verdict = json.loads(verdict_path.read_text(encoding="utf-8")) if verdict_path.is_file() else {}
    meta = stages[0][1].meta
    source, session = meta.run_id, session or f"argus-replay-{meta.run_id}"
    total = sum(len(t.steps) for _, t, _ in stages)
    if not total:
        raise ValueError(f"{run} has no steps to replay")
    end = verdict.get("finished_at") or clock()
    start = verdict.get("started_at") or end - total
    slot = (end - start) / total
    common = {"argus.replay": True, "argus.replay.source_run": source}
    tracer = telemetry._tracer()  # ponytail: the helpers are context managers that stamp "now"; replay needs explicit times

    def open_span(name: str, kind: SpanKind, attrs: dict, parent: Span | None, at: float) -> Span:
        ctx = trace.set_span_in_context(parent) if parent else None
        return tracer.start_span(name, context=ctx, kind=kind, attributes={**common, **attrs}, start_time=_ns(at))

    root = open_span("invoke_agent argus-run", SpanKind.INTERNAL, {
        "gen_ai.operation.name": "invoke_agent", "gen_ai.agent.name": "argus-run", "gen_ai.conversation.id": session,
        "argus.task.id": meta.task_id,
        "argus.replay.note": f"timing: recorded wall time split evenly per step; tokens: {verdict.get('token_source', 'as stored')}",
    }, None, start)
    spans, cursor = 1, start
    for agent, traj, stage in stages:
        first = cursor
        stage_span = open_span(f"invoke_agent {agent}", SpanKind.INTERNAL, {
            "gen_ai.operation.name": "invoke_agent", "gen_ai.agent.name": agent, "gen_ai.conversation.id": session,
            "argus.task.id": meta.task_id, "argus.stage": stage,
        }, root, first)
        spans += 1
        for step in traj.steps:
            model = step.model or meta.model
            attrs = {"gen_ai.operation.name": "chat", "gen_ai.request.model": model, "gen_ai.conversation.id": session,
                     "argus.step.index": step.index, "argus.stage": stage}
            if step.tier:
                attrs["argus.tier"] = step.tier
            chat_end = cursor + slot * (CHAT_SHARE if step.tool_name else 1)
            chat = open_span(f"chat {model}", SpanKind.CLIENT, attrs, stage_span, cursor)
            usage = SimpleNamespace(tokens_in=step.tokens_in, tokens_out=step.tokens_out, tokens_cached=step.tokens_cached)
            telemetry.record_completion(chat, model, SimpleNamespace(usage=usage, raw={}))  # finish reason is not stored: absent
            if step.stop_reason:
                chat.set_attribute("argus.stop_reason", step.stop_reason.value)
            if not step.tool_name:  # a reply that was not a tool call (e.g. `not-a-repro`): note it, no error status
                telemetry.record_tool_error(chat, step.tool_error, failed=False)
            chat.end(end_time=_ns(chat_end))
            spans += 1
            if step.tool_name:
                tool = open_span(f"execute_tool {step.tool_name}", SpanKind.INTERNAL, {
                    "gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": step.tool_name, "gen_ai.tool.type": "function",
                    "gen_ai.conversation.id": session, "argus.step.index": step.index, "argus.stage": stage,
                }, stage_span, chat_end)
                telemetry.record_tool_error(tool, step.tool_error)
                tool.end(end_time=_ns(cursor + slot))
                spans += 1
            cursor += slot
        last = traj.steps[-1].stop_reason if traj.steps else None
        if last:
            stage_span.set_attribute("argus.stop_reason", last.value)
        stage_span.end(end_time=_ns(cursor))
    for attr, key in (("argus.stop_reason", "stop_reason"), ("argus.verdict", "verdict")):
        if verdict.get(key):
            root.set_attribute(attr, str(verdict[key]))
    root.end(end_time=_ns(end))
    return Replay(format(root.get_span_context().trace_id, "032x"), session, source, spans, start, end)


def _iso(seconds: float) -> str:
    return datetime.fromtimestamp(seconds, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_observations(config: telemetry.TraceConfig, done: Replay) -> list[dict]:
    """Observation rows of the replay's session from the Langfuse API.

    `GET <base>/api/public/v2/observations?sessionId=...`: the legacy `/api/public/traces` is deprecated (Cloud serves it until
    2026-11-16, Hobby allows 5 requests a minute on it). The docs read do not show the v2 response body, so `data` is optional.
    """
    base = (config.endpoint or "").removesuffix(OTLP_SUFFIX)
    query = urlencode({
        "sessionId": done.session, "fields": "core,basic", "limit": 1000,
        "fromStartTime": _iso(done.start - 86400), "toStartTime": _iso(done.end + 86400),
    })
    request = Request(f"{base}/api/public/v2/observations?{query}", headers={"Authorization": config.headers["Authorization"]})
    with urlopen(request, timeout=20) as response:
        body = json.load(response)
    return body.get("data", []) if isinstance(body, dict) else body


def write_evidence(path: Path, done: Replay, rows: list[dict]) -> None:
    """Names, types, counts and times of what Langfuse returned. No keys, no message text (the API call asks for none)."""
    rows = sorted(rows, key=lambda r: r.get("startTime") or "")
    types: dict[str, int] = {}
    for row in rows:
        types[row.get("type", "?")] = types.get(row.get("type", "?"), 0) + 1
    ids = sorted({r.get("traceId", "?") for r in rows})
    lines = [
        "# P5-T23 trace evidence (from the Langfuse API)",
        "",
        "This is a **replay** of a stored run (`argus.replay=true` on every span), not a live run. It stands in for a screenshot.",
        f"Written by `python -m eval.trace_replay` on {_iso(time.time())}. Fields: `GET /api/public/v2/observations?sessionId=`, `fields=core,basic`.",
        "",
        f"- Source run: `{done.source_run}`",
        f"- Langfuse session: `{done.session}`",
        f"- Trace id(s) returned: {', '.join(f'`{i}`' for i in ids)}",
        f"- Spans sent: {done.spans}. Observations returned: {len(rows)}. By type: {', '.join(f'{k} {v}' for k, v in sorted(types.items()))}",
        "",
        "| # | name | type | level | start | end | root |",
        "|---|---|---|---|---|---|---|",
    ]
    for n, row in enumerate(rows, 1):
        root = "yes" if not row.get("parentObservationId") else ""
        lines.append(f"| {n} | {row.get('name', '')} | {row.get('type', '')} | {row.get('level', '')} | {row.get('startTime', '')} | {row.get('endTime', '')} | {root} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def verify(config: telemetry.TraceConfig, done: Replay, evidence: Path, *, fetch=fetch_observations, sleep=time.sleep, tries: int = 6) -> bool:
    """Ask the API until the replay's observations show up (ingestion lags), then write the evidence file."""
    rows: list[dict] = []
    for attempt in range(tries):
        try:
            rows = fetch(config, done)
        except (URLError, OSError, ValueError) as exc:  # HTTPError is a URLError; its text holds the status, not the key
            print(f"api check: attempt {attempt + 1} failed: {exc}")
        if len(rows) >= done.spans:
            break
        sleep(5)
    if not rows:
        print(f"api check: no observations for session {done.session} after {tries} tries; evidence file not written")
        return False
    write_evidence(evidence, done, rows)
    print(f"api check: {len(rows)} of {done.spans} observations found; evidence written to {evidence}")
    return len(rows) >= done.spans


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="eval.trace_replay", description=__doc__.split("\n")[0])
    parser.add_argument("run", type=Path, help="a finished run folder, e.g. packages/eval/results/t14/B/seed-e01")
    parser.add_argument("--session", help="Langfuse session id (default argus-replay-<run id>)")
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    args = parser.parse_args(argv)
    try:
        config = telemetry.trace_config()
        provider = telemetry.start_tracing()
    except telemetry.TraceConfigError as exc:
        print(f"trace config error: {exc}", file=sys.stderr)
        return 2
    results: list[str] = []
    normalizer = telemetry._normalizer
    send = normalizer.export  # record what each real export returned
    normalizer.export = lambda spans: (r := send(spans), results.append(r.name))[0]
    done = replay(args.run, args.session)
    if done.spans > telemetry.QUEUE_SIZE:
        print(f"warning: {done.spans} spans is more than the queue ({telemetry.QUEUE_SIZE}); the rest are dropped", file=sys.stderr)
    provider.force_flush(30_000)
    provider.shutdown()
    export = "SUCCESS" if results and all(r == "SUCCESS" for r in results) else (results[-1] if results else "NONE")
    print(f"backend={config.backend} profile={config.profile} endpoint={config.endpoint or '-'} session={done.session} "
          f"trace_id={done.trace_id} spans={done.spans} export={export}")
    if export != "SUCCESS":
        return 1
    if config.backend != "langfuse":
        print("api check: skipped, the backend is not langfuse")
    else:
        verify(config, done, args.evidence)  # a failed check is reported, not an exit code: the export itself worked
    return 0


if __name__ == "__main__":
    sys.exit(main())
