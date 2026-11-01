"""Fix-loop tools. `edit` is an exact unique match. There is no whole-file write tool."""

from __future__ import annotations

import json
import shutil
import shlex
import subprocess
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ToolErrorCode(StrEnum):
    outside_worktree = "outside-worktree"
    not_found = "not-found"
    not_unique = "not-unique"
    not_allowed = "not-allowed"
    timeout = "timeout"
    failed = "failed"
    bad_pattern = "bad-pattern"


class ToolError(_Model):
    """Typed failure from a fix-loop tool. The code is not a loop stop reason."""

    ok: Literal[False] = False
    error: ToolErrorCode
    message: str = Field(min_length=1)


class ToolResult(_Model):
    ok: Literal[True] = True
    tool: str
    text: str
    returncode: int | None = None


class ReadFileArgs(_Model):
    """Read a UTF-8 file inside the worktree."""

    path: str = Field(min_length=1, description="Path relative to the worktree.")


class ListDirArgs(_Model):
    """List the names in one directory inside the worktree."""

    path: str = Field(default=".", min_length=1, description="Directory relative to the worktree.")


class SearchArgs(_Model):
    """Find an exact string and return file and line."""

    query: str = Field(min_length=1, description="Exact text to find. No regular expression.")
    path: str = Field(default=".", min_length=1, description="File or directory relative to the worktree.")


class EditArgs(_Model):
    """Replace one exact occurrence of old with new. A second match is an error that names the lines."""

    path: str = Field(min_length=1, description="File relative to the worktree.")
    old: str = Field(min_length=1, description="Exact text to replace. Whitespace is significant.")
    new: str = Field(description="Replacement text. Empty deletes the match.")


class RunCmdArgs(_Model):
    """Run one command with the worktree as the working directory."""

    command: str = Field(min_length=1, description="Command line. The working directory is the worktree.")


class SubmitArgs(_Model):
    """Stop the run. The scored artifact is the worktree diff, not this call."""


class AstGrepArgs(_Model):
    """Run an ast-grep pattern over the Canvas tree and return file and line."""

    pattern: str = Field(min_length=1, description="ast-grep pattern. A pattern the parser rejects is bad-pattern.")
    path: str = Field(default=".", min_length=1, description="File or directory under apps/canvas.")
    lang: str = Field(default="tsx", min_length=1, description="Language name, such as tsx.")


ALLOW = ("read_file", "list_dir", "search", "edit", "run_cmd", "submit", "ast_grep")

_ARGS: dict[str, type[_Model]] = {
    "read_file": ReadFileArgs,
    "list_dir": ListDirArgs,
    "search": SearchArgs,
    "edit": EditArgs,
    "run_cmd": RunCmdArgs,
    "submit": SubmitArgs,
    "ast_grep": AstGrepArgs,
}

_TIMEOUT = 30


def call(name: str, payload: dict, root: Path) -> ToolResult | ToolError:
    model = _ARGS.get(name)
    if model is None:
        return ToolError(error="not-allowed", message=f"{name} is not a fix-loop tool")
    try:
        args = model.model_validate(payload)
    except ValidationError as exc:
        missing = [str(item["loc"][-1]) for item in exc.errors() if item.get("type") == "missing" and item.get("loc")]
        if missing:
            return ToolError(error="failed", message="missing " + ", ".join(missing))
        return ToolError(error="failed", message=exc.errors()[0]["msg"])
    return _RUN[name](root.resolve(), args)


def dump_schemas(directory: str | Path) -> None:
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    models: dict[str, type[_Model]] = {**_ARGS, "tool-error": ToolError}
    for name, model in models.items():
        schema = model.model_json_schema()
        schema["$id"] = f"https://argus.local/schemas/fix/{name}.schema.json"
        (out / f"{name}.schema.json").write_text(
            json.dumps(schema, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _inside(root: Path, raw: str) -> Path | ToolError:
    try:
        resolved = (root / raw).resolve()
        resolved.relative_to(root)
    except ValueError:
        return ToolError(error="outside-worktree", message=f"{raw} is outside the worktree")
    return resolved


def _read(root: Path, args: ReadFileArgs) -> ToolResult | ToolError:
    path = _inside(root, args.path)
    if isinstance(path, ToolError):
        return path
    if not path.is_file():
        return ToolError(error="not-found", message=f"{args.path} is not a file")
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ToolError(error="failed", message=f"{args.path} is not utf-8 text")
    return ToolResult(tool="read_file", text=text)


def _list(root: Path, args: ListDirArgs) -> ToolResult | ToolError:
    path = _inside(root, args.path)
    if isinstance(path, ToolError):
        return path
    if not path.is_dir():
        return ToolError(error="not-found", message=f"{args.path} is not a directory")
    names = sorted(item.name for item in path.iterdir())
    return ToolResult(tool="list_dir", text="\n".join(names))


def _search(root: Path, args: SearchArgs) -> ToolResult | ToolError:
    path = _inside(root, args.path)
    if isinstance(path, ToolError):
        return path
    if not path.exists():
        return ToolError(error="not-found", message=f"{args.path} is not in the worktree")
    files = [path] if path.is_file() else sorted(item for item in path.rglob("*") if item.is_file())
    hits: list[str] = []
    for file in files:
        if ".git" in file.relative_to(root).parts:
            continue
        try:
            text = file.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        start = 0
        while True:
            index = text.find(args.query, start)
            if index < 0:
                break
            line_no = text.count("\n", 0, index) + 1
            line = text.splitlines()[line_no - 1]
            hits.append(f"{file.relative_to(root).as_posix()}:{line_no}:{line}")
            start = index + len(args.query)
    if not hits:
        return ToolError(error="not-found", message=f"{args.query} is not in {args.path}")
    return ToolResult(tool="search", text="\n".join(hits))


def _edit(root: Path, args: EditArgs) -> ToolResult | ToolError:
    path = _inside(root, args.path)
    if isinstance(path, ToolError):
        return path
    if not path.is_file():
        return ToolError(error="not-found", message=f"{args.path} is not a file")
    text = path.read_text(encoding="utf-8")
    lines = _match_lines(text, args.old)
    rel = path.relative_to(root).as_posix()
    if not lines:
        return ToolError(error="not-found", message=f"{args.old!r} is not in {rel}")
    if len(lines) > 1:
        listed = ", ".join(str(number) for number in lines)
        return ToolError(error="not-unique", message=f"{rel} matches lines {listed}")
    path.write_text(text.replace(args.old, args.new, 1), encoding="utf-8", newline="\n")
    return ToolResult(tool="edit", text=f"edited {rel}")


_INTERACTIVE = {"vim", "vi", "nvim", "nano", "less", "more", "top", "man", "emacs"}
_REPL = {"python", "python3", "ipython", "node"}
_AST_GREP = "@ast-grep/cli@0.51.0"


def _interactive(command: str) -> bool:
    try:
        parts = shlex.split(command, posix=True)
    except ValueError:
        return False
    if not parts:
        return False
    name = Path(parts[0]).name.lower()
    if name.endswith(".exe"):
        name = name[:-4]
    if name in _INTERACTIVE:
        return True
    return name in _REPL and len(parts) == 1


def _run(root: Path, args: RunCmdArgs) -> ToolResult | ToolError:
    if _interactive(args.command):
        return ToolError(error="not-allowed", message="interactive command rejected")
    if not root.is_dir():
        return ToolError(error="failed", message="worktree is not a directory")
    try:
        proc = subprocess.run(
            args.command,
            shell=True,
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return ToolError(error="timeout", message=f"command timed out after {_TIMEOUT}s")
    except OSError as exc:
        return ToolError(error="failed", message=str(exc))
    return ToolResult(tool="run_cmd", text=proc.stdout + proc.stderr, returncode=proc.returncode)


def _ast(root: Path, args: AstGrepArgs) -> ToolResult | ToolError:
    target = _inside(root, args.path)
    if isinstance(target, ToolError):
        return target
    if not target.exists():
        return ToolError(error="not-found", message=f"{args.path} is not in the worktree")
    npx = shutil.which("npx")
    if npx is None:
        return ToolError(error="failed", message="npx is not on PATH")
    proc = subprocess.run(
        [
            npx,
            "--yes",
            "-p",
            _AST_GREP,
            "ast-grep",
            "run",
            "-p",
            args.pattern,
            "-l",
            args.lang,
            "--json=compact",
            str(target),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    if "ERROR node" in proc.stderr:
        return ToolError(error="bad-pattern", message=proc.stderr.strip())
    try:
        matches = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return ToolError(error="failed", message=(proc.stderr or "ast-grep did not return JSON").strip())
    if not isinstance(matches, list):
        return ToolError(error="failed", message="ast-grep did not return a list")
    if not matches:
        return ToolError(error="not-found", message=f"{args.pattern!r} matched nothing")
    lines: list[str] = []
    for match in matches:
        file = Path(str(match["file"]))
        try:
            rel = file.resolve().relative_to(root).as_posix()
        except ValueError:
            rel = file.as_posix()
        line = int(match["range"]["start"]["line"]) + 1
        lines.append(f"{rel}:{line}")
    return ToolResult(tool="ast_grep", text="\n".join(lines))


def _submit(root: Path, args: SubmitArgs) -> ToolResult | ToolError:
    del root, args
    return ToolResult(tool="submit", text="submitted")


def _match_lines(text: str, old: str) -> list[int]:
    found: list[int] = []
    start = 0
    while True:
        index = text.find(old, start)
        if index < 0:
            return found
        found.append(text.count("\n", 0, index) + 1)
        start = index + len(old)


_RUN = {
    "read_file": _read,
    "list_dir": _list,
    "search": _search,
    "edit": _edit,
    "run_cmd": _run,
    "submit": _submit,
    "ast_grep": _ast,
}
