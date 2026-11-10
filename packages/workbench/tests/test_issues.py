"""P10-T03: the New issue screen's API. Text, screenshot, repo, route and acknowledgement are checked before anything is
written; every refusal is typed with its field and leaves the run store empty; the stored folder passes `bench validate`.
No model is called."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from argus_core.types import Ticket
from fastapi.testclient import TestClient

from argus_workbench import store
from argus_workbench.routes import issues
from argus_workbench.spec import load_spec

TOKEN = "test-token-not-secret"  # same value as conftest.TOKEN
PNG = b"\x89PNG\r\n\x1a\n"
JPG = b"\xff\xd8\xff\xe0"
OK_FIELDS = {"text": "The radar card text is 10 px.", "repo": "dcortex", "route": "/ops/radar", "ack_public_or_synthetic": "true"}


def post(client, fields=None, files=None, drop=(), headers=None, content=None):
    data = {k: v for k, v in {**OK_FIELDS, **(fields or {})}.items() if k not in drop}
    h = {"X-Workbench-Token": TOKEN, **(headers or {})}
    if content is not None:
        return client.post("/api/issues", content=content, headers=h)
    parts = [(k, (None, v)) for k, v in data.items()]  # (None, text) makes httpx send a text part, so the body is always multipart
    parts += list(files.items()) if isinstance(files, dict) else list(files or [])
    return client.post("/api/issues", files=parts, headers=h)


def shot(body=PNG + b"\x00" * 64, name="shot.png", ctype="image/png"):
    return {"screenshot": (name, body, ctype)}


def assert_nothing_stored(root: Path):
    assert not root.exists() or list(root.iterdir()) == []


def assert_error(r, code, field, status=None):
    assert r.status_code == (status or r.status_code) and r.status_code >= 400, r.text
    assert r.json() == {"error": {"code": code, "field": field, "message": r.json()["error"]["message"]}}
    assert r.json()["error"]["message"]


# ---- options ------------------------------------------------------------------------------------------------------


def test_options_come_from_the_spec_targets(client):
    r = client.get("/api/issues/options")
    assert r.status_code == 200
    o, t = r.json(), load_spec()["targets"]
    assert [x["id"] for x in o["repos"]] == [x["id"] for x in t["repos"]]
    assert o["routes"] == t["routes"]
    assert o["max_file_bytes"] == 5 * 1024 * 1024 and o["max_text_chars"] == issues.MAX_TEXT_CHARS
    assert o["media_types"] == ["image/png", "image/jpeg"]
    assert [x["id"] for x in o["triggers"]] == ["typed", "github"]
    assert "reconcile" in next(x for x in o["triggers"] if x["id"] == "github")["blurb"]
    assert o["default_scenario"] == "normal" and o["seeded"] == {"id": "bug-17", "available": True}


# ---- the happy path and what is stored ----------------------------------------------------------------------------


def test_text_only_issue_creates_a_received_run(client, runs_root):
    r = post(client, {"text": "  padded text \n"})
    assert r.status_code == 201
    body = r.json()
    run_id = body["run_id"]
    assert body["ticket"] == {"id": run_id, "text": "padded text"}
    folder = runs_root / run_id
    assert sorted(p.name for p in folder.iterdir()) == ["intake.json", "state.json", "ticket.json"]
    state = store.get_state(run_id)
    assert (state.state.value, state.origin, state.scenario, state.created_by_retry_of) == ("received", "SIMULATED", "normal", None)
    assert Ticket.model_validate_json((folder / "ticket.json").read_text("utf-8")).text == "padded text"
    intake = store.read_file(run_id, "intake.json")
    assert (intake.repo, intake.route, intake.ack_public_or_synthetic) == ("dcortex", "/ops/radar", True)


@pytest.mark.parametrize("body,ext,media", [(PNG, "png", "image/png"), (JPG, "jpg", "image/jpeg")])
def test_screenshot_is_stored_under_a_server_chosen_name(client, runs_root, body, ext, media):
    r = post(client, files=shot(body + b"\x01" * 32, name="../../evil name.exe", ctype="text/plain"))
    assert r.status_code == 201
    run_id = r.json()["run_id"]
    ticket = store.read_file(run_id, "ticket.json")
    assert ticket.screenshot.media_type == media and ticket.screenshot.path == f"shots/screenshot.{ext}"
    folder = runs_root / run_id
    assert (folder / "shots" / f"screenshot.{ext}").read_bytes() == body + b"\x01" * 32
    assert sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()) == sorted(
        ["intake.json", "state.json", "ticket.json", f"shots/screenshot.{ext}"])
    assert "evil" not in json.dumps(r.json()) and not any("evil" in p.name for p in folder.rglob("*"))


def test_scenario_is_stored_when_chosen(client):
    r = post(client, {"scenario": "quota"})
    assert r.status_code == 201 and store.get_state(r.json()["run_id"]).scenario == "quota"


def test_text_is_stored_as_plain_text_not_interpreted(client):
    hostile = '<script>alert(1)</script> $(rm -rf /) <img src=x onerror=alert(1)>'
    r = post(client, {"text": hostile})
    assert r.status_code == 201 and store.read_file(r.json()["run_id"], "ticket.json").text == hostile


# ---- bench validate -----------------------------------------------------------------------------------------------


def _as_task_dir(run_folder: Path, target: Path) -> Path:
    """The stored ticket directory plus the four files only a bench task has (taken from the seeded BUG-17 task)."""
    seeded = issues.seeded_dir()
    shutil.copytree(run_folder / "shots", target / "shots")
    shutil.copy(run_folder / "ticket.json", target / "ticket.json")
    for name in ("checks.json", "meta.json", "bug.patch", "golden.patch"):
        shutil.copy(seeded / name, target / name)
    return target


def test_stored_ticket_directory_passes_bench_validate(client, runs_root, tmp_path):
    from argus_bench.cli import main as bench

    run_id = post(client, files=shot()).json()["run_id"]
    task = _as_task_dir(runs_root / run_id, tmp_path / "task")
    assert bench(["validate", str(task)]) == 0
    # the real command line, not only the function
    done = subprocess.run([sys.executable, "-m", "argus_bench.cli", "validate", str(task)], capture_output=True, text=True)
    assert done.returncode == 0 and done.stdout.startswith("valid"), done.stderr
    # the validator really looks at the screenshot: remove it and the same directory is refused
    (task / "shots" / "screenshot.png").unlink()
    assert bench(["validate", str(task)]) == 1
    # honest limit: the run folder alone is not a task directory, a bench task also holds checks, meta and two patches
    assert bench(["validate", str(runs_root / run_id)]) == 1


# ---- refusals: typed, with their field, nothing stored ------------------------------------------------------------

REFUSALS = [
    ("missing text", dict(drop=("text",)), "text_required", "text"),
    ("blank text", dict(fields={"text": " \n\t "}), "text_required", "text"),
    ("nul in text", dict(fields={"text": "a\x00b"}), "text_invalid", "text"),
    ("text over the cap", dict(fields={"text": "x" * (issues.MAX_TEXT_CHARS + 1)}), "text_too_long", "text"),
    ("html as png", dict(files=shot(b"<html><script>alert(1)</script></html>", "a.png", "image/png")), "unsupported_file_type", "screenshot"),
    ("svg", dict(files=shot(b'<svg xmlns="http://www.w3.org/2000/svg"><script>1</script></svg>', "a.svg", "image/svg+xml")), "unsupported_file_type", "screenshot"),
    ("svg called png", dict(files=shot(b"<svg/>", "a.png", "image/png")), "unsupported_file_type", "screenshot"),
    ("gif", dict(files=shot(b"GIF89a" + b"\x00" * 20, "a.gif", "image/gif")), "unsupported_file_type", "screenshot"),
    ("zero bytes", dict(files=shot(b"", "a.png", "image/png")), "empty_file", "screenshot"),
    ("file over 5 MB", dict(files=shot(PNG + b"\x00" * (5 * 1024 * 1024), "a.png")), "file_too_large", "screenshot"),
    ("two files", dict(files=[("screenshot", ("a.png", PNG + b"1", "image/png")), ("screenshot", ("b.png", PNG + b"2", "image/png"))]), "too_many_files", "screenshot"),
    ("screenshot as plain text", dict(fields={"screenshot": "not a file"}), "not_a_file", "screenshot"),
    ("missing repo", dict(drop=("repo",)), "unknown_repo", "repo"),
    ("repo not in the list", dict(fields={"repo": "someone/else"}), "unknown_repo", "repo"),
    ("route not in the list", dict(fields={"route": "/etc/passwd"}), "unknown_route", "route"),
    ("route with traversal", dict(fields={"route": "/ops/../admin"}), "unknown_route", "route"),
    ("missing acknowledgement", dict(drop=("ack_public_or_synthetic",)), "ack_required", "ack_public_or_synthetic"),
    ("acknowledgement false", dict(fields={"ack_public_or_synthetic": "false"}), "ack_required", "ack_public_or_synthetic"),
    ("github trigger", dict(fields={"trigger": "github"}), "trigger_not_typed", "trigger"),
    ("unknown trigger", dict(fields={"trigger": "email"}), "unknown_trigger", "trigger"),
    ("unknown scenario", dict(fields={"scenario": "chaos"}), "unknown_scenario", "scenario"),
]


@pytest.mark.parametrize("name,kwargs,code,field", REFUSALS, ids=[r[0] for r in REFUSALS])
def test_each_refusal_is_typed_with_its_field_and_stores_nothing(client, runs_root, name, kwargs, code, field):
    r = post(client, **kwargs)
    assert_error(r, code, field)
    assert_nothing_stored(runs_root)


def test_the_first_failure_follows_the_form_order(client, runs_root):
    r = post(client, {"text": "", "repo": "nope", "route": "nope"}, drop=("ack_public_or_synthetic",))
    assert_error(r, "text_required", "text")
    r = post(client, {"repo": "nope", "route": "nope"}, drop=("ack_public_or_synthetic",))
    assert_error(r, "unknown_repo", "repo")
    assert_nothing_stored(runs_root)


def test_the_file_type_is_decided_by_the_bytes_not_by_name_or_header(client, runs_root):
    assert post(client, files=shot(PNG + b"1", "readme.txt", "text/plain")).status_code == 201  # real PNG, lying name and header
    bad = post(client, files=shot(b"<html>", "pic.png", "image/png"))                          # HTML, honest name and header
    assert_error(bad, "unsupported_file_type", "screenshot")
    assert len(store.list_runs()) == 1


def test_size_and_text_boundaries(client, runs_root):
    assert post(client, {"text": "x" * issues.MAX_TEXT_CHARS}).status_code == 201
    assert post(client, {"text": " " + "x" * issues.MAX_TEXT_CHARS + " "}).status_code == 201  # the cap is on the trimmed text
    assert post(client, {"text": "é" * issues.MAX_TEXT_CHARS}).status_code == 201             # characters, not bytes
    exactly = PNG + b"\x00" * (issues.MAX_FILE_BYTES - len(PNG))
    assert len(exactly) == 5 * 1024 * 1024
    assert post(client, files=shot(exactly)).status_code == 201
    assert_error(post(client, files=shot(exactly + b"\x00")), "file_too_large", "screenshot", 413)
    assert len(store.list_runs()) == 4


def test_a_body_without_a_declared_size_or_too_big_is_refused_before_parsing(client, runs_root):
    def chunks():
        yield b"--b\r\n"
    r = client.post("/api/issues", content=chunks(), headers={"X-Workbench-Token": TOKEN, "Content-Type": "multipart/form-data; boundary=b"})
    assert_error(r, "length_required", "screenshot", 411)
    huge = client.post("/api/issues", content=b"x" * (issues.MAX_BODY_BYTES + 1), headers={"X-Workbench-Token": TOKEN, "Content-Type": "multipart/form-data; boundary=b"})
    assert_error(huge, "file_too_large", "screenshot", 413)
    assert_nothing_stored(runs_root)


def test_not_multipart_and_broken_multipart_are_typed(client, runs_root):
    r = client.post("/api/issues", json={"text": "hi"}, headers={"X-Workbench-Token": TOKEN})
    assert_error(r, "multipart_required", None, 415)
    r = client.post("/api/issues", content=b"--b\r\nnot a part", headers={"X-Workbench-Token": TOKEN, "Content-Type": "multipart/form-data; boundary=b"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "bad_form"
    assert_nothing_stored(runs_root)


def test_the_token_is_still_required(app, runs_root):
    anon = TestClient(app, base_url="http://127.0.0.1")
    r = anon.post("/api/issues", data=OK_FIELDS)
    assert r.status_code == 403 and r.json()["error"]["code"] == "token_required"
    assert_nothing_stored(runs_root)


def test_a_write_failure_after_create_leaves_no_folder(client, runs_root, monkeypatch):
    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(issues.store, "write_file", boom)
    with pytest.raises(OSError):
        post(client, files=shot())
    assert_nothing_stored(runs_root)


# ---- the real seeded BUG-17 ticket --------------------------------------------------------------------------------


def test_seeded_bug_17_comes_from_the_bench_package(client):
    real = json.loads((issues.seeded_dir() / "ticket.json").read_text("utf-8"))
    got = client.get("/api/issues/seeded/bug-17").json()
    assert got == {"id": "BUG-17", "text": real["text"], "has_screenshot": True}
    img = client.get("/api/issues/seeded/bug-17/screenshot")
    assert img.status_code == 200 and img.headers["content-type"] == "image/png"
    assert img.content == (issues.seeded_dir() / real["screenshot"]["path"]).read_bytes() and img.content.startswith(PNG)


def test_seeded_ticket_and_its_screenshot_post_like_any_other_issue(client, runs_root):
    got = client.get("/api/issues/seeded/bug-17").json()
    img = client.get("/api/issues/seeded/bug-17/screenshot").content
    r = post(client, {"text": got["text"]}, files=shot(img, "radar-card.png"))
    assert r.status_code == 201
    assert (runs_root / r.json()["run_id"] / "shots" / "screenshot.png").read_bytes() == img


def test_seeded_route_is_absent_when_the_task_is_missing(client, monkeypatch, tmp_path):
    monkeypatch.setattr(issues, "seeded_dir", lambda: tmp_path / "nope")
    assert client.get("/api/issues/options").json()["seeded"]["available"] is False
    assert_error(client.get("/api/issues/seeded/bug-17"), "seeded_ticket_missing", "seeded", 404)
    assert_error(client.get("/api/issues/seeded/bug-17/screenshot"), "seeded_ticket_missing", "seeded", 404)


# ---- the page module ----------------------------------------------------------------------------------------------


def test_issue_screen_names_every_form_field_and_guards_the_start_route():
    js = (Path(issues.__file__).parents[1] / "static" / "screens" / "issue.js").read_text("utf-8")
    for name in ("text", "screenshot", "repo", "route", "ack_public_or_synthetic", "trigger", "scenario"):
        assert f"'{name}'" in js, name
    assert "/api/issues" in js and "/start" in js and "not_found" in js
    assert "not built yet" not in js
