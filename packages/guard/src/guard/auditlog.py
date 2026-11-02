"""Append-only, hash-chained audit log (P7-T06). One JSON object per line.

Record: seq, ts, kind, payload, prev, hash. `hash` is SHA-256 over the canonical JSON of the record without `hash`.
`prev` is the previous record's hash; the first record uses GENESIS.

Detects: an edited line, a deleted or reordered line, bad JSON. Does NOT detect a cut tail or a full rewrite by someone
who recomputes every hash: compare the head hash with a copy kept somewhere else (`guard verify-log --head`).
"""
import argparse
import hashlib
import json
import os
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NamedTuple

GENESIS = "0" * 64
# Fix-loop tool errors that mean the harness refused something the agent asked for.
POLICY_ERRORS = {"not-allowed", "outside-worktree"}


def _no_redact(value: Any) -> Any:
    # P7-T03 HOOK: replace with the shared redactor (`guard.redact`) once it is merged, so no secret is written or hashed.
    return value


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _hash(record: dict) -> str:
    body = {k: v for k, v in record.items() if k != "hash"}
    text = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    return hashlib.sha256(text.encode("ascii")).hexdigest()


class Verdict(NamedTuple):
    count: int
    head: str
    bad_line: int | None = None
    reason: str = ""


def verify(path: str | Path) -> Verdict:
    """Walk the file. `bad_line` is the first bad line (1-based) with `reason`, or None when the chain holds."""
    prev = GENESIS
    lines = Path(path).read_bytes().split(b"\n")
    if lines[-1] == b"":
        lines.pop()  # the newline that ends the last record
    for n, raw in enumerate(lines, 1):
        try:
            rec = json.loads(raw)
            ok = isinstance(rec, dict) and {"seq", "ts", "kind", "payload", "prev", "hash"} <= rec.keys()
        except ValueError:
            ok = False
        if not ok:
            return Verdict(n - 1, prev, n, "bad JSON or missing field")
        if rec["hash"] != _hash(rec):
            return Verdict(n - 1, prev, n, "edited content (hash does not match the record)")
        if rec["prev"] != prev:
            return Verdict(n - 1, prev, n, "broken link (a line was deleted, inserted or moved)")
        if rec["seq"] != n - 1:
            return Verdict(n - 1, prev, n, f"seq is {rec['seq']}, expected {n - 1}")
        prev = rec["hash"]
    return Verdict(len(lines), prev)


class AuditLog:
    """Writer. Opening an existing file verifies it first and refuses to extend a broken chain."""

    def __init__(self, path: str | Path, clock: Callable[[], Any] = _utc_now, redact: Callable[[Any], Any] = _no_redact):
        self.path, self.clock, self.redact = Path(path), clock, redact
        if self.path.exists():
            v = verify(self.path)
            if v.bad_line is not None:
                raise ValueError(f"{self.path}: line {v.bad_line}: {v.reason}")
            self.seq, self.head = v.count, v.head
            if self.path.stat().st_size and not self.path.read_bytes().endswith(b"\n"):
                self._write("\n")
        else:
            self.seq, self.head = 0, GENESIS

    def append(self, kind: str, payload: Any) -> dict:
        rec = {"seq": self.seq, "ts": self.clock(), "kind": kind, "payload": self.redact(payload), "prev": self.head}
        rec["hash"] = _hash(rec)
        # ponytail: single writer, no lock. Add one if the loop ever logs from threads.
        self._write(json.dumps(rec, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False) + "\n")
        self.seq, self.head = self.seq + 1, rec["hash"]
        return rec

    def _write(self, text: str) -> None:
        with self.path.open("a", encoding="ascii", newline="\n") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())


def audited(log: AuditLog, execute: Callable[[str, dict], Any]) -> Callable[[str, dict], Any]:
    """Wrap a fix-loop `execute(name, payload)` so each tool call is appended (a refusal also gets a `policy_event`).

    Not wired into `run_fix` yet: pass `execute=audited(log, ...)` where the worktree is known.
    """

    def run(name: str, payload: dict) -> Any:
        try:
            result = execute(name, payload)
        except BaseException as exc:  # the call that blew up must still be on record
            log.append("tool_call", {"tool": name, "args": payload, "exception": repr(exc)})
            raise
        out = result.model_dump(mode="json") if hasattr(result, "model_dump") else result
        log.append("tool_call", {"tool": name, "args": payload, "result": out})
        if isinstance(out, dict) and out.get("ok") is False and out.get("error") in POLICY_ERRORS:
            log.append("policy_event", {"tool": name, "error": out["error"], "message": out.get("message")})
        return result

    return run


def verify_log_main(argv: list[str]) -> int:
    """`guard verify-log <file> [--head HASH]`: exit 0 good, 1 bad (names the line), prints the head hash."""
    ap = argparse.ArgumentParser(prog="guard verify-log")
    ap.add_argument("file")
    ap.add_argument("--head", help="head hash shipped to a second place; a different head means the tail was cut or rewritten")
    args = ap.parse_args(argv)
    try:
        v = verify(args.file)
    except OSError as exc:
        print(f"verify-log: {exc}", file=sys.stderr)
        return 1
    if v.bad_line is not None:
        print(f"BAD line {v.bad_line}: {v.reason}", file=sys.stderr)
        return 1
    if args.head and args.head != v.head:
        print(f"BAD head: file ends at {v.head}, expected {args.head} (tail cut or log rewritten)", file=sys.stderr)
        return 1
    print(f"OK {v.count} records, head {v.head}")
    return 0
