"""P10-T02: token, Host, Origin, CSP and the other headers. TestClient only; nothing listens on a port.

A refused request must never reach the route, so each case checks the probe route's call list too.
"""

import logging

import pytest
from fastapi import Response
from fastapi.testclient import TestClient

from argus_workbench import security
from argus_workbench.server import create_app

TOKEN = "test-token-not-secret"
H = {"X-Workbench-Token": TOKEN}
UNSAFE = ["post", "put", "patch", "delete"]


def err(r):
    assert set(r.json()) == {"error"} and set(r.json()["error"]) == {"code", "field", "message"}
    return r.json()["error"]


@pytest.mark.parametrize("method", UNSAFE)
def test_unsafe_method_without_token_is_refused_and_does_nothing(app, client, method):
    r = getattr(client, method)("/__probe")
    assert r.status_code == 403 and err(r)["code"] == "token_required" and err(r)["field"] == "token"
    assert app.state.calls == []


@pytest.mark.parametrize("method", UNSAFE)
def test_unsafe_method_with_right_token_runs(app, client, method):
    r = getattr(client, method)("/__probe", headers=H)
    assert r.status_code == 200 and app.state.calls == [method.upper()]


@pytest.mark.parametrize("bad", ["", "wrong", TOKEN + "x", TOKEN[:-1], TOKEN.upper(), " " + TOKEN, "Bearer " + TOKEN])
def test_wrong_token_is_refused(app, client, bad):
    r = client.post("/__probe", headers={"X-Workbench-Token": bad})
    assert r.status_code == 403 and err(r)["code"] == "token_required"
    assert app.state.calls == []


def test_token_in_a_url_or_body_or_cookie_does_not_count(app, client):
    assert client.post(f"/__probe?token={TOKEN}").status_code == 403
    assert client.post(f"/__probe?x-workbench-token={TOKEN}").status_code == 403
    assert client.post("/__probe", json={"token": TOKEN}).status_code == 403
    assert client.post("/__probe", headers={"Authorization": f"Bearer {TOKEN}"}).status_code == 403
    client.cookies.set("x-workbench-token", TOKEN)
    assert client.post("/__probe").status_code == 403
    assert app.state.calls == []


def test_get_needs_no_token(client):
    assert client.get("/api/tabs").status_code == 200


def test_token_on_a_route_that_does_not_exist_is_still_a_typed_404(client):
    r = client.post("/api/nope", headers=H)
    assert r.status_code == 404 and err(r)["code"] == "not_found"


@pytest.mark.parametrize(
    "host",
    ["evil.example", "evil.example:8765", "127.0.0.1.evil.example", "localhost.evil.example", "127.0.0.1:abc", "127.0.0.1:",
     "127.0.0.1:123456", "0.0.0.0", "0.0.0.0:8765", "[::1]", "[::1]:8765", "127.0.0.2", "localhost@evil.example",
     "evil.example#127.0.0.1", "127.0.0.1 evil.example", "localhost.", "169.254.169.254", ""],
)
def test_foreign_host_is_refused_for_every_method(app, client, host):
    for method in ["get", *UNSAFE]:
        r = getattr(client, method)("/api/tabs" if method == "get" else "/__probe", headers={**H, "Host": host})
        assert r.status_code == 403, (method, host)
        assert err(r)["code"] == "host_not_allowed" and err(r)["field"] == "host"
    assert app.state.calls == []


@pytest.mark.parametrize("host", ["127.0.0.1", "127.0.0.1:8765", "localhost", "localhost:3000", "LOCALHOST:80", "127.0.0.1:1"])
def test_loopback_hosts_are_allowed(app, client, host):
    assert client.get("/api/tabs", headers={"Host": host}).status_code == 200
    assert client.post("/__probe", headers={**H, "Host": host}).status_code == 200


def test_dns_rebinding_shape_is_refused_on_index_and_static_too(client):
    for path in ["/", "/static/app.js", "/api/tabs", "/api/nope"]:
        r = client.get(path, headers={"Host": "evil.example"})
        assert r.status_code == 403 and err(r)["code"] == "host_not_allowed"
        assert "argus-token" not in r.text


@pytest.mark.parametrize(
    "origin", ["http://evil.example", "https://evil.example", "null", "https://127.0.0.1", "https://localhost:8765",
               "http://127.0.0.1.evil.example", "http://localhost.evil.example", "http://127.0.0.1@evil.example",
               "http://evil.example/http://127.0.0.1", "file://", "http://127.0.0.1:8765/path", ""],
)
def test_foreign_origin_is_refused_even_with_the_token(app, client, origin):
    r = client.post("/__probe", headers={**H, "Origin": origin})
    assert r.status_code == 403 and err(r)["code"] == "origin_not_allowed" and err(r)["field"] == "origin"
    assert app.state.calls == []


@pytest.mark.parametrize("origin", ["http://127.0.0.1", "http://127.0.0.1:8765", "http://localhost", "http://localhost:3000"])
def test_same_machine_origin_with_token_is_allowed(app, client, origin):
    assert client.post("/__probe", headers={**H, "Origin": origin}).status_code == 200


def test_origin_is_checked_before_the_token_is_considered(app, client):
    r = client.post("/__probe", headers={"Origin": "http://evil.example"})
    assert err(r)["code"] == "origin_not_allowed"


def test_no_cors_header_for_another_origin(client):
    evil = {"Origin": "http://evil.example"}
    for r in [
        client.get("/api/tabs", headers=evil),
        client.get("/", headers=evil),
        client.get("/static/app.js", headers=evil),
        client.post("/__probe", headers={**H, **evil}),
        client.options("/api/tabs", headers={**evil, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "x-workbench-token"}),
        client.options("/__probe", headers={**evil, "Access-Control-Request-Method": "POST"}),
    ]:
        assert not [k for k in r.headers if k.lower().startswith("access-control-")], r.request.url
    assert client.options("/__probe", headers={**evil, "Access-Control-Request-Method": "POST"}).status_code in (403, 405)


def test_security_headers_on_every_kind_of_response(client):
    responses = [
        client.get("/"), client.get("/api/tabs"), client.get("/static/app.js"), client.get("/static/nope.js"),
        client.get("/api/nope"), client.post("/__probe"), client.get("/", headers={"Host": "evil.example"}),
        client.post("/api/tabs", headers=H),
    ]
    for r in responses:
        assert r.headers["content-security-policy"] == security.CSP, r.request.url
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["x-frame-options"] == "SAMEORIGIN"
        assert r.headers["referrer-policy"] == "no-referrer"
        assert r.headers["cache-control"] == "no-store"


def test_csp_is_default_src_self_with_no_inline_or_eval_and_frame_rules():
    csp = security.CSP
    assert csp.startswith("default-src 'self';")
    assert "unsafe-inline" not in csp and "unsafe-eval" not in csp and "*" not in csp and "http:" not in csp
    assert "script-src 'self'" in csp and "object-src 'none'" in csp and "base-uri 'none'" in csp
    assert "frame-ancestors 'self'" in csp and "frame-src 'self'" in csp


def test_report_csp_is_inert_and_sandboxed():
    csp = security.REPORT_CSP
    assert "default-src 'none'" in csp and "sandbox" in csp and "frame-ancestors 'self'" in csp
    assert "script-src" not in csp and "unsafe-eval" not in csp and "connect-src" not in csp


def test_a_route_may_set_a_stricter_csp_and_still_gets_the_other_headers(app):
    @app.get("/__report")
    def report():
        return Response("<p>x</p>", media_type="text/html", headers={"Content-Security-Policy": security.REPORT_CSP})

    r = TestClient(app, base_url="http://127.0.0.1").get("/__report")
    assert r.headers["content-security-policy"] == security.REPORT_CSP
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "SAMEORIGIN"


def test_token_is_never_logged_in_full(app, client, caplog):
    caplog.set_level(logging.DEBUG)
    client.get("/")
    client.post("/__probe", headers=H)
    client.post("/__probe", headers={"X-Workbench-Token": "wrong"})  # (a URL with the token in it would be logged by the test client itself)
    assert TOKEN not in caplog.text
    assert security.mask(TOKEN) == "test..." and TOKEN not in security.mask(TOKEN)


def test_error_bodies_never_contain_the_token(client):
    for r in [client.post("/__probe", headers={"X-Workbench-Token": "wrong"}), client.post("/__probe")]:
        assert TOKEN not in r.text


def test_token_header_name_is_the_documented_one(client):
    assert security.TOKEN_HEADER == "x-workbench-token"
    assert client.post("/__probe", headers={"x-workbench-token": TOKEN}).status_code == 200


def test_new_token_is_random_and_long():
    assert len({security.new_token() for _ in range(50)}) == 50 and len(security.new_token()) >= 32


def test_a_fresh_app_has_its_own_token_and_rejects_the_old_one():
    other = TestClient(create_app(token="another-fake-token"), base_url="http://127.0.0.1")
    other.app.post("/__p")(lambda: {"ok": True})
    assert other.post("/__p", headers=H).status_code == 403
    assert other.post("/__p", headers={"X-Workbench-Token": "another-fake-token"}).status_code == 200
