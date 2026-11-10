"""The run store: one folder per run under the store root, one validated file per concern.

Layout and owners are in docs/architecture/p10.md ("Run folder contract"). Every read and write goes through
`read_file` / `write_file`, which check the file name against a fixed list and the content against its schema,
so a route or a runner cannot write a file the contract does not name, and a hand-edited file that no longer
validates is refused on read, not shown.

Schemas come from elsewhere where they exist and are not copied: `Ticket` and `Trajectory` from argus-core,
`State` and the transition table from flow.states, `StopReason` from argus-core, the check order from verify.

Safety: a run id must fully match `[a-z0-9-]{1,64}`, must not be a Windows device name, and the resolved folder
must be a direct child of the resolved root (a symlink out of the root is refused). File names are never taken
from a caller: only the names in `FILES`.

ponytail: no file lock. One server process and one runner thread per run write one run at a time. A second
writer on the same run needs a lock around read-modify-write (T13 adds one around decide-and-open-PR).
ponytail: `list_runs` reads every state.json; fine for hundreds of runs, add an index file for thousands.
"""

from __future__ import annotations

import os
import re
import secrets
import shutil
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from argus_core.types import StopReason, Ticket, Trajectory
from flow.states import Event, IllegalTransition, State, next_state
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError, model_validator
from verify.pipeline import ORDER as CHECK_ORDER

from argus_workbench.errors import WorkbenchError, from_validation
from argus_workbench.spec import scenario_ids

RUN_ID = re.compile(r"[a-z0-9-]{1,64}")  # used with fullmatch, never match/search
_DEVICE_NAMES = frozenset({"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(1, 10)} | {f"lpt{i}" for i in range(1, 10)})
ENV_ROOT = "ARGUS_WORKBENCH_RUNS"
MAX_TEXT_BYTES = 2_000_000  # report.html and patch.diff
Origin = Literal["SIMULATED", "REPLAY"]
Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(UTC)


# ---- schemas of the files that have no schema elsewhere -------------------------------------------------------


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


def display_state(state: State, stop_reason: StopReason | None) -> str:
    """`quota-wait` and `stuck` are display states, derived from the stop reason. They are never stored as a state."""
    if stop_reason == StopReason.quota_exceeded:
        return "quota-wait"
    if stop_reason == StopReason.stuck:
        return "stuck"
    return State(state).value


class RunState(_Model):
    """state.json. `state` is a flow.states.State value; `display_state` is derived and checked on read."""

    run_id: str
    state: State
    stop_reason: StopReason | None = None
    display_state: str | None = None
    origin: Origin
    scenario: str | None = None
    created_by_retry_of: str | None = None
    created_at: AwareDatetime
    updated_at: AwareDatetime

    @model_validator(mode="after")
    def _derived(self) -> RunState:
        check_run_id(self.run_id)
        if self.created_by_retry_of is not None:
            check_run_id(self.created_by_retry_of, field="created_by_retry_of")
        if self.scenario is not None and self.scenario not in scenario_ids():
            raise ValueError(f"scenario must be one of {', '.join(scenario_ids())}")
        expected = display_state(self.state, self.stop_reason)
        if self.display_state is None:
            self.display_state = expected
        elif self.display_state != expected:
            raise ValueError(f"display_state must be {expected!r} for this state and stop reason")
        return self


class Check(_Model):
    """One check result, the fields of verify.checks.CheckResult plus the route it ran on."""

    name: Literal["pixel", "overflow", "axe", "console"]
    ok: bool
    hard: bool = True
    reason: str
    route: str | None = None


class Verdict(_Model):
    """verdict.json. Checks are listed in verify's order and stop at the first hard failure (verify.pipeline.run).

    A check that did not run (short-circuited) is absent, not listed as passed. The judge label is advisory
    while its agreement with humans is uncalibrated (ADR-013), so `judge_advisory` is true unless a calibration
    file says otherwise.
    """

    ok: bool
    checks: list[Check]
    first_failure: str | None = None
    failed_check: str | None = None
    judge_label: Literal["pass", "fail", "not run"] = "not run"
    judge_note: str | None = None
    judge_advisory: bool = True
    origin: Origin

    @model_validator(mode="after")
    def _consistent(self) -> Verdict:
        names = [c.name for c in self.checks]
        # ponytail: one result per check name; the route says which route it concerns. verify.run_routes merges
        # every route into one list with repeated names; a writer keeps the first failing route's result per check.
        if len(set(names)) != len(names) or names != sorted(names, key=CHECK_ORDER.index):
            raise ValueError(f"checks are unique and follow the order {', '.join(CHECK_ORDER)}")
        if self.ok:
            if names != list(CHECK_ORDER) or not all(c.ok for c in self.checks):
                raise ValueError("an ok verdict lists all four checks, each passing")
            if self.first_failure is not None or self.failed_check is not None:
                raise ValueError("an ok verdict has no first failure")
        elif self.first_failure is None or self.failed_check not in CHECK_ORDER:
            raise ValueError("a failed verdict names the first failure and the failed check")
        return self


class Decision(_Model):
    """decision.json: written once per idempotency key (T07)."""

    decision: Literal["approve", "request-changes", "reject"]
    reason: str | None = None
    idempotency_key: str = Field(min_length=1, max_length=128)
    decided_at: AwareDatetime


class PrFile(BaseModel):
    """pr.json: the argus_app.pr / flow.workflow.PullRequest result (number, url, draft) of the MOCK transport.

    Extra keys are allowed so T08 can add title, branch, body and CI state without changing this file.
    """

    model_config = ConfigDict(extra="allow")
    number: int = Field(ge=1)
    url: str = Field(min_length=1)
    draft: bool
    origin: Origin


class Intake(BaseModel):
    """intake.json (sidecar of ticket.json, written by T03): what the person chose besides the ticket text."""

    model_config = ConfigDict(extra="allow")
    repo: str = Field(min_length=1)
    route: str = Field(min_length=1)
    ack_public_or_synthetic: bool


# name -> how it is validated. "model": pydantic model, "trajectory": argus-core JSONL, "text": utf-8 text.
FILES: dict[str, tuple[str, Any]] = {
    "ticket.json": ("model", Ticket),
    "intake.json": ("model", Intake),
    "state.json": ("model", RunState),
    "trajectory.jsonl": ("trajectory", Trajectory),
    "verdict.json": ("model", Verdict),
    "report.html": ("text", None),
    "patch.diff": ("text", None),
    "decision.json": ("model", Decision),
    "pr.json": ("model", PrFile),
}
_CODES = {"state": "unknown_state", "stop_reason": "unknown_stop_reason", "origin": "bad_origin"}


# ---- ids and paths --------------------------------------------------------------------------------------------


def check_run_id(run_id: object, field: str = "run_id") -> str:
    """The id if it is safe as a folder name, else a typed error. Nothing here touches the disk."""
    if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id) or run_id in _DEVICE_NAMES:
        raise WorkbenchError("bad_run_id", "a run id is 1 to 64 characters of a-z, 0-9 and -", field=field)
    return run_id


def new_run_id() -> str:
    return "run-" + secrets.token_hex(6)


def store_root(root: Path | str | None = None) -> Path:
    """`root` if given, else $ARGUS_WORKBENCH_RUNS, else <repo>/.local/workbench/runs (git-ignored)."""
    if root is None:
        root = os.environ.get(ENV_ROOT)
    if root:
        return Path(root)
    here = Path(__file__).resolve()
    repo = next((p for p in here.parents if (p / "uv.lock").exists()), Path.cwd())
    return repo / ".local" / "workbench" / "runs"


def run_dir(run_id: str, root: Path | str | None = None) -> Path:
    """The folder of a run (it may not exist yet). Refuses an unsafe id and a folder that resolves outside the root."""
    check_run_id(run_id)
    base = store_root(root).resolve()
    path = (base / run_id).resolve()
    if path.parent != base:
        raise WorkbenchError("bad_run_id", "the run folder is outside the run store", field="run_id")
    return path


def _existing_dir(run_id: str, root: Path | str | None) -> Path:
    path = run_dir(run_id, root)
    if not path.is_dir():
        raise WorkbenchError("unknown_run", "no run with this id", field="run_id", status=404)
    return path


# ---- read and write -------------------------------------------------------------------------------------------


def _file_spec(name: str) -> tuple[str, Any]:
    if name not in FILES:
        raise WorkbenchError("unknown_file", "not a run file", field="file")
    return FILES[name]


def _validate(name: str, kind: str, schema: Any, value: Any) -> Any:
    try:
        if kind == "model":
            return value if isinstance(value, schema) else schema.model_validate(value)
        if kind == "trajectory":
            return value if isinstance(value, Trajectory) else Trajectory.from_jsonl(value)
    except ValidationError as exc:
        err = from_validation(exc, "invalid_file", name)
        raise WorkbenchError(_CODES.get(err.field or "", f"invalid_{name.split('.')[0]}"), err.message, err.field) from None
    except (ValueError, TypeError, AttributeError) as exc:  # bad JSONL, or a pydantic error raised inside from_jsonl
        raise WorkbenchError("invalid_trajectory", f"{name}: {exc}", field=None) from None
    if not isinstance(value, str):
        raise WorkbenchError(f"invalid_{name.split('.')[0]}", f"{name} must be text", field=None)
    if len(value.encode("utf-8")) > MAX_TEXT_BYTES:
        raise WorkbenchError("file_too_large", f"{name} is over {MAX_TEXT_BYTES} bytes", field=None)
    return value


def _serialise(kind: str, value: Any) -> bytes:
    if kind == "model":
        return (value.model_dump_json(indent=2) + "\n").encode("utf-8")
    if kind == "trajectory":
        return value.to_jsonl().encode("utf-8")
    return value.encode("utf-8")


def _retry_if_busy(action: Callable[[], Any]) -> Any:
    """Run a file action; on Windows a file that another thread has open raises PermissionError for a moment.

    The live-run screen reads trajectory.jsonl while the runner replaces it, so a read can block the replace
    (and the replace can block a read). Retry for about half a second; a real permission problem still raises.
    ponytail: retry loop, not a lock; a lock across the readers is needed if a run writes in big bursts.
    """
    for _ in range(50):
        try:
            return action()
        except PermissionError:
            time.sleep(0.01)
    return action()


def write_file(run_id: str, name: str, value: Any, *, overwrite: bool = True, root: Path | str | None = None) -> Any:
    """Validate `value` (a model, a dict, a Trajectory, JSONL text or plain text by file) and write it.

    The write is atomic (temp file, then replace). `overwrite=False` creates the file or fails with
    `already_written`, which is how a once-only file (decision.json) is kept once.
    """
    kind, schema = _file_spec(name)
    folder = _existing_dir(run_id, root)
    checked = _validate(name, kind, schema, value)
    data = _serialise(kind, checked)
    target = folder / name
    if not overwrite:
        try:
            with open(target, "xb") as fh:
                fh.write(data)
        except FileExistsError:
            raise WorkbenchError("already_written", f"{name} already exists", status=409) from None
        return checked
    tmp = folder / f".{name}.{secrets.token_hex(4)}.tmp"
    tmp.write_bytes(data)
    _retry_if_busy(lambda: os.replace(tmp, target))
    return checked


def read_file(run_id: str, name: str, *, root: Path | str | None = None) -> Any:
    """The validated content: a model, a Trajectory, or text. Missing file: `missing_file`; invalid file: refused."""
    kind, schema = _file_spec(name)
    target = _existing_dir(run_id, root) / name
    try:
        raw = _retry_if_busy(target.read_bytes).decode("utf-8")
    except FileNotFoundError:
        raise WorkbenchError("missing_file", f"{name} does not exist for this run", field="file", status=404) from None
    except UnicodeDecodeError:
        raise WorkbenchError(f"invalid_{name.split('.')[0]}", f"{name} is not UTF-8 text") from None
    if kind == "model":
        try:
            return _validate(name, kind, schema, schema.model_validate_json(raw))
        except ValidationError as exc:
            err = from_validation(exc, "invalid_file", name)
            raise WorkbenchError(_CODES.get(err.field or "", f"invalid_{name.split('.')[0]}"), err.message, err.field) from None
    return _validate(name, kind, schema, raw)


def has_file(run_id: str, name: str, *, root: Path | str | None = None) -> bool:
    _file_spec(name)
    return (_existing_dir(run_id, root) / name).is_file()


# ---- runs -----------------------------------------------------------------------------------------------------


def create_run(
    ticket: Ticket | dict,
    *,
    scenario: str | None = None,
    origin: Origin = "SIMULATED",
    run_id: str | None = None,
    retry_of: str | None = None,
    clock: Clock = utc_now,
    root: Path | str | None = None,
) -> RunState:
    """Create the folder with `ticket.json` and `state.json` (state `received`). Nothing is left behind on a refusal."""
    run_id = check_run_id(run_id if run_id is not None else new_run_id())
    now = clock()
    state = _validate("state.json", "model", RunState, {
        "run_id": run_id, "state": State.RECEIVED, "stop_reason": None, "origin": origin, "scenario": scenario,
        "created_by_retry_of": retry_of, "created_at": now, "updated_at": now,
    })
    ticket = _validate("ticket.json", "model", Ticket, ticket)
    base = store_root(root)
    path = run_dir(run_id, root)
    if retry_of is not None:
        _existing_dir(retry_of, root)  # the old run must exist; it is read, never written
    base.mkdir(parents=True, exist_ok=True)
    try:
        path.mkdir()
    except FileExistsError:
        raise WorkbenchError("run_exists", "a run with this id already exists", field="run_id", status=409) from None
    try:
        write_file(run_id, "ticket.json", ticket, root=root)
        write_file(run_id, "state.json", state, root=root)
    except BaseException:
        shutil.rmtree(path, ignore_errors=True)
        raise
    return state


def get_state(run_id: str, *, root: Path | str | None = None) -> RunState:
    return read_file(run_id, "state.json", root=root)


def advance(
    run_id: str,
    event: Event,
    *,
    stop_reason: StopReason | None = None,
    clock: Clock = utc_now,
    root: Path | str | None = None,
) -> RunState:
    """Move the run along one legal flow.states transition. An illegal one is a typed 409 and changes nothing."""
    current = get_state(run_id, root=root)
    try:
        new = next_state(current.state, event)
    except IllegalTransition as exc:
        raise WorkbenchError("illegal_transition", str(exc), field="state", status=409) from None
    updated = current.model_copy(update={"state": new, "stop_reason": stop_reason, "display_state": None, "updated_at": clock()})
    return write_file(run_id, "state.json", RunState.model_validate(updated.model_dump()), root=root)


def list_runs(*, root: Path | str | None = None) -> list[RunState]:
    """Every readable run, newest first. A folder that is not a valid run id or whose state.json fails is skipped."""
    base = store_root(root)
    if not base.is_dir():
        return []
    found = []
    for child in base.iterdir():
        try:
            if child.is_dir():
                found.append(get_state(child.name, root=root))
        except WorkbenchError:
            continue
    return sorted(found, key=lambda s: (s.created_at, s.run_id), reverse=True)
