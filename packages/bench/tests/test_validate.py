import json
from pathlib import Path

from argus_bench.cli import main
from argus_bench.task_dir import load_task_dir

SAMPLE = Path(__file__).resolve().parents[1] / "tasks" / "seeded" / "bug-17"


def test_bug_17_validates():
    task = load_task_dir(SAMPLE)
    assert task.id == "BUG-17"
    assert task.meta.tier == "medium"
    assert task.checks[0].type == "computed_style"
    assert "font-size: 10px" in task.bug_patch
    assert "font-size: 12px" in task.golden_patch
    assert main(["validate", str(SAMPLE)]) == 0


def test_missing_patch_is_rejected(tmp_path: Path):
    for name in ("ticket.json", "checks.json", "meta.json", "bug.patch", "golden.patch"):
        source = SAMPLE / name
        target = tmp_path / name
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "shots").mkdir()
    (tmp_path / "shots" / "radar-card.png").write_bytes((SAMPLE / "shots" / "radar-card.png").read_bytes())
    (tmp_path / "golden.patch").unlink()
    assert main(["validate", str(tmp_path)]) == 1


def test_bad_tier_is_rejected(tmp_path: Path):
    for name in ("ticket.json", "checks.json", "meta.json", "bug.patch", "golden.patch"):
        (tmp_path / name).write_text((SAMPLE / name).read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "shots").mkdir()
    (tmp_path / "shots" / "radar-card.png").write_bytes((SAMPLE / "shots" / "radar-card.png").read_bytes())
    meta = json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))
    meta["tier"] = "impossible"
    (tmp_path / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    assert main(["validate", str(tmp_path)]) == 1
