"""P5-T23: a stored run replayed as spans against a local OTLP/HTTP receiver that also fakes the Langfuse read API.

Nothing here reaches the network or a real Langfuse project. It shows what is sent and that no key is printed; it does not
show that Langfuse accepts the spans (that is the owner's run, `docs/notes/p5-t23.md`).
"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

from argus_core.types import StopReason, Trajectory, TrajectoryMeta, TrajectoryStep
from eval import trace_replay

RUN = Path(__file__).resolve().parents[1] / "results" / "t14" / "B" / "seed-e01"
PUBLIC, SECRET = "pk-lf-test-public", "sk-lf-test-secret"


def _value(v):
    kind = v.WhichOneof("value")
    return [_value(x) for x in v.array_value.values] if kind == "array_value" else getattr(v, kind)


class Receiver:
    """POST /…/v1/traces collects spans; GET /api/public/v2/observations answers from what was collected."""

    def __init__(self):
        self.spans: list[dict] = []
        self.gets: list[tuple[str, str]] = []  # (path with query, Authorization header)
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                request = ExportTraceServiceRequest.FromString(self.rfile.read(int(self.headers["Content-Length"])))
                for resource in request.resource_spans:
                    for scope in resource.scope_spans:
                        for s in scope.spans:
                            outer.spans.append({
                                "name": s.name, "trace": s.trace_id.hex(), "id": s.span_id.hex(), "parent": s.parent_span_id.hex(),
                                "start": s.start_time_unix_nano, "end": s.end_time_unix_nano, "error": s.status.code == 2,
                                "attrs": {kv.key: _value(kv.value) for kv in s.attributes},
                            })
                self.send_response(200)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def do_GET(self):
                outer.gets.append((self.path, self.headers.get("Authorization", "")))
                rows = [{"id": s["id"], "traceId": s["trace"], "name": s["name"], "type": "SPAN", "level": "DEFAULT",
                         "startTime": str(s["start"]), "endTime": str(s["end"]), "parentObservationId": s["parent"] or None}
                        for s in outer.spans]
                body = json.dumps({"data": rows, "meta": {}}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_port}"

    def by_name(self, name: str) -> list[dict]:
        return [s for s in self.spans if s["name"] == name]


@pytest.fixture
def receiver(monkeypatch):
    r = Receiver()
    for key in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_BASE_URL", "LANGFUSE_HOST", "ARGUS_TRACE_PROFILE"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ARGUS_TRACE_BACKEND", "otlp")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", f"{r.url}/v1/traces")
    yield r
    r.server.shutdown()


def test_stored_run_becomes_a_span_tree(receiver, capsys):
    assert trace_replay.main([str(RUN)]) == 0
    spans = receiver.spans
    assert "export=SUCCESS" in capsys.readouterr().out
    assert len(spans) == 16  # root, 2 stage agents, 8 chat (3 repro + 5 fix), 5 tool (fix only)
    assert len({s["trace"] for s in spans}) == 1
    by_id = {s["id"]: s for s in spans}
    (root,) = receiver.by_name("invoke_agent argus-run")
    assert root["parent"] == ""
    repro, fix = receiver.by_name("invoke_agent repro-agent")[0], receiver.by_name("invoke_agent fix-loop")[0]
    assert repro["parent"] == fix["parent"] == root["id"]
    chats = [s for s in spans if s["name"].startswith("chat ")]
    tools = [s for s in spans if s["name"].startswith("execute_tool ")]
    assert (len(chats), len(tools)) == (8, 5)
    for s in chats + tools:
        assert by_id[s["parent"]]["attrs"]["argus.stage"] == s["attrs"]["argus.stage"]
    assert [s["name"] for s in tools] == ["execute_tool search", "execute_tool search", "execute_tool read_file", "execute_tool edit", "execute_tool submit"]


def test_every_span_is_marked_as_a_replay(receiver):
    trace_replay.main([str(RUN)])
    assert receiver.spans
    for s in receiver.spans:
        assert s["attrs"]["argus.replay"] is True
        assert s["attrs"]["argus.replay.source_run"] == "B-seed-e01"
    (root,) = receiver.by_name("invoke_agent argus-run")
    assert root["attrs"]["gen_ai.conversation.id"] == "argus-replay-B-seed-e01"
    assert root["attrs"]["argus.verdict"] == "resolved"
    assert "evenly" in root["attrs"]["argus.replay.note"]


def test_chat_spans_carry_model_tier_stage_tokens_cost_and_stop_reason(receiver):
    trace_replay.main([str(RUN), "--session", "my-session"])
    chats = sorted((s for s in receiver.spans if s["name"].startswith("chat ")), key=lambda s: s["start"])
    first, last = chats[0], chats[-1]
    assert first["name"] == "chat claude-haiku-5-5"
    assert first["attrs"]["argus.tier"] == "cheap" and first["attrs"]["argus.stage"] == "repro"
    assert (first["attrs"]["gen_ai.usage.input_tokens"], first["attrs"]["gen_ai.usage.output_tokens"]) == (236, 47)
    assert first["attrs"]["argus.usage.cost_usd"] > 0
    assert first["attrs"]["gen_ai.conversation.id"] == "my-session"
    assert "gen_ai.response.finish_reasons" not in first["attrs"]  # not stored, so not invented
    assert last["name"] == "chat claude-sonnet-5-5" and last["attrs"]["argus.stage"] == "fix"
    assert last["attrs"]["argus.stop_reason"] == "submit"
    assert chats[2]["attrs"]["argus.stop_reason"] == "retry-cap"
    assert chats[0]["attrs"]["argus.tool.error"] == "not-a-repro" and not chats[0]["error"]


def test_times_follow_step_order_inside_the_recorded_window(receiver):
    trace_replay.main([str(RUN)])
    verdict = json.loads((RUN / "verdict.json").read_text())
    (root,) = receiver.by_name("invoke_agent argus-run")
    assert root["start"] == int(verdict["started_at"] * 1e9) and root["end"] == int(verdict["finished_at"] * 1e9)
    steps = sorted((s for s in receiver.spans if s["name"].startswith("chat ")), key=lambda s: s["attrs"]["argus.step.index"] + 100 * (s["attrs"]["argus.stage"] == "fix"))
    for a, b in zip(steps, steps[1:]):
        assert a["start"] < a["end"] <= b["start"]
    assert all(root["start"] <= s["start"] <= s["end"] <= root["end"] for s in receiver.spans)


def test_no_message_text_on_any_span(receiver):
    trace_replay.main([str(RUN)])
    texts = [json.loads(line)["reply"] for line in (RUN / "answers.jsonl").read_text(encoding="utf-8").splitlines()]
    values = [str(v) for s in receiver.spans for v in s["attrs"].values()]
    assert not any(t[:30] in v for t in texts for v in values)
    assert not any(k.startswith(("gen_ai.input", "gen_ai.output", "gen_ai.tool.call")) for s in receiver.spans for k in s["attrs"])


def test_failed_tool_is_marked(receiver, tmp_path):
    meta = TrajectoryMeta(run_id="r1", task_id="t1", model="claude-sonnet-5-5", host="h", prompt_hash="x", git_commit="y")
    steps = [TrajectoryStep(index=0, tokens_in=10, tokens_out=2, tool_name="edit", tool_error="timeout", model="claude-sonnet-5-5"),
             TrajectoryStep(index=1, tokens_in=12, tokens_out=2, tool_name="submit", stop_reason=StopReason.submit)]
    (tmp_path / "fix").mkdir()
    (tmp_path / "fix" / "trajectory.jsonl").write_text(Trajectory(meta=meta, steps=steps).to_jsonl(), encoding="utf-8")
    trace_replay.main([str(tmp_path)])  # no verdict.json: the window ends now
    bad, ok = receiver.by_name("execute_tool edit")[0], receiver.by_name("execute_tool submit")[0]
    assert bad["error"] and bad["attrs"]["error.type"] == "timeout" and bad["attrs"]["argus.tool.error"] == "timeout"
    assert not ok["error"]
    assert receiver.by_name("invoke_agent argus-run")[0]["attrs"]["gen_ai.conversation.id"] == "argus-replay-r1"


def test_langfuse_backend_checks_the_api_writes_evidence_and_prints_no_key(receiver, monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("ARGUS_TRACE_BACKEND", "langfuse")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", PUBLIC)
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", SECRET)
    monkeypatch.setenv("LANGFUSE_BASE_URL", receiver.url)
    evidence = tmp_path / "evidence.md"
    assert trace_replay.main([str(RUN), "--evidence", str(evidence)]) == 0
    out = capsys.readouterr()
    assert "export=SUCCESS" in out.out and "16 of 16 observations found" in out.out
    root = receiver.by_name("invoke_agent argus-run")[0]
    assert root["attrs"]["langfuse.session.id"] == "argus-replay-B-seed-e01"  # the langfuse profile moved it
    assert not any(k.startswith("argus.usage") for s in receiver.spans for k in s["attrs"])
    (path, auth), = receiver.gets
    assert path.startswith("/api/public/v2/observations?") and "sessionId=argus-replay-B-seed-e01" in path
    assert auth.startswith("Basic ")
    text = evidence.read_text(encoding="utf-8")
    assert "| invoke_agent argus-run | SPAN |" in text and "Observations returned: 16" in text and "`argus-replay-B-seed-e01`" in text
    import base64
    for blob in (out.out, out.err, text):
        assert PUBLIC not in blob and SECRET not in blob and auth.split()[1] not in blob
        assert base64.b64encode(f"{PUBLIC}:{SECRET}".encode()).decode() not in blob


def test_missing_langfuse_keys_say_so_without_a_traceback(monkeypatch, capsys):
    for key in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ARGUS_TRACE_BACKEND", "langfuse")
    assert trace_replay.main([str(RUN)]) == 2
    err = capsys.readouterr().err
    assert "LANGFUSE_PUBLIC_KEY" in err and "trace config error" in err


def test_non_langfuse_backend_skips_the_api_check(receiver, capsys):
    assert trace_replay.main([str(RUN)]) == 0
    assert "api check: skipped" in capsys.readouterr().out and receiver.gets == []


def test_unreachable_backend_exits_one(monkeypatch, capsys):
    monkeypatch.setenv("ARGUS_TRACE_BACKEND", "otlp")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://127.0.0.1:9/v1/traces")  # discard port: refused
    assert trace_replay.main([str(RUN)]) == 1
    assert "export=FAILURE" in capsys.readouterr().out


def test_evidence_writer_with_a_fake_api_response(tmp_path):
    done = trace_replay.Replay("a" * 32, "argus-replay-x", "x", 3, 0.0, 1.0)
    rows = [{"name": "chat m", "type": "GENERATION", "startTime": "2026-11-02T10:00:02Z", "endTime": "2026-11-02T10:00:03Z", "traceId": "t1", "level": "DEFAULT", "parentObservationId": "r"},
            {"name": "invoke_agent a", "type": "AGENT", "startTime": "2026-11-02T10:00:01Z", "endTime": "2026-11-02T10:00:04Z", "traceId": "t1", "level": "DEFAULT"}]
    trace_replay.write_evidence(tmp_path / "e.md", done, rows)
    text = (tmp_path / "e.md").read_text(encoding="utf-8")
    assert "`t1`" in text and "AGENT 1, GENERATION 1" in text and "Spans sent: 3. Observations returned: 2" in text
    assert text.index("invoke_agent a") < text.index("chat m")  # sorted by start time
    assert "| yes |" in text


def test_verify_retries_until_rows_arrive_and_gives_up_without_writing(tmp_path):
    done = trace_replay.Replay("a" * 32, "s", "x", 2, 0.0, 1.0)
    calls = []
    answers = [[], [{"name": "a", "type": "AGENT"}], [{"name": "a", "type": "AGENT"}, {"name": "b", "type": "SPAN"}]]
    ok = trace_replay.verify(None, done, tmp_path / "e.md", fetch=lambda *_: (calls.append(1), answers[len(calls) - 1])[1], sleep=lambda _: None)
    assert ok and len(calls) == 3
    empty = tmp_path / "none.md"
    assert not trace_replay.verify(None, done, empty, fetch=lambda *_: [], sleep=lambda _: None, tries=2)
    assert not empty.exists()
