"""Apply a unified diff (`git diff` output) to file texts, in memory (P6 GitHub write client).

The GitHub REST API has no "apply this patch" call, so `flow.github_write` reads the touched files
at the base commit, applies the diff here, and sends the new texts as tree entries. `apply_unified`
takes a `read(path) -> text | None` and returns one `FileChange` per file; it touches no disk and no network.

Strict on purpose: every context and removed line must match the file exactly (no offset, no fuzz), or
`PatchError` is raised and nothing is half applied.

ponytail: text files only (UTF-8). Refused with `PatchError`: binary patches, renames, copies, paths
without the `a/` `b/` prefix of `git diff`. A mode is taken from the diff header (default 100644).
Upgrade path: `git apply` in a clone, when a real patch needs one of these.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import NamedTuple

_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
_MODE = re.compile(r"^(?:new file mode|new mode|index \S+) (\d{6})$")


class PatchError(ValueError):
    """The diff cannot be applied here. Retrying the same diff cannot help."""


class FileChange(NamedTuple):
    path: str
    mode: str
    content: str | None  # None: the file is deleted


def _path(header: str) -> str | None:
    name = header[4:].split("\t")[0].strip()
    if name == "/dev/null":
        return None
    if not name.startswith(("a/", "b/")):
        raise PatchError(f"unsupported path in diff header: {name!r}")
    return name[2:]


def apply_unified(patch: str, read: Callable[[str], str | None]) -> list[FileChange]:
    lines = patch.split("\n")
    i, mode, changes = 0, "100644", []
    while i < len(lines):
        line = lines[i]
        if line.startswith("diff --git"):
            mode = "100644"
        elif line.startswith(("GIT binary patch", "Binary files")):
            raise PatchError("binary files are not supported")
        elif line.startswith(("rename ", "copy ")):
            raise PatchError("renames and copies are not supported")
        elif m := _MODE.match(line):
            mode = m.group(1)
        elif line.startswith("--- ") and i + 1 < len(lines) and lines[i + 1].startswith("+++ "):
            old_path, new_path = _path(line), _path(lines[i + 1])
            i, hunks = _hunks(lines, i + 2)
            changes.append(_apply(hunks, old_path, new_path, mode, read))
            continue
        i += 1
    if not changes:
        raise PatchError("the patch has no file changes")
    return changes


class _Hunk(NamedTuple):
    start: int  # index of the first old line the hunk covers
    old: list[str]
    new: list[str]
    eol: bool | None  # a "\ No newline at end of file" marker decided it; None: no marker


def _hunks(lines: list[str], i: int) -> tuple[int, list[_Hunk]]:
    """Read the hunks of one file starting at line `i`; return the index after them."""
    hunks: list[_Hunk] = []
    while i < len(lines) and (m := _HUNK.match(lines[i])):
        old_start, old_n, new_n = int(m[1]), int(m[2] or 1), int(m[4] or 1)
        old, new, eol, last = [], [], None, ""
        i += 1
        while (old_n > 0 or new_n > 0 or (i < len(lines) and lines[i].startswith("\\"))) and i < len(lines):
            line = lines[i]
            kind, text = (line[:1] or " "), line[1:]  # an empty line is an empty context line
            if kind == "\\":
                eol = last == "-"  # after a `-` line the old side lacked the newline, so the new side has it
            elif kind == " ":
                old.append(text), new.append(text)
                old_n, new_n = old_n - 1, new_n - 1
            elif kind == "-":
                old.append(text)
                old_n -= 1
            elif kind == "+":
                new.append(text)
                new_n -= 1
            else:
                raise PatchError(f"unexpected line in hunk: {line[:40]!r}")
            last = kind if kind != "\\" else last
            i += 1
        if old_n or new_n:
            raise PatchError("a hunk is shorter than its header says")
        hunks.append(_Hunk(old_start if not old else old_start - 1, old, new, eol))
    if not hunks:
        raise PatchError("a file header has no hunks")
    return i, hunks


def _apply(hunks: list[_Hunk], old_path: str | None, new_path: str | None, mode: str, read: Callable[[str], str | None]) -> FileChange:
    path = old_path or new_path
    assert path is not None
    text = read(path)
    if old_path is None:
        if text is not None:
            raise PatchError(f"{path} is created by the patch but already exists")
        text = ""
    elif text is None:
        raise PatchError(f"{path} is changed by the patch but does not exist")
    old = text.split("\n")
    eol = old[-1] == ""
    if eol:
        old.pop()
    out, pos = [], 0
    for h in hunks:
        if h.start < pos or old[h.start : h.start + len(h.old)] != h.old:
            raise PatchError(f"{path}: the patch does not match the file near line {h.start + 1}")
        out += old[pos : h.start] + h.new
        pos = h.start + len(h.old)
        eol = h.eol if h.eol is not None else eol
    out += old[pos:]
    if new_path is None:
        return FileChange(path, mode, None)
    return FileChange(new_path, mode, "\n".join(out) + ("\n" if eol and out else ""))
