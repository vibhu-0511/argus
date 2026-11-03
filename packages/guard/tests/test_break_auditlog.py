"""P7-T19 break it: change one record in the middle of the audit log, then run the real `guard verify-log` command.

The log is built with `AuditLog` (12 records). Record 6 (line 6) is a `policy_event` that says the harness refused a path
outside the worktree: the line an attacker would most want to hide. Every check runs the command line in a subprocess,
so the exit code and the text are the real ones. Run with `-s` to see them.
"""

from __future__ import annotations

import itertools
import json
import subprocess
import sys

from guard.auditlog import AuditLog, _hash

REFUSED = 6  # 1-based line of the record that gets changed
CODE = "import sys; from guard.cli import main; sys.exit(main(sys.argv[1:]))"


def _build(path, n=12):
    ticks = itertools.count()
    log = AuditLog(path, clock=lambda: next(ticks))
    for i in range(1, n + 1):
        if i == REFUSED:
            log.append("policy_event", {"tool": "read_file", "error": "outside-worktree", "message": "../host-secret.txt is outside the worktree"})
        else:
            log.append("tool_call", {"tool": "run_cmd", "args": {"command": f"echo step {i}"}, "result": {"ok": True, "text": f"step {i}"}})
    return log


def _verify(path, *extra):
    proc = subprocess.run([sys.executable, "-c", CODE, "verify-log", path.name, *extra], capture_output=True, text=True, cwd=path.parent)
    out = (proc.stdout + proc.stderr).strip()
    print(f"\n$ guard verify-log {path.name} {' '.join(extra)}".rstrip() + f"\n{out}\n(exit {proc.returncode})")
    return proc.returncode, out


def _records(path):
    return [json.loads(line) for line in path.read_bytes().split(b"\n") if line]


def _save(path, records):
    lines = [json.dumps(r, sort_keys=True, separators=(",", ":"), ensure_ascii=True) for r in records]
    path.write_bytes(("\n".join(lines) + "\n").encode("ascii"))


def _rechain(records, start):
    """What an attacker with the source can do: recompute `hash` and `prev` from index `start` (0-based) onward."""
    for i in range(start, len(records)):
        records[i]["prev"] = records[i - 1]["hash"] if i else "0" * 64
        records[i]["hash"] = _hash(records[i])


def test_untouched_log_passes(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = _build(path)
    code, out = _verify(path)
    assert code == 0 and out == f"OK 12 records, head {log.head}"


def test_edit_one_field_in_place_fails_and_names_the_line(tmp_path):
    path = tmp_path / "audit.jsonl"
    _build(path)
    data = path.read_bytes()
    assert data.count(b"outside-worktree") == 1
    path.write_bytes(data.replace(b"outside-worktree", b"none-refused-xx"))  # same length, one field, one record
    code, out = _verify(path)
    assert code == 1 and out.startswith(f"BAD line {REFUSED}: edited content")


def test_edit_and_recompute_only_that_hash_is_caught_one_line_later(tmp_path):
    path = tmp_path / "audit.jsonl"
    _build(path)
    records = _records(path)
    records[REFUSED - 1]["payload"]["error"] = "none"
    records[REFUSED - 1]["hash"] = _hash(records[REFUSED - 1])  # the record is now self-consistent
    _save(path, records)
    code, out = _verify(path)
    assert code == 1 and out.startswith(f"BAD line {REFUSED + 1}: broken link")  # the NEXT record still points at the old hash


def test_full_rewrite_from_the_edit_passes_alone_and_fails_against_the_shipped_head(tmp_path):
    path = tmp_path / "audit.jsonl"
    shipped = _build(path).head  # the head hash, copied to a second place when the run ended
    records = _records(path)
    records[REFUSED - 1]["payload"]["error"] = "none"
    _rechain(records, REFUSED - 1)
    _save(path, records)
    code, out = _verify(path)
    assert code == 0 and out.startswith("OK 12 records") and shipped not in out  # a consistent rewrite verifies on its own
    code, out = _verify(path, "--head", shipped)
    assert code == 1 and out.startswith("BAD head: file ends at") and shipped in out
    assert [r["hash"] for r in records[: REFUSED - 1]] == [r["hash"] for r in _records(path)[: REFUSED - 1]]  # lines 1 to 5 unchanged


def test_cut_tail_passes_alone_and_fails_against_the_shipped_head(tmp_path):
    path = tmp_path / "audit.jsonl"
    shipped = _build(path).head
    _save(path, _records(path)[:9])
    code, out = _verify(path)
    assert code == 0 and out.startswith("OK 9 records")
    code, out = _verify(path, "--head", shipped)
    assert code == 1 and out.startswith("BAD head")


def test_rewriting_the_shipped_head_too_is_not_caught(tmp_path):
    """The limit: the second copy must be somewhere the attacker cannot write."""
    path = tmp_path / "audit.jsonl"
    _build(path)
    records = _records(path)
    records[REFUSED - 1]["payload"]["error"] = "none"
    _rechain(records, REFUSED - 1)
    _save(path, records)
    code, out = _verify(path, "--head", records[-1]["hash"])
    assert code == 0 and out.startswith("OK 12 records")
