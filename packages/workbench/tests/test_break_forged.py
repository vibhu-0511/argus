"""P10-T12 break it: forged requests. The real app (every router found by pkgutil), TestClient only, no model.

A page on another site, or a DNS-rebinding page, tries to drive the workbench. Each forgery must be refused with the
typed error and must change NOTHING: the whole run store (every byte of every file) and the mock GitHub's request log
are compared before and after. Routes are tried both from an explicit list (issue create, start, decision, retry, PR:
a guard refuses before routing, so the list is valid even for a route another group has not merged yet) and from every
unsafe-method route the app really has, so a route added later is covered without an edit here.

Mutation proof: docs/notes/p10-break-it-t12.md (token check removed, Host check removed, Origin check removed, CORS added).
"""

import importlib
import pkgutil
import re

import pytest
from fastapi.testclient import TestClient

from argus_workbench import fixtures
from argus_workbench import routes as routes_pkg
from argus_workbench.mock_github import mock_for
from argus_workbench.security import UNSAFE_METHODS
from argus_workbench.server import create_app

TOKEN = "test-token-not-secret"
GOOD = {"X-Workbench-Token": TOKEN}
EVIL_ORIGIN = "https://evil.example"
RUN = "fixture-normal"

# (method path, body) the page would send. Bodies are valid, so a request that got past the guards WOULD change the store.
EXPLICIT = {
    "issue create": ("/api/runs", {"text": "The header is cut off", "repo": "dcortex", "route": "/ops/radar"}),
    "start": (f"/api/runs/{RUN}/start", {}),
    "decision approve": (f"/api/runs/{RUN}/decision", {"action": "approve", "idempotency_key": "forged-1"}),
    "decision reject": (f"/api/runs/{RUN}/decision", {"action": "reject", "reason": "Not a bug", "idempotency_key": "forged-2"}),
    "retry (request changes)": (f"/api/runs/{RUN}/decision", {"action": "request-changes", "note": "try again", "idempotency_key": "forged-3"}),
    "raise PR": (f"/api/runs/{RUN}/pr", {}),
}
FORGERIES = {  # name -> (headers, the error code the guard must give)
    "no token": ({}, "token_required"),
    "empty token": ({"X-Workbench-Token": ""}, "token_required"),
    "wrong token": ({"X-Workbench-Token": "wrong-fake-token"}, "token_required"),
    "wrong origin": ({**GOOD, "Origin": EVIL_ORIGIN}, "origin_not_allowed"),
    "wrong origin, no token": ({"Origin": EVIL_ORIGIN}, "origin_not_allowed"),
    "null origin": ({**GOOD, "Origin": "null"}, "origin_not_allowed"),
    "dns rebinding host": ({**GOOD, "Host": "evil.example"}, "host_not_allowed"),
    "dns rebinding host with port": ({**GOOD, "Host": "evil.example:8765", "Origin": "http://evil.example:8765"}, "host_not_allowed"),
    "dns rebinding host, no token": ({"Host": "evil.example"}, "host_not_allowed"),
}


def _real_unsafe_routes() -> dict[str, tuple[str, dict]]:
    """Every (method, path) of the real app with an unsafe method, path parameters filled with the fixture run."""
    found = {}
    create_app(token=TOKEN)  # a route module that does not import stops here, as it would at start
    for info in pkgutil.iter_modules(routes_pkg.__path__):  # the same discovery create_app uses (this FastAPI wraps included routers)
        router = getattr(importlib.import_module(f"{routes_pkg.__name__}.{info.name}"), "router", None)
        for route in getattr(router, "routes", ()):
            for method in getattr(route, "methods", None) or ():
                if method in UNSAFE_METHODS:
                    found[f"{method} {route.path}"] = (method, re.sub(r"\{[^}]+\}", RUN, route.path))
    return found


REAL = _real_unsafe_routes()
CASES = {f"POST {name}": ("POST", path, body) for name, (path, body) in EXPLICIT.items()}
CASES.update({name: (method, path, {}) for name, (method, path) in REAL.items() if not any(path == p for p, _ in EXPLICIT.values())})


@pytest.fixture(autouse=True)
def folders(runs_root):
    fixtures.write_all_fixtures(root=runs_root)


def store_bytes(root) -> dict[str, bytes]:
    """Every file of the run store, by relative path: the 'before' and 'after' of a forged request."""
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def world(root) -> tuple[dict[str, bytes], int]:
    return store_bytes(root), len(mock_for(root).requests)


def typed(r) -> dict:
    assert set(r.json()) == {"error"} and set(r.json()["error"]) == {"code", "field", "message"}, r.text
    return r.json()["error"]


def has_cors(r) -> list[str]:
    return [k for k in r.headers if k.lower().startswith("access-control-")]


def test_the_case_list_covers_the_routes_this_branch_really_has():
    # the decision (approve, reject, retry) and PR routes exist here; the guard test does not depend on the others existing
    assert {"POST /api/runs/{run_id}/decision", "POST /api/runs/{run_id}/pr"} <= set(REAL)
    assert len(CASES) >= 6


@pytest.mark.parametrize("forgery", FORGERIES)
@pytest.mark.parametrize("case", CASES)
def test_a_forged_request_is_refused_with_a_typed_error_and_changes_nothing(client, runs_root, case, forgery):
    method, path, body = CASES[case]
    headers, code = FORGERIES[forgery]
    before = world(runs_root)
    r = client.request(method, path, json=body, headers=headers)
    assert r.status_code == 403, (case, forgery, r.text)
    assert typed(r)["code"] == code
    assert world(runs_root) == before  # not one byte of the store, not one call to the mock GitHub
    assert TOKEN not in r.text


@pytest.mark.parametrize("case", ["POST decision approve", "POST decision reject", "POST retry (request changes)", "POST raise PR"])
def test_control_the_same_request_with_the_token_and_a_good_host_does_change_things(client, runs_root, case):
    """Without this the refusal tests could pass because the request was harmless anyway."""
    method, path, body = CASES[case]
    before = world(runs_root)
    r = client.request(method, path, json=body, headers={**GOOD, "Origin": "http://127.0.0.1"})
    if case == "POST raise PR":
        assert r.status_code == 409 and typed(r)["code"] == "not_approved"  # fine: it is a real route that reached its own rules
        return
    assert r.status_code == 200, r.text
    assert world(runs_root) != before


def test_a_forged_retry_creates_no_run_folder(client, runs_root):
    folders_before = sorted(p.name for p in runs_root.iterdir())
    path, body = EXPLICIT["retry (request changes)"]
    for headers, _ in FORGERIES.values():
        assert client.post(path, json=body, headers=headers).status_code == 403
    assert sorted(p.name for p in runs_root.iterdir()) == folders_before
    genuine = client.post(path, json=body, headers=GOOD)
    assert genuine.status_code == 200 and genuine.json()["new_run_id"]  # the real thing makes exactly one new folder
    assert len(list(runs_root.iterdir())) == len(folders_before) + 1


@pytest.mark.parametrize("path", ["/", "/api/tabs", f"/api/runs/{RUN}/review", f"/api/runs/{RUN}/pr", f"/api/runs/{RUN}/trajectory.jsonl",
                                  f"/api/runs/{RUN}/report", "/static/app.js", "/api/nope"])
@pytest.mark.parametrize("host", ["evil.example", "evil.example:8765", "127.0.0.1.evil.example", "localhost.evil.example"])
def test_a_get_with_the_wrong_host_is_refused_and_leaks_nothing(client, path, host):
    r = client.get(path, headers={"Host": host})
    assert r.status_code == 403 and typed(r)["code"] == "host_not_allowed"
    assert "argus-token" not in r.text and TOKEN not in r.text


def test_a_get_with_a_good_host_still_works(client):
    assert client.get(f"/api/runs/{RUN}/review").status_code == 200
    assert client.get("/", headers={"Host": "localhost:8765"}).status_code == 200


def test_no_cors_header_comes_back_for_a_request_from_another_origin(client):
    evil = {"Origin": EVIL_ORIGIN}
    path, body = EXPLICIT["decision approve"]
    answers = [
        client.get("/api/tabs", headers=evil),
        client.get(f"/api/runs/{RUN}/review", headers=evil),
        client.get("/", headers=evil),
        client.get("/static/app.js", headers=evil),
        client.post(path, json=body, headers=evil),                 # refused: no token
        client.post(path, json=body, headers={**GOOD, **evil}),     # refused: wrong origin, even with the token
        client.post(path, json=body, headers={**evil, "Host": "evil.example"}),
        client.get("/api/tabs", headers={**evil, "Host": "evil.example"}),
    ]
    for r in answers:
        assert has_cors(r) == [], (r.request.method, r.request.url, r.headers)
    # the reflected Origin must not be echoed either
    assert all(EVIL_ORIGIN not in "".join(r.headers.values()) for r in answers)


@pytest.mark.parametrize("path", ["/api/tabs", f"/api/runs/{RUN}/review", f"/api/runs/{RUN}/decision", f"/api/runs/{RUN}/pr", "/api/runs", "/"])
def test_a_preflight_from_another_origin_gets_no_permissive_answer(client, runs_root, path):
    before = world(runs_root)
    r = client.options(path, headers={
        "Origin": EVIL_ORIGIN, "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "x-workbench-token,content-type",
    })
    assert has_cors(r) == []
    assert r.status_code in (403, 404, 405), r.status_code  # never a 200/204 that a browser would read as "allowed"
    assert typed(r)["code"] in ("method_not_allowed", "not_found", "origin_not_allowed", "host_not_allowed")
    assert world(runs_root) == before


def test_a_preflight_with_a_rebinding_host_is_refused_by_the_host_guard(client):
    r = client.options("/api/tabs", headers={"Origin": "http://evil.example", "Host": "evil.example", "Access-Control-Request-Method": "GET"})
    assert r.status_code == 403 and typed(r)["code"] == "host_not_allowed" and has_cors(r) == []


def test_the_app_has_no_cors_middleware():
    names = [m.cls.__name__ for m in create_app(token=TOKEN).user_middleware]
    assert not [n for n in names if "cors" in n.lower()], names


def test_the_real_page_client_would_still_work(client):
    """The same-origin page sends the token and no foreign Origin: the refusals above are not a broken guard."""
    r = client.post(EXPLICIT["decision reject"][0], json=EXPLICIT["decision reject"][1], headers={**GOOD, "Origin": "http://127.0.0.1:8765"})
    assert r.status_code == 200 and r.json()["decision"]["decision"] == "reject"


def test_a_second_app_with_another_token_refuses_the_first_ones_token():
    other = TestClient(create_app(token="another-fake-token"), base_url="http://127.0.0.1")
    path, body = EXPLICIT["decision approve"]
    r = other.post(path, json=body, headers=GOOD)
    assert r.status_code == 403 and typed(r)["code"] == "token_required"
