"""P5.5-T03: the split is clean, and the check fails when it should. No model, no network."""

import json
import shutil

from skills.split import SPLIT, TASKS, build, main, pairs, problems

DOC = json.loads(SPLIT.read_text(encoding="utf-8"))


def test_committed_split_is_clean_and_current():
    assert problems(DOC) == []
    assert DOC == build()
    assert main(["check"]) == 0


def test_counts_and_sets():
    held = {h["id"] for h in DOC["held_out"]}
    assert len(held) == 30 and sum(h["runnable"] for h in DOC["held_out"]) == 29
    assert held == {d.name for d in (TASKS / "seeded").iterdir()}
    assert len(DOC["train"]) == len(set(DOC["train"])) >= 40
    assert all(i.startswith("mut-") for i in DOC["train"])


def test_shared_id_fails():
    doc = {**DOC, "train": [*DOC["train"], "seed-e07"]}
    assert any("both sets: seed-e07" in p for p in problems(doc))


def test_shared_pair_fails(tmp_path):
    shutil.copytree(TASKS / "seeded" / "seed-e07", tmp_path / "seeded" / "seed-e07")
    clone = tmp_path / "mutated" / "mut-9999"
    clone.mkdir(parents=True)
    for name in ("bug.patch", "meta.json"):  # a "mutant" that makes the same edit to the same file
        shutil.copy(TASKS / "seeded" / "seed-e07" / name, clone / name)
    doc = {"held_out": [{"id": "seed-e07", "runnable": True}], "train": ["mut-9999"]}
    found = problems(doc, tmp_path)
    assert found == ["mut-9999 shares pair apps/canvas/src/styles/tokens.css + change-unit with seed-e07"]


def test_derived_operators_match_the_recorded_archetype():
    expected = {"missing-style": {"delete-rule"}, "font-size": {"change-unit"}}
    for d in (TASKS / "mutated").iterdir():
        archetype = json.loads((d / "meta.json").read_text(encoding="utf-8"))["archetype"]
        assert {op for _, op in pairs(d)} == expected[archetype], d.name
