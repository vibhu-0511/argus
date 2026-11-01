# Indexed directory: apps/canvas/src of the platform checkout.
# Worktree: the checkout named by the env var ARGUS_PLATFORM_REPO (config/platform.md).
# That directory is the Canvas UI source for the five flows: sign-in (/login, /ops/login),
# the ops menu (/ops/radar, /ops/operations, /ops/launchpad, /ops/rules), desk tabs (/desk),
# user admin (/admin/users), and the audit table (/admin/audit).
# Excludes node_modules, the airline database, and generated output.
# ponytail: this is a scoped index of the Canvas UI tree, not the whole platform monorepo; the upgrade is to walk the rest of the worktree when a query misses.

"""Repo-map and tsserver index for the dcortex Canvas UI tree.

Symbols come from the TypeScript language server (tsserver) shipped with the
platform worktree. typescript-language-server, the LSP adapter, is not installed.
Retrieval raises StaleIndex when a named file's bytes differ from the content
hash stored on the index. It does not re-index that file.
"""

from __future__ import annotations

import hashlib
import json
import os
import queue
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

_SOURCE_SUFFIXES = {".ts", ".tsx", ".js", ".jsx"}
_SKIP_DIRS = {"node_modules", "dist", "coverage", "generated", "build", ".turbo"}
_CONTAINERS = {"module", "class", "interface", "enum", "type", "namespace"}
_KINDS = {
    "function",
    "class",
    "interface",
    "type",
    "enum",
    "enum member",
    "method",
    "const",
    "let",
    "var",
    "constructor",
    "getter",
    "setter",
    "property",
}
_SKIP_NAME = re.compile(r"""[\s(){}<>"'`]""")

INDEX_PATH = Path(__file__).resolve().parents[2] / "index.json"


class LanguageServerUnavailable(RuntimeError):
    """The TypeScript language server is not on this machine."""


class StaleIndex(RuntimeError):
    """A file named by the index no longer matches the hash stored with it."""

    def __init__(self, files: list[str]):
        self.files = list(files)
        super().__init__("stale index: " + ", ".join(self.files))


def platform_repo() -> Path:
    """The dcortex-platform checkout. config/platform.md names the repo; this machine's path is in the env."""
    path = os.environ.get("ARGUS_PLATFORM_REPO")
    if not path:
        raise RuntimeError("set ARGUS_PLATFORM_REPO to the dcortex-platform checkout (see config/platform.md)")
    root = Path(path)
    if not root.is_dir():
        raise RuntimeError(f"platform repo is not a directory: {root}")
    return root


def indexed_dir() -> Path:
    return platform_repo() / "apps" / "canvas" / "src"


def tsserver_js() -> Path:
    candidate = platform_repo() / "node_modules" / "typescript" / "lib" / "tsserver.js"
    if candidate.is_file():
        return candidate
    found = shutil.which("tsserver")
    if found:
        return Path(found)
    raise LanguageServerUnavailable(
        "TypeScript language server is not installed. "
        f"Missing {candidate}, tsserver is not on PATH, and typescript-language-server is not installed. "
        "Refusing to invent an index."
    )


def _node() -> str:
    found = shutil.which("node")
    if not found:
        raise LanguageServerUnavailable(
            "node is not installed, so the TypeScript language server cannot run. "
            "Refusing to invent an index."
        )
    return found


def _server_version(js: Path) -> str:
    package = js.parent.parent / "package.json" if js.name == "tsserver.js" else None
    if package and package.is_file():
        return json.loads(package.read_text(encoding="utf-8"))["version"]
    return "unknown"


def _file_hash(path: Path) -> str | None:
    if not path.is_file():
        return None
    # CRLF working trees (Windows autocrlf) must hash like the LF files in git.
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _stale_files(index: dict, root: Path) -> list[str]:
    # ponytail: hash the files the index already names; do not walk the monorepo.
    # An index with no content_hashes is left alone; the committed index.json has them (test_repo_map checks).
    # Upgrade: incremental re-index on hash mismatch.
    stored = index.get("content_hashes")
    if not isinstance(stored, dict):
        return []
    stale = []
    for rel in index.get("files") or {}:
        if stored.get(rel) != _file_hash(root / rel):
            stale.append(rel)
    return stale


def _is_name(name: str) -> bool:
    return bool(name) and _SKIP_NAME.search(name) is None


def _repo_path(path: str) -> str:
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(platform_repo().resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def source_files(root: Path) -> list[Path]:
    found = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in _SOURCE_SUFFIXES:
            continue
        if any(part in _SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        found.append(path)
    return sorted(found)


def symbols_from_navtree(root: dict) -> list[dict]:
    found: list[dict] = []

    def walk(node: dict) -> None:
        for child in node.get("childItems") or []:
            kind = child.get("kind") or ""
            name = child.get("text") or ""
            spans = child.get("spans") or []
            if kind in _KINDS and _is_name(name) and spans and spans[0].get("start"):
                start = spans[0]["start"]
                found.append(
                    {
                        "name": name,
                        "kind": kind,
                        "line": start["line"],
                        "offset": start["offset"],
                    }
                )
            if kind in _CONTAINERS:
                walk(child)

    walk(root)
    found.sort(key=lambda item: (item["line"], item["offset"], item["name"], item["kind"]))
    unique = []
    seen = set()
    for item in found:
        key = (item["name"], item["kind"], item["line"], item["offset"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


class _Reader:
    def __init__(self, stream):
        self.stream = stream
        self.buf = b""

    def _fill(self) -> None:
        # Raw pipes return whatever is already available. A buffered read(n)
        # waits until n bytes arrive, which deadlocks on small server messages.
        read = getattr(self.stream, "read1", self.stream.read)
        chunk = read(65536)
        if not chunk:
            raise EOFError("language server closed stdout")
        self.buf += chunk

    def read_exact(self, count: int) -> bytes:
        while len(self.buf) < count:
            self._fill()
        data, self.buf = self.buf[:count], self.buf[count:]
        return data

    def read_line(self) -> bytes:
        while b"\n" not in self.buf:
            self._fill()
        line, self.buf = self.buf.split(b"\n", 1)
        return line

    def read_message(self) -> dict:
        headers = {}
        while True:
            text = self.read_line().decode().strip()
            if not text:
                break
            key, _, value = text.partition(":")
            headers[key.lower()] = value.strip()
        length = int(headers["content-length"])
        data = self.read_exact(length)
        # tsserver's Content-Length counts one trailing newline byte. On Windows
        # the trailer is \r\n, so one byte is still sitting in the stream.
        if not data.endswith(b"\n"):
            data += self.read_exact(1)
        return json.loads(data.decode().strip())


class _TsServer:
    def __init__(self):
        js = tsserver_js()
        self.version = _server_version(js)
        self.proc = subprocess.Popen(
            [
                _node(),
                str(js),
                "--disableAutomaticTypingAcquisition",
                "--suppressDiagnosticEvents",
                "--noGetErrOnBackgroundUpdate",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )
        self.inbox: queue.Queue = queue.Queue()
        self.reader = _Reader(self.proc.stdout)
        self.seq = 0
        self.thread = threading.Thread(target=self._read_loop, daemon=True)
        self.thread.start()

    def _read_loop(self) -> None:
        try:
            while True:
                self.inbox.put(self.reader.read_message())
        except Exception as exc:
            self.inbox.put(exc)

    def request(self, command: str, arguments: dict, timeout: float = 180) -> dict:
        self.seq += 1
        seq = self.seq
        payload = json.dumps(
            {"seq": seq, "type": "request", "command": command, "arguments": arguments},
            separators=(",", ":"),
        )
        assert self.proc.stdin is not None
        self.proc.stdin.write((payload + "\n").encode())
        self.proc.stdin.flush()
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"tsserver timed out during {command}")
            try:
                item = self.inbox.get(timeout=remaining)
            except queue.Empty:
                raise TimeoutError(f"tsserver timed out during {command}") from None
            if isinstance(item, Exception):
                raise RuntimeError(f"tsserver stopped during {command}: {item}") from item
            if item.get("type") == "response" and item.get("request_seq") == seq:
                return item

    def close(self) -> None:
        if self.proc.poll() is None:
            if self.proc.stdin:
                self.proc.stdin.close()
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=5)

    def __enter__(self) -> _TsServer:
        return self

    def __exit__(self, *_) -> None:
        self.close()


def _location(file: str, start: dict, is_definition: bool | None = None) -> dict:
    loc = {"file": _repo_path(file), "line": start["line"], "offset": start["offset"]}
    if is_definition is not None:
        loc["is_definition"] = is_definition
    return loc


def build_index() -> dict:
    """Ask tsserver for each Canvas UI file's symbols and write index.json."""
    root = indexed_dir()
    files = source_files(root)
    if not files:
        raise RuntimeError(f"no Canvas UI source under {root}")
    by_file: dict[str, list[dict]] = {}
    hashes: dict[str, str] = {}
    with _TsServer() as server:
        version = server.version
        server.request("open", {"file": str(files[0])})
        for index, path in enumerate(files, start=1):
            rel = path.relative_to(platform_repo()).as_posix()
            server.request("open", {"file": str(path)})
            message = server.request("navtree", {"file": str(path)})
            if not message.get("success"):
                raise RuntimeError(f"navtree failed for {rel}: {message.get('message')}")
            by_file[rel] = symbols_from_navtree(message.get("body") or {})
            digest = _file_hash(path)
            if digest is None:
                raise RuntimeError(f"indexed file disappeared before it could be hashed: {rel}")
            hashes[rel] = digest
            if index % 50 == 0:
                print(f"indexed {index}/{len(files)}", flush=True)
    if not any(by_file.values()):
        raise RuntimeError("language server returned no symbols; refusing to write index.json")
    payload = {
        "language_server": "tsserver",
        "language_server_version": version,
        "indexed_dir": "apps/canvas/src",
        "files": by_file,
        "content_hashes": hashes,
    }
    INDEX_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def query(symbol: str, *, index: dict | None = None, root: Path | None = None) -> dict:
    """Return definition and reference locations for symbol from tsserver.

    A miss stays inside the Canvas UI tree. Walking the rest of the worktree
    is the upgrade named in the module comment. A content-hash mismatch raises
    StaleIndex before the language server is asked.
    """
    if index is None:
        index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    if root is None:
        root = platform_repo()
    stale = _stale_files(index, root)
    if stale:
        raise StaleIndex(stale)
    seed = indexed_dir() / "main.tsx"
    if not seed.is_file():
        raise RuntimeError(f"Canvas entry is missing: {seed}")
    definitions = []
    seen_defs = set()
    references = []
    seen_refs = set()
    with _TsServer() as server:
        server.request("open", {"file": str(seed)})
        found = server.request(
            "navto",
            {"searchValue": symbol, "file": str(seed), "maxResultCount": 256},
        )
        if not found.get("success"):
            raise RuntimeError(found.get("message") or "navto failed")
        for item in found.get("body") or []:
            if item.get("name") != symbol or not item.get("start"):
                continue
            loc = _location(item["file"], item["start"])
            key = (loc["file"], loc["line"], loc["offset"])
            if key in seen_defs:
                continue
            seen_defs.add(key)
            definitions.append(loc)
        repo = platform_repo()
        for loc in definitions:
            target = str(repo / loc["file"]) if not Path(loc["file"]).is_absolute() else loc["file"]
            server.request("open", {"file": target})
            message = server.request(
                "references",
                {"file": target, "line": loc["line"], "offset": loc["offset"]},
            )
            if not message.get("success"):
                raise RuntimeError(message.get("message") or "references failed")
            body = message.get("body") or {}
            for ref in body.get("refs") or []:
                if not ref.get("start"):
                    continue
                rloc = _location(ref["file"], ref["start"], bool(ref.get("isDefinition")))
                key = (rloc["file"], rloc["line"], rloc["offset"], rloc["is_definition"])
                if key in seen_refs:
                    continue
                seen_refs.add(key)
                references.append(rloc)
    return {"symbol": symbol, "definitions": definitions, "references": references}


if __name__ == "__main__":
    built = build_index()
    count = sum(len(symbols) for symbols in built["files"].values())
    print(f"wrote {INDEX_PATH} ({len(built['files'])} files, {count} symbols, tsserver {built['language_server_version']})")
