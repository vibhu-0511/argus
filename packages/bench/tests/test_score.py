import json
import struct
import zlib
from pathlib import Path

from argus_bench.cli import main
from argus_bench.verdict import Verdict

FLOWS = ["/login", "/ops/radar", "/desk?sel=console", "/admin/users", "/admin/audit"]


def _png(width: int, height: int) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + b"\xff\x00\x00" * width for _ in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def _task(directory: Path, checks: list) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "ticket.json").write_text(
        json.dumps({"id": "score-probe", "text": "Probe the clock size."}),
        encoding="utf-8",
    )
    (directory / "meta.json").write_text(
        json.dumps({"source": "seeded", "archetype": "font-size", "tier": "easy", "seed": None}),
        encoding="utf-8",
    )
    (directory / "checks.json").write_text(json.dumps(checks), encoding="utf-8")
    (directory / "bug.patch").write_text("--- a/x\n+++ b/x\n@@\n-a\n+b\n", encoding="utf-8")
    (directory / "golden.patch").write_text("--- a/x\n+++ b/x\n@@\n-b\n+a\n", encoding="utf-8")


def _tree(directory: Path, css: str) -> None:
    css_path = directory / "apps" / "canvas" / "src" / "ops" / "radar.css"
    css_path.parent.mkdir(parents=True)
    css_path.write_text(css, encoding="utf-8")


def _classes(size: str) -> str:
    rules = [".radar-clock-time { font-size: 20px; font-weight: 600; }"]
    rules.extend(f".fail-{index:02d} {{ font-size: {size}; }}" for index in range(8))
    return "\n".join(rules) + "\n"


def test_missing_task_tree_and_bad_dir_are_infra(tmp_path: Path, capsys):
    missing = tmp_path / "nope"
    assert main(["score", str(missing), "--tree", str(tmp_path)]) == 2
    verdict = Verdict.model_validate_json(capsys.readouterr().out)
    assert verdict.ok is False
    assert verdict.checks == []
    assert str(missing) in verdict.log

    assert main(["score", "bug-17", "--tree", str(missing)]) == 2
    loaded = Verdict.model_validate_json(capsys.readouterr().out)
    assert loaded.task_id == "BUG-17"
    assert f"missing tree: {missing}" in loaded.log

    empty = tmp_path / "empty"
    empty.mkdir()
    assert main(["score", str(empty), "--tree", str(tmp_path)]) == 2
    bad = Verdict.model_validate_json(capsys.readouterr().out)
    assert bad.checks == []
    assert bad.log


def test_score_pass_fail_and_unsliced_reasons(tmp_path: Path, capsys):
    tree = tmp_path / "tree"
    _tree(tree, _classes("12px"))
    task = tmp_path / "task"
    _task(
        task,
        [
            {
                "type": "computed_style",
                "params": {"flow": flow, "selector": "#probe", "property": "font-size", "expected": "20px"},
            }
            for flow in FLOWS
        ]
        + [
            {
                "type": "bounding_box",
                "params": {"flow": "/ops/radar", "selector": "#probe", "maxWidth": 160, "maxHeight": 40},
            },
            {"type": "computed_style", "params": {"flow": "/ops/radar", "property": "font-size", "min_px": 12}},
        ],
    )
    assert main(["score", str(task), "--tree", str(tree)]) == 0
    passed = Verdict.model_validate_json(capsys.readouterr().out)
    assert passed.ok is True
    assert passed.log == "\n".join(item.reason for item in passed.checks)
    assert all(item.ok for item in passed.checks)
    assert passed.checks[-1].reason.count("font-size=") == 9

    broken = tmp_path / "broken"
    _tree(broken, _classes("10px"))
    shots = task / "shots"
    shots.mkdir()
    (shots / "one.png").write_bytes(_png(1, 1))
    _task(
        task,
        [
            {"type": "computed_style", "params": {"flow": "/ops/radar", "property": "font-size", "min_px": 12}},
            {
                "type": "pixel_diff",
                "params": {
                    "flow": "/ops/radar",
                    "selector": "#probe",
                    "baseline": "shots/one.png",
                    "maxChangedRatio": 0,
                },
            },
        ],
    )
    assert main(["score", str(task), "--tree", str(broken)]) == 1
    failed = Verdict.model_validate_json(capsys.readouterr().out)
    assert failed.ok is False
    assert failed.log == "\n".join(item.reason for item in failed.checks)
    style, pixels = failed.checks
    assert style.ok is False
    assert pixels.ok is False
    for index in range(8):
        assert f".fail-{index:02d} font-size is 10px, expected >= 12px" in style.reason
    assert ".radar-clock-time" not in style.reason
    assert style.reason.count("expected >= 12px") == 8
    assert pixels.reason.startswith("size ")
    assert "vs baseline 1x1" in pixels.reason
    assert pixels.reason in failed.log
