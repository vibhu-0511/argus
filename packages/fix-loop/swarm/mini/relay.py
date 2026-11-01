"""OpenAI-compatible relay for variant E (P3-T17). No provider call: each chat request waits for a reply file written by a fresh Claude subagent.

    python relay.py [port]        one process serves every run; mini's OPENAI_BASE_URL is http://127.0.0.1:<port>/<run id>/v1

Per run, under runs/<run id>/mini/: req-N.json (the request), rep-N.json (the reply, written by mini_turn.py answer), ledger.json.
Every call goes through argus_core's Ledger (self-imposed 300-call budget, like turn.py; not a provider limit).
Token counts are chars/4 estimates. ponytail: one Ledger per run behind a lock; a relay crash loses the in-flight call, restart the run.
"""

import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from argus_core.ledger import Ledger, ModelQuota, Usage

RUNS = Path(__file__).resolve().parents[2] / "runs"
MODEL = "claude-session"
BUDGET = {MODEL: ModelQuota(300, 10**7, 300, 10**7, False)}
WAIT = 4 * 3600
_ledgers: dict[str, Ledger] = {}
_lock = threading.Lock()


def est(text: str) -> int:
    return max(1, len(text) // 4)


def reply_for(run: str, body: dict) -> dict:
    out = RUNS / run / "mini"
    with _lock:
        n = len(list(out.glob("req-*.json")))
        (out / f"req-{n}.json").write_text(json.dumps(body), encoding="utf-8")
        ledger = _ledgers.setdefault(run, Ledger(out / "ledger.json", BUDGET))
    rep = out / f"rep-{n}.json"

    def send() -> Usage:
        deadline = time.time() + WAIT
        while not rep.exists():
            if time.time() > deadline:
                raise TimeoutError(f"no reply for {run} request {n}")
            time.sleep(0.5)
        got = json.loads(rep.read_text(encoding="utf-8"))
        return Usage(est(json.dumps(body["messages"])), est(json.dumps(got)), 0)

    usage = ledger.call(MODEL, send, token_estimate=est(json.dumps(body["messages"])))
    got = json.loads(rep.read_text(encoding="utf-8"))
    call = {"id": f"call_{n}", "type": "function", "function": {"name": "bash", "arguments": json.dumps({"command": got["command"]})}}
    message = {"role": "assistant", "content": got.get("text") or "", "tool_calls": [call]}
    return {
        "id": f"chatcmpl-{run}-{n}", "object": "chat.completion", "created": int(time.time()), "model": MODEL,
        "choices": [{"index": 0, "message": message, "finish_reason": "tool_calls"}],
        "usage": {"prompt_tokens": usage.tokens_in, "completion_tokens": usage.tokens_out, "total_tokens": usage.tokens_in + usage.tokens_out},
    }


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        parts = self.path.strip("/").split("/")
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        try:
            if len(parts) != 4 or parts[1:] != ["v1", "chat", "completions"] or not (RUNS / parts[0] / "mini").is_dir():
                raise FileNotFoundError(self.path)
            payload, code = reply_for(parts[0], body), 200
        except FileNotFoundError as exc:
            payload, code = {"error": {"message": f"unknown route or run: {exc}", "type": "not_found"}}, 404
        except Exception as exc:  # the caller sees a 500 with the reason; mini records it as an exit status
            payload, code = {"error": {"message": f"{type(exc).__name__}: {exc}", "type": "server_error"}}, 500
        data = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args: object) -> None:
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
