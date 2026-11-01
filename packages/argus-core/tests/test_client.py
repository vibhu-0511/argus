import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from argus_core.client import ModelClient
from argus_core.profile import ProfileError, client_from_profile, load_profiles

PROFILES = Path(__file__).resolve().parents[3] / "config" / "profiles.md"


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        self.server.requests.append(
            (self.path, self.headers.get("Authorization"), json.loads(raw))
        )
        body = json.dumps(
            {
                "choices": [{"message": {"role": "assistant", "content": "pong"}}],
                "usage": {
                    "prompt_tokens": 5,
                    "completion_tokens": 1,
                    "prompt_tokens_details": {"cached_tokens": 4},
                },
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return


def test_mock_server_completion():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    httpd.requests = []
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        port = httpd.server_address[1]
        client = ModelClient(f"http://127.0.0.1:{port}/v1", "secret")
        done = client.complete("mock-model", [{"role": "user", "content": "hi"}])
    finally:
        httpd.shutdown()
        thread.join(timeout=2)
        httpd.server_close()

    assert done.content == "pong"
    assert done.usage.tokens_in == 5
    assert done.usage.tokens_out == 1
    assert done.usage.tokens_cached == 4
    path, auth, payload = httpd.requests[0]
    assert path == "/v1/chat/completions"
    assert auth == "Bearer secret"
    assert payload["model"] == "mock-model"


def test_profile_hosts_share_one_client(monkeypatch):
    monkeypatch.setenv("ARGUS_MODEL_API_KEY", "from-env")
    active, profiles = load_profiles(PROFILES)
    personal = profiles[active]
    default = client_from_profile(personal)
    assert default.base_url == "https://api.groq.com/openai/v1"
    assert default.api_key == "from-env"

    clients = [
        client_from_profile(personal, host=name, api_key=name)
        for name in ("groq", "mistral", "ollama")
    ]
    assert {type(client) for client in clients} == {ModelClient}
    assert [client.base_url for client in clients] == [
        "https://api.groq.com/openai/v1",
        "https://api.mistral.ai/v1",
        "http://localhost:11434/v1",
    ]
    assert [client.api_key for client in clients] == ["groq", "mistral", "ollama"]


def test_non_openai_wire_format_is_rejected():
    _, profiles = load_profiles(PROFILES)
    with pytest.raises(ProfileError):
        client_from_profile(profiles["company"])
