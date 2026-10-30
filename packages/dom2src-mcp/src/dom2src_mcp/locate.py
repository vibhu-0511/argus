"""Resolve a selector to the file and line stamped on data-src.

The attribute value is repo-relative ``file:line:col`` with no tag suffix.
Repeated matches and a wrapper call site return ranked candidates.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Literal

_ID = re.compile(r"#[A-Za-z_][\w-]*")
_TESTID = re.compile(r"""\[data-testid=(?:"([^"]+)"|'([^']+)')]""")
_SRC = re.compile(r"([^:\\]+):(\d+):(\d+)")
# Void elements never close. Leaving them open would fake a wrapper ancestor.
_VOID = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
)


@dataclass(frozen=True)
class Location:
    file: str
    line: int
    col: int


@dataclass(frozen=True)
class Candidate:
    file: str
    line: int
    col: int
    rank: int


@dataclass(frozen=True)
class NotFound:
    selector: str
    error: Literal["not-found"] = "not-found"


@dataclass(frozen=True)
class NoSourceInfo:
    selector: str
    error: Literal["no-source-info"] = "no-source-info"


@dataclass(frozen=True)
class Ambiguous:
    selector: str
    candidates: tuple[Candidate, ...]
    error: Literal["ambiguous"] = "ambiguous"


class _Tree(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._stack: list[tuple[str, dict[str, str]]] = []
        self.nodes: list[tuple[dict[str, str], tuple[dict[str, str], ...]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {name: value or "" for name, value in attrs}
        ancestors = tuple(frame[1] for frame in self._stack)
        self.nodes.append((attr, ancestors))
        if tag not in _VOID:
            self._stack.append((tag, attr))

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self._stack) - 1, -1, -1):
            if self._stack[index][0] == tag:
                del self._stack[index:]
                return


def locate(selector: str, html: str) -> Location | NotFound | NoSourceInfo | Ambiguous:
    """Map selector to data-src locations.

    No match is NotFound. One match with no data-src is NoSourceInfo and
    does not invent a file. One match with data-src and no ancestor with a
    different data-src is Location. Two or more matches with data-src are
    Ambiguous, one candidate per node, document order, rank 1 first. One
    match whose ancestor has a different data-src is Ambiguous: rank 1 is
    the nearest such ancestor (JSX call site), rank 2 is the matched node.
    """
    attr, expected = _selector(selector)
    parser = _Tree()
    parser.feed(html)
    parser.close()
    matches = [node for node in parser.nodes if node[0].get(attr) == expected]
    if not matches:
        return NotFound(selector)
    sourced = [node for node in matches if "data-src" in node[0]]
    if len(sourced) >= 2:
        return Ambiguous(selector, _candidates([node[0]["data-src"] for node in sourced]))
    attrs, ancestors = matches[0]
    if "data-src" not in attrs:
        return NoSourceInfo(selector)
    definition = attrs["data-src"]
    call = _call_site(ancestors, definition)
    if call is None:
        return _location(definition)
    return Ambiguous(selector, _candidates([call, definition]))


def _selector(selector: str) -> tuple[str, str]:
    if _ID.fullmatch(selector):
        return "id", selector[1:]
    match = _TESTID.fullmatch(selector)
    if match:
        value = match.group(1) if match.group(1) is not None else match.group(2)
        return "data-testid", value
    raise ValueError(selector)


def _call_site(ancestors: tuple[dict[str, str], ...], definition: str) -> str | None:
    for attrs in reversed(ancestors):
        src = attrs.get("data-src")
        if src and src != definition:
            return src
    return None


def _candidates(values: list[str]) -> tuple[Candidate, ...]:
    ranked: list[Candidate] = []
    for rank, value in enumerate(values, start=1):
        loc = _location(value)
        ranked.append(Candidate(loc.file, loc.line, loc.col, rank))
    return tuple(ranked)


def _location(value: str) -> Location:
    match = _SRC.fullmatch(value)
    if match is None:
        raise ValueError(value)
    file, line_s, col_s = match.group(1), match.group(2), match.group(3)
    if any(part in ("", ".", "..") for part in file.split("/")):
        raise ValueError(value)
    line, col = int(line_s), int(col_s)
    if line < 1 or col < 1:
        raise ValueError(value)
    return Location(file, line, col)
