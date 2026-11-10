"""Screen 1, New issue (P10-T03): POST /api/issues turns a typed bug report into a run folder in state `received`.

    GET  /api/issues/options              what the form may offer (repos, routes, limits, triggers, scenarios)
    POST /api/issues                      multipart: text, screenshot?, repo, route, ack_public_or_synthetic, trigger?, scenario?
    GET  /api/issues/seeded/bug-17        the real seeded BUG-17 ticket from packages/bench (text only)
    GET  /api/issues/seeded/bug-17/screenshot

Every refusal is a typed error naming its field and happens BEFORE anything is written, so a refused request
leaves the run store untouched. The checks run in the order of the form: trigger, text, screenshot, repo, route,
acknowledgement, scenario. The first failure is the one returned.

The screenshot is judged by its first bytes (PNG or JPEG), never by the client's file name or content type; the
stored name is chosen here (`shots/screenshot.png` or `.jpg`) and the client's name is never read. The stored folder
holds ticket.json (an argus-core Ticket), intake.json (repo, route, acknowledgement), state.json and the screenshot,
so ticket.json + the screenshot are what `bench validate` reads (tests run that validator).

ponytail: the upload is bounded by the Content-Length header (a request with none is refused with 411) because
Starlette spools a multipart body to disk before the route runs; a streaming cap would need a custom body reader.
ponytail: "PNG or JPEG" is decided by the signature only; the image is not decoded, so a file with a PNG header and
junk after it is stored. Nothing here serves it back inline; a screen that does must keep nosniff and the image type.
ponytail: a double submit makes two runs (the page disables the button while the request is open); a dedupe key
(the spec's "one workflow per ticket id") needs the runner's workflow id and is not built here.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from argus_core.types import Ticket
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from pydantic import ValidationError
from starlette.datastructures import UploadFile

from argus_workbench import store
from argus_workbench.errors import WorkbenchError
from argus_workbench.spec import load_spec, scenario_ids

router = APIRouter()

MAX_TEXT_CHARS = 10_000  # characters, after trimming. BUG-17 is about 1,000; a screenful of pasted log fits.
MAX_FILE_BYTES = int(load_spec()["targets"]["maxFileMB"] * 1024 * 1024)  # the spec's 5 MB, taken as 5 MiB
BODY_SLACK = 64 * 1024  # multipart framing and the small text fields
MAX_BODY_BYTES = MAX_FILE_BYTES + 4 * MAX_TEXT_CHARS + BODY_SLACK  # a character is at most 4 bytes in UTF-8
SIGNATURES = (  # (first bytes, media type, stored extension)
    (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
    (b"\xff\xd8\xff", "image/jpeg", "jpg"),
)
TRIGGERS = ("typed", "github")
DEFAULT_SCENARIO = "normal"
SEEDED_ID = "bug-17"
_TRUE = {"true", "1", "on", "yes"}


def sniff(head: bytes) -> tuple[str, str] | None:
    """(media type, extension) if `head` starts with a PNG or JPEG signature, else None."""
    for magic, media, ext in SIGNATURES:
        if head.startswith(magic):
            return media, ext
    return None


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    return next((p for p in here.parents if (p / "uv.lock").exists()), Path.cwd())


def seeded_dir() -> Path:
    # ponytail: found through the repo root (uv.lock), like the default run store; a wheel install has no bench tasks.
    return _repo_root() / "packages" / "bench" / "tasks" / "seeded" / SEEDED_ID


def _seeded_ticket() -> Ticket:
    path = seeded_dir() / "ticket.json"
    try:
        return Ticket.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError):
        raise WorkbenchError("seeded_ticket_missing", "the seeded BUG-17 ticket is not in this checkout", field="seeded", status=404) from None


def _seeded_available() -> bool:
    try:
        _seeded_ticket()
    except WorkbenchError:
        return False
    return True


@router.get("/api/issues/options")
def options() -> dict:
    spec = load_spec()
    targets = spec["targets"]
    return {
        "repos": targets["repos"],
        "routes": targets["routes"],
        "viewport": targets["viewport"],
        "max_text_chars": MAX_TEXT_CHARS,
        "max_file_bytes": MAX_FILE_BYTES,
        "max_file_mb": targets["maxFileMB"],
        "media_types": [m for _, m, _ in SIGNATURES],
        "triggers": spec["triggers"],
        "scenarios": [{"id": s["id"], "label": s["label"], "effect": s["effect"]} for s in spec["scenarios"]],
        "default_scenario": DEFAULT_SCENARIO,
        "seeded": {"id": SEEDED_ID, "available": _seeded_available()},
    }


@router.get("/api/issues/seeded/bug-17")
def seeded_ticket() -> dict:
    ticket = _seeded_ticket()
    return {"id": ticket.id, "text": ticket.text, "has_screenshot": _seeded_screenshot_path(ticket) is not None}


def _seeded_screenshot_path(ticket: Ticket) -> Path | None:
    """The screenshot file named by the seeded ticket, only if it really sits inside the seeded folder."""
    if ticket.screenshot is None:
        return None
    base = seeded_dir().resolve()
    path = (base / ticket.screenshot.path).resolve()
    return path if base in path.parents and path.is_file() else None


@router.get("/api/issues/seeded/bug-17/screenshot")
def seeded_screenshot() -> FileResponse:
    path = _seeded_screenshot_path(_seeded_ticket())
    if path is None or not path.is_file():
        raise WorkbenchError("seeded_ticket_missing", "the seeded BUG-17 ticket has no screenshot here", field="seeded", status=404)
    kind = sniff(path.read_bytes()[:8])
    if kind is None:
        raise WorkbenchError("seeded_ticket_missing", "the seeded screenshot is not a PNG or JPEG", field="seeded", status=404)
    return FileResponse(path, media_type=kind[0])


# ---- validation ------------------------------------------------------------------------------------------------


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise WorkbenchError("text_required", "Describe the bug: the text is required.", field="text")
    text = value.strip()
    if "\x00" in text:
        raise WorkbenchError("text_invalid", "The text contains a NUL character.", field="text")
    if len(text) > MAX_TEXT_CHARS:
        raise WorkbenchError("text_too_long", f"The text is {len(text)} characters; the limit is {MAX_TEXT_CHARS}.", field="text")
    return text


async def _screenshot(form) -> tuple[bytes, str, str] | None:
    """(bytes, media type, extension) of the optional screenshot, or None when none was attached."""
    parts = form.getlist("screenshot")
    if not parts:
        return None
    if len(parts) > 1:
        raise WorkbenchError("too_many_files", "Attach one screenshot.", field="screenshot")
    part = parts[0]
    if isinstance(part, str):
        if part == "":  # a browser sends an empty text part when no file was chosen
            return None
        raise WorkbenchError("not_a_file", "The screenshot must be a file upload.", field="screenshot")
    assert isinstance(part, UploadFile)
    data = await part.read(MAX_FILE_BYTES + 1)
    if not data:
        raise WorkbenchError("empty_file", "The screenshot file is empty.", field="screenshot")
    if len(data) > MAX_FILE_BYTES:
        raise WorkbenchError("file_too_large", f"The screenshot is over {MAX_FILE_BYTES // (1024 * 1024)} MB.", field="screenshot", status=413)
    kind = sniff(data[:8])
    if kind is None:
        raise WorkbenchError("unsupported_file_type", "The screenshot must be a PNG or JPEG image (judged by the file's first bytes).", field="screenshot", status=415)
    return data, kind[0], kind[1]


def _choice(form, name: str, allowed: list[str], code: str, label: str) -> str:
    value = form.get(name)
    if not isinstance(value, str) or value not in allowed:
        raise WorkbenchError(code, f"Pick one {label} from the list.", field=name)
    return value


def _check_length(request: Request) -> None:
    declared = request.headers.get("content-length")
    if declared is None:
        raise WorkbenchError("length_required", "The request must declare its size.", field="screenshot", status=411)
    if not declared.isdigit():
        raise WorkbenchError("bad_form", "The request size is not a number.", status=400)
    if int(declared) > MAX_BODY_BYTES:
        raise WorkbenchError("file_too_large", f"The request is over {MAX_FILE_BYTES // (1024 * 1024)} MB.", field="screenshot", status=413)


@router.post("/api/issues", status_code=201)
async def create_issue(request: Request) -> dict:
    _check_length(request)
    if not request.headers.get("content-type", "").lower().startswith("multipart/form-data"):
        raise WorkbenchError("multipart_required", "Send the issue as multipart/form-data.", status=415)
    try:
        form = await request.form(max_files=2, max_fields=20)
    except WorkbenchError:
        raise
    except Exception:  # Starlette raises its own errors for a broken body or a part over its size limit
        raise WorkbenchError("bad_form", "The form could not be read.", status=400) from None
    try:
        return await _create(form)
    finally:
        await form.close()


async def _create(form) -> dict:
    spec = load_spec()
    trigger = form.get("trigger", "typed")
    if trigger == "github":
        raise WorkbenchError("trigger_not_typed", "A labelled GitHub issue is not filed here: add the label on the repo issue.", field="trigger")
    if trigger != "typed":
        raise WorkbenchError("unknown_trigger", "The trigger must be typed.", field="trigger")
    text = _text(form.get("text"))
    shot = await _screenshot(form)
    repo = _choice(form, "repo", [r["id"] for r in spec["targets"]["repos"]], "unknown_repo", "repo")
    route = _choice(form, "route", spec["targets"]["routes"], "unknown_route", "route")
    ack = form.get("ack_public_or_synthetic")
    if not isinstance(ack, str) or ack.strip().lower() not in _TRUE:
        raise WorkbenchError("ack_required", "Confirm that only public or synthetic code goes through free tiers.", field="ack_public_or_synthetic")
    scenario = _choice(form, "scenario", list(scenario_ids()), "unknown_scenario", "scenario") if "scenario" in form else DEFAULT_SCENARIO

    run_id = store.new_run_id()
    ticket: dict = {"id": run_id, "text": text}
    if shot is not None:
        ticket["screenshot"] = {"media_type": shot[1], "path": f"shots/screenshot.{shot[2]}"}
    intake = {"repo": repo, "route": route, "ack_public_or_synthetic": True, "trigger": "typed"}
    state = store.create_run(ticket, scenario=scenario, run_id=run_id)
    try:
        store.write_file(run_id, "intake.json", intake)
        if shot is not None:
            shots = store.run_dir(run_id) / "shots"
            shots.mkdir()
            (shots / f"screenshot.{shot[2]}").write_bytes(shot[0])
    except BaseException:
        shutil.rmtree(store.run_dir(run_id), ignore_errors=True)
        raise
    return {"run_id": run_id, "ticket": ticket, "intake": intake, "state": state.model_dump(mode="json")}
