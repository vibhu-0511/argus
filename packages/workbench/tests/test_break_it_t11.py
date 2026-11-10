"""P10-T11 break it: hostile uploads through the real POST /api/issues.

Refused, each with a typed error that names the field `screenshot`, and with NOTHING left behind (the run store is
empty, no folder was made, and every spooled upload was closed with its temp file removed):
HTML bytes named x.png, a file of 5 MB + 1 byte, a 6 MB file, SVG as image/svg+xml, SVG named x.png, hostile bytes with
a ".." in the client file name, and a zero-byte file.
Accepted: a real PNG and a real JPEG, even with a client file name like "../../evil.png", and they are stored under
a name the SERVER chose (`shots/screenshot.png` / `shots/screenshot.jpg`).

The limits are written out here (5 MiB, PNG and JPEG signatures) and are NOT imported from the code under test, so
a weakened check (names instead of magic bytes, a bigger size cap) makes this module fail. See
docs/notes/p10-break-it-t11.md for the two mutated builds. No model is called.
"""

import tempfile
from pathlib import Path

import pytest
from starlette import formparsers

from argus_workbench import store

TOKEN = "test-token-not-secret"
H = {"X-Workbench-Token": TOKEN}
MB5 = 5 * 1024 * 1024
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 24
FIELDS = [("text", (None, "The radar card text is 10 px.")), ("repo", (None, "dcortex")), ("route", (None, "/ops/radar")),
          ("ack_public_or_synthetic", (None, "true"))]
HTML = b"<!doctype html><html><body><script>window.__pwned=1</script></body></html>"
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" onload="window.__pwned=1"><script>window.__pwned=1</script></svg>'
SVG_XML = b'<?xml version="1.0"?>' + SVG


@pytest.fixture
def spool(tmp_path, monkeypatch):
    """Send temp files to an empty folder of our own and remember every spooled upload, so 'no temp files left' is checkable."""
    tmp = tmp_path / "tmp"
    tmp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(tmp))
    made = []

    class Recording(tempfile.SpooledTemporaryFile):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            made.append(self)

    monkeypatch.setattr(formparsers, "SpooledTemporaryFile", Recording)
    return tmp, made


def upload(client, body: bytes, name="x.png", ctype="image/png", token=True):
    parts = [*FIELDS, ("screenshot", (name, body, ctype))]
    return client.post("/api/issues", files=parts, headers=H if token else {})


def tree(path: Path) -> list[str]:
    return sorted(p.relative_to(path).as_posix() for p in path.rglob("*")) if path.exists() else []


def assert_refused_and_nothing_stored(r, code, status, runs_root, spool):
    assert r.status_code == status, r.text
    assert r.json() == {"error": {"code": code, "field": "screenshot", "message": r.json()["error"]["message"]}}
    assert r.json()["error"]["message"]
    assert r.headers["content-type"].startswith("application/json")
    assert tree(runs_root) == [], "the run store must stay empty"
    assert store.list_runs() == []
    tmp, made = spool
    assert tree(tmp) == [], "no temp file may be left behind"
    assert all(f.closed for f in made), "every spooled upload must be closed"


CASES = [
    ("html bytes named x.png", HTML, "x.png", "image/png", "unsupported_file_type", 415),
    ("html bytes named x.jpg", HTML, "x.jpg", "image/jpeg", "unsupported_file_type", 415),
    ("svg as image/svg+xml", SVG, "x.svg", "image/svg+xml", "unsupported_file_type", 415),
    ("svg named x.png", SVG, "x.png", "image/png", "unsupported_file_type", 415),
    ("svg with an xml prolog named x.png", SVG_XML, "x.png", "image/png", "unsupported_file_type", 415),
    ("html with a .. in the file name", HTML, "../../evil.png", "image/png", "unsupported_file_type", 415),
    ("html with backslashes and .. in the name", HTML, "..\\..\\evil.png", "image/png", "unsupported_file_type", 415),
    ("html with a name that is only ..", HTML, "..", "image/png", "unsupported_file_type", 415),
    ("gif named x.png", b"GIF89a" + b"\x00" * 24, "x.png", "image/png", "unsupported_file_type", 415),
    ("a png signature cut short", PNG[:7], "x.png", "image/png", "unsupported_file_type", 415),
    ("zero bytes named x.png", b"", "x.png", "image/png", "empty_file", 400),
    ("zero bytes with a .. name", b"", "../../x.png", "image/png", "empty_file", 400),
    ("5 MB + 1 byte, valid png start", PNG + b"\x00" * (MB5 + 1 - len(PNG)), "x.png", "image/png", "file_too_large", 413),
    ("5 MB + 1 byte, valid jpeg start", JPG + b"\x00" * (MB5 + 1 - len(JPG)), "x.jpg", "image/jpeg", "file_too_large", 413),
    ("6 MB, valid png start", PNG + b"\x00" * (6 * 1024 * 1024 - len(PNG)), "x.png", "image/png", "file_too_large", 413),
    ("6 MB of html named x.png", HTML + b" " * (6 * 1024 * 1024 - len(HTML)), "x.png", "image/png", "file_too_large", 413),
]


@pytest.mark.parametrize("name,body,fname,ctype,code,status", CASES, ids=[c[0] for c in CASES])
def test_hostile_upload_is_refused_with_a_typed_error_and_nothing_is_stored(client, runs_root, spool, name, body, fname, ctype, code, status):
    r = upload(client, body, fname, ctype)
    assert_refused_and_nothing_stored(r, code, status, runs_root, spool)


def test_the_size_cap_is_exactly_5_mib(client, runs_root, spool):
    over = upload(client, PNG + b"\x00" * (MB5 + 1 - len(PNG)))
    assert_refused_and_nothing_stored(over, "file_too_large", 413, runs_root, spool)
    exact = upload(client, PNG + b"\x00" * (MB5 - len(PNG)))  # 5 MiB exactly is allowed: the limit is "over 5 MB", not "5 MB or more"
    assert exact.status_code == 201, exact.text
    run_id = exact.json()["run_id"]
    assert (runs_root / run_id / "shots" / "screenshot.png").stat().st_size == MB5
    assert _spools_closed(spool)


def _spools_closed(spool) -> bool:
    tmp, made = spool
    return tree(tmp) == [] and all(f.closed for f in made)


def test_a_big_upload_really_goes_through_the_spool(client, runs_root, spool):
    """Guards the 'no temp files' check against being vacuous: a 5 MB + 1 body must have rolled over to a temp file."""
    tmp, made = spool
    upload(client, PNG + b"\x00" * (MB5 + 1 - len(PNG)))
    assert made and any(f._rolled for f in made), "the body never reached the temp file path, so the check proves nothing"
    assert _spools_closed(spool)


@pytest.mark.parametrize("body,ext,media", [(PNG, "png", "image/png"), (JPG, "jpg", "image/jpeg")])
@pytest.mark.parametrize("fname", ["../../evil.png", "..\\..\\evil.jpg", "..", "a/b/../../c.png", "evil name;rm -rf.exe", "x" * 300 + ".png"])
def test_a_real_image_with_an_odd_name_is_stored_under_a_server_chosen_name(client, runs_root, spool, tmp_path, body, ext, media, fname):
    outside_before = tree(tmp_path)
    inside = body + b"\x07" * 100
    r = upload(client, inside, fname, "text/plain")  # the content type is a lie too
    assert r.status_code == 201, r.text
    out = r.json()
    run_id = out["run_id"]
    assert out["ticket"]["screenshot"] == {"media_type": media, "path": f"shots/screenshot.{ext}"}
    folder = runs_root / run_id
    assert tree(folder) == sorted(["intake.json", "shots", f"shots/screenshot.{ext}", "state.json", "ticket.json"])
    assert (folder / "shots" / f"screenshot.{ext}").read_bytes() == inside
    stored = store.read_file(run_id, "ticket.json")
    assert stored.screenshot.path == f"shots/screenshot.{ext}" and stored.screenshot.media_type == media
    # the client's name is nowhere: not in the response, not in any stored file name or file content
    assert "evil" not in r.text and ".." not in r.text.replace("...", "")
    assert not any("evil" in p for p in tree(runs_root))
    for p in folder.rglob("*"):
        if p.is_file() and p.suffix == ".json":
            assert "evil" not in p.read_text("utf-8")
    # and nothing was written outside the run folder: only the run store and the temp folder exist under tmp_path
    created = set(tree(tmp_path)) - set(outside_before)
    assert all(c.startswith(("runs", "tmp")) for c in created), created
    assert not (tmp_path / "evil.png").exists() and not (runs_root.parent / "evil.png").exists() and not (runs_root / "evil.png").exists()
    assert _spools_closed(spool)


def test_the_type_follows_the_bytes_not_the_name(client, runs_root, spool):
    jpg_named_png = upload(client, JPG + b"\x01", "photo.png", "image/png")
    png_named_jpg = upload(client, PNG + b"\x01", "photo.jpg", "image/jpeg")
    assert jpg_named_png.json()["ticket"]["screenshot"]["path"] == "shots/screenshot.jpg"
    assert png_named_jpg.json()["ticket"]["screenshot"]["path"] == "shots/screenshot.png"


def test_a_refusal_after_a_good_upload_leaves_only_the_good_run(client, runs_root, spool):
    good = upload(client, PNG + b"\x01", "../../evil.png")
    assert good.status_code == 201
    for body, fname, ctype in [(HTML, "x.png", "image/png"), (SVG, "x.svg", "image/svg+xml"), (b"", "x.png", "image/png")]:
        assert upload(client, body, fname, ctype).status_code >= 400
    assert [s.run_id for s in store.list_runs()] == [good.json()["run_id"]]
    assert _spools_closed(spool)


def test_a_hostile_upload_without_the_token_is_refused_before_anything_is_read(client, runs_root, spool):
    r = upload(client, HTML, "x.png", "image/png", token=False)
    assert r.status_code == 403 and r.json()["error"]["code"] == "token_required"
    assert tree(runs_root) == [] and _spools_closed(spool)
