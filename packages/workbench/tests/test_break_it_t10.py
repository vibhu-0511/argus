"""P10-T10 break it: script and markup in ticket text, run id, reviewer note, report and PR body stay inert.

Three layers, none of which needs a browser:
1. SOURCE: no page script turns text into markup (no innerHTML and friends, no dynamic code, no handler properties,
   no setAttribute with a free name), and the report frame is `<iframe sandbox>` with no `allow-` token.
2. HEADERS: every response carries a CSP whose script source is 'self' only (no 'unsafe-inline', no 'unsafe-eval',
   no scheme or wildcard), and the report is served with the sandbox CSP (`default-src 'none'`, bare `sandbox`).
3. DATA: hostile strings come back from the JSON API byte for byte (escaping is the page's job, and the page uses
   textContent only), as `application/json` with nosniff; a run id with markup is refused by the id rule and
   nothing is created.

The expected values are written out here on purpose and are NOT imported from the code under test, so weakening the
code makes this module fail (see docs/notes/p10-break-it-t10.md for the three mutated builds).
No model is called.
"""

import importlib
import json
import re
from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.routing import APIRoute

from argus_workbench import fixtures, server, store
from argus_workbench.errors import WorkbenchError

TOKEN = "test-token-not-secret"
H = {"X-Workbench-Token": TOKEN}
STATIC = Path(server.__file__).parent / "static"
SCREENS = sorted((STATIC / "screens").glob("*.js"))
ALL_JS = sorted(STATIC.rglob("*.js"))
FIVE = {"issue", "run", "review", "pr", "history"}

HOSTILE = [
    "<script>window.__pwned=1</script>",
    "<img src=x onerror=window.__pwned=1>",
    "$(touch /tmp/pwned) `id` ${7*7}",
    '"><svg onload=window.__pwned=1>',
    "</script><script>window.__pwned=1</script>",
    "javascript:window.__pwned=1",
    "{{7*7}} <iframe srcdoc='<script>1</script>'>",
]
HOSTILE_IDS = [
    "<script>window.__pwned=1</script>",
    "<img src=x onerror=1>",
    "a/b",
    "..",
    "../runs",
    "UPPER",
    'x"onerror="1',
    "a" * 65,
    "con",
    "$(id)",
    "run-1;rm",
]


def media_type(r) -> str:
    return r.headers["content-type"].split(";")[0].strip().lower()


def csp_directives(csp: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for part in csp.split(";"):
        words = part.split()
        if words:
            out[words[0].lower()] = words[1:]
    return out


def assert_scripts_only_from_self(csp: str):
    d = csp_directives(csp)
    sources = d.get("script-src", d.get("default-src"))
    assert sources == ["'self'"], f"script sources must be exactly 'self', got {sources!r} in {csp!r}"
    assert "script-src-elem" not in d and "script-src-attr" not in d, "no per-element script source may loosen script-src"
    for name in ("default-src", "script-src", "style-src", "frame-src"):
        for src in d.get(name, []):
            assert src in ("'self'", "'none'"), f"{name} must not allow {src!r}"
    assert "unsafe" not in csp.lower(), f"no unsafe-* keyword in a page CSP: {csp!r}"


# ---- layer 1: source -----------------------------------------------------------------------------------------------

BANNED = re.compile(
    r"innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\s*\(|new\s+Function|\bFunction\s*\(|"
    r"setTimeout\s*\(\s*['\"`]|setInterval\s*\(\s*['\"`]|\.srcdoc\s*=|createContextualFragment|DOMParser|"
    r"javascript:|\.on[a-z]+\s*=[^=]|\.(href|src|action|formAction)\s*=[^=]|window\.open|location\s*=[^=]|location\.(href|assign|replace)"
)
SET_ATTRIBUTE = re.compile(r"\.setAttribute\(\s*(?!['\"](aria-[a-z]+|role)['\"])")


def test_the_five_screens_and_the_shell_exist():
    names = {p.stem for p in SCREENS}
    assert FIVE <= names, FIVE - names
    assert {p.name for p in STATIC.glob("*.js")} >= {"app.js", "api.js", "dom.js"}


@pytest.mark.parametrize("path", ALL_JS, ids=lambda p: p.relative_to(STATIC).as_posix())
def test_no_script_turns_text_into_markup_or_code(path):
    text = path.read_text("utf-8")
    hit = BANNED.search(text)
    assert not hit, f"{path.name}: {hit.group(0)!r}"
    if path.name != "dom.js":  # dom.js is the one guarded place that calls setAttribute, with a deny list
        bad = SET_ATTRIBUTE.search(text)
        assert not bad, f"{path.name}: setAttribute with a name that is not an aria-* literal"


def test_every_screen_builds_dom_through_the_text_only_helper():
    for path in SCREENS:
        text = path.read_text("utf-8")
        if path.stem in ("run", "pr", "history") and "not built yet" in text:
            continue  # placeholder screens of this checkout: static text only
        assert "from '../dom.js'" in text, f"{path.name} does not use el()/clear() from dom.js"


def test_dom_helper_keeps_its_deny_list():
    dom = (STATIC / "dom.js").read_text("utf-8")
    assert "BAD_ATTR = /^(on|style$|srcdoc$)/i" in dom
    assert "same-origin path" in dom and "textContent" in dom and "createTextNode" in dom


def test_run_id_rule_in_the_router_matches_the_store_rule():
    app_js = (STATIC / "app.js").read_text("utf-8")
    assert "const RUN_ID = /^[a-z0-9-]{1,64}$/;" in app_js
    assert store.RUN_ID.pattern == "[a-z0-9-]{1,64}"
    assert "arg && RUN_ID.test(arg) ? arg : null" in app_js  # a hash with markup becomes null, never reaches a screen


def test_the_report_frame_is_sandboxed_with_no_allow_tokens():
    text = (STATIC / "screens" / "review.js").read_text("utf-8")
    frames = re.findall(r"el\('iframe',\s*\{[^}]*\}", text)
    assert frames, "the review screen must show the report in an iframe"
    for frame in frames:
        assert re.search(r"sandbox:\s*''", frame), f"iframe without an empty sandbox attribute: {frame}"
        assert "allow-" not in frame
    for path in ALL_JS:
        assert "allow-scripts" not in path.read_text("utf-8") and "allow-same-origin" not in path.read_text("utf-8")


def test_index_html_has_one_external_script_and_no_inline_code():
    html = (STATIC / "index.html").read_text("utf-8")
    scripts = re.findall(r"<script\b[^>]*>(.*?)</script>", html, re.S | re.I)
    assert len(scripts) == 1 and scripts[0].strip() == ""
    assert re.search(r'<script type="module" src="/static/app\.js">', html)
    assert not re.search(r"\son[a-z]+\s*=", html, re.I), "no inline event handler"
    assert not re.search(r"\sstyle\s*=", html, re.I), "no inline style"
    assert "javascript:" not in html.lower()


# ---- layer 2: headers ----------------------------------------------------------------------------------------------


def test_every_response_has_a_csp_with_scripts_from_self_only(client, runs_root):
    fixtures.write_fixture_run("judge", root=runs_root)
    urls = [
        "/", "/static/index.html", "/static/app.js", "/static/screens/review.js", "/static/style.css", "/api/tabs",
        "/api/runs/fixture-judge/review", "/api/runs/fixture-judge/report", "/no-such-page", "/static/no-such-file",
        "/api/runs/%3Cscript%3E/review",
    ]
    for url in urls:
        r = client.get(url)
        csp = r.headers.get("content-security-policy")
        assert csp, f"{url}: no CSP"
        if url.endswith("/report"):
            continue  # the report has its own, stricter CSP, checked below
        assert_scripts_only_from_self(csp)
        assert r.headers["x-content-type-options"] == "nosniff", url


def test_a_refused_post_also_carries_the_csp(client):
    r = client.post("/api/issues")  # no token: refused
    assert r.status_code == 403
    assert_scripts_only_from_self(r.headers["content-security-policy"])


def test_every_html_response_is_checked_and_has_no_inline_script_allowed(client):
    html_urls = ["/", "/static/index.html"]
    for url in html_urls:
        r = client.get(url)
        assert media_type(r) == "text/html", url
        assert_scripts_only_from_self(r.headers["content-security-policy"])
        assert "object-src 'none'" in r.headers["content-security-policy"] and "base-uri 'none'" in r.headers["content-security-policy"]


def test_query_strings_and_paths_are_never_echoed_into_html(client):
    r = client.get("/?q=<script>window.__pwned=1</script>")
    assert media_type(r) == "text/html" and "window.__pwned" not in r.text
    r = client.get("/static/<script>window.__pwned=1</script>")
    assert media_type(r) == "application/json" and "window.__pwned" not in r.text


def write_report(runs_root, report: str) -> str:
    fixtures.write_fixture_run("judge", run_id="run-report", root=runs_root)
    store.write_file("run-report", "report.html", report)
    return "run-report"


def test_the_report_is_served_with_the_sandbox_csp_and_unchanged(client, runs_root):
    report = "<!doctype html><title>t</title>" + "".join(f"<p>{h}</p>" for h in HOSTILE) + "<script>window.__pwned=1</script>"
    run_id = write_report(runs_root, report)
    r = client.get(f"/api/runs/{run_id}/report")
    assert r.status_code == 200 and r.text == report  # the server does not rewrite it; the SANDBOX is what makes it inert
    d = csp_directives(r.headers["content-security-policy"])
    assert d.get("sandbox") == [], f"a bare `sandbox` directive is required (no allow-* token): {d}"
    assert d.get("default-src") == ["'none'"]
    assert "script-src" not in d, "no script source may be named for the report"
    assert "unsafe-eval" not in r.headers["content-security-policy"] and "allow-" not in r.headers["content-security-policy"]
    assert d.get("style-src", ["'unsafe-inline'"]) == ["'unsafe-inline'"]  # styles only; scripts have no source at all
    assert r.headers["x-content-type-options"] == "nosniff"
    assert "access-control-allow-origin" not in r.headers


def test_the_review_page_points_the_frame_at_a_same_origin_path(client, runs_root):
    run_id = write_report(runs_root, "<script>window.__pwned=1</script>")
    body = client.get(f"/api/runs/{run_id}/review").json()
    assert body["report_url"] == f"/api/runs/{run_id}/report"
    assert body["report_url"].startswith("/") and not body["report_url"].startswith("//")


# ---- layer 3: data -------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("hostile", HOSTILE)
def test_ticket_text_comes_back_unchanged_as_json(client, runs_root, hostile):
    r = client.post(
        "/api/issues", headers=H,
        files=[("text", (None, hostile)), ("repo", (None, "dcortex")), ("route", (None, "/ops/radar")), ("ack_public_or_synthetic", (None, "true"))],
    )
    assert r.status_code == 201 and media_type(r) == "application/json"
    assert r.headers["x-content-type-options"] == "nosniff"
    body = r.json()
    assert body["ticket"]["text"] == hostile.strip()
    assert store.read_file(body["run_id"], "ticket.json").text == hostile.strip()
    assert re.fullmatch(r"[a-z0-9-]{1,64}", body["run_id"]), "the server picks the id; the text never reaches a path"


@pytest.mark.parametrize("hostile", HOSTILE)
def test_reviewer_note_and_reason_come_back_unchanged(client, runs_root, hostile):
    fixtures.write_fixture_run("judge", run_id="run-approve", root=runs_root)
    fixtures.write_fixture_run("normal", run_id="run-changes", root=runs_root)
    approve = client.post("/api/runs/run-approve/decision", headers=H, json={"action": "approve", "reason": hostile, "idempotency_key": "k1"})
    assert approve.status_code == 200 and media_type(approve) == "application/json"
    assert approve.json()["decision"]["reason"] == hostile.strip()
    review = client.get("/api/runs/run-approve/review").json()
    assert review["decision"]["reason"] == hostile.strip()

    changes = client.post("/api/runs/run-changes/decision", headers=H, json={"action": "request-changes", "note": hostile, "idempotency_key": "k2"})
    assert changes.status_code == 200 and changes.json()["decision"]["reason"] == hostile.strip()
    new_id = changes.json()["new_run_id"]
    assert store.read_file(new_id, "intake.json").reviewer_note == hostile.strip()
    assert store.get_state(new_id).state.value == "received"  # a hostile note starts nothing by itself


def test_judge_and_check_text_from_the_verdict_come_back_unchanged(client, runs_root):
    fixtures.write_fixture_run("judge", run_id="run-verdict", root=runs_root)
    verdict = store.read_file("run-verdict", "verdict.json").model_dump(mode="json")
    verdict["judge_note"] = HOSTILE[0]
    verdict["checks"][0]["reason"] = HOSTILE[1]
    verdict["checks"][0]["route"] = HOSTILE[3]
    store.write_file("run-verdict", "verdict.json", verdict)
    body = client.get("/api/runs/run-verdict/review").json()
    assert body["judge"]["note"] == HOSTILE[0]
    assert body["checks"][0]["reason"] == HOSTILE[1] and body["checks"][0]["route"] == HOSTILE[3]


def test_patch_file_names_come_back_unchanged(client, runs_root):
    fixtures.write_fixture_run("normal", run_id="run-patch", root=runs_root)
    store.write_file("run-patch", "patch.diff", f"--- a/x\n+++ b/{HOSTILE[0]}.css\n@@ -1 +1 @@\n-a\n+{HOSTILE[1]}\n")
    body = client.get("/api/runs/run-patch/review").json()
    assert body["patch"]["files"] == [f"{HOSTILE[0]}.css"] and media_type(client.get("/api/runs/run-patch/review")) == "application/json"


@pytest.mark.parametrize("run_id", HOSTILE_IDS)
def test_a_run_id_with_markup_is_refused_by_the_id_rule_and_creates_nothing(client, runs_root, run_id):
    before = sorted(p.name for p in runs_root.parent.rglob("*"))
    path = quote(run_id, safe="")
    for method, url, kwargs in [
        ("get", f"/api/runs/{path}/review", {}),
        ("get", f"/api/runs/{path}/report", {}),
        ("post", f"/api/runs/{path}/decision", {"headers": H, "json": {"action": "reject", "reason": "x", "idempotency_key": "k"}}),
    ]:
        r = getattr(client, method)(url, **kwargs)
        assert r.status_code in (400, 404), (url, r.status_code)
        assert media_type(r) == "application/json", "an error echoing the id must never be HTML"
        assert r.json()["error"]["code"] in ("bad_run_id", "not_found"), r.text
        assert "<script" not in r.text.lower() and "onerror" not in r.text.lower()
    assert sorted(p.name for p in runs_root.parent.rglob("*")) == before, "a refused id must not create a folder or file"


@pytest.mark.parametrize("run_id", HOSTILE_IDS)
def test_the_store_itself_refuses_a_run_id_with_markup(runs_root, run_id):
    with pytest.raises(WorkbenchError) as e:
        store.check_run_id(run_id)
    assert e.value.code == "bad_run_id"
    with pytest.raises(WorkbenchError):
        store.create_run({"id": "T-1", "text": "x"}, run_id=run_id)
    assert not runs_root.exists() or list(runs_root.iterdir()) == []


# ---- PR body (T08 is built by another group) -----------------------------------------------------------------------


def _pr_module():
    try:
        return importlib.import_module("argus_workbench.routes.pr")
    except ModuleNotFoundError:
        return None


def test_pr_body_hostile_text_is_inert_on_the_pr_routes(client, runs_root):
    """Runs against the PR routes once T08 is merged. Without routes/pr.py it is skipped and the gap is in the write-up."""
    module = _pr_module()
    if module is None:
        pytest.skip("routes/pr.py (T08) is not in this branch; the PR body cannot be served yet")
    fixtures.write_fixture_run("normal", run_id="run-pr", root=runs_root)
    store.write_file("run-pr", "pr.json", {"number": 1, "url": "https://example.invalid/pr/1", "draft": True, "origin": "SIMULATED",
                                         "title": HOSTILE[0], "body": "\n".join(HOSTILE), "branch": "argus/run-pr"})
    gets = [r for r in module.router.routes if isinstance(r, APIRoute) and "GET" in r.methods and "{run_id}" in r.path]
    assert gets, "routes/pr.py has no GET route with {run_id}"
    needle = json.dumps(HOSTILE[0])[1:-1]  # as it appears inside a JSON string
    seen_body = False
    for route in gets:
        r = client.get(route.path.replace("{run_id}", "run-pr"))
        csp = r.headers["content-security-policy"]
        if media_type(r) == "text/html":
            assert "sandbox" in csp_directives(csp), "an HTML PR response must be sandboxed"
        else:
            assert_scripts_only_from_self(csp)
            seen_body = seen_body or (media_type(r) == "application/json" and r.status_code == 200 and needle in r.text)
    assert seen_body, "the PR body was not returned unchanged by any PR route"
