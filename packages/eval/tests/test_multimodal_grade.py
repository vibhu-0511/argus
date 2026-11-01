"""Offline check of the grading loop: a fake `docker` and a fake harness python, no Docker, no network."""

from __future__ import annotations

import json
import os
import stat
import sys
from argparse import Namespace

from eval import multimodal_grade as g


def test_image_name_matches_the_dataset_rows():
    assert g.image_name("chartjs__Chart.js-10157") == "swebench/sweb.eval.x86_64.chartjs_1776_chart.js-10157:latest"
    assert g.image_name("Automattic__wp-calypso-21492") == "swebench/sweb.eval.x86_64.automattic_1776_wp-calypso-21492:latest"


def test_grade_records_resolved_unresolved_and_error_and_skips_resolved(tmp_path, monkeypatch, capsys):
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        if cmd[0] == "docker":
            return None
        iid, run_id = cmd[cmd.index("--instance_ids") + 1], cmd[cmd.index("--run_id") + 1]
        if iid.endswith("1262"):
            raise g.subprocess.CalledProcessError(1, cmd, stderr=b"boom")
        d = kw["cwd"] / "logs" / "run_evaluation" / run_id / "gold" / iid
        d.mkdir(parents=True, exist_ok=True)
        (d / "report.json").write_text(json.dumps({iid: {"resolved": iid.endswith("1435"), "patch_successfully_applied": True, "infra_failure": False}}), encoding="utf-8")

    monkeypatch.setattr(g.subprocess, "run", fake_run)
    monkeypatch.setattr(g, "windows_fix_missing", lambda py: False)
    ids = ["markedjs__marked-1435", "markedjs__marked-1262", "markedjs__marked-1535"]
    args = Namespace(swebench_python="py", predictions="gold", ids=ids, run_prefix="t", cwd=tmp_path, force=False, remove_images=False, dry_run=False)
    assert g.grade(args) == 0
    summary = json.loads((tmp_path / "summary-t.json").read_text(encoding="utf-8"))
    assert [summary[i]["status"] for i in ids] == ["resolved", "error", "unresolved"]
    assert "boom" in summary[ids[1]]["note"] and summary[ids[0]]["resolved"] is True
    n = len(calls)
    g.grade(args)  # second pass: the resolved one is skipped, the other two run again
    assert len(calls) == n + 4
    assert "already resolved, skipped" in capsys.readouterr().out
