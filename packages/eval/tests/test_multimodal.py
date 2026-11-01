"""Offline tests for the SWE-bench Multimodal adapter, run against the committed dev-subset snapshot."""

from __future__ import annotations

import json

import pytest

from eval import multimodal as mm

SUBSET = json.loads((mm.DATA_DIR / "subset.json").read_text(encoding="utf-8"))
GOLD = json.loads((mm.DATA_DIR / "gold_patches.json").read_text(encoding="utf-8"))
EXCLUDED = json.loads((mm.DATA_DIR / "excluded.json").read_text(encoding="utf-8"))
ROW = SUBSET["rows"][0]


def test_subset_loads_at_least_ten_dev_tasks():
    tasks = mm.load_subset()
    assert 10 <= len(tasks) <= 20
    assert [t.id for t in tasks] == SUBSET["instance_ids"]
    assert SUBSET["split"] == mm.SPLIT == "dev"
    assert all(r["split"] == "dev" and t.image_urls for r, t in zip(SUBSET["rows"], tasks, strict=True))


def test_load_subset_refuses_other_split(tmp_path):
    path = tmp_path / "subset.json"
    path.write_text(json.dumps({**SUBSET, "split": "test"}), encoding="utf-8")
    with pytest.raises(ValueError, match="pins 'dev'"):
        mm.load_subset(path)


def test_test_split_rows_are_all_excluded():
    rows = [{**ROW, "split": "test", "instance_id": f"t{i}", "image_assets": ""} for i in range(3)]
    tasks, excluded = mm.adapt(rows)
    assert tasks == []
    assert [(e.instance_id, e.reason) for e in excluded] == [(f"t{i}", "wrong-split") for i in range(3)]


@pytest.mark.parametrize(
    "assets",
    [
        "",
        "not json",
        '{"patch": [], "test_patch": []}',
        '{"problem_statement": [], "patch": [], "test_patch": []}',
        '{"problem_statement": ["ftp://x/a.png"]}',
    ],
)
def test_dev_row_without_usable_image_urls_is_excluded(assets):
    tasks, excluded = mm.adapt([{**ROW, "image_assets": assets}])
    assert tasks == []
    assert [e.reason for e in excluded] == ["missing-image-assets"]


def test_dev_row_quoting_the_gold_patch_is_excluded():
    patch = "diff --git a/x.js b/x.js\n+++ b/x.js\n+const secretFixValue = computeTheAnswer(input);\n"
    row = {**ROW, "patch": patch, "problem_statement": "Try const secretFixValue = computeTheAnswer(input); here"}
    tasks, excluded = mm.adapt([row])
    assert tasks == [] and excluded[0].reason == "statement-quotes-gold-patch"


def test_every_dev_row_is_selected_or_excluded_with_a_reason():
    ids = [e["instance_id"] for e in EXCLUDED["excluded"]]
    assert len(ids) == len(set(ids)) and not set(ids) & set(SUBSET["instance_ids"])
    assert len(ids) + len(SUBSET["instance_ids"]) == EXCLUDED["dev_rows"] == 102
    assert {e["reason"] for e in EXCLUDED["excluded"]} == {"missing-image-assets", "statement-quotes-gold-patch", "not-selected"}
    assert all(e["detail"] for e in EXCLUDED["excluded"])


def test_gold_patch_text_is_not_in_any_prompt():
    tasks = mm.load_subset()
    assert set(GOLD) == {t.id for t in tasks}
    for task in tasks:
        prompt = mm.build_prompt(task)
        assert GOLD[task.id].strip() not in prompt
        assert mm.leaks_gold(prompt, GOLD[task.id]) is None, task.id
    # a patch that only adds short lines gets the whole-patch check only; make sure that stays the exception
    assert sum(not mm.gold_lines(p) for p in GOLD.values()) <= 2
    assert not {"patch", "test_patch", "hints_text"} & set(mm.MultimodalTask.model_fields)


def test_leak_check_catches_a_leak():
    task = mm.load_subset()[0]
    line = mm.gold_lines(GOLD[task.id])[0]
    assert mm.leaks_gold(mm.build_prompt(task) + "\n" + line, GOLD[task.id]) == line
