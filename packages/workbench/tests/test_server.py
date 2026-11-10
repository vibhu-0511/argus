"""P10-T02: the page shell, the tabs and their labels, static files, route discovery, typed errors."""

import json
import re
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from argus_workbench import server
from argus_workbench.spec import P10_STATUS, load_spec, tabs

TOKEN = "test-token-not-secret"  # same value as conftest.TOKEN

REPO = Path(__file__).resolve().parents[3]
STATIC = Path(server.__file__).parent / "static"


def test_packaged_spec_equals_the_repo_spec():
    repo_spec = json.loads((REPO / "docs" / "notes" / "p10-spec.json").read_text("utf-8"))
    assert load_spec() == repo_spec


def test_five_tabs_with_the_spec_labels_and_the_p10_status_line(client):
    body = client.get("/api/tabs").json()["tabs"]
    spec = {s["id"]: s for s in load_spec()["screens"]}
    assert [t["id"] for t in body] == ["issue", "run", "review", "pr", "history"]
    assert [t["short"] for t in body] == ["Issue", "Run", "Review", "PR", "History"]
    for t in body:
        assert t["label"] == spec[t["id"]]["built"]["label"] and t["level"] == spec[t["id"]]["built"]["level"]
        assert t["status"] == P10_STATUS == "local, scripted"
    assert {t["label"] for t in body} <= {"BUILT", "PARTLY BUILT", "PLANNED P8", "PLANNED"}
    assert [t["label"] for t in body] == ["PARTLY BUILT", "PARTLY BUILT", "PARTLY BUILT", "PLANNED P8", "PARTLY BUILT"]
    assert body == tabs()


def test_index_carries_the_token_in_a_meta_tag_and_nothing_inline(client):
    r = client.get("/")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    assert f'<meta name="argus-token" content="{TOKEN}">' in r.text
    assert "{{ARGUS_TOKEN}}" not in r.text
    assert re.findall(r"<script\b[^>]*>", r.text) == ['<script type="module" src="/static/app.js">']
    assert not re.search(r"\son[a-z]+\s*=", r.text, re.I) and not re.search(r"\sstyle\s*=", r.text, re.I)
    assert "<style" not in r.text.lower() and "javascript:" not in r.text.lower()
    assert 'id="tabs"' in r.text and 'id="screen"' in r.text


def test_token_is_escaped_in_the_meta_tag():
    app = server.create_app(token='a"b<c>')
    r = TestClient(app, base_url="http://127.0.0.1").get("/")
    assert 'content="a&quot;b&lt;c&gt;"' in r.text and 'a"b<c>' not in r.text


def test_token_is_random_per_start():
    a, b = server.create_app(), server.create_app()
    assert a.state.token != b.state.token and len(a.state.token) >= 32


def test_static_files_are_served_with_javascript_type(client):
    r = client.get("/static/app.js")
    assert r.status_code == 200 and "javascript" in r.headers["content-type"]
    for name in ["style.css", "dom.js", "api.js", "index.html"]:
        assert client.get(f"/static/{name}").status_code == 200
    for tab in tabs():
        assert client.get(f"/static/screens/{tab['id']}.js").status_code == 200


def test_every_tab_has_a_screen_module_that_exports_render():
    for tab in tabs():
        assert "export async function render(root, ctx)" in (STATIC / "screens" / f"{tab['id']}.js").read_text("utf-8")


def test_static_path_traversal_is_refused(client):
    secret_marker = "def create_app"
    for path in [
        "/static/../server.py", "/static/%2e%2e/server.py", "/static/%2E%2E/server.py", "/static/..%2fserver.py",
        "/static/..%5cserver.py", "/static/screens/../../server.py", "/static/screens/%2e%2e/%2e%2e/server.py",
        "/static/%2e%2e%2f%2e%2e%2fstore.py", "/static//etc/passwd", "/static/C:/Windows/win.ini",
        "/static/..\\server.py", "/static/%00", "/static/app.js%00.png", "/static/screens", "/static/",
    ]:
        r = client.get(path)
        assert r.status_code in (400, 404), path
        assert secret_marker not in r.text, path
        assert r.headers["content-type"].startswith("application/json") or r.status_code == 400


def test_unknown_route_and_wrong_method_are_typed(client):
    r = client.get("/api/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    assert set(r.json()["error"]) == {"code", "field", "message"}
    r = client.post("/api/tabs", headers={"X-Workbench-Token": TOKEN})
    assert r.status_code == 405 and r.json()["error"]["code"] == "method_not_allowed"


def test_validation_errors_use_the_typed_shape(app):
    from pydantic import BaseModel

    class Body(BaseModel):
        text: str

    @app.post("/__typed")
    def typed(body: Body):
        return {}

    c = TestClient(app, base_url="http://127.0.0.1")
    r = c.post("/__typed", json={}, headers={"X-Workbench-Token": TOKEN})
    assert r.status_code == 422
    assert r.json()["error"] == {"code": "invalid_request", "field": "text", "message": "Field required"}


def test_workbench_error_in_a_route_is_typed(app):
    from argus_workbench.errors import WorkbenchError

    @app.get("/__boom")
    def boom():
        raise WorkbenchError("bad_thing", "it broke", field="x", status=409)

    r = TestClient(app, base_url="http://127.0.0.1").get("/__boom")
    assert r.status_code == 409 and r.json() == {"error": {"code": "bad_thing", "field": "x", "message": "it broke"}}


def test_docs_pages_are_not_served(client):
    for path in ["/docs", "/redoc", "/openapi.json"]:
        assert client.get(path).status_code == 404


def test_routes_are_found_by_pkgutil(tmp_path, monkeypatch):
    pkg = tmp_path / "fake_routes"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "b_second.py").write_text(
        "from fastapi import APIRouter\nrouter = APIRouter()\n@router.get('/api/b')\ndef b():\n    return {'b': 1}\n", encoding="utf-8")
    (pkg / "a_first.py").write_text(
        "from fastapi import APIRouter\nrouter = APIRouter()\n@router.get('/api/a')\ndef a():\n    return {'a': 1}\n", encoding="utf-8")
    (pkg / "helper.py").write_text("VALUE = 1\n", encoding="utf-8")  # no router: ignored
    monkeypatch.syspath_prepend(str(tmp_path))
    import importlib
    importlib.invalidate_caches()
    fake = importlib.import_module("fake_routes")
    app = FastAPI()
    assert server.include_route_modules(app, fake) == ["a_first", "b_second"]
    c = TestClient(app)
    assert c.get("/api/a").json() == {"a": 1} and c.get("/api/b").json() == {"b": 1}
    for name in [m for m in sys.modules if m.startswith("fake_routes")]:
        del sys.modules[name]


def test_the_real_routes_package_is_included():
    from argus_workbench import routes

    assert "shell" in server.include_route_modules(FastAPI(), routes)
