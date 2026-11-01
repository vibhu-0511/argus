"""Three file retrievers for one seeded task. None of them reads golden.patch.

Repo-map ranks files in the tsserver index by symbol names that appear in the
ticket. It does not start tsserver. ponytail: CSS is outside that index, so a
style bug cannot hit; the upgrade is a live query() when a ticket word is a
symbol, and an index that includes stylesheets.

pgvector embeds the ticket with the local CPU model and ranks indexed chunks.
locate() runs only when the ticket contains a #id or data-testid selector and
the task directory has an HTML file. Otherwise it returns no file.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from dom2src_mcp.locate import Ambiguous, Location, locate
from dom2src_mcp.repo_map import INDEX_PATH

_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_ID = re.compile(r"#[A-Za-z_][\w-]*")
_TESTID = re.compile(r"""\[data-testid=(?:"[^"]+"|'[^']+')]""")
_index: dict | None = None


def seeded_tasks(root: Path | None = None) -> list[Path]:
    base = root or Path(__file__).resolve().parents[4] / "packages" / "bench" / "tasks" / "seeded"
    return sorted(path.parent for path in base.glob("*/meta.json"))


def ticket_text(task_dir: Path) -> str:
    return json.loads((task_dir / "ticket.json").read_text(encoding="utf-8"))["text"]


def _symbols(index: dict | None) -> dict:
    if index is not None:
        return index
    global _index
    if _index is None:
        _index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    return _index


def repo_map_files(task_dir: Path, index: dict | None = None) -> list[str]:
    words = set(_WORD.findall(ticket_text(task_dir)))
    scored: list[tuple[int, str]] = []
    for path, symbols in _symbols(index)["files"].items():
        names = {item["name"] for item in symbols if item.get("name") in words}
        if names:
            scored.append((len(names), path))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [path for _, path in scored]


def embed_files(task_dir: Path) -> list[str]:
    from dom2src_mcp.embed import query_files

    return [path for path, _score in query_files(ticket_text(task_dir), limit=10)]


def _selector(text: str) -> str | None:
    found = _ID.search(text)
    if found:
        return found.group(0)
    found = _TESTID.search(text)
    if found:
        return found.group(0)
    return None


def locate_files(task_dir: Path) -> list[str]:
    selector = _selector(ticket_text(task_dir))
    pages = sorted(task_dir.glob("*.html"))
    if selector is None or not pages:
        return []
    found = locate(selector, pages[0].read_text(encoding="utf-8"))
    if isinstance(found, Location):
        return [found.file]
    if isinstance(found, Ambiguous):
        return [candidate.file for candidate in found.candidates]
    return []
