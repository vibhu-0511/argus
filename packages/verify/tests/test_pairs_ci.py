"""Saved calibration pairs, their labels and provenance. The CI gate uses stored screenshots."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from verify.ci import check_dir
from verify.pairs import MIX, generate, load_tickets
from verify.png import encode_png, fill, solid

ROOT = Path(__file__).resolve().parents[1]
CALIBRATION = ROOT / "fixtures" / "calibration"  # real Canvas shots, built by calibration/build_set.py
SQUARES = ROOT / "fixtures" / "calibration-squares"  # 16x16 synthetic squares: a plumbing fixture only, never for alpha
MATCH = ROOT / "fixtures" / "ci" / "match"
OVER = ROOT / "fixtures" / "ci" / "over"


def test_generator_mix_and_blank_labels(tmp_path: Path):
    tickets = tmp_path / "tasks"
    (tickets / "bug-a").mkdir(parents=True)
    (tickets / "bug-a" / "ticket.json").write_text(json.dumps({"id": "A", "text": "clipped button"}), encoding="utf-8")
    loaded = load_tickets(tickets)
    dest = tmp_path / "pairs"
    generate(dest, loaded)
    labels = json.loads((dest / "labels.json").read_text(encoding="utf-8"))
    assert len(labels["pairs"]) == 100
    assert all(item["label"] is None for item in labels["pairs"])
    kinds = [json.loads((dest / f"{i:03d}" / "meta.json").read_text(encoding="utf-8"))["constructed_as"] for i in range(100)]
    assert kinds.count("correct") == 40
    assert kinds.count("wrong") == 30
    assert kinds.count("collateral") == 30
    assert len(MIX) == 100
    assert (dest / "000" / "before.png").is_file()
    assert (dest / "000" / "ticket.txt").read_text(encoding="utf-8") == "clipped button"


def test_saved_calibration_set_is_labelled_with_provenance_and_real():
    labels = json.loads((CALIBRATION / "labels.json").read_text(encoding="utf-8"))
    assert len(labels["pairs"]) == 100
    assert all(item["label"] in {"pass", "fail", "collateral"} for item in labels["pairs"])
    provenance = json.loads((CALIBRATION / "labels.provenance.json").read_text(encoding="utf-8"))
    assert set(provenance["source"]) == {item["id"] for item in labels["pairs"]}  # every label says whose it is
    assert set(provenance["source"].values()) <= {"owner", "owner-accepted-draft"}
    metas = [json.loads((CALIBRATION / item["id"] / "meta.json").read_text(encoding="utf-8")) for item in labels["pairs"]]
    assert {m["shot_source"] for m in metas} == {"real-canvas-mocked-api"}
    assert all(m["label"] is None for m in metas)
    kinds = [m["constructed_as"] for m in metas]
    assert (kinds.count("correct"), kinds.count("wrong"), kinds.count("collateral")) == (40, 30, 30)
    for item in labels["pairs"]:
        folder = CALIBRATION / item["id"]
        assert all((folder / name).is_file() for name in ("before.png", "after.png", "ticket.txt"))
        assert (folder / "before.png").read_bytes()[1:4] == b"PNG"


def test_squares_fixture_is_kept_for_plumbing_only():
    labels = json.loads((SQUARES / "labels.json").read_text(encoding="utf-8"))
    assert len(labels["pairs"]) == 100
    sample = json.loads((SQUARES / "000" / "meta.json").read_text(encoding="utf-8"))
    assert sample["shot_source"] == "synthetic"
    assert sample["label"] is None


def test_ci_match_exits_zero_and_over_ratio_exits_nonzero(tmp_path: Path):
    assert check_dir(MATCH) == 0
    assert check_dir(OVER) == 1
    missing = tmp_path / "missing"
    missing.mkdir()
    (missing / "before.png").write_bytes((MATCH / "before.png").read_bytes())
    (missing / "after.png").write_bytes((MATCH / "after.png").read_bytes())
    assert check_dir(missing) == 1
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "before.png").write_bytes((MATCH / "before.png").read_bytes())
    (bad / "after.png").write_bytes((MATCH / "after.png").read_bytes())
    (bad / "verdict.json").write_text("{", encoding="utf-8")
    assert check_dir(bad) == 1


def test_encode_roundtrip_used_by_fixtures():
    image = fill(solid(8, 8, (10, 20, 30)), 1, 1, 2, 2, (1, 2, 3))
    from verify.png import decode_png

    assert decode_png(encode_png(image)) == image
