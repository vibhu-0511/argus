import itertools
import json

import pytest

from guard.auditlog import GENESIS, AuditLog, audited, verify
from guard.cli import main


def _log(path, n=5, **kw):
    ticks = itertools.count()
    log = AuditLog(path, clock=lambda: next(ticks), **kw)
    for i in range(n):
        log.append("tool_call", {"tool": "read_file", "path": f"src/f{i}.py"})
    return log


def _lines(path):
    return path.read_bytes().split(b"\n")[:-1]


def _put(path, lines):
    path.write_bytes(b"\n".join(lines) + b"\n")


def test_good_file_passes_and_chains(tmp_path):
    p = tmp_path / "audit.jsonl"
    log = _log(p)
    v = verify(p)
    assert (v.bad_line, v.count, v.head) == (None, 5, log.head)
    recs = [json.loads(x) for x in _lines(p)]
    assert recs[0]["prev"] == GENESIS
    assert all(b["prev"] == a["hash"] for a, b in zip(recs, recs[1:]))
    assert [r["ts"] for r in recs] == [0, 1, 2, 3, 4]  # injected clock


def test_empty_file_is_good(tmp_path):
    p = tmp_path / "audit.jsonl"
    p.write_bytes(b"")
    assert verify(p) == (0, GENESIS, None, "")


def test_edit_middle_line_names_it(tmp_path):
    p = tmp_path / "audit.jsonl"
    _log(p)
    ls = _lines(p)
    ls[2] = ls[2].replace(b"f2.py", b"f9.py")
    _put(p, ls)
    v = verify(p)
    assert v.bad_line == 3 and "edited" in v.reason


def test_delete_line(tmp_path):
    p = tmp_path / "audit.jsonl"
    _log(p)
    ls = _lines(p)
    del ls[1]
    _put(p, ls)
    v = verify(p)
    assert v.bad_line == 2 and "broken link" in v.reason


def test_swap_two_lines(tmp_path):
    p = tmp_path / "audit.jsonl"
    _log(p)
    ls = _lines(p)
    ls[1], ls[2] = ls[2], ls[1]
    _put(p, ls)
    assert verify(p).bad_line == 2


def test_bad_json_line(tmp_path):
    p = tmp_path / "audit.jsonl"
    _log(p)
    ls = _lines(p)
    ls[3] = b"{not json"
    _put(p, ls)
    v = verify(p)
    assert v.bad_line == 4 and "JSON" in v.reason


def test_tail_cut_and_full_rewrite_need_the_shipped_head(tmp_path, capsys):
    p = tmp_path / "audit.jsonl"
    shipped = _log(p).head
    _put(p, _lines(p)[:3])  # tail cut
    assert verify(p).bad_line is None  # the chain alone cannot see it
    assert main(["verify-log", str(p)]) == 0
    assert main(["verify-log", str(p), "--head", shipped]) == 1
    assert "BAD head" in capsys.readouterr().err
    # full rewrite: the attacker recomputes every hash, so the file verifies, but the head moved
    q = tmp_path / "rewrite.jsonl"
    log = AuditLog(q, clock=lambda: 0)
    for i in range(5):
        log.append("tool_call", {"tool": "read_file", "path": f"evil{i}.py"})
    assert verify(q).bad_line is None and log.head != shipped


def test_cli_good_and_bad(tmp_path, capsys):
    p = tmp_path / "audit.jsonl"
    log = _log(p)
    assert main(["verify-log", str(p), "--head", log.head]) == 0
    assert f"OK 5 records, head {log.head}" in capsys.readouterr().out
    ls = _lines(p)
    ls[1] = ls[1].replace(b"f1.py", b"f8.py")
    _put(p, ls)
    assert main(["verify-log", str(p)]) == 1
    assert "BAD line 2" in capsys.readouterr().err
    assert main(["verify-log", str(tmp_path / "missing.jsonl")]) == 1


def test_reopen_extends_chain_and_refuses_broken_file(tmp_path):
    p = tmp_path / "audit.jsonl"
    _log(p, n=2)
    log = AuditLog(p, clock=lambda: 9)
    log.append("policy_event", {"x": 1})
    assert verify(p).count == 3 and verify(p).bad_line is None
    ls = _lines(p)
    ls[0] = ls[0].replace(b"f0.py", b"f7.py")
    _put(p, ls)
    with pytest.raises(ValueError, match="line 1"):
        AuditLog(p)


def test_redact_runs_before_the_hash(tmp_path):
    p = tmp_path / "audit.jsonl"
    log = AuditLog(p, clock=lambda: 0, redact=lambda v: json.loads(json.dumps(v).replace("FAKE-SECRET", "[REDACTED]")))
    log.append("tool_call", {"cmd": "echo FAKE-SECRET"})
    assert b"FAKE-SECRET" not in p.read_bytes() and verify(p).bad_line is None


def test_audited_wrapper_records_calls_refusals_and_exceptions(tmp_path):
    class Err:  # shaped like fix_loop.tools.ToolError
        def model_dump(self, mode="python"):
            return {"ok": False, "error": "outside-worktree", "message": "no"}

    def execute(name, payload):
        if name == "boom":
            raise RuntimeError("x")
        return Err() if name == "read_file" else {"ok": True, "text": "fine"}

    p = tmp_path / "audit.jsonl"
    run = audited(AuditLog(p, clock=lambda: 0), execute)
    run("search", {"q": "a"})
    run("read_file", {"path": "/etc/passwd"})
    with pytest.raises(RuntimeError):
        run("boom", {})
    recs = [json.loads(x) for x in _lines(p)]
    assert [r["kind"] for r in recs] == ["tool_call", "tool_call", "policy_event", "tool_call"]
    assert recs[2]["payload"]["error"] == "outside-worktree" and "RuntimeError" in recs[3]["payload"]["exception"]
    assert verify(p).bad_line is None
